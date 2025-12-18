"""Bulk operations frame for batch mailbox operations."""

from pathlib import Path
from typing import TYPE_CHECKING

import customtkinter as ctk
from tkinter import ttk, filedialog

from src.gui.frames.base_frame import BaseFrame
from src.gui.theme import COLORS, get_button_colors
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.data.session import SessionManager

logger = get_logger(__name__)


class BulkFrame(BaseFrame):
    """Frame for bulk mailbox operations.

    Provides interface for CSV import, operation selection,
    and batch execution with progress tracking.
    """

    def __init__(
        self,
        master,
        session: "SessionManager | None" = None,
        **kwargs,
    ) -> None:
        """Initialize the bulk operations frame.

        Args:
            master: Parent widget
            session: Session manager for data access
            **kwargs: Additional frame arguments
        """
        super().__init__(master, session, **kwargs)

        self._csv_items: list[dict] = []
        self._operation_var = ctk.StringVar(value="recovery")
        self._csv_path_var = ctk.StringVar()

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create frame widgets."""
        # Configure grid
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Title
        title = ctk.CTkLabel(
            self,
            text="Bulk Operations",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=COLORS["primary"],
        )
        title.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))

        # Operation selection
        self._create_operation_section()

        # CSV import section
        self._create_import_section()

        # Preview and results
        self._create_preview_section()

        # Progress and controls
        self._create_progress_section()

    def _create_operation_section(self) -> None:
        """Create operation type selection."""
        op_frame = ctk.CTkFrame(self, fg_color=COLORS["surface"])
        op_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)

        ctk.CTkLabel(
            op_frame,
            text="Select Operation:",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"],
        ).pack(anchor="w", padx=15, pady=(15, 10))

        options_frame = ctk.CTkFrame(op_frame, fg_color="transparent")
        options_frame.pack(fill="x", padx=15, pady=(0, 15))

        operations = [
            ("recovery", "Bulk Recovery"),
            ("restore", "Bulk Restore"),
            ("validate", "Bulk Validation"),
            ("export", "Bulk Export"),
        ]

        for value, text in operations:
            rb = ctk.CTkRadioButton(
                options_frame,
                text=text,
                variable=self._operation_var,
                value=value,
                fg_color=COLORS["primary"],
            )
            rb.pack(side="left", padx=20)

    def _create_import_section(self) -> None:
        """Create CSV import section."""
        import_frame = ctk.CTkFrame(self, fg_color=COLORS["surface"])
        import_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=10)

        ctk.CTkLabel(
            import_frame,
            text="Import Data:",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"],
        ).pack(anchor="w", padx=15, pady=(15, 10))

        path_frame = ctk.CTkFrame(import_frame, fg_color="transparent")
        path_frame.pack(fill="x", padx=15, pady=(0, 15))

        self._path_entry = ctk.CTkEntry(
            path_frame,
            textvariable=self._csv_path_var,
            placeholder_text="Select CSV file...",
            width=400,
            fg_color=COLORS["background"],
        )
        self._path_entry.pack(side="left", padx=(0, 10))

        browse_btn = ctk.CTkButton(
            path_frame,
            text="Browse",
            width=80,
            command=self._browse_file,
            **get_button_colors(),
        )
        browse_btn.pack(side="left", padx=5)

        load_btn = ctk.CTkButton(
            path_frame,
            text="Load",
            width=80,
            command=self._load_csv,
            **get_button_colors("primary"),
        )
        load_btn.pack(side="left", padx=5)

        self._import_status = ctk.CTkLabel(
            import_frame,
            text="No file loaded",
            text_color=COLORS["text_muted"],
        )
        self._import_status.pack(anchor="w", padx=15, pady=(0, 10))

    def _create_preview_section(self) -> None:
        """Create preview and results section."""
        preview_frame = ctk.CTkFrame(self, fg_color=COLORS["surface"])
        preview_frame.grid(row=3, column=0, sticky="nsew", padx=20, pady=10)
        preview_frame.grid_rowconfigure(1, weight=1)
        preview_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            preview_frame,
            text="Preview:",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"],
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(15, 10))

        # Style treeview
        style = ttk.Style()
        style.configure(
            "Bulk.Treeview",
            background=COLORS["background"],
            foreground=COLORS["text"],
            fieldbackground=COLORS["background"],
        )

        # Create treeview
        columns = ("identity", "name", "status")
        self._preview_tree = ttk.Treeview(
            preview_frame,
            columns=columns,
            show="headings",
            style="Bulk.Treeview",
        )

        self._preview_tree.heading("identity", text="Identity")
        self._preview_tree.heading("name", text="Display Name")
        self._preview_tree.heading("status", text="Status")

        self._preview_tree.column("identity", width=200)
        self._preview_tree.column("name", width=250)
        self._preview_tree.column("status", width=100)

        self._preview_tree.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))

    def _create_progress_section(self) -> None:
        """Create progress and control section."""
        progress_frame = ctk.CTkFrame(self, fg_color=COLORS["surface"])
        progress_frame.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 20))

        # Progress bar
        self._progress_bar = ctk.CTkProgressBar(
            progress_frame,
            fg_color=COLORS["background"],
            progress_color=COLORS["primary"],
        )
        self._progress_bar.pack(fill="x", padx=15, pady=15)
        self._progress_bar.set(0)

        # Stats and controls
        controls_frame = ctk.CTkFrame(progress_frame, fg_color="transparent")
        controls_frame.pack(fill="x", padx=15, pady=(0, 15))

        self._stats_label = ctk.CTkLabel(
            controls_frame,
            text="Ready to start",
            text_color=COLORS["text_muted"],
        )
        self._stats_label.pack(side="left")

        # Control buttons
        self._cancel_btn = ctk.CTkButton(
            controls_frame,
            text="Cancel",
            width=80,
            state="disabled",
            command=self._cancel_operation,
            **get_button_colors("danger"),
        )
        self._cancel_btn.pack(side="right", padx=5)

        self._start_btn = ctk.CTkButton(
            controls_frame,
            text="Start",
            width=80,
            command=self._start_operation,
            **get_button_colors("primary"),
        )
        self._start_btn.pack(side="right", padx=5)

    def _browse_file(self) -> None:
        """Open file browser for CSV selection."""
        filename = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if filename:
            self._csv_path_var.set(filename)

    def _load_csv(self) -> None:
        """Load and parse the CSV file."""
        csv_path = self._csv_path_var.get().strip()

        if not csv_path:
            self.show_notification("Please select a CSV file", "warning")
            return

        path = Path(csv_path)
        if not path.exists():
            self.show_notification(f"File not found: {csv_path}", "error")
            self._import_status.configure(text="File not found", text_color=COLORS["error"])
            return

        try:
            import csv

            self._csv_items = []
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self._csv_items.append(row)

            count = len(self._csv_items)
            self._import_status.configure(
                text=f"Loaded {count} items",
                text_color=COLORS["success"],
            )
            self._update_preview()

        except Exception as e:
            logger.error(f"Failed to load CSV: {e}")
            self.show_notification(f"Failed to load CSV: {e}", "error")
            self._import_status.configure(text=f"Error: {e}", text_color=COLORS["error"])

    def _update_preview(self) -> None:
        """Update the preview treeview."""
        # Clear existing
        for item in self._preview_tree.get_children():
            self._preview_tree.delete(item)

        # Add items (first 20)
        for item in self._csv_items[:20]:
            identity = item.get("Identity") or item.get("identity") or item.get("ExchangeGuid", "Unknown")
            name = item.get("DisplayName") or item.get("display_name", "Unknown")
            self._preview_tree.insert("", "end", values=(identity[:30], name[:30], "Pending"))

        self._stats_label.configure(text=f"{len(self._csv_items)} items ready")

    def _start_operation(self) -> None:
        """Start the bulk operation."""
        if not self._csv_items:
            self.show_notification("Please load a CSV file first", "warning")
            return

        operation = self._operation_var.get()
        self._start_btn.configure(state="disabled")
        self._cancel_btn.configure(state="normal")

        self.show_notification(f"Starting bulk {operation}...", "info")
        self._stats_label.configure(text=f"Running {operation}...")

        # Simulate progress
        self._simulate_progress()

    def _simulate_progress(self) -> None:
        """Simulate operation progress."""
        total = len(self._csv_items)
        current = [0]

        def update():
            current[0] += 1
            progress = current[0] / total
            self._progress_bar.set(progress)
            self._stats_label.configure(text=f"Processing {current[0]}/{total}")

            if current[0] < total:
                self.after(50, update)
            else:
                self._complete_operation()

        self.after(100, update)

    def _complete_operation(self) -> None:
        """Complete the operation."""
        self._start_btn.configure(state="normal")
        self._cancel_btn.configure(state="disabled")
        self._stats_label.configure(text="Operation complete")
        self.show_notification("Bulk operation completed", "success")

    def _cancel_operation(self) -> None:
        """Cancel the operation."""
        self._start_btn.configure(state="normal")
        self._cancel_btn.configure(state="disabled")
        self._stats_label.configure(text="Cancelled")
        self.show_notification("Operation cancelled", "warning")

    def refresh(self) -> None:
        """Refresh frame (no-op for bulk)."""
        pass
