"""Bulk operations screen for batch mailbox operations."""

from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Label,
    ProgressBar,
    RadioButton,
    RadioSet,
    Static,
)

from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.data.session import SessionManager

logger = get_logger(__name__)


class BulkOperationsScreen(Screen):
    """Screen for bulk mailbox operations.

    Provides interface for CSV import, operation selection,
    batch execution with progress tracking.
    """

    BINDINGS = [
        Binding("escape", "back", "Back", show=True),
        Binding("s", "start", "Start", show=True),
        Binding("p", "pause", "Pause", show=False),
        Binding("c", "cancel_operation", "Cancel", show=False),
    ]

    def __init__(
        self,
        session: "SessionManager | None" = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the bulk operations screen.

        Args:
            session: Session manager for operations
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._session = session
        self._operation_in_progress = False
        self._csv_items: list[dict] = []

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        with Vertical():
            yield Static("[bold]Bulk Operations[/bold]", classes="title")

            # Operation Type Selection
            with Container(classes="panel"):
                yield Static("[bold]Select Operation[/bold]", classes="section-title")
                with RadioSet(id="operation-type"):
                    yield RadioButton("Bulk Recovery", id="op-recovery", value=True)
                    yield RadioButton("Bulk Restore", id="op-restore")
                    yield RadioButton("Bulk Validation", id="op-validate")
                    yield RadioButton("Bulk Export", id="op-export")

            # CSV Import Section
            with Container(classes="panel"):
                yield Static("[bold]Import Data[/bold]", classes="section-title")
                yield Label("CSV File Path:")
                with Horizontal():
                    yield Input(
                        placeholder="C:\\path\\to\\mailboxes.csv",
                        id="csv-path",
                    )
                    yield Button("Browse", id="btn-browse")
                    yield Button("Load", id="btn-load")

                yield Static("", id="csv-status")

            # Preview Section
            with Container(classes="panel"):
                yield Static("[bold]Preview[/bold]", classes="section-title")
                yield DataTable(id="preview-table")
                yield Static("", id="preview-count")

            # Progress Section
            with Container(classes="panel"):
                yield Static("[bold]Progress[/bold]", classes="section-title")
                yield ProgressBar(id="bulk-progress", total=100, show_eta=True)
                yield Static("Ready to start", id="progress-status")

                with Horizontal(id="stats-row"):
                    yield Static("Success: 0", id="stat-success", classes="success")
                    yield Static("Failed: 0", id="stat-failed", classes="error")
                    yield Static("Pending: 0", id="stat-pending")

            # Results Section
            with Container(classes="panel"):
                yield Static("[bold]Results[/bold]", classes="section-title")
                yield DataTable(id="results-table")

            # Action Buttons
            with Horizontal(classes="button-row"):
                yield Button("Start", id="btn-start", variant="primary")
                yield Button("Pause", id="btn-pause", disabled=True)
                yield Button("Cancel", id="btn-cancel-op", disabled=True)
                yield Button("Export Results", id="btn-export", disabled=True)
                yield Button("Back", id="btn-back")

    def on_mount(self) -> None:
        """Handle screen mount."""
        logger.debug("BulkOperationsScreen mounted")

        # Setup preview table
        preview_table = self.query_one("#preview-table", DataTable)
        preview_table.add_columns("Identity", "Display Name", "Status")

        # Setup results table
        results_table = self.query_one("#results-table", DataTable)
        results_table.add_columns("Identity", "Operation", "Result", "Message")

    def _load_csv(self) -> None:
        """Load and validate CSV file."""
        csv_path = self.query_one("#csv-path", Input).value.strip()

        if not csv_path:
            self.app.notify("Please enter a CSV file path", severity="warning")
            return

        path = Path(csv_path)
        if not path.exists():
            self.app.notify(f"File not found: {csv_path}", severity="error")
            self.query_one("#csv-status", Static).update("[error]File not found[/error]")
            return

        try:
            # Read and parse CSV
            import csv

            self._csv_items = []
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self._csv_items.append(row)

            # Update status
            count = len(self._csv_items)
            self.query_one("#csv-status", Static).update(
                f"[success]Loaded {count} items[/success]"
            )

            # Update preview
            self._update_preview()

        except Exception as e:
            logger.error(f"Failed to load CSV: {e}")
            self.app.notify(f"Failed to load CSV: {e}", severity="error")
            self.query_one("#csv-status", Static).update(f"[error]Error: {e}[/error]")

    def _update_preview(self) -> None:
        """Update the preview table with loaded items."""
        table = self.query_one("#preview-table", DataTable)
        table.clear()

        # Show first 10 items
        for i, item in enumerate(self._csv_items[:10]):
            identity = item.get("Identity") or item.get("identity") or item.get("ExchangeGuid", "Unknown")
            display_name = item.get("DisplayName") or item.get("display_name", "Unknown")
            table.add_row(identity[:30], display_name[:30], "Pending")

        # Update count
        total = len(self._csv_items)
        shown = min(10, total)
        self.query_one("#preview-count", Static).update(
            f"Showing {shown} of {total} items"
        )

        # Update pending stat
        self.query_one("#stat-pending", Static).update(f"Pending: {total}")

    def _start_operation(self) -> None:
        """Start the bulk operation."""
        if not self._csv_items:
            self.app.notify("No items loaded. Please load a CSV file first.", severity="warning")
            return

        if self._operation_in_progress:
            self.app.notify("Operation already in progress", severity="warning")
            return

        self._operation_in_progress = True

        # Get selected operation
        radio_set = self.query_one("#operation-type", RadioSet)
        operation = "recovery"
        if radio_set.pressed_button:
            button_id = radio_set.pressed_button.id
            if button_id == "op-restore":
                operation = "restore"
            elif button_id == "op-validate":
                operation = "validate"
            elif button_id == "op-export":
                operation = "export"

        # Update UI
        self.query_one("#btn-start", Button).disabled = True
        self.query_one("#btn-pause", Button).disabled = False
        self.query_one("#btn-cancel-op", Button).disabled = False
        self.query_one("#progress-status", Static).update(f"Running {operation}...")

        # Simulate operation
        self._simulate_bulk_operation(operation)

    def _simulate_bulk_operation(self, operation: str) -> None:
        """Simulate bulk operation for demo.

        Args:
            operation: Operation type
        """
        import asyncio

        async def run_bulk():
            total = len(self._csv_items)
            results_table = self.query_one("#results-table", DataTable)
            results_table.clear()

            success = 0
            failed = 0

            for i, item in enumerate(self._csv_items):
                if not self._operation_in_progress:
                    break

                # Update progress
                progress = int((i + 1) / total * 100)
                self.query_one("#bulk-progress", ProgressBar).update(progress=progress)

                identity = item.get("Identity") or item.get("identity", "Unknown")
                display_name = item.get("DisplayName") or item.get("display_name", "Unknown")

                # Simulate success/failure (90% success rate)
                import random
                if random.random() < 0.9:
                    result = "Success"
                    message = "Completed"
                    success += 1
                else:
                    result = "Failed"
                    message = "Connection error"
                    failed += 1

                results_table.add_row(identity[:30], operation, result, message)

                # Update stats
                pending = total - i - 1
                self.query_one("#stat-success", Static).update(f"Success: {success}")
                self.query_one("#stat-failed", Static).update(f"Failed: {failed}")
                self.query_one("#stat-pending", Static).update(f"Pending: {pending}")

                await asyncio.sleep(0.1)

            # Complete
            self._complete_operation(success, failed)

        self.app.call_later(0.1, lambda: asyncio.create_task(run_bulk()))

    def _complete_operation(self, success: int, failed: int) -> None:
        """Complete the bulk operation.

        Args:
            success: Number of successful items
            failed: Number of failed items
        """
        self._operation_in_progress = False

        # Update UI
        self.query_one("#btn-start", Button).disabled = False
        self.query_one("#btn-pause", Button).disabled = True
        self.query_one("#btn-cancel-op", Button).disabled = True
        self.query_one("#btn-export", Button).disabled = False

        self.query_one("#progress-status", Static).update(
            f"[success]Complete: {success} success, {failed} failed[/success]"
        )

        self.app.notify(
            f"Bulk operation complete: {success} success, {failed} failed",
            severity="information"
        )

    def action_back(self) -> None:
        """Go back to the main screen."""
        if self._operation_in_progress:
            self.app.notify("Please cancel the operation first", severity="warning")
            return
        self.app.pop_screen()

    def action_start(self) -> None:
        """Start the operation."""
        self._start_operation()

    def action_pause(self) -> None:
        """Pause the operation."""
        self._operation_in_progress = False
        self.query_one("#progress-status", Static).update("Paused")
        self.query_one("#btn-pause", Button).disabled = True
        self.query_one("#btn-start", Button).disabled = False
        self.app.notify("Operation paused", timeout=2)

    def action_cancel_operation(self) -> None:
        """Cancel the operation."""
        self._operation_in_progress = False
        self.query_one("#progress-status", Static).update("Cancelled")
        self.query_one("#btn-pause", Button).disabled = True
        self.query_one("#btn-cancel-op", Button).disabled = True
        self.query_one("#btn-start", Button).disabled = False
        self.app.notify("Operation cancelled", timeout=2)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: Button press event
        """
        if event.button.id == "btn-load":
            self._load_csv()
        elif event.button.id == "btn-browse":
            self.app.notify("File browser not implemented - enter path manually", timeout=2)
        elif event.button.id == "btn-start":
            self._start_operation()
        elif event.button.id == "btn-pause":
            self.action_pause()
        elif event.button.id == "btn-cancel-op":
            self.action_cancel_operation()
        elif event.button.id == "btn-export":
            self.app.notify("Exporting results...", timeout=2)
        elif event.button.id == "btn-back":
            self.action_back()
