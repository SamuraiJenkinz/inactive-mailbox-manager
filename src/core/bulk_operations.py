"""Bulk operations manager for batch processing of mailbox operations."""

import csv
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from src.core.recovery_service import RecoveryRequest, RecoveryService
from src.core.recovery_validator import RecoveryValidator
from src.core.restore_service import RestoreRequest, RestoreService
from src.data.audit_logger import OperationType
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.data.session import SessionManager

logger = get_logger(__name__)


class BulkOperationType(Enum):
    """Types of bulk operations."""

    RECOVERY = "recovery"
    RESTORE = "restore"
    VALIDATE = "validate"
    EXPORT = "export"


class BulkItemStatus(Enum):
    """Status of a bulk operation item."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class BulkOperationItem:
    """Individual item in a bulk operation."""

    row_number: int
    source_identity: str
    target_identity: str | None = None
    additional_data: dict[str, Any] = field(default_factory=dict)
    status: BulkItemStatus = BulkItemStatus.PENDING
    result: Any | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def duration_seconds(self) -> float:
        """Get item operation duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for CSV export."""
        return {
            "row_number": self.row_number,
            "source_identity": self.source_identity,
            "target_identity": self.target_identity or "",
            "status": self.status.value,
            "error": self.error or "",
            "started_at": self.started_at.isoformat() if self.started_at else "",
            "completed_at": self.completed_at.isoformat() if self.completed_at else "",
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class BulkOperationResult:
    """Result of a bulk operation."""

    operation_id: str
    operation_type: BulkOperationType
    total_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    skipped_items: int = 0
    items: list[BulkOperationItem] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    cancelled: bool = False

    @property
    def pending_items(self) -> int:
        """Get count of pending items."""
        return self.total_items - self.completed_items - self.failed_items - self.skipped_items

    @property
    def duration_seconds(self) -> float:
        """Get total operation duration."""
        end_time = self.completed_at or datetime.now()
        return (end_time - self.started_at).total_seconds()

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_items == 0:
            return 0.0
        processed = self.completed_items + self.failed_items
        if processed == 0:
            return 0.0
        return (self.completed_items / processed) * 100

    @property
    def is_complete(self) -> bool:
        """Check if operation is finished."""
        return self.completed_at is not None

    @property
    def progress_percent(self) -> float:
        """Get progress as percentage."""
        if self.total_items == 0:
            return 0.0
        processed = self.completed_items + self.failed_items + self.skipped_items
        return (processed / self.total_items) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/display."""
        return {
            "operation_id": self.operation_id,
            "operation_type": self.operation_type.value,
            "total_items": self.total_items,
            "completed_items": self.completed_items,
            "failed_items": self.failed_items,
            "skipped_items": self.skipped_items,
            "success_rate": f"{self.success_rate:.1f}%",
            "duration_seconds": self.duration_seconds,
            "progress_percent": f"{self.progress_percent:.1f}%",
        }


@dataclass
class BulkOperationConfig:
    """Configuration for bulk operations."""

    batch_size: int = 10
    parallel_execution: bool = False
    stop_on_error: bool = False
    retry_failed: bool = True
    max_retries: int = 3
    delay_between_batches: float = 1.0
    delay_between_items: float = 0.5


# CSV column mappings
RECOVERY_COLUMNS = {
    "source_guid": "source_identity",
    "source_identity": "source_identity",
    "target_upn": "target_identity",
    "target_smtp": "target_smtp",
    "display_name": "display_name",
    "first_name": "first_name",
    "last_name": "last_name",
    "department": "department",
    "company": "company",
}

RECOVERY_REQUIRED = ["source_guid", "target_upn", "display_name"]

RESTORE_COLUMNS = {
    "source_guid": "source_identity",
    "source_identity": "source_identity",
    "target_mailbox": "target_identity",
    "target_folder": "target_folder",
    "conflict_resolution": "conflict_resolution",
}

