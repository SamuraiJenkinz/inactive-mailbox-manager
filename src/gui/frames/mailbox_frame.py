"""Mailbox list frame showing all inactive mailboxes."""

from typing import TYPE_CHECKING

import customtkinter as ctk
from tkinter import ttk

from src.gui.frames.base_frame import BaseFrame
from src.gui.theme import COLORS, get_button_colors
from src.core.dashboard_service import format_size
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.data.session import SessionManager
    from src.data.models import InactiveMailbox

logger = get_logger(__name__)


class MailboxFrame(BaseFrame):
    """Frame displaying the mailbox list with search and actions.

    Main view showing all inactive mailboxes in a treeview
    with search, filtering, and quick actions.
    """

    def __init__(
        self,
        master,
        session: "SessionManager | None" = None,
        **kwargs,
    ) -> None:
        """Initialize the mailbox frame.

        Args:
            master: Parent widget
            session: Session manager for data access
            **kwargs: Additional frame arguments
        """
        super().__init__(master, session, **kwargs)

        self._mailboxes: list["InactiveMailbox"] = []
        self._filtered_mailboxes: list["InactiveMailbox"] = []
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", self._on_search_changed)

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create frame widgets."""
        # Configure grid
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header with search and actions
        self._create_header()

        # Mailbox treeview
        self._create_treeview()

        # Footer with stats
        self._create_footer()

    def _create_header(self) -> None:
        """Create the header section with search and actions."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        header.grid_columnconfigure(1, weight=1)

        # Title
        title = ctk.CTkLabel(
            header,
            text="Inactive Mailboxes",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=COLORS["primary"],
        )
        title.grid(row=0, column=0, sticky="w")

        # Search entry
        search_frame = ctk.CTkFrame(header, fg_color="transparent")
        search_frame.grid(row=0, column=1, sticky="e", padx=20)

        search_label = ctk.CTkLabel(
            search_frame,
            text="Search:",
            text_color=COLORS["text_muted"],
        )
        search_label.pack(side="left", padx=(0, 5))

        self._search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=self._search_var,
            width=250,
            placeholder_text="Filter by name or email...",
            fg_color=COLORS["surface"],
            border_color=COLORS["surface_light"],
        )
        self._search_entry.pack(side="left")

        # Action buttons
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.grid(row=0, column=2, sticky="e")

        refresh_btn = ctk.CTkButton(
            btn_frame,
            text="Refresh",
            width=80,
            command=self.refresh,
            **get_button_colors(),
        )
        refresh_btn.pack(side="left", padx=5)

        export_btn = ctk.CTkButton(
            btn_frame,
            text="Export",
            width=80,
            command=self._export_data,
            **get_button_colors(),
        )
        export_btn.pack(side="left", padx=5)

    def _create_treeview(self) -> None:
        """Create the mailbox treeview."""
        # Container for treeview and scrollbar
        tree_container = ctk.CTkFrame(self, fg_color=COLORS["surface"])
        tree_container.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

        # Style the treeview
        style = ttk.Style()
        style.theme_use("clam")

        # Configure treeview colors
        style.configure(
            "Treeview",
            background=COLORS["background"],
            foreground=COLORS["text"],
            fieldbackground=COLORS["background"],
            rowheight=30,
        )
        style.configure(
            "Treeview.Heading",
            background=COLORS["surface"],
            foreground=COLORS["primary"],
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "Treeview",
            background=[("selected", COLORS["primary_dim"])],
            foreground=[("selected", COLORS["background"])],
        )

        # Create treeview
        columns = ("name", "email", "size", "items", "holds", "deleted")
        self._tree = ttk.Treeview(
            tree_container,
            columns=columns,
            show="headings",
            selectmode="browse",
        )

        # Configure columns
        self._tree.heading("name", text="Display Name")
        self._tree.heading("email", text="Primary SMTP")
        self._tree.heading("size", text="Size")
        self._tree.heading("items", text="Items")
        self._tree.heading("holds", text="Hold Status")
        self._tree.heading("deleted", text="Deleted")

        self._tree.column("name", width=200, minwidth=150)
        self._tree.column("email", width=250, minwidth=200)
        self._tree.column("size", width=100, minwidth=80)
        self._tree.column("items", width=80, minwidth=60)
        self._tree.column("holds", width=120, minwidth=100)
        self._tree.column("deleted", width=100, minwidth=80)

        # Scrollbar
        scrollbar = ttk.Scrollbar(
            tree_container,
            orient="vertical",
            command=self._tree.yview,
        )
        self._tree.configure(yscrollcommand=scrollbar.set)

        # Grid
        self._tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Bind events
        self._tree.bind("<Double-1>", self._on_double_click)
        self._tree.bind("<Return>", self._on_double_click)

    def _create_footer(self) -> None:
        """Create the footer with stats and quick actions."""
        footer = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=50)
        footer.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))

        # Stats
        self._stats_label = ctk.CTkLabel(
            footer,
            text="0 mailboxes",
            text_color=COLORS["text_muted"],
        )
        self._stats_label.pack(side="left", padx=20, pady=10)

        # Quick action buttons
        action_frame = ctk.CTkFrame(footer, fg_color="transparent")
        action_frame.pack(side="right", padx=10)

        recover_btn = ctk.CTkButton(
            action_frame,
            text="Recover Selected",
            width=120,
            command=self._recover_selected,
            **get_button_colors("primary"),
        )
        recover_btn.pack(side="left", padx=5, pady=10)

        details_btn = ctk.CTkButton(
            action_frame,
            text="View Details",
            width=100,
            command=self._view_details,
            **get_button_colors(),
        )
        details_btn.pack(side="left", padx=5, pady=10)

    def refresh(self) -> None:
        """Refresh mailbox data."""
        logger.debug("Refreshing mailbox list")

        if not self._session:
            self._mailboxes = []
            self._update_stats("No session - connect to load data")
            return

        try:
            self._mailboxes = self._session.db.get_all_mailboxes()
            self._filter_mailboxes()
            self._update_stats(f"Loaded {len(self._mailboxes)} mailboxes")
            self.set_status(f"Loaded {len(self._mailboxes)} mailboxes")
        except Exception as e:
            logger.error(f"Failed to load mailboxes: {e}")
            self.show_notification(f"Error loading mailboxes: {e}", "error")

    def _filter_mailboxes(self) -> None:
        """Filter mailboxes based on search query."""
        query = self._search_var.get().lower()

        if not query:
            self._filtered_mailboxes = self._mailboxes.copy()
        else:
            self._filtered_mailboxes = [
                m for m in self._mailboxes
                if query in m.display_name.lower()
                or query in m.primary_smtp.lower()
                or query in m.identity.lower()
            ]

        self._populate_tree()

    def _populate_tree(self) -> None:
        """Populate the treeview with filtered mailboxes."""
        # Clear existing items
        for item in self._tree.get_children():
            self._tree.delete(item)

        # Add filtered items
        for mailbox in self._filtered_mailboxes:
            # Format hold status
            holds = []
            if mailbox.litigation_hold:
                holds.append("Litigation")
            if mailbox.hold_types:
                holds.append(f"{len(mailbox.hold_types)} holds")
            hold_status = ", ".join(holds) if holds else "None"

            # Format deleted date
            deleted_date = ""
            if mailbox.when_soft_deleted:
                deleted_date = mailbox.when_soft_deleted.strftime("%Y-%m-%d")

            self._tree.insert(
                "",
                "end",
                iid=mailbox.identity,
                values=(
                    mailbox.display_name[:40],
                    mailbox.primary_smtp[:35],
                    format_size(mailbox.size_mb),
                    f"{mailbox.item_count:,}",
                    hold_status,
                    deleted_date,
                ),
            )

        # Update stats
        total = len(self._mailboxes)
        filtered = len(self._filtered_mailboxes)
        if self._search_var.get():
            self._update_stats(f"Showing {filtered} of {total} mailboxes")
        else:
            self._update_stats(f"{total} mailboxes")

    def _update_stats(self, text: str) -> None:
        """Update the stats label.

        Args:
            text: Stats text to display
        """
        self._stats_label.configure(text=text)

    def _on_search_changed(self, *args) -> None:
        """Handle search input changes."""
        self._filter_mailboxes()

    def _on_double_click(self, event) -> None:
        """Handle double-click on a row."""
        self._view_details()

    def _get_selected_mailbox(self) -> "InactiveMailbox | None":
        """Get the currently selected mailbox.

        Returns:
            Selected mailbox or None
        """
        selection = self._tree.selection()
        if not selection:
            return None

        identity = selection[0]
        for mailbox in self._mailboxes:
            if mailbox.identity == identity:
                return mailbox
        return None

    def _view_details(self) -> None:
        """View details for the selected mailbox."""
        mailbox = self._get_selected_mailbox()
        if not mailbox:
            self.show_notification("Please select a mailbox first", "warning")
            return

        # Show detail dialog
        from src.gui.dialogs.detail_dialog import MailboxDetailDialog
        dialog = MailboxDetailDialog(self, mailbox, self._session)
        dialog.grab_set()

    def _recover_selected(self) -> None:
        """Start recovery for the selected mailbox."""
        mailbox = self._get_selected_mailbox()
        if not mailbox:
            self.show_notification("Please select a mailbox first", "warning")
            return

        # Show recovery wizard
        from src.gui.dialogs.recovery_dialog import RecoveryDialog
        dialog = RecoveryDialog(self, mailbox, self._session)
        dialog.grab_set()

    def _export_data(self) -> None:
        """Export mailbox data."""
        self.show_notification("Export functionality - use Bulk Operations", "info")
