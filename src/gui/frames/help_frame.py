"""Help frame showing documentation and keyboard shortcuts."""

from typing import TYPE_CHECKING

import customtkinter as ctk

from src.gui.frames.base_frame import BaseFrame
from src.gui.theme import COLORS

if TYPE_CHECKING:
    from src.data.session import SessionManager


class HelpFrame(BaseFrame):
    """Help frame with documentation and shortcuts reference.

    Displays keyboard shortcuts, feature overview,
    and support information.
    """

    def __init__(
        self,
        master,
        session: "SessionManager | None" = None,
        **kwargs,
    ) -> None:
        """Initialize the help frame.

        Args:
            master: Parent widget
            session: Session manager (unused)
            **kwargs: Additional frame arguments
        """
        super().__init__(master, session, **kwargs)
        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create help widgets."""
        # Scrollable content
        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        ctk.CTkLabel(
            content,
            text="Help & Documentation",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=COLORS["primary"],
        ).pack(anchor="w", pady=(0, 20))

        # Quick Start
        self._create_section(content, "Quick Start", [
            "1. Click 'Settings' in the sidebar to configure connection",
            "2. Enter your organization domain and connect",
            "3. Navigate to 'Mailboxes' to view inactive mailboxes",
            "4. Double-click a mailbox to view details",
            "5. Use 'Bulk Operations' for batch processing",
        ])

        # Navigation
        self._create_section(content, "Navigation", [
            "Mailboxes - Main mailbox list view",
            "Dashboard - Overview metrics and statistics",
            "Bulk Operations - Batch processing with CSV import",
            "Settings - Connection and preferences",
            "Help - This documentation",
        ])

        # Features
        self._create_section(content, "Features", [
            "View all inactive mailboxes in your organization",
            "Search and filter mailboxes by name or email",
            "View detailed mailbox information and hold status",
            "Recover mailboxes to new accounts",
            "Restore content to existing mailboxes",
            "Bulk operations via CSV import",
            "Cost analysis and reporting",
            "Export data in multiple formats",
        ])

        # Tips
        self._create_section(content, "Tips", [
            "Use the search bar to quickly find mailboxes",
            "Double-click a row to view mailbox details",
            "Check hold status before attempting recovery",
            "Export data regularly for compliance records",
            "Use bulk operations for large-scale tasks",
        ])

        # Support
        self._create_section(content, "Support & Resources", [
            "Documentation: See README.md in project root",
            "Microsoft Docs: docs.microsoft.com/exchange",
            "Admin Center: admin.microsoft.com",
            "Purview Portal: compliance.microsoft.com",
        ])

        # Version info
        version_frame = ctk.CTkFrame(content, fg_color=COLORS["surface"])
        version_frame.pack(fill="x", pady=20)

        ctk.CTkLabel(
            version_frame,
            text="Inactive Mailbox Manager",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["primary"],
        ).pack(anchor="w", padx=15, pady=(15, 5))

        ctk.CTkLabel(
            version_frame,
            text="Version 1.0.0\nDesktop GUI built with CustomTkinter",
            text_color=COLORS["text_muted"],
            justify="left",
        ).pack(anchor="w", padx=15, pady=(0, 15))

    def _create_section(self, parent, title: str, items: list[str]) -> None:
        """Create a help section.

        Args:
            parent: Parent widget
            title: Section title
            items: List of help items
        """
        section = ctk.CTkFrame(parent, fg_color=COLORS["surface"])
        section.pack(fill="x", pady=10)

        ctk.CTkLabel(
            section,
            text=title,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["primary"],
        ).pack(anchor="w", padx=15, pady=(15, 10))

        for item in items:
            ctk.CTkLabel(
                section,
                text=f"  • {item}",
                text_color=COLORS["text"],
                justify="left",
            ).pack(anchor="w", padx=15, pady=2)

        # Bottom padding
        ctk.CTkFrame(section, height=10, fg_color="transparent").pack()

    def refresh(self) -> None:
        """Refresh (no-op for help)."""
        pass
