"""Operation monitoring service for tracking async operations."""

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.data.session import SessionManager

logger = get_logger(__name__)


class OperationStatus(Enum):
    """Status of an async operation."""

    QUEUED = "Queued"
    IN_PROGRESS = "InProgress"
    COMPLETED = "Completed"
    COMPLETED_WITH_WARNINGS = "CompletedWithWarning"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
    SUSPENDED = "Suspended"
    UNKNOWN = "Unknown"

    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal status."""
        return self in [
            OperationStatus.COMPLETED,
            OperationStatus.COMPLETED_WITH_WARNINGS,
            OperationStatus.FAILED,
            OperationStatus.CANCELLED,
        ]

    @property
    def is_successful(self) -> bool:
        """Check if this represents success."""
        return self in [
            OperationStatus.COMPLETED,
            OperationStatus.COMPLETED_WITH_WARNINGS,
        ]


@dataclass
class OperationProgress:
    """Progress information for an operation."""

    operation_id: str
    operation_type: str  # restore, recovery, bulk
    status: OperationStatus = OperationStatus.UNKNOWN
    percent_complete: float = 0.0
    items_processed: int = 0
    items_total: int = 0
    bytes_processed: int = 0
    bytes_total: int = 0
    current_item: str | None = None
    started_at: datetime = field(default_factory=datetime.now)
    estimated_completion: datetime | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)
    raw_data: dict[str, Any] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        """Check if operation is complete."""
        return self.status.is_terminal

    @property
    def is_successful(self) -> bool:
        """Check if operation was successful."""
        return self.status.is_successful

    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        return (datetime.now() - self.started_at).total_seconds()

    @property
    def estimated_remaining_seconds(self) -> float | None:
        """Estimate remaining time based on progress."""
        if self.percent_complete <= 0 or self.is_complete:
            return None

        elapsed = self.elapsed_seconds
        total_estimated = elapsed / (self.percent_complete / 100)
        return total_estimated - elapsed

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for display/logging."""
        return {
            "operation_id": self.operation_id,
            "operation_type": self.operation_type,
            "status": self.status.value,
            "percent_complete": self.percent_complete,
            "items_processed": self.items_processed,
            "items_total": self.items_total,
            "bytes_processed": self.bytes_processed,
            "elapsed_seconds": self.elapsed_seconds,
            "estimated_remaining": self.estimated_remaining_seconds,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
        }


