"""Base frame class for all content frames."""

from typing import TYPE_CHECKING

import customtkinter as ctk

from src.gui.theme import COLORS

if TYPE_CHECKING:
    from src.data.session import SessionManager


class BaseFrame(ctk.CTkFrame):
    """Base class for all content frames.

    Provides common functionality like session access,
    standard styling, and refresh capability.
    """

    def __init__(
        self,
        master,
        session: "SessionManager | None" = None,
        **kwargs,
    ) -> None:
        """Initialize the base frame.

        Args:
            master: Parent widget
            session: Session manager for data access
            **kwargs: Additional frame arguments
        """
        super().__init__(
            master,
            fg_color=COLORS["background"],
            corner_radius=0,
            **kwargs,
        )

        self._session = session

        # Configure grid
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    @property
    def session(self) -> "SessionManager | None":
        """Get the session manager."""
        return self._session

    def refresh(self) -> None:
        """Refresh the frame data.

        Override in subclasses to implement refresh logic.
        """
        pass

    def get_app(self) -> ctk.CTk:
        """Get the root application.

        Returns:
            The CTk application instance
        """
        return self.winfo_toplevel()

    def show_notification(self, message: str, level: str = "info") -> None:
        """Show a notification via the app.

        Args:
            message: Message to display
            level: Notification level
        """
        app = self.get_app()
        if hasattr(app, "show_notification"):
            app.show_notification(message, level)

    def set_status(self, message: str) -> None:
        """Set status bar message via the app.

        Args:
            message: Status message
        """
        app = self.get_app()
        if hasattr(app, "set_status"):
            app.set_status(message)
