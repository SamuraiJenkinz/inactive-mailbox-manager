"""Main Desktop GUI application using CustomTkinter."""

from typing import TYPE_CHECKING

import customtkinter as ctk

from src.gui.theme import apply_theme, COLORS
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.data.session import SessionManager

logger = get_logger(__name__)


class DesktopApp(ctk.CTk):
    """Main desktop application window.

    A CustomTkinter-based GUI with sidebar navigation,
    frame-based content, and brutalist dark theme.
    """

    def __init__(self, session: "SessionManager | None" = None) -> None:
        """Initialize the desktop application.

        Args:
            session: Optional session manager for data access
        """
        super().__init__()

        self._session = session
        self._frames: dict[str, ctk.CTkFrame] = {}
        self._current_frame: str | None = None

        # Apply theme
        apply_theme()

        # Configure window
        self.title("Inactive Mailbox Manager")
        self.geometry("1400x900")
        self.minsize(1000, 700)

        # Configure grid layout
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Build UI
        self._create_sidebar()
        self._create_main_container()
        self._create_status_bar()

        # Initialize frames
        self._init_frames()

        # Show default frame
        self.show_frame("mailboxes")

        logger.info("DesktopApp initialized")

    @property
    def session(self) -> "SessionManager | None":
        """Get the current session manager."""
        return self._session

    def _create_sidebar(self) -> None:
        """Create the sidebar navigation."""
        from src.gui.components.sidebar import Sidebar

        self._sidebar = Sidebar(
            self,
            on_navigate=self.show_frame,
            width=200,
        )
        self._sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")

    def _create_main_container(self) -> None:
        """Create the main content container."""
        self._main_container = ctk.CTkFrame(
            self,
            fg_color=COLORS["background"],
            corner_radius=0,
        )
        self._main_container.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self._main_container.grid_rowconfigure(0, weight=1)
        self._main_container.grid_columnconfigure(0, weight=1)

    def _create_status_bar(self) -> None:
        """Create the status bar."""
        self._status_bar = ctk.CTkFrame(
            self,
            height=30,
            fg_color=COLORS["surface"],
            corner_radius=0,
        )
        self._status_bar.grid(row=1, column=1, sticky="ew")

        # Status label
        self._status_label = ctk.CTkLabel(
            self._status_bar,
            text="Ready",
            text_color=COLORS["text_muted"],
            anchor="w",
        )
        self._status_label.pack(side="left", padx=10)

        # Connection status
        self._connection_label = ctk.CTkLabel(
            self._status_bar,
            text="Disconnected",
            text_color=COLORS["error"],
            anchor="e",
        )
        self._connection_label.pack(side="right", padx=10)

    def _init_frames(self) -> None:
        """Initialize all content frames."""
        from src.gui.frames.mailbox_frame import MailboxFrame
        from src.gui.frames.dashboard_frame import DashboardFrame
        from src.gui.frames.bulk_frame import BulkFrame
        from src.gui.frames.settings_frame import SettingsFrame
        from src.gui.frames.help_frame import HelpFrame

        # Create frames
        self._frames["mailboxes"] = MailboxFrame(self._main_container, self._session)
        self._frames["dashboard"] = DashboardFrame(self._main_container, self._session)
        self._frames["bulk"] = BulkFrame(self._main_container, self._session)
        self._frames["settings"] = SettingsFrame(self._main_container, self._session)
        self._frames["help"] = HelpFrame(self._main_container, self._session)

        # Grid all frames (stacked)
        for frame in self._frames.values():
            frame.grid(row=0, column=0, sticky="nsew")

    def show_frame(self, name: str) -> None:
        """Show a specific frame.

        Args:
            name: Frame name to show
        """
        if name not in self._frames:
            logger.warning(f"Unknown frame: {name}")
            return

        # Hide current frame
        if self._current_frame and self._current_frame in self._frames:
            self._frames[self._current_frame].grid_remove()

        # Show new frame
        self._frames[name].grid()
        self._frames[name].tkraise()
        self._current_frame = name

        # Refresh frame data
        if hasattr(self._frames[name], "refresh"):
            self._frames[name].refresh()

        # Update sidebar selection
        if hasattr(self, "_sidebar"):
            self._sidebar.set_selected(name)

        logger.debug(f"Showing frame: {name}")

    def set_status(self, message: str) -> None:
        """Update the status bar message.

        Args:
            message: Status message to display
        """
        self._status_label.configure(text=message)

    def set_connection_status(self, connected: bool) -> None:
        """Update the connection status indicator.

        Args:
            connected: Whether connected to Exchange Online
        """
        if connected:
            self._connection_label.configure(
                text="Connected",
                text_color=COLORS["success"],
            )
        else:
            self._connection_label.configure(
                text="Disconnected",
                text_color=COLORS["error"],
            )

    def show_notification(self, message: str, level: str = "info") -> None:
        """Show a notification message.

        Args:
            message: Message to display
            level: Notification level (info, warning, error, success)
        """
        # Update status bar as simple notification
        color = COLORS.get(level, COLORS["text"])
        self._status_label.configure(text=message, text_color=color)

        # Reset after 5 seconds
        self.after(5000, lambda: self._status_label.configure(
            text="Ready",
            text_color=COLORS["text_muted"],
        ))


def run_desktop_app(session: "SessionManager | None" = None) -> None:
    """Run the desktop application.

    Args:
        session: Optional session manager
    """
    app = DesktopApp(session=session)
    app.mainloop()


if __name__ == "__main__":
    run_desktop_app()
