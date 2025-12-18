"""Holds analysis screen showing hold details and recommendations."""

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Static

from src.data.models import InactiveMailbox
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.data.session import SessionManager

logger = get_logger(__name__)


# Hold type to display info mapping
HOLD_TYPE_INFO = {
    "LitigationHold": {
        "name": "Litigation Hold",
        "class": "hold-litigation",
        "description": "Legal hold preventing deletion",
        "impact": "Cannot recover until hold removed",
    },
    "UniH": {
        "name": "Unified Hold (eDiscovery)",
        "class": "hold-ediscovery",
        "description": "eDiscovery case hold",
        "impact": "Content preserved for legal discovery",
    },
    "mbxHold": {
        "name": "Mailbox Hold",
        "class": "hold-retention",
        "description": "Retention policy hold",
        "impact": "Subject to retention policy",
    },
    "InPlaceHold": {
        "name": "In-Place Hold (Legacy)",
        "class": "hold-ediscovery",
        "description": "Legacy Exchange hold",
        "impact": "Preserved until hold removed",
    },
}


class HoldsScreen(Screen):
    """Screen showing hold analysis and recommendations.

    Displays detailed information about holds applied to mailboxes,
    their impact on operations, and recommendations for handling.
    """

    BINDINGS = [
        Binding("escape", "back", "Back", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("e", "export", "Export", show=True),
    ]

    def __init__(
        self,
        mailbox: InactiveMailbox | None = None,
        session: "SessionManager | None" = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the holds screen.

        Args:
            mailbox: Optional specific mailbox to analyze (None for all)
            session: Session manager for data access
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._mailbox = mailbox
        self._session = session

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        with VerticalScroll():
            # Header
            if self._mailbox:
                yield Static(
                    f"[bold]Holds Analysis: {self._mailbox.display_name}[/bold]",
                    classes="title",
                )
            else:
                yield Static("[bold]Holds Overview[/bold]", classes="title")

            # Summary Section
            with Container(classes="panel"):
                yield Static("[bold]Summary[/bold]", classes="section-title")
                yield Static("", id="summary-content")

            # Holds Detail Table
            with Container(classes="panel"):
                yield Static("[bold]Hold Details[/bold]", classes="section-title")
                yield DataTable(id="holds-table")

            # Impact Section
            with Container(classes="panel"):
                yield Static("[bold]Impact Analysis[/bold]", classes="section-title")
                yield Static("", id="impact-content")

            # Recommendations Section
            with Container(classes="panel"):
                yield Static("[bold]Recommendations[/bold]", classes="section-title")
                yield Static("", id="recommendations-content")

    def on_mount(self) -> None:
        """Handle screen mount."""
        logger.debug("HoldsScreen mounted")

        # Setup table
        table = self.query_one("#holds-table", DataTable)
        table.add_columns("Mailbox", "Hold Type", "Source", "Impact")

        # Load data
        self._load_holds_data()

    def _load_holds_data(self) -> None:
        """Load and display holds data."""
        if self._mailbox:
            # Single mailbox analysis
            self._analyze_single_mailbox()
        else:
            # Overview of all mailboxes
            self._analyze_all_mailboxes()

    def _analyze_single_mailbox(self) -> None:
        """Analyze holds for a single mailbox."""
        if not self._mailbox:
            return

        # Update summary
        summary_lines = [
            f"Display Name: {self._mailbox.display_name}",
            f"Primary SMTP: {self._mailbox.primary_smtp}",
            "",
        ]

        holds_count = 0
        if self._mailbox.litigation_hold:
            holds_count += 1
        if self._mailbox.hold_types:
            holds_count += len(self._mailbox.hold_types)

        if holds_count == 0:
            summary_lines.append("[success]No holds applied[/success]")
        else:
            summary_lines.append(f"[warning]Total holds: {holds_count}[/warning]")

        self.query_one("#summary-content", Static).update("\n".join(summary_lines))

        # Populate table
        table = self.query_one("#holds-table", DataTable)
        table.clear()

        if self._mailbox.litigation_hold:
            info = HOLD_TYPE_INFO.get("LitigationHold", {})
            table.add_row(
                self._mailbox.display_name[:30],
                info.get("name", "Litigation Hold"),
                "Mailbox Property",
                info.get("impact", "Recovery blocked"),
            )

        for hold_guid in self._mailbox.hold_types or []:
            hold_type = self._identify_hold_type(hold_guid)
            info = HOLD_TYPE_INFO.get(hold_type, {})
            table.add_row(
                self._mailbox.display_name[:30],
                info.get("name", hold_type),
                hold_guid[:20] + "...",
                info.get("impact", "Content preserved"),
            )

        # Impact analysis
        self._update_impact_analysis()

        # Recommendations
        self._update_recommendations()

    def _analyze_all_mailboxes(self) -> None:
        """Analyze holds across all mailboxes."""
        if not self._session:
            self.query_one("#summary-content", Static).update(
                "No session - connect to load data"
            )
            return

        try:
            mailboxes = self._session.db.get_all_mailboxes()

            # Calculate summary
            total = len(mailboxes)
            lit_hold_count = sum(1 for m in mailboxes if m.litigation_hold)
            in_place_count = sum(1 for m in mailboxes if m.hold_types)
            no_hold_count = total - lit_hold_count - in_place_count

            summary_lines = [
                f"Total Mailboxes: {total}",
                "",
                f"[hold-litigation]Litigation Hold: {lit_hold_count}[/hold-litigation]",
                f"[hold-ediscovery]In-Place Holds: {in_place_count}[/hold-ediscovery]",
                f"[hold-none]No Hold: {no_hold_count}[/hold-none]",
            ]
            self.query_one("#summary-content", Static).update("\n".join(summary_lines))

            # Populate table with mailboxes that have holds
            table = self.query_one("#holds-table", DataTable)
            table.clear()

            for mailbox in mailboxes:
                if mailbox.litigation_hold:
                    info = HOLD_TYPE_INFO.get("LitigationHold", {})
                    table.add_row(
                        mailbox.display_name[:30],
                        info.get("name", "Litigation Hold"),
                        "Mailbox Property",
                        info.get("impact", "Recovery blocked"),
                    )

                for hold_guid in mailbox.hold_types or []:
                    hold_type = self._identify_hold_type(hold_guid)
                    info = HOLD_TYPE_INFO.get(hold_type, {})
                    table.add_row(
                        mailbox.display_name[:30],
                        info.get("name", hold_type),
                        hold_guid[:20] + "..." if len(hold_guid) > 20 else hold_guid,
                        info.get("impact", "Content preserved"),
                    )

            # Impact and recommendations
            self._update_impact_analysis()
            self._update_recommendations()

        except Exception as e:
            logger.error(f"Failed to analyze holds: {e}")
            self.query_one("#summary-content", Static).update(f"Error: {e}")

    def _identify_hold_type(self, hold_guid: str) -> str:
        """Identify hold type from GUID pattern.

        Args:
            hold_guid: The hold GUID

        Returns:
            Hold type identifier
        """
        # Common patterns for hold type identification
        if hold_guid.startswith("UniH"):
            return "UniH"
        elif hold_guid.startswith("mbxHold"):
            return "mbxHold"
        elif "InPlaceHold" in hold_guid:
            return "InPlaceHold"
        else:
            return "Unknown"

    def _update_impact_analysis(self) -> None:
        """Update the impact analysis section."""
        impact_lines = [
            "Recovery Operations:",
            "  - Mailboxes with Litigation Hold cannot be fully deleted",
            "  - eDiscovery holds preserve content for legal compliance",
            "  - Retention holds maintain data per organizational policy",
            "",
            "Recommended Actions:",
            "  - Review holds before recovery operations",
            "  - Contact Legal/Compliance before removing holds",
            "  - Document hold removal for audit purposes",
        ]
        self.query_one("#impact-content", Static).update("\n".join(impact_lines))

    def _update_recommendations(self) -> None:
        """Update the recommendations section."""
        rec_lines = [
            "1. Review all holds with Legal/Compliance team",
            "2. Document justification for any hold removal",
            "3. Use Compliance Center for eDiscovery hold management",
            "4. Consider archive export before hold removal",
            "5. Audit all hold changes per organizational policy",
            "",
            "[info]Note: Hold removal may require elevated permissions[/info]",
        ]
        self.query_one("#recommendations-content", Static).update("\n".join(rec_lines))

    def action_back(self) -> None:
        """Go back to the previous screen."""
        self.app.pop_screen()

    def action_refresh(self) -> None:
        """Refresh holds data."""
        self._load_holds_data()
        self.app.notify("Holds data refreshed", timeout=2)

    def action_export(self) -> None:
        """Export holds analysis."""
        self.app.notify("Exporting holds analysis...", timeout=2)