class OperationMonitor:
    """Monitors and tracks async operations.

    Provides centralized operation tracking with progress callbacks
    and status polling.
    """

    def __init__(self, session: "SessionManager") -> None:
        """Initialize operation monitor.

        Args:
            session: Session manager with active connection
        """
        self._session = session
        self._active_operations: dict[str, OperationProgress] = {}
        self._callbacks: dict[str, list[Callable[[OperationProgress], None]]] = {}
        self._polling_threads: dict[str, threading.Thread] = {}
        self._stop_flags: dict[str, threading.Event] = {}

        logger.debug("OperationMonitor initialized")

    def start_monitoring(
        self,
        operation_id: str,
        operation_type: str,
        items_total: int = 0,
        bytes_total: int = 0,
    ) -> OperationProgress:
        """Start monitoring an operation.

        Args:
            operation_id: Unique operation identifier
            operation_type: Type of operation (restore, recovery, bulk)
            items_total: Total items expected
            bytes_total: Total bytes expected

        Returns:
            Initial OperationProgress
        """
        progress = OperationProgress(
            operation_id=operation_id,
            operation_type=operation_type,
            status=OperationStatus.QUEUED,
            items_total=items_total,
            bytes_total=bytes_total,
        )

        self._active_operations[operation_id] = progress
        self._callbacks[operation_id] = []
        self._stop_flags[operation_id] = threading.Event()

        logger.info(f"Started monitoring operation: {operation_id}")
        return progress

    def update_progress(
        self,
        operation_id: str,
        status: OperationStatus | None = None,
        percent_complete: float | None = None,
        items_processed: int | None = None,
        bytes_processed: int | None = None,
        current_item: str | None = None,
        error: str | None = None,
        warning: str | None = None,
        raw_data: dict[str, Any] | None = None,
    ) -> OperationProgress | None:
        """Update progress for an operation.

        Args:
            operation_id: Operation to update
            status: New status
            percent_complete: Percent complete
            items_processed: Items processed
            bytes_processed: Bytes processed
            current_item: Current item being processed
            error: Error message to add
            warning: Warning message to add
            raw_data: Raw data from Exchange

        Returns:
            Updated progress or None if not found
        """
        progress = self._active_operations.get(operation_id)
        if not progress:
            return None

        if status is not None:
            progress.status = status
        if percent_complete is not None:
            progress.percent_complete = percent_complete
        if items_processed is not None:
            progress.items_processed = items_processed
        if bytes_processed is not None:
            progress.bytes_processed = bytes_processed
        if current_item is not None:
            progress.current_item = current_item
        if error:
            progress.errors.append(error)
        if warning:
            progress.warnings.append(warning)
        if raw_data:
            progress.raw_data = raw_data

        progress.last_updated = datetime.now()

        # Estimate completion
        if progress.percent_complete > 0 and not progress.is_complete:
            remaining = progress.estimated_remaining_seconds
            if remaining:
                progress.estimated_completion = datetime.now() + \
                    __import__('datetime').timedelta(seconds=remaining)

        # Notify callbacks
        self._notify_callbacks(operation_id, progress)

        return progress

    def get_progress(self, operation_id: str) -> OperationProgress | None:
        """Get current progress for an operation.

        Args:
            operation_id: Operation identifier

        Returns:
            OperationProgress or None if not found
        """
        return self._active_operations.get(operation_id)

    def add_callback(
        self,
        operation_id: str,
        callback: Callable[[OperationProgress], None],
    ) -> None:
        """Add a progress callback for an operation.

        Args:
            operation_id: Operation to monitor
            callback: Function to call on progress updates
        """
        if operation_id in self._callbacks:
            self._callbacks[operation_id].append(callback)

    def remove_callback(
        self,
        operation_id: str,
        callback: Callable[[OperationProgress], None],
    ) -> None:
        """Remove a progress callback.

        Args:
            operation_id: Operation identifier
            callback: Callback to remove
        """
        if operation_id in self._callbacks:
            try:
                self._callbacks[operation_id].remove(callback)
            except ValueError:
                pass

    def _notify_callbacks(
        self,
        operation_id: str,
        progress: OperationProgress,
    ) -> None:
        """Notify all callbacks for an operation.

        Args:
            operation_id: Operation identifier
            progress: Current progress
        """
        callbacks = self._callbacks.get(operation_id, [])
        for callback in callbacks:
            try:
                callback(progress)
            except Exception as e:
                logger.warning(f"Callback error for {operation_id}: {e}")

    def poll_restore_status(
        self,
        operation_id: str,
        poll_interval: int = 30,
        callback: Callable[[OperationProgress], None] | None = None,
    ) -> None:
        """Start polling for restore request status.

        Args:
            operation_id: Restore request ID
            poll_interval: Seconds between polls
            callback: Optional callback for updates
        """
        if callback:
            self.add_callback(operation_id, callback)

        def poll_thread():
            from src.core.restore_service import RestoreService

            restore_service = RestoreService(self._session)
            stop_flag = self._stop_flags.get(operation_id)

            while stop_flag and not stop_flag.is_set():
                try:
                    result = restore_service.get_restore_status(operation_id)

                    # Map status
                    status_map = {
                        "Queued": OperationStatus.QUEUED,
                        "InProgress": OperationStatus.IN_PROGRESS,
                        "Completed": OperationStatus.COMPLETED,
                        "CompletedWithWarning": OperationStatus.COMPLETED_WITH_WARNINGS,
                        "Failed": OperationStatus.FAILED,
                        "Suspended": OperationStatus.SUSPENDED,
                    }

                    status = status_map.get(result.status, OperationStatus.UNKNOWN)

                    self.update_progress(
                        operation_id,
                        status=status,
                        percent_complete=result.percent_complete,
                        items_processed=result.items_copied,
                        bytes_processed=result.bytes_copied,
                        raw_data=result.raw_output,
                    )

                    progress = self.get_progress(operation_id)
                    if progress and progress.is_complete:
                        break

                except Exception as e:
                    logger.warning(f"Poll error for {operation_id}: {e}")

                time.sleep(poll_interval)

        thread = threading.Thread(target=poll_thread, daemon=True)
        self._polling_threads[operation_id] = thread
        thread.start()

    def stop_monitoring(self, operation_id: str) -> None:
        """Stop monitoring an operation.

        Args:
            operation_id: Operation to stop monitoring
        """
        # Signal thread to stop
        if operation_id in self._stop_flags:
            self._stop_flags[operation_id].set()

        # Wait for thread to finish
        if operation_id in self._polling_threads:
            thread = self._polling_threads[operation_id]
            if thread.is_alive():
                thread.join(timeout=5)

        # Clean up
        self._active_operations.pop(operation_id, None)
        self._callbacks.pop(operation_id, None)
        self._stop_flags.pop(operation_id, None)
        self._polling_threads.pop(operation_id, None)

        logger.info(f"Stopped monitoring operation: {operation_id}")

    def get_active_operations(self) -> list[OperationProgress]:
        """Get all active operations.

        Returns:
            List of active operation progress
        """
        return [
            progress for progress in self._active_operations.values()
            if not progress.is_complete
        ]

    def get_all_operations(self) -> list[OperationProgress]:
        """Get all tracked operations.

        Returns:
            List of all operation progress
        """
        return list(self._active_operations.values())

    def cleanup_completed(self) -> int:
        """Remove completed operations from tracking.

        Returns:
            Number of operations cleaned up
        """
        completed = [
            op_id for op_id, progress in self._active_operations.items()
            if progress.is_complete
        ]

        for op_id in completed:
            self.stop_monitoring(op_id)

        return len(completed)
