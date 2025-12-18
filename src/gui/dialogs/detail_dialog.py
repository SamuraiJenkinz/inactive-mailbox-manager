"""Mailbox detail dialog showing comprehensive mailbox information."""

from typing import TYPE_CHECKING

import customtkinter as ctk

from src.gui.theme import COLORS, get_button_colors
from src.core.dashboard_service import format_size

if TYPE_CHECKING:
    from src.data.session import SessionManager
    from src.data.models import InactiveMailbox


class MailboxDetailDialog(ctk.CTkToplevel):
    """Dialog showing detailed mailbox information.

    Displays all mailbox properties, hold status,
    recovery eligibility, and provides action buttons.
    """

    def __init__(
        self,
        parent,
        mailbox: "InactiveMailbox",
        session: "SessionManager | None" = None,
    ) -> None:
        """Initialize the detail dialog.

        Args:
            parent: Parent widget
            mailbox: Mailbox to display
            session: Session manager for operations
        """
        super().__init__(parent)

        self._mailbox = mailbox
        self._session = session

        # Configure window
        self.title(f"Mailbox Details - {mailbox.display_name}")
        self.geometry("600x700")
        self.minsize(500, 600)

        # Set colors
        self.configure(fg_color=COLORS["background"])

        self._create_widgets()

        # Center on parent
        self.transient(parent)
        self.update_idletasks()

    def _create_widgets(self) -> None:
        """Create dialog widgets."""
        # Scrollable content
        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)

        # Header
        ctk.CTkLabel(
            content,
            text=self._mailbox.display_name,
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["primary"],
        ).pack(anchor="w", pady=(0, 5))

        ctk.CTkLabel(
            content,
            text=self._mailbox.primary_smtp,
            text_color=COLORS["text_muted"],
        ).pack(anchor="w", pady=(0, 20))

        # Basic Information
        self._create_section(content, "Basic Information", [
            ("Identity", self._mailbox.identity),
            ("UPN", self._mailbox.user_principal_name or "N/A"),
            ("Department", self._mailbox.department or "N/A"),
            ("Company", self._mailbox.operating_company or "N/A"),
        ])

        # Size & Items
        self._create_section(content, "Size & Items", [
            ("Size", format_size(self._mailbox.size_mb)),
            ("Item Count", f"{self._mailbox.item_count:,}"),
            ("Age", f"{self._mailbox.age_days} days"),
            ("Deleted", self._mailbox.when_soft_deleted.strftime("%Y-%m-%d %H:%M") if self._mailbox.when_soft_deleted else "Unknown"),
        ])

        # Hold Status
        hold_items = [
            ("Litigation Hold", "Yes" if self._mailbox.litigation_hold else "No"),
        ]
        if self._mailbox.hold_types:
            hold_items.append(("In-Place Holds", f"{len(self._mailbox.hold_types)} holds"))
            for i, hold in enumerate(self._mailbox.hold_types[:5], 1):
                hold_items.append((f"  Hold {i}", hold[:40]))
        else:
            hold_items.append(("In-Place Holds", "None"))

        self._create_section(content, "Hold Status", hold_items)

        # Archive Information
        self._create_section(content, "Archive Information", [
            ("Archive Status", self._mailbox.archive_status or "None"),
            ("Archive GUID", self._mailbox.archive_guid or "N/A"),
        ])

        # Recovery Status
        recovery_items = [
            ("Eligible", "Yes" if self._mailbox.recovery_eligible else "No"),
        ]
        if self._mailbox.recovery_blockers:
            for blocker in self._mailbox.recovery_blockers:
                recovery_items.append(("Blocker", blocker))

        self._create_section(content, "Recovery Status", recovery_items)

        # License & Cost
        self._create_section(content, "License & Cost", [
            ("License Type", self._mailbox.license_type or "Unknown"),
            ("Monthly Cost", f"${self._mailbox.monthly_cost:.2f}" if self._mailbox.monthly_cost else "N/A"),
        ])

        # Action buttons
        btn_frame = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=60)
        btn_frame.pack(fill="x", side="bottom")
        btn_frame.pack_propagate(False)

        inner_frame = ctk.CTkFrame(btn_frame, fg_color="transparent")
        inner_frame.pack(expand=True)

        recover_btn = ctk.CTkButton(
            inner_frame,
            text="Recover",
            width=100,
            command=self._recover,
            **get_button_colors("primary"),
        )
        recover_btn.pack(side="left", padx=10, pady=15)

        restore_btn = ctk.CTkButton(
            inner_frame,
            text="Restore",
            width=100,
            command=self._restore,
            **get_button_colors(),
        )
        restore_btn.pack(side="left", padx=10, pady=15)

        close_btn = ctk.CTkButton(
            inner_frame,
            text="Close",
            width=100,
            command=self.destroy,
            **get_button_colors(),
        )
        close_btn.pack(side="left", padx=10, pady=15)

    def _create_section(self, parent, title: str, items: list[tuple[str, str]]) -> None:
        """Create a detail section.

        Args:
            parent: Parent widget
            title: Section title
            items: List of (label, value) tuples
        """
        section = ctk.CTkFrame(parent, fg_color=COLORS["surface"])
        section.pack(fill="x", pady=10)

        ctk.CTkLabel(
            section,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["primary"],
        ).pack(anchor="w", padx=15, pady=(15, 10))

        for label, value in items:
            row = ctk.CTkFrame(section, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=2)

            ctk.CTkLabel(
                row,
                text=f"{label}:",
                width=120,
                anchor="w",
                text_color=COLORS["text_muted"],
            ).pack(side="left")

            # Color code certain values
            text_color = COLORS["text"]
            if label == "Litigation Hold" and value == "Yes":
                text_color = COLORS["error"]
            elif label == "Eligible" and value == "No":
                text_color = COLORS["error"]
            elif label == "Eligible" and value == "Yes":
                text_color = COLORS["success"]

            ctk.CTkLabel(
                row,
                text=value,
                anchor="w",
                text_color=text_color,
            ).pack(side="left", fill="x", expand=True)

        # Bottom padding
        ctk.CTkFrame(section, height=10, fg_color="transparent").pack()

    def _recover(self) -> None:
        """Start recovery for this mailbox."""
        self.destroy()
        from src.gui.dialogs.recovery_dialog import RecoveryDialog
        dialog = RecoveryDialog(self.master, self._mailbox, self._session)
        dialog.grab_set()

    def _restore(self) -> None:
        """Start restore for this mailbox."""
        # Show notification (restore wizard not implemented)
        pass
