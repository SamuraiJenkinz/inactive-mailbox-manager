"""Sidebar navigation component."""

from typing import Callable

import customtkinter as ctk

from src.gui.theme import COLORS, get_button_colors


class SidebarButton(ctk.CTkButton):
    """Custom sidebar navigation button."""

    def __init__(
        self,
        master,
        text: str,
        command: Callable,
        selected: bool = False,
        **kwargs,
    ) -> None:
        """Initialize sidebar button.

        Args:
            master: Parent widget
            text: Button text
            command: Click callback
            selected: Whether button is selected
            **kwargs: Additional button arguments
        """
        self._selected = selected

        colors = self._get_colors()

        super().__init__(
            master,
            text=text,
            command=command,
            height=40,
            corner_radius=0,
            anchor="w",
            **colors,
            **kwargs,
        )

    def _get_colors(self) -> dict:
        """Get colors based on selection state."""
        if self._selected:
            return {
                "fg_color": COLORS["primary_dim"],
                "hover_color": COLORS["primary"],
                "text_color": COLORS["background"],
            }
        else:
            return {
                "fg_color": "transparent",
                "hover_color": COLORS["surface_light"],
                "text_color": COLORS["text"],
            }

    def set_selected(self, selected: bool) -> None:
        """Set the selection state.

        Args:
            selected: Whether button is selected
        """
        self._selected = selected
        colors = self._get_colors()
        self.configure(**colors)


class Sidebar(ctk.CTkFrame):
    """Sidebar navigation frame.

    Contains navigation buttons, connection status,
    and settings access.
    """

    def __init__(
        self,
        master,
        on_navigate: Callable[[str], None],
        width: int = 200,
        **kwargs,
    ) -> None:
        """Initialize the sidebar.

        Args:
            master: Parent widget
            on_navigate: Callback when navigation item selected
            width: Sidebar width
            **kwargs: Additional frame arguments
        """
        super().__init__(
            master,
            width=width,
            corner_radius=0,
            fg_color=COLORS["surface"],
            **kwargs,
        )

        self._on_navigate = on_navigate
        self._buttons: dict[str, SidebarButton] = {}
        self._selected: str = ""

        # Prevent frame from shrinking
        self.grid_propagate(False)

        # Configure grid
        self.grid_rowconfigure(6, weight=1)  # Spacer row

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create sidebar widgets."""
        # Logo/Title
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(20, 10))

        title_label = ctk.CTkLabel(
            title_frame,
            text="IMM",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=COLORS["primary"],
        )
        title_label.pack(anchor="w")

        subtitle_label = ctk.CTkLabel(
            title_frame,
            text="Mailbox Manager",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_muted"],
        )
        subtitle_label.pack(anchor="w")

        # Separator
        separator = ctk.CTkFrame(self, height=2, fg_color=COLORS["surface_light"])
        separator.grid(row=1, column=0, sticky="ew", padx=10, pady=10)

        # Navigation buttons
        nav_items = [
            ("mailboxes", "Mailboxes"),
            ("dashboard", "Dashboard"),
            ("bulk", "Bulk Operations"),
        ]

        for i, (name, text) in enumerate(nav_items, start=2):
            btn = SidebarButton(
                self,
                text=f"  {text}",
                command=lambda n=name: self._navigate(n),
            )
            btn.grid(row=i, column=0, sticky="ew", padx=5, pady=2)
            self._buttons[name] = btn

        # Spacer (row 6 with weight=1)

        # Bottom section
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.grid(row=7, column=0, sticky="ew", padx=5, pady=5)

        # Settings button
        settings_btn = SidebarButton(
            bottom_frame,
            text="  Settings",
            command=lambda: self._navigate("settings"),
        )
        settings_btn.pack(fill="x", pady=2)
        self._buttons["settings"] = settings_btn

        # Help button
        help_btn = SidebarButton(
            bottom_frame,
            text="  Help",
            command=lambda: self._navigate("help"),
        )
        help_btn.pack(fill="x", pady=2)
        self._buttons["help"] = help_btn

        # Connection status
        self._connection_frame = ctk.CTkFrame(
            self,
            fg_color=COLORS["background"],
            corner_radius=5,
        )
        self._connection_frame.grid(row=8, column=0, sticky="ew", padx=10, pady=10)

        self._connection_indicator = ctk.CTkLabel(
            self._connection_frame,
            text="●",
            text_color=COLORS["error"],
            font=ctk.CTkFont(size=12),
        )
        self._connection_indicator.pack(side="left", padx=5)

        self._connection_label = ctk.CTkLabel(
            self._connection_frame,
            text="Disconnected",
            text_color=COLORS["text_muted"],
            font=ctk.CTkFont(size=11),
        )
        self._connection_label.pack(side="left", padx=5, pady=5)

    def _navigate(self, name: str) -> None:
        """Handle navigation button click.

        Args:
            name: Navigation target name
        """
        self.set_selected(name)
        self._on_navigate(name)

    def set_selected(self, name: str) -> None:
        """Set the selected navigation item.

        Args:
            name: Item name to select
        """
        # Deselect previous
        if self._selected and self._selected in self._buttons:
            self._buttons[self._selected].set_selected(False)

        # Select new
        self._selected = name
        if name in self._buttons:
            self._buttons[name].set_selected(True)

    def set_connection_status(self, connected: bool, org: str = "") -> None:
        """Update the connection status display.

        Args:
            connected: Whether connected
            org: Organization name if connected
        """
        if connected:
            self._connection_indicator.configure(text_color=COLORS["success"])
            self._connection_label.configure(
                text=org[:15] if org else "Connected",
                text_color=COLORS["text"],
            )
        else:
            self._connection_indicator.configure(text_color=COLORS["error"])
            self._connection_label.configure(
                text="Disconnected",
                text_color=COLORS["text_muted"],
            )
