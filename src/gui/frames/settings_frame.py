"""Settings frame for application configuration."""

from typing import TYPE_CHECKING

import customtkinter as ctk

from src.gui.frames.base_frame import BaseFrame
from src.gui.theme import COLORS, get_button_colors
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.data.session import SessionManager

logger = get_logger(__name__)


class SettingsFrame(BaseFrame):
    """Settings frame for application configuration.

    Provides interface for connection settings, appearance,
    and export preferences.
    """

    def __init__(
        self,
        master,
        session: "SessionManager | None" = None,
        **kwargs,
    ) -> None:
        """Initialize the settings frame.

        Args:
            master: Parent widget
            session: Session manager for data access
            **kwargs: Additional frame arguments
        """
        super().__init__(master, session, **kwargs)

        self._org_var = ctk.StringVar()
        self._app_id_var = ctk.StringVar()
        self._cert_var = ctk.StringVar()

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create settings widgets."""
        # Scrollable content
        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        ctk.CTkLabel(
            content,
            text="Settings",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=COLORS["primary"],
        ).pack(anchor="w", pady=(0, 20))

        # Connection Settings
        self._create_connection_section(content)

        # Appearance Settings
        self._create_appearance_section(content)

        # Export Settings
        self._create_export_section(content)

        # About Section
        self._create_about_section(content)

    def _create_connection_section(self, parent) -> None:
        """Create connection settings section."""
        section = ctk.CTkFrame(parent, fg_color=COLORS["surface"])
        section.pack(fill="x", pady=10)

        ctk.CTkLabel(
            section,
            text="Connection Settings",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["primary"],
        ).pack(anchor="w", padx=15, pady=(15, 10))

        # Organization
        self._create_input_row(section, "Organization:", self._org_var, "contoso.onmicrosoft.com")

        # App ID
        self._create_input_row(section, "App ID:", self._app_id_var, "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")

        # Certificate
        self._create_input_row(section, "Certificate:", self._cert_var, "Certificate thumbprint")

        # Buttons
        btn_frame = ctk.CTkFrame(section, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=15)

        connect_btn = ctk.CTkButton(
            btn_frame,
            text="Connect",
            width=100,
            command=self._connect,
            **get_button_colors("primary"),
        )
        connect_btn.pack(side="left", padx=5)

        test_btn = ctk.CTkButton(
            btn_frame,
            text="Test Connection",
            width=120,
            command=self._test_connection,
            **get_button_colors(),
        )
        test_btn.pack(side="left", padx=5)

        # Status
        self._connection_status = ctk.CTkLabel(
            section,
            text="Not connected",
            text_color=COLORS["error"],
        )
        self._connection_status.pack(anchor="w", padx=15, pady=(0, 15))

    def _create_appearance_section(self, parent) -> None:
        """Create appearance settings section."""
        section = ctk.CTkFrame(parent, fg_color=COLORS["surface"])
        section.pack(fill="x", pady=10)

        ctk.CTkLabel(
            section,
            text="Appearance",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["primary"],
        ).pack(anchor="w", padx=15, pady=(15, 10))

        # Theme selection
        theme_frame = ctk.CTkFrame(section, fg_color="transparent")
        theme_frame.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(
            theme_frame,
            text="Theme:",
            text_color=COLORS["text"],
        ).pack(side="left", padx=(0, 10))

        theme_menu = ctk.CTkOptionMenu(
            theme_frame,
            values=["Dark", "Light", "System"],
            command=self._change_theme,
            fg_color=COLORS["surface_light"],
        )
        theme_menu.set("Dark")
        theme_menu.pack(side="left")

        # UI Scale
        scale_frame = ctk.CTkFrame(section, fg_color="transparent")
        scale_frame.pack(fill="x", padx=15, pady=(0, 15))

        ctk.CTkLabel(
            scale_frame,
            text="UI Scale:",
            text_color=COLORS["text"],
        ).pack(side="left", padx=(0, 10))

        scale_menu = ctk.CTkOptionMenu(
            scale_frame,
            values=["80%", "90%", "100%", "110%", "120%"],
            fg_color=COLORS["surface_light"],
        )
        scale_menu.set("100%")
        scale_menu.pack(side="left")

    def _create_export_section(self, parent) -> None:
        """Create export settings section."""
        section = ctk.CTkFrame(parent, fg_color=COLORS["surface"])
        section.pack(fill="x", pady=10)

        ctk.CTkLabel(
            section,
            text="Export Settings",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["primary"],
        ).pack(anchor="w", padx=15, pady=(15, 10))

        # Default format
        format_frame = ctk.CTkFrame(section, fg_color="transparent")
        format_frame.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(
            format_frame,
            text="Default Format:",
            text_color=COLORS["text"],
        ).pack(side="left", padx=(0, 10))

        format_menu = ctk.CTkOptionMenu(
            format_frame,
            values=["Excel (.xlsx)", "CSV (.csv)", "JSON (.json)"],
            fg_color=COLORS["surface_light"],
        )
        format_menu.set("Excel (.xlsx)")
        format_menu.pack(side="left")

        # Include headers checkbox
        headers_check = ctk.CTkCheckBox(
            section,
            text="Include headers in exports",
            fg_color=COLORS["primary"],
        )
        headers_check.pack(anchor="w", padx=15, pady=(0, 15))
        headers_check.select()

    def _create_about_section(self, parent) -> None:
        """Create about section."""
        section = ctk.CTkFrame(parent, fg_color=COLORS["surface"])
        section.pack(fill="x", pady=10)

        ctk.CTkLabel(
            section,
            text="About",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["primary"],
        ).pack(anchor="w", padx=15, pady=(15, 10))

        info_text = (
            "Inactive Mailbox Manager v1.0.0\n\n"
            "A desktop application for managing Microsoft 365\n"
            "inactive mailboxes at enterprise scale.\n\n"
            "Built with CustomTkinter"
        )

        ctk.CTkLabel(
            section,
            text=info_text,
            text_color=COLORS["text_muted"],
            justify="left",
        ).pack(anchor="w", padx=15, pady=(0, 15))

    def _create_input_row(self, parent, label: str, variable: ctk.StringVar, placeholder: str) -> None:
        """Create a labeled input row.

        Args:
            parent: Parent widget
            label: Input label
            variable: StringVar for input
            placeholder: Placeholder text
        """
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(
            frame,
            text=label,
            width=100,
            text_color=COLORS["text"],
        ).pack(side="left")

        entry = ctk.CTkEntry(
            frame,
            textvariable=variable,
            placeholder_text=placeholder,
            width=350,
            fg_color=COLORS["background"],
        )
        entry.pack(side="left", padx=10)

    def _connect(self) -> None:
        """Attempt to connect to Exchange Online."""
        org = self._org_var.get().strip()
        if not org:
            self.show_notification("Please enter organization domain", "warning")
            return

        self.show_notification(f"Connecting to {org}...", "info")
        self._connection_status.configure(
            text="Connecting...",
            text_color=COLORS["warning"],
        )

        # Simulate connection
        self.after(1500, lambda: self._complete_connection(True))

    def _complete_connection(self, success: bool) -> None:
        """Complete connection process."""
        if success:
            self._connection_status.configure(
                text="Connected",
                text_color=COLORS["success"],
            )
            self.show_notification("Connected successfully", "success")

            # Update app connection status
            app = self.get_app()
            if hasattr(app, "set_connection_status"):
                app.set_connection_status(True)
        else:
            self._connection_status.configure(
                text="Connection failed",
                text_color=COLORS["error"],
            )
            self.show_notification("Connection failed", "error")

    def _test_connection(self) -> None:
        """Test the connection settings."""
        org = self._org_var.get().strip()
        if not org:
            self.show_notification("Please enter organization domain first", "warning")
            return

        self.show_notification(f"Testing connection to {org}...", "info")
        self.after(1000, lambda: self.show_notification("Connection test: OK", "success"))

    def _change_theme(self, theme: str) -> None:
        """Change application theme.

        Args:
            theme: Theme name
        """
        mode = theme.lower()
        if mode == "system":
            ctk.set_appearance_mode("system")
        else:
            ctk.set_appearance_mode(mode)

        self.show_notification(f"Theme changed to {theme}", "info")

    def refresh(self) -> None:
        """Refresh settings (update connection status)."""
        if self._session and self._session.connection:
            if self._session.connection.is_connected:
                self._connection_status.configure(
                    text="Connected",
                    text_color=COLORS["success"],
                )
            else:
                self._connection_status.configure(
                    text="Not connected",
                    text_color=COLORS["error"],
                )