RESTORE_REQUIRED = ["source_guid", "target_mailbox"]

RESULTS_COLUMNS = [
    "row_number",
    "source_identity",
    "target_identity",
    "status",
    "error",
    "started_at",
    "completed_at",
    "duration_seconds",
]


class BulkCSVError(Exception):
    """Raised when CSV processing fails."""

    pass


class BulkCSVHandler:
    """Handles CSV import/export for bulk operations."""

    # Regex patterns for validation
    GUID_PATTERN = re.compile(
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    )
    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

    def __init__(self) -> None:
        """Initialize CSV handler."""
        logger.debug("BulkCSVHandler initialized")

    def import_recovery_csv(self, path: Path) -> list[BulkOperationItem]:
        """Import recovery operations from CSV.

        Args:
            path: Path to CSV file

        Returns:
            List of BulkOperationItem objects

        Raises:
            BulkCSVError: If CSV is invalid
        """
        errors = self.validate_csv_format(path, BulkOperationType.RECOVERY)
        if errors:
            raise BulkCSVError(f"CSV validation failed: {'; '.join(errors)}")

        items = []

        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is 1)
                # Map CSV columns to internal names
                source = row.get("source_guid") or row.get("source_identity", "")
                target = row.get("target_upn", "")

                additional = {
                    "target_smtp": row.get("target_smtp") or target,
                    "display_name": row.get("display_name", ""),
                    "first_name": row.get("first_name", ""),
                    "last_name": row.get("last_name", ""),
                    "department": row.get("department", ""),
                    "company": row.get("company", ""),
                }

                item = BulkOperationItem(
                    row_number=row_num,
                    source_identity=source.strip(),
                    target_identity=target.strip(),
                    additional_data=additional,
                )
                items.append(item)

        logger.info(f"Imported {len(items)} recovery items from {path}")
        return items

    def import_restore_csv(self, path: Path) -> list[BulkOperationItem]:
        """Import restore operations from CSV.

        Args:
            path: Path to CSV file

        Returns:
            List of BulkOperationItem objects

        Raises:
            BulkCSVError: If CSV is invalid
        """
        errors = self.validate_csv_format(path, BulkOperationType.RESTORE)
        if errors:
            raise BulkCSVError(f"CSV validation failed: {'; '.join(errors)}")

        items = []

        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            for row_num, row in enumerate(reader, start=2):
                source = row.get("source_guid") or row.get("source_identity", "")
                target = row.get("target_mailbox", "")

                additional = {
                    "target_folder": row.get("target_folder", ""),
                    "conflict_resolution": row.get("conflict_resolution", "KeepAll"),
                }

                item = BulkOperationItem(
                    row_number=row_num,
                    source_identity=source.strip(),
                    target_identity=target.strip(),
                    additional_data=additional,
                )
                items.append(item)

        logger.info(f"Imported {len(items)} restore items from {path}")
        return items

    def export_results_csv(
        self,
        result: BulkOperationResult,
        path: Path,
    ) -> None:
        """Export bulk operation results to CSV.

        Args:
            result: Bulk operation result
            path: Output path for CSV
        """
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=RESULTS_COLUMNS)
            writer.writeheader()

            for item in result.items:
                writer.writerow(item.to_dict())

        logger.info(f"Exported {len(result.items)} results to {path}")

    def validate_csv_format(
        self,
        path: Path,
        operation_type: BulkOperationType,
    ) -> list[str]:
        """Validate CSV format for operation type.

        Args:
            path: Path to CSV file
            operation_type: Type of operation

        Returns:
            List of validation error messages (empty if valid)
        """
        errors: list[str] = []

        if not path.exists():
            errors.append(f"File not found: {path}")
            return errors

        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []

                # Check required columns
                if operation_type == BulkOperationType.RECOVERY:
                    required = RECOVERY_REQUIRED
                    has_source = "source_guid" in headers or "source_identity" in headers
                    if not has_source:
                        errors.append("Missing required column: source_guid or source_identity")
                    if "target_upn" not in headers:
                        errors.append("Missing required column: target_upn")
                    if "display_name" not in headers:
                        errors.append("Missing required column: display_name")

                elif operation_type == BulkOperationType.RESTORE:
                    has_source = "source_guid" in headers or "source_identity" in headers
                    if not has_source:
                        errors.append("Missing required column: source_guid or source_identity")
                    if "target_mailbox" not in headers:
                        errors.append("Missing required column: target_mailbox")

                # Validate row data
                seen_sources: set[str] = set()
                for row_num, row in enumerate(reader, start=2):
                    source = row.get("source_guid") or row.get("source_identity", "")

                    # Check for empty source
                    if not source.strip():
                        errors.append(f"Row {row_num}: Empty source identity")
                        continue

                    # Check for duplicate sources
                    if source in seen_sources:
                        errors.append(f"Row {row_num}: Duplicate source '{source}'")
                    seen_sources.add(source)

                    # Validate GUID format if it looks like a GUID
                    if "-" in source and not self.GUID_PATTERN.match(source):
                        errors.append(f"Row {row_num}: Invalid GUID format '{source}'")

                    # Validate email formats
                    if operation_type == BulkOperationType.RECOVERY:
                        target_upn = row.get("target_upn", "")
                        if target_upn and not self.EMAIL_PATTERN.match(target_upn):
                            errors.append(f"Row {row_num}: Invalid email format '{target_upn}'")

        except csv.Error as e:
            errors.append(f"CSV parsing error: {e}")
        except UnicodeDecodeError as e:
            errors.append(f"File encoding error: {e}")

        return errors

    def generate_template(
        self,
        operation_type: BulkOperationType,
        path: Path,
    ) -> None:
        """Generate a CSV template for bulk operations.

        Args:
            operation_type: Type of operation
            path: Output path for template
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        if operation_type == BulkOperationType.RECOVERY:
            headers = [
                "source_guid",
                "target_upn",
                "target_smtp",
                "display_name",
                "first_name",
                "last_name",
                "department",
                "company",
            ]
            example = {
                "source_guid": "12345678-1234-1234-1234-123456789abc",
                "target_upn": "john.doe@contoso.com",
                "target_smtp": "john.doe@contoso.com",
                "display_name": "John Doe",
                "first_name": "John",
                "last_name": "Doe",
                "department": "IT",
                "company": "Contoso",
            }

        elif operation_type == BulkOperationType.RESTORE:
            headers = [
                "source_guid",
                "target_mailbox",
                "target_folder",
                "conflict_resolution",
            ]
            example = {
                "source_guid": "12345678-1234-1234-1234-123456789abc",
                "target_mailbox": "jane.doe@contoso.com",
                "target_folder": "Restored-2024-01",
                "conflict_resolution": "KeepAll",
            }

        else:
            headers = ["source_guid"]
            example = {"source_guid": "12345678-1234-1234-1234-123456789abc"}

        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerow(example)

        logger.info(f"Generated {operation_type.value} template at {path}")


class BulkOperationError(Exception):
    """Raised when bulk operation fails."""

    pass


class BulkOperationManager:
    """Manages execution of bulk mailbox operations.

    Handles batch processing with progress tracking, error handling,
    and audit logging for bulk recovery and restore operations.
    """

    def __init__(
        self,
        session: "SessionManager",
        config: BulkOperationConfig | None = None,
    ) -> None:
        """Initialize bulk operation manager.

        Args:
            session: Session manager with active connection
            config: Optional bulk operation configuration
        """
        self._session = session
        self._config = config or BulkOperationConfig()
        self._recovery_service = RecoveryService(session)
        self._restore_service = RestoreService(session)
        self._validator = RecoveryValidator(session)
        self._audit = session.audit
        self._active_operations: dict[str, BulkOperationResult] = {}
        self._cancel_flags: dict[str, bool] = {}

        logger.debug("BulkOperationManager initialized")

    def execute_bulk_recovery(
        self,
        items: list[BulkOperationItem],
        progress_callback: Callable[[BulkOperationResult], None] | None = None,
    ) -> BulkOperationResult:
        """Execute bulk recovery operations.

        Args:
            items: List of items to process
            progress_callback: Optional callback for progress updates

        Returns:
            BulkOperationResult with all item results
        """
        operation_id = str(uuid.uuid4())
        result = BulkOperationResult(
            operation_id=operation_id,
            operation_type=BulkOperationType.RECOVERY,
            total_items=len(items),
            items=items,
        )

        self._active_operations[operation_id] = result
        self._cancel_flags[operation_id] = False

        logger.info(f"Starting bulk recovery: {operation_id} with {len(items)} items")

        self._audit.log_operation(
            OperationType.BULK_RECOVERY,
            details={
                "action": "start",
                "operation_id": operation_id,
                "total_items": len(items),
                "batch_size": self._config.batch_size,
            },
        )

        try:
            self._execute_batch_operation(
                result=result,
                operation_func=self._execute_single_recovery,
                progress_callback=progress_callback,
            )

        except Exception as e:
            logger.error(f"Bulk recovery failed: {e}")
            self._audit.log_operation(
                OperationType.BULK_RECOVERY,
                result="failure",
                error=str(e),
                details={"operation_id": operation_id},
            )

        finally:
            result.completed_at = datetime.now()
            self._audit.log_operation(
                OperationType.BULK_RECOVERY,
                details={
                    "action": "complete",
                    "operation_id": operation_id,
                    **result.to_dict(),
                },
            )

        return result

    def execute_bulk_restore(
        self,
        items: list[BulkOperationItem],
        progress_callback: Callable[[BulkOperationResult], None] | None = None,
    ) -> BulkOperationResult:
        """Execute bulk restore operations.

        Args:
            items: List of items to process
            progress_callback: Optional callback for progress updates

        Returns:
            BulkOperationResult with all item results
        """
        operation_id = str(uuid.uuid4())
        result = BulkOperationResult(
            operation_id=operation_id,
            operation_type=BulkOperationType.RESTORE,
            total_items=len(items),
            items=items,
        )

        self._active_operations[operation_id] = result
        self._cancel_flags[operation_id] = False

        logger.info(f"Starting bulk restore: {operation_id} with {len(items)} items")

        self._audit.log_operation(
            OperationType.BULK_RESTORE,
            details={
                "action": "start",
                "operation_id": operation_id,
                "total_items": len(items),
            },
        )

        try:
            self._execute_batch_operation(
                result=result,
                operation_func=self._execute_single_restore,
                progress_callback=progress_callback,
            )

        except Exception as e:
            logger.error(f"Bulk restore failed: {e}")
            self._audit.log_operation(
                OperationType.BULK_RESTORE,
                result="failure",
                error=str(e),
                details={"operation_id": operation_id},
            )

        finally:
            result.completed_at = datetime.now()
            self._audit.log_operation(
                OperationType.BULK_RESTORE,
                details={
                    "action": "complete",
                    "operation_id": operation_id,
                    **result.to_dict(),
                },
            )

        return result

    def execute_bulk_validation(
        self,
        items: list[BulkOperationItem],
        progress_callback: Callable[[BulkOperationResult], None] | None = None,
    ) -> BulkOperationResult:
        """Execute bulk validation without actual recovery.

        Args:
            items: List of items to validate
            progress_callback: Optional callback for progress updates

        Returns:
            BulkOperationResult with validation results
        """
        operation_id = str(uuid.uuid4())
        result = BulkOperationResult(
            operation_id=operation_id,
            operation_type=BulkOperationType.VALIDATE,
            total_items=len(items),
            items=items,
        )

        self._active_operations[operation_id] = result
        self._cancel_flags[operation_id] = False

        logger.info(f"Starting bulk validation: {operation_id} with {len(items)} items")

        try:
            self._execute_batch_operation(
                result=result,
                operation_func=self._execute_single_validation,
                progress_callback=progress_callback,
            )

        finally:
            result.completed_at = datetime.now()

        return result

    def _execute_batch_operation(
        self,
        result: BulkOperationResult,
        operation_func: Callable[[BulkOperationItem], None],
        progress_callback: Callable[[BulkOperationResult], None] | None,
    ) -> None:
        """Execute operation in batches.

        Args:
            result: Result object to update
            operation_func: Function to execute for each item
            progress_callback: Optional progress callback
        """
        batches = list(self._batch_items(result.items))

        for batch_num, batch in enumerate(batches, start=1):
            logger.debug(f"Processing batch {batch_num}/{len(batches)}")

            for item in batch:
                # Check for cancellation
                if self._cancel_flags.get(result.operation_id, False):
                    result.cancelled = True
                    item.status = BulkItemStatus.SKIPPED
                    result.skipped_items += 1
                    continue

                # Execute single operation
                item.started_at = datetime.now()
                item.status = BulkItemStatus.IN_PROGRESS

                try:
                    operation_func(item)

                    if item.status == BulkItemStatus.IN_PROGRESS:
                        # Operation completed successfully
                        item.status = BulkItemStatus.COMPLETED
                        result.completed_items += 1

                except Exception as e:
                    item.status = BulkItemStatus.FAILED
                    item.error = str(e)
                    result.failed_items += 1
                    logger.warning(f"Item {item.row_number} failed: {e}")

                    if self._config.stop_on_error:
                        logger.info("Stopping on error as configured")
                        # Mark remaining as skipped
                        for remaining in result.items:
                            if remaining.status == BulkItemStatus.PENDING:
                                remaining.status = BulkItemStatus.SKIPPED
                                result.skipped_items += 1
                        return

                finally:
                    item.completed_at = datetime.now()

                # Notify progress
                if progress_callback:
                    try:
                        progress_callback(result)
                    except Exception as e:
                        logger.warning(f"Progress callback error: {e}")

                # Delay between items
                if self._config.delay_between_items > 0:
                    time.sleep(self._config.delay_between_items)

            # Delay between batches
            if batch_num < len(batches) and self._config.delay_between_batches > 0:
                time.sleep(self._config.delay_between_batches)

        # Retry failed items if configured
        if self._config.retry_failed and result.failed_items > 0:
            self._retry_failed_items(result, operation_func, progress_callback)

    def _execute_single_recovery(self, item: BulkOperationItem) -> None:
        """Execute single recovery operation.

        Args:
            item: Item to process
        """
        request = RecoveryRequest(
            source_identity=item.source_identity,
            target_upn=item.target_identity or "",
            target_smtp=item.additional_data.get("target_smtp", item.target_identity or ""),
            display_name=item.additional_data.get("display_name", ""),
            first_name=item.additional_data.get("first_name", ""),
            last_name=item.additional_data.get("last_name", ""),
            department=item.additional_data.get("department"),
            company=item.additional_data.get("company"),
        )

        recovery_result = self._recovery_service.recover_mailbox(request)
        item.result = recovery_result

        if not recovery_result.success:
            item.status = BulkItemStatus.FAILED
            item.error = recovery_result.error

    def _execute_single_restore(self, item: BulkOperationItem) -> None:
        """Execute single restore operation.

        Args:
            item: Item to process
        """
        request = RestoreRequest(
            source_identity=item.source_identity,
            target_identity=item.target_identity or "",
            target_root_folder=item.additional_data.get("target_folder"),
            conflict_resolution=item.additional_data.get("conflict_resolution", "KeepAll"),
        )

        restore_result = self._restore_service.create_restore_request(request)
        item.result = restore_result

        if not restore_result.success:
            item.status = BulkItemStatus.FAILED
            item.error = restore_result.error

    def _execute_single_validation(self, item: BulkOperationItem) -> None:
        """Execute single validation.

        Args:
            item: Item to validate
        """
        validation_result = self._validator.validate_recovery(
            identity=item.source_identity,
            target_upn=item.target_identity,
            target_smtp=item.additional_data.get("target_smtp"),
        )

        item.result = validation_result

        if not validation_result.can_proceed:
            item.status = BulkItemStatus.FAILED
            item.error = "; ".join(validation_result.blockers)

    def _retry_failed_items(
        self,
        result: BulkOperationResult,
        operation_func: Callable[[BulkOperationItem], None],
        progress_callback: Callable[[BulkOperationResult], None] | None,
    ) -> None:
        """Retry failed items.

        Args:
            result: Result with failed items
            operation_func: Operation function to retry
            progress_callback: Optional progress callback
        """
        failed_items = [
            item for item in result.items
            if item.status == BulkItemStatus.FAILED
        ]

        if not failed_items:
            return

        logger.info(f"Retrying {len(failed_items)} failed items")

        for retry_num in range(self._config.max_retries):
            items_to_retry = [
                item for item in failed_items
                if item.status == BulkItemStatus.FAILED
            ]

            if not items_to_retry:
                break

            logger.debug(f"Retry attempt {retry_num + 1}/{self._config.max_retries}")

            for item in items_to_retry:
                item.status = BulkItemStatus.IN_PROGRESS
                item.error = None
                item.started_at = datetime.now()

                try:
                    operation_func(item)

                    if item.status == BulkItemStatus.IN_PROGRESS:
                        item.status = BulkItemStatus.COMPLETED
                        result.completed_items += 1
                        result.failed_items -= 1

                except Exception as e:
                    item.status = BulkItemStatus.FAILED
                    item.error = str(e)

                finally:
                    item.completed_at = datetime.now()

                if progress_callback:
                    try:
                        progress_callback(result)
                    except Exception:
                        pass

    def _batch_items(
        self,
        items: list[BulkOperationItem],
    ) -> list[list[BulkOperationItem]]:
        """Split items into batches.

        Args:
            items: Items to batch

        Yields:
            Batches of items
        """
        batch_size = self._config.batch_size
        for i in range(0, len(items), batch_size):
            yield items[i:i + batch_size]

    def cancel_operation(self, operation_id: str) -> bool:
        """Cancel a running operation.

        Args:
            operation_id: Operation to cancel

        Returns:
            True if cancellation was signaled
        """
        if operation_id in self._cancel_flags:
            self._cancel_flags[operation_id] = True
            logger.info(f"Cancellation signaled for {operation_id}")
            return True
        return False

    def get_operation_status(self, operation_id: str) -> BulkOperationResult | None:
        """Get status of an operation.

        Args:
            operation_id: Operation identifier

        Returns:
            BulkOperationResult or None if not found
        """
        return self._active_operations.get(operation_id)

    def retry_failed(
        self,
        result: BulkOperationResult,
        progress_callback: Callable[[BulkOperationResult], None] | None = None,
    ) -> BulkOperationResult:
        """Retry failed items from a completed operation.

        Args:
            result: Previous result with failed items
            progress_callback: Optional progress callback

        Returns:
            Updated BulkOperationResult
        """
        failed_items = [
            item for item in result.items
            if item.status == BulkItemStatus.FAILED
        ]

        if not failed_items:
            return result

        # Reset failed items to pending
        for item in failed_items:
            item.status = BulkItemStatus.PENDING
            item.error = None
            item.result = None

        # Determine operation function
        if result.operation_type == BulkOperationType.RECOVERY:
            operation_func = self._execute_single_recovery
        elif result.operation_type == BulkOperationType.RESTORE:
            operation_func = self._execute_single_restore
        else:
            operation_func = self._execute_single_validation

        # Execute with only failed items
        result.failed_items = 0
        self._execute_batch_operation(
            result=result,
            operation_func=operation_func,
            progress_callback=progress_callback,
        )

        return result
