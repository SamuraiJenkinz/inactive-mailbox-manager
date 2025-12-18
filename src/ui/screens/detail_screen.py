"""Mailbox detail screen showing comprehensive information."""

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Static

from src.core.dashboard_service import format_size
from src.data.models import InactiveMailbox
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.data.session import SessionManager

logger = get_logger(__name__)


class MailboxDetailScreen(Screen):
    """Screen showing detailed information about a single mailbox.

    Displays all properties, hold status, recovery eligibility,
    and provides actions for recovery/restore operations.
    """

    BINDINGS = [
        Binding("escape", "back", "Back", show=True),
        Binding("r", "recover", "Recover", show=True),
        Binding("s", "restore", "Restore", show=True),
    ]

    def __init__(
        self,
        mailbox: InactiveMailbox,
        session: "SessionManager | None" = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the detail screen.

        Args:
            mailbox: Mailbox to display
            session: Session manager for operations
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
            # Header with mailbox name
            yield Static(
                f"[bold]{self._mailbox.display_name}[/bold]",
                classes="title",
            )
            yield Static(self._mailbox.primary_smtp, classes="subtitle")

            # Basic Information Section
            with Container(classes="panel"):
                yield Static("[bold]Basic Information[/bold]", classes="section-title")
                with Horizontal():
                    with Vertical():
                        yield self._info_row("Identity", self._mailbox.identity)
                        yield self._info_row("UPN", self._mailbox.user_principal_name or "N/A")
                        yield self._info_row("Department", self._mailbox.department or "N/A")
                        yield self._info_row("Company", self._mailbox.operating_company or "N/A")
                    with Vertical():
                        yield self._info_row("Size", format_size(self._mailbox.size_mb))
                        yield self._info_row("Items", f"{self._mailbox.item_count:,}")
                        yield self._info_row("Age", f"{self._mailbox.age_days} days")
                        yield self._info_row(
                            "Deleted",
                            self._mailbox.when_soft_deleted.strftime("%Y-%m-%d %H:%M")
                            if self._mailbox.when_soft_deleted else "Unknown",
                        )

            # Hold Status Section
            with Container(classes="panel"):
                yield Static("[bold]Hold Status[/bold]", classes="section-title")

                lit_hold = "Yes" if self._mailbox.litigation_hold else "No"
                lit_class = "hold-litigation" if self._mailbox.litigation_hold else "hold-none"
                yield Static(
                    f"Litigation Hold: [{lit_class}]{lit_hold}[/{lit_class}]",
                )

                if self._mailbox.hold_types:
                    yield Static(f"In-Place Holds ({len(self._mailbox.hold_types)}):")
                    for hold in self._mailbox.hold_types:
                        yield Static(f"  - {hold}", classes="hold-ediscovery")
                else:
                    yield Static("No in-place holds", classes="hold-none")

            # Archive Status Section
            with Container(classes="panel"):
                yield Static("[bold]Archive Information[/bold]", classes="section-title")
                yield self._info_row("Archive Status", self._mailbox.archive_status or "None")
                yield self._info_row("Archive GUID", self._mailbox.archive_guid or "N/A")

            # Recovery Status Section
            with Container(classes="panel"):
                yield Static("[bold]Recovery Status[/bold]", classes="section-title")

                eligible_text = "Eligible" if self._mailbox.recovery_eligible else "Not Eligible"
                eligible_class = "success" if self._mailbox.recovery_eligible else "error"
                yield Static(
                    f"Recovery: [{eligible_class}]{eligible_text}[/{eligible_class}]",
                )

                if self._mailbox.recovery_blockers:
                    yield Static("Blockers:")
                    for blocker in self._mailbox.recovery_blockers:
                        yield Static(f"  - {blocker}", classes="error")

            # License & Cost Section
            with Container(classes="panel"):
                yield Static("[bold]License & Cost[/bold]", classes="section-title")
                yield self._info_row("License Type", self._mailbox.license_type or "Unknown")
                yield self._info_row(
                    "Monthly Cost",
                    f"${self._mailbox.monthly_cost:.2f}" if self._mailbox.monthly_cost else "N/A",
                )

            # Action Buttons
            with Horizontal(classes="button-row"):
                yield Button("Recover", id="btn-recover", variant="primary")
                yield Button("Restore", id="btn-restore")
                yield Button("Export", id="btn-export")
                yield Button("Back", id="btn-back")

    def _info_row(self, label: str, value: str) -> Static:
        """Create an info row widget.

        Args:
            label: Row label
            value: Row value

        Returns:
            Static widget with formatted info
        """
        return Static(f"[bold]{label}:[/bold] {value}")

    def action_back(self) -> None:
        """Go back to the main screen."""
        self.app.pop_screen()

    def action_recover(self) -> None:
        """Start recovery wizard for this mailbox."""
        from src.ui.screens.recovery_wizard_screen import RecoveryWizardScreen
        self.app.push_screen(RecoveryWizardScreen(self._mailbox, self._session))

    def action_restore(self) -> None:
        """Start restore wizard for this mailbox."""
        self.app.notify("Restore wizard - coming soon", timeout=2)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: Button press event
        """
        if event.button.id == "btn-recover":
            self.action_recover()
        elif event.button.id == "btn-restore":
            self.action_restore()
        elif event.button.id == "btn-export":
            self.app.notify("Exporting mailbox data...", timeout=2)
        elif event.button.id == "btn-back":
            self.action_back()
