"""Main Textual application for Inactive Mailbox Manager."""

from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from src.ui.screens.main_screen import MainScreen
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.data.session import SessionManager

logger = get_logger(__name__)


class InactiveMailboxApp(App):
    """Main Textual application for managing inactive mailboxes.

    A terminal-based interface with brutalist dark theme for
    viewing, filtering, and managing M365 inactive mailboxes.
    """

    TITLE = "Inactive Mailbox Manager"
    SUB_TITLE = "Microsoft 365 Management Tool"

    CSS_PATH = Path(__file__).parent / "styles" / "theme.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("?", "toggle_help", "Help", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("c", "connect", "Connect", show=True),
        Binding("d", "dashboard", "Dashboard", show=True),
        Binding("/", "focus_search", "Search", show=True),
        Binding("escape", "back", "Back", show=False),
    ]

    def __init__(
        self,
        session: "SessionManager | None" = None,
        **kwargs,
    ) -> None:
        """Initialize the application.

        Args:
            session: Optional session manager (creates new if not provided)
            **kwargs: Additional arguments for App
        """
        super().__init__(**kwargs)
        self._session = session
        self._connected = False

        logger.info("InactiveMailboxApp initialized")

    @property
    def session(self) -> "SessionManager | None":
        """Get the current session manager."""
        return self._session

    @property
    def is_connected(self) -> bool:
        """Check if connected to Exchange Online."""
        if self._session and self._session.connection:
            return self._session.connection.is_connected
        return False

    def compose(self) -> ComposeResult:
        """Compose the application layout."""
        yield Header(show_clock=True)
        yield Footer()

    def on_mount(self) -> None:
        """Handle application mount."""
        logger.debug("Application mounted")
        # Push the main screen
        self.push_screen(MainScreen(self._session))

    def action_quit(self) -> None:
        """Quit the application."""
        logger.info("Application quit requested")
        self.exit()

    def action_refresh(self) -> None:
        """Refresh current screen data."""
        logger.debug("Refresh action triggered")
        # Get current screen and call refresh if available
        if hasattr(self.screen, "refresh_data"):
            self.screen.refresh_data()

    def action_toggle_help(self) -> None:
        """Toggle help screen."""
        logger.debug("Help toggle requested")
        self.notify("Help: Press ? for shortcuts, q to quit", timeout=3)

    def action_connect(self) -> None:
        """Show connection screen."""
        logger.debug("Connect action triggered")
        from src.ui.screens.connection_screen import ConnectionScreen
        self.push_screen(ConnectionScreen(self._session))

    def action_dashboard(self) -> None:
        """Show dashboard screen."""
        logger.debug("Dashboard action triggered")
        from src.ui.screens.dashboard_screen import DashboardScreen
        self.push_screen(DashboardScreen(self._session))

    def action_focus_search(self) -> None:
        """Focus the search input."""
        logger.debug("Focus search triggered")
        if hasattr(self.screen, "focus_search"):
            self.screen.focus_search()

    def action_back(self) -> None:
        """Go back to previous screen."""
        if len(self.screen_stack) > 1:
            self.pop_screen()

    def set_session(self, session: "SessionManager") -> None:
        """Set the session manager.

        Args:
            session: Session manager to use
        """
        self._session = session
        logger.info("Session manager updated")

    def notify_error(self, message: str) -> None:
        """Show an error notification.

        Args:
            message: Error message to display
        """
        self.notify(message, severity="error", timeout=5)

    def notify_success(self, message: str) -> None:
        """Show a success notification.

        Args:
            message: Success message to display
        """
        self.notify(message, severity="information", timeout=3)


def run_app(session: "SessionManager | None" = None) -> None:
    """Run the Textual application.

    Args:
        session: Optional session manager
    """
    app = InactiveMailboxApp(session=session)
    app.run()


if __name__ == "__main__":
    run_app()
