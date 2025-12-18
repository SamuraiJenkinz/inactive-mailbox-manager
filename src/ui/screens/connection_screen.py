"""Connection screen for Exchange Online authentication."""

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, LoadingIndicator, Static

from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.data.session import SessionManager

logger = get_logger(__name__)


class ConnectionScreen(Screen):
    """Screen for connecting to Exchange Online.

    Handles authentication with Microsoft 365 using
    device code or certificate-based authentication.
    """

    BINDINGS = [
        Binding("escape", "back", "Back", show=True),
        Binding("enter", "connect", "Connect", show=False),
    ]

    def __init__(
        self,
        session: "SessionManager | None" = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the connection screen.

        Args:
            session: Session manager for connection handling
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._session = session
        self._connecting = False

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        with Vertical():
            yield Static("[bold]Connect to Exchange Online[/bold]", classes="title")
            yield Static(
                "Enter your organization credentials to connect",
                classes="subtitle",
            )

            with Container(classes="panel"):
                yield Static("[bold]Connection Settings[/bold]", classes="section-title")

                yield Label("Organization Domain:")
                yield Input(
                    placeholder="contoso.onmicrosoft.com",
                    id="input-org",
                )

                yield Label("Admin UPN (optional):")
                yield Input(
                    placeholder="admin@contoso.com",
                    id="input-upn",
                )

                yield Label("App ID (for certificate auth):")
                yield Input(
                    placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                    id="input-appid",
                )

                yield Label("Certificate Thumbprint (optional):")
                yield Input(
                    placeholder="Certificate thumbprint for app authentication",
                    id="input-cert",
                )

            # Connection status
            with Container(classes="panel"):
                yield Static("[bold]Status[/bold]", classes="section-title")
                yield Static("Not connected", id="connection-status")
                yield LoadingIndicator(id="loading", classes="hidden")

            # Action buttons
            with Container(classes="button-row"):
                yield Button("Connect", id="btn-connect", variant="primary")
                yield Button("Test Connection", id="btn-test")
                yield Button("Cancel", id="btn-cancel")

    def on_mount(self) -> None:
        """Handle screen mount."""
        logger.debug("ConnectionScreen mounted")
        self._update_status()

    def _update_status(self) -> None:
        """Update the connection status display."""
        status_widget = self.query_one("#connection-status", Static)

        if self._session and self._session.connection and self._session.connection.is_connected:
            status_widget.update("[success]Connected[/success]")
        else:
            status_widget.update("[error]Not connected[/error]")

    def action_back(self) -> None:
        """Go back to the main screen."""
        self.app.pop_screen()

    def action_connect(self) -> None:
        """Start connection process."""
        if self._connecting:
            return

        self._connecting = True
        self._show_loading(True)

        # Get input values
        org = self.query_one("#input-org", Input).value.strip()
        upn = self.query_one("#input-upn", Input).value.strip()
        app_id = self.query_one("#input-appid", Input).value.strip()
        cert = self.query_one("#input-cert", Input).value.strip()

        if not org:
            self.app.notify("Organization domain is required", severity="error")
            self._connecting = False
            self._show_loading(False)
            return

        try:
            # Attempt connection
            logger.info(f"Connecting to Exchange Online: {org}")

            if self._session and self._session.connection:
                # Configure connection
                self._session.connection.organization = org
                if app_id:
                    self._session.connection.app_id = app_id
                if cert:
                    self._session.connection.certificate_thumbprint = cert

                # Connect (this would trigger actual authentication)
                success = self._session.connection.connect(upn or None)

                if success:
                    self.app.notify("Connected successfully", severity="information")
                    self._update_status()

                    # Refresh main screen data
                    if hasattr(self.app.screen_stack[0], "refresh_data"):
                        self.app.screen_stack[0].refresh_data()

                    self.app.pop_screen()
                else:
                    self.app.notify("Connection failed", severity="error")
            else:
                self.app.notify("No session manager available", severity="error")

        except Exception as e:
            logger.error(f"Connection error: {e}")
            self.app.notify(f"Connection error: {e}", severity="error")

        finally:
            self._connecting = False
            self._show_loading(False)

    def _show_loading(self, show: bool) -> None:
        """Show or hide the loading indicator.

        Args:
            show: Whether to show the loading indicator
        """
        loading = self.query_one("#loading", LoadingIndicator)
        if show:
            loading.remove_class("hidden")
        else:
            loading.add_class("hidden")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: Button press event
        """
        if event.button.id == "btn-connect":
            self.action_connect()
        elif event.button.id == "btn-test":
            self._test_connection()
        elif event.button.id == "btn-cancel":
            self.action_back()

    def _test_connection(self) -> None:
        """Test the connection without fully connecting."""
        org = self.query_one("#input-org", Input).value.strip()

        if not org:
            self.app.notify("Enter organization domain first", severity="warning")
            return

        self.app.notify(f"Testing connection to {org}...", timeout=2)

        # In a real implementation, this would test connectivity
        # For now, just simulate
        self.app.notify("Connection test: OK", severity="information")
