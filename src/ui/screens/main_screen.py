"""Main screen with mailbox list view."""

from datetime import datetime
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Input, Static

from src.core.dashboard_service import format_size
from src.data.models import InactiveMailbox
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.data.session import SessionManager

logger = get_logger(__name__)


class MainScreen(Screen):
    """Main screen showing the mailbox list with search and filtering.

    Displays all inactive mailboxes in a DataTable with search
    functionality and keyboard navigation.
    """

    BINDINGS = [
        Binding("enter", "select_row", "Details", show=True),
        Binding("r", "recover", "Recover", show=True),
        Binding("s", "restore", "Restore", show=True),
        Binding("e", "export", "Export", show=True),
        Binding("f", "filter", "Filter", show=True),
        Binding("escape", "clear_search", "Clear", show=False),
    ]

    def __init__(
        self,
        session: "SessionManager | None" = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the main screen.

        Args:
            session: Session manager for data access
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._session = session
        self._mailboxes: list[InactiveMailbox] = []
        self._filtered_mailboxes: list[InactiveMailbox] = []
        self._search_query = ""

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        # Search bar
        with Container(classes="search-container"):
            yield Horizontal(
                Static("Search: ", classes="label"),
                Input(
                    placeholder="Type to filter mailboxes...",
                    id="search-input",
                ),
                Static("", id="status-text"),
            )

        # Main content - DataTable
        with Container(classes="main-content"):
            yield DataTable(id="mailbox-table", cursor_type="row")

        # Status bar
        yield Static("", id="status-bar", classes="status-bar")

    def on_mount(self) -> None:
        """Handle screen mount."""
        logger.debug("MainScreen mounted")

        # Setup table columns
        table = self.query_one("#mailbox-table", DataTable)
        table.add_columns(
            "Display Name",
            "Primary SMTP",
            "Size",
            "Items",
            "Hold Status",
            "Disconnected",
        )

        # Load data
        self.load_mailboxes()

    def load_mailboxes(self) -> None:
        """Load mailboxes from database."""
        logger.debug("Loading mailboxes")

        if not self._session:
            self._mailboxes = []
            self._update_status("No session - connect to load data")
            return

        try:
            self._mailboxes = self._session.db.get_all_mailboxes()
            self._filtered_mailboxes = self._mailboxes.copy()
            self._populate_table()
            self._update_status(f"Loaded {len(self._mailboxes)} mailboxes")
        except Exception as e:
            logger.error(f"Failed to load mailboxes: {e}")
            self._update_status(f"Error: {e}")

    def _populate_table(self) -> None:
        """Populate the DataTable with mailbox data."""
        table = self.query_one("#mailbox-table", DataTable)
        table.clear()

        for mailbox in self._filtered_mailboxes:
            # Format hold status
            holds = []
            if mailbox.litigation_hold:
                holds.append("Litigation")
            if mailbox.hold_types:
                hold_count = len(mailbox.hold_types)
                holds.append(f"{hold_count} hold{'s' if hold_count > 1 else ''}")

            hold_status = ", ".join(holds) if holds else "None"

            # Format disconnected date
            disc_date = ""
            if mailbox.when_soft_deleted:
                disc_date = mailbox.when_soft_deleted.strftime("%Y-%m-%d")

            # Add row
            table.add_row(
                mailbox.display_name[:40],  # Truncate long names
                mailbox.primary_smtp[:35],
                format_size(mailbox.size_mb),
                f"{mailbox.item_count:,}",
                hold_status,
                disc_date,
                key=mailbox.identity,
            )

    def _update_status(self, message: str) -> None:
        """Update the status bar message.

        Args:
            message: Status message to display
        """
        status_bar = self.query_one("#status-bar", Static)

        # Include count info
        total = len(self._mailboxes)
        filtered = len(self._filtered_mailboxes)

        if self._search_query:
            count_info = f"[{filtered}/{total}] "
        else:
            count_info = f"[{total}] "

        # Connection status
        connected = "Connected" if self._session and self._session.connection and self._session.connection.is_connected else "Disconnected"
        conn_class = "status-connected" if connected == "Connected" else "status-disconnected"

        status_bar.update(f"{count_info}{message} | {connected}")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes.

        Args:
            event: Input change event
        """
        if event.input.id == "search-input":
            self._search_query = event.value.lower()
            self._filter_mailboxes()

    def _filter_mailboxes(self) -> None:
        """Filter mailboxes based on search query."""
        if not self._search_query:
            self._filtered_mailboxes = self._mailboxes.copy()
        else:
            query = self._search_query
            self._filtered_mailboxes = [
                m for m in self._mailboxes
                if query in m.display_name.lower()
                or query in m.primary_smtp.lower()
                or query in m.identity.lower()
            ]

        self._populate_table()
        self._update_status(f"Showing {len(self._filtered_mailboxes)} mailboxes")

    def action_select_row(self) -> None:
        """Show details for the selected mailbox."""
        table = self.query_one("#mailbox-table", DataTable)

        if table.cursor_row is not None:
            row_key = table.get_row_at(table.cursor_row)
            if row_key:
                # Find the mailbox
                identity = str(table.get_row_key(row_key))
                mailbox = self._get_mailbox_by_identity(identity)
                if mailbox:
                    self._show_details(mailbox)

    def _get_mailbox_by_identity(self, identity: str) -> InactiveMailbox | None:
        """Get mailbox by identity.

        Args:
            identity: Mailbox identity

        Returns:
            InactiveMailbox or None
        """
        for mailbox in self._mailboxes:
            if mailbox.identity == identity:
                return mailbox
        return None

    def _show_details(self, mailbox: InactiveMailbox) -> None:
        """Show mailbox details screen.

        Args:
            mailbox: Mailbox to show details for
        """
        logger.debug(f"Showing details for: {mailbox.display_name}")
        from src.ui.screens.detail_screen import MailboxDetailScreen
        self.app.push_screen(MailboxDetailScreen(mailbox, self._session))

    def action_recover(self) -> None:
        """Start recovery wizard for selected mailbox."""
        table = self.query_one("#mailbox-table", DataTable)

        if table.cursor_row is not None:
            row_key = table.get_row_at(table.cursor_row)
            if row_key:
                identity = str(table.get_row_key(row_key))
                mailbox = self._get_mailbox_by_identity(identity)
                if mailbox:
                    from src.ui.screens.recovery_wizard_screen import RecoveryWizardScreen
                    self.app.push_screen(RecoveryWizardScreen(mailbox, self._session))

    def action_restore(self) -> None:
        """Start restore wizard for selected mailbox."""
        table = self.query_one("#mailbox-table", DataTable)

        if table.cursor_row is not None:
            self.app.notify("Restore wizard - coming soon", timeout=2)

    def action_export(self) -> None:
        """Export mailbox data."""
        self.app.notify(f"Exporting {len(self._filtered_mailboxes)} mailboxes...", timeout=2)
        # TODO: Implement export dialog

    def action_filter(self) -> None:
        """Show filter options."""
        self.app.notify("Filter options - coming soon", timeout=2)
        # TODO: Implement filter dialog

    def action_clear_search(self) -> None:
        """Clear the search input."""
        search_input = self.query_one("#search-input", Input)
        search_input.value = ""
        self._search_query = ""
        self._filter_mailboxes()

    def focus_search(self) -> None:
        """Focus the search input."""
        search_input = self.query_one("#search-input", Input)
        search_input.focus()

    def refresh_data(self) -> None:
        """Refresh mailbox data."""
        self.load_mailboxes()
        self.app.notify("Data refreshed", timeout=2)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the DataTable.

        Args:
            event: Row selection event
        """
        if event.row_key:
            identity = str(event.row_key.value)
            mailbox = self._get_mailbox_by_identity(identity)
            if mailbox:
                self._show_details(mailbox)
