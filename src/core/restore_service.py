"""Restore service for merging inactive mailbox content into existing mailboxes."""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

from src.core.recovery_validator import RecoveryValidator, ValidationResult, ValidationCode, ValidationIssue, ValidationSeverity
from src.data.audit_logger import OperationType
from src.utils.command_builder import CommandBuilder
from src.utils.logging import get_logger
from src.utils.ps_parser import parse_json_output

if TYPE_CHECKING:
    from src.data.session import SessionManager

logger = get_logger(__name__)


@dataclass
class RestoreRequest:
    """Request parameters for mailbox restore operation."""

    source_identity: str
    target_identity: str
    target_root_folder: str | None = None
    allow_legacy_dn_mismatch: bool = True
    exclude_dumpster: bool = False
    conflict_resolution: str = "KeepAll"  # KeepSourceItem, KeepLatestItem, KeepAll
    include_folders: list[str] | None = None
    exclude_folders: list[str] | None = None
    batch_name: str | None = None

    def __post_init__(self) -> None:
        """Set default target folder if not provided."""
        if not self.target_root_folder:
            timestamp = datetime.now().strftime("%Y-%m-%d")
            self.target_root_folder = f"Restored-{timestamp}"


@dataclass
class RestoreResult:
    """Result of a mailbox restore operation."""

    success: bool = False
    request_id: str | None = None
    request_name: str | None = None
    status: str = "Unknown"  # Queued, InProgress, Completed, Failed
    error: str | None = None
    items_copied: int = 0
    items_skipped: int = 0
    bytes_copied: int = 0
    percent_complete: float = 0.0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    validation_result: ValidationResult | None = None
    raw_output: dict[str, Any] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        """Check if restore is complete."""
        return self.status in ["Completed", "Failed", "CompletedWithWarning"]

    @property
    def duration_seconds(self) -> float:
        """Get operation duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0


class RestoreServiceError(Exception):
    """Raised when restore operations fail."""

    pass


class RestoreService:
    """Service for restoring inactive mailbox content to active mailboxes.

    Creates and manages mailbox restore requests that run asynchronously
    in Exchange Online.
    """

    # Conflict resolution options
    CONFLICT_OPTIONS = ["KeepSourceItem", "KeepLatestItem", "KeepAll"]

    def __init__(
        self,
        session: "SessionManager",
        validator: RecoveryValidator | None = None,
    ) -> None:
        """Initialize restore service.

        Args:
            session: Session manager with active connection
            validator: Optional pre-initialized validator
        """
        self._session = session
        self._validator = validator or RecoveryValidator(session)
        self._command_builder = CommandBuilder()
        self._audit = session.audit

        logger.debug("RestoreService initialized")

    def create_restore_request(
        self,
        request: RestoreRequest,
        skip_validation: bool = False,
    ) -> RestoreResult:
        """Create a new mailbox restore request.

        Args:
            request: Restore request parameters
            skip_validation: Skip validation checks

        Returns:
            RestoreResult with request details
        """
        result = RestoreResult(started_at=datetime.now())

        logger.info(
            f"Creating restore request: {request.source_identity} -> {request.target_identity}"
        )

        # Log restore attempt
        self._audit.log_operation(
            OperationType.RESTORE_MAILBOX,
            identity=request.source_identity,
            details={
                "action": "start",
                "target": request.target_identity,
                "folder": request.target_root_folder,
            },
        )

        try:
            # Validate restore
            if not skip_validation:
                result.validation_result = self.validate_restore(request)

                if not result.validation_result.can_proceed:
                    result.error = "Validation failed: " + ", ".join(
                        result.validation_result.blockers
                    )
                    logger.warning(f"Restore validation failed: {result.error}")

                    self._audit.log_operation(
                        OperationType.RESTORE_MAILBOX,
                        identity=request.source_identity,
                        result="failure",
                        error=result.error,
                    )
                    return result

            # Execute restore request
            result = self._execute_restore_request(request, result)

            # Log result
            if result.success:
                self._audit.log_operation(
                    OperationType.RESTORE_MAILBOX,
                    identity=request.source_identity,
                    details={
                        "action": "created",
                        "request_id": result.request_id,
                        "status": result.status,
                    },
                )
            else:
                self._audit.log_operation(
                    OperationType.RESTORE_MAILBOX,
                    identity=request.source_identity,
                    result="failure",
                    error=result.error,
                )

            return result

        except Exception as e:
            logger.error(f"Restore request failed: {e}")
            result.error = str(e)

            self._audit.log_operation(
                OperationType.RESTORE_MAILBOX,
                identity=request.source_identity,
                result="failure",
                error=str(e),
            )

            return result

    def _execute_restore_request(
        self,
        request: RestoreRequest,
        result: RestoreResult,
    ) -> RestoreResult:
        """Execute the restore request command.

        Args:
            request: Restore request
            result: Result object to update

        Returns:
            Updated RestoreResult
        """
        self._session.ensure_connected()

        # Build restore command
        cmd = self._command_builder.build_new_restore_request(
            source_mailbox=request.source_identity,
            target_mailbox=request.target_identity,
            target_root_folder=request.target_root_folder,
            allow_legacy_dn_mismatch=request.allow_legacy_dn_mismatch,
            conflict_resolution=request.conflict_resolution,
        )

        logger.debug("Executing restore request command")

        ps_result = self._session.connection.execute_command(cmd, timeout=120)

        if not ps_result.success:
            result.success = False
            result.error = ps_result.error
            result.status = "Failed"
            return result

        # Parse result
        try:
            data = parse_json_output(ps_result.output)
            if isinstance(data, list):
                data = data[0] if data else {}

            result.success = True
            result.request_id = data.get("Identity") or data.get("RequestGuid")
            result.request_name = data.get("Name")
            result.status = data.get("Status", "Queued")
            result.raw_output = data

            logger.info(f"Restore request created: {result.request_id}")

        except Exception as e:
            # Command may have succeeded even if parsing fails
            result.success = True
            result.status = "Queued"
            logger.warning(f"Restore created but output parsing failed: {e}")

        return result

    def validate_restore(self, request: RestoreRequest) -> ValidationResult:
        """Validate a restore request.

        Args:
            request: Restore request to validate

        Returns:
            ValidationResult with any issues
        """
        return self._validator.validate_restore(
            request.source_identity,
            request.target_identity,
        )

    def get_restore_status(self, request_id: str) -> RestoreResult:
        """Get status of a restore request.

        Args:
            request_id: Restore request identity

        Returns:
            RestoreResult with current status
        """
        result = RestoreResult(request_id=request_id)

        if not self._session.connection or not self._session.connection.is_connected:
            result.status = "Unknown"
            return result

        cmd = self._command_builder.build_get_restore_request_status(request_id)
        ps_result = self._session.connection.execute_command(cmd, timeout=60)

        if not ps_result.success:
            result.status = "Unknown"
            result.error = ps_result.error
            return result

        try:
            data = parse_json_output(ps_result.output)
            if isinstance(data, list):
                data = data[0] if data else {}

            result.status = data.get("Status", "Unknown")
            result.percent_complete = float(data.get("PercentComplete", 0))
            result.items_copied = int(data.get("ItemsTransferred", 0))
            result.bytes_copied = int(data.get("BytesTransferred", 0))
            result.raw_output = data

            if result.status in ["Completed", "CompletedWithWarning"]:
                result.success = True
                result.completed_at = datetime.now()

        except Exception as e:
            logger.warning(f"Failed to parse restore status: {e}")
            result.status = "Unknown"

        return result

    def get_all_restore_requests(
        self,
        batch_name: str | None = None,
    ) -> list[RestoreResult]:
        """Get all restore requests.

        Args:
            batch_name: Optional batch name to filter by

        Returns:
            List of RestoreResult objects
        """
        if not self._session.connection or not self._session.connection.is_connected:
            return []

        if batch_name:
            cmd = f"Get-MailboxRestoreRequest -BatchName '{batch_name}' | ConvertTo-Json -Depth 5"
        else:
            cmd = "Get-MailboxRestoreRequest | ConvertTo-Json -Depth 5"

        ps_result = self._session.connection.execute_command(cmd, timeout=120)

        if not ps_result.success:
            logger.warning(f"Failed to get restore requests: {ps_result.error}")
            return []

        try:
            data = parse_json_output(ps_result.output)
            if isinstance(data, dict):
                data = [data]

            results = []
            for item in data:
                result = RestoreResult(
                    request_id=item.get("Identity") or item.get("RequestGuid"),
                    request_name=item.get("Name"),
                    status=item.get("Status", "Unknown"),
                    raw_output=item,
                )
                results.append(result)

            return results

        except Exception as e:
            logger.warning(f"Failed to parse restore requests: {e}")
            return []

    def cancel_restore_request(self, request_id: str) -> bool:
        """Cancel a restore request.

        Args:
            request_id: Request identity to cancel

        Returns:
            True if cancelled successfully
        """
        if not self._session.connection or not self._session.connection.is_connected:
            return False

        cmd = f"Get-MailboxRestoreRequest -Identity '{request_id}' | Suspend-MailboxRestoreRequest"
        ps_result = self._session.connection.execute_command(cmd, timeout=60)

        if ps_result.success:
            self._audit.log_operation(
                OperationType.RESTORE_MAILBOX,
                details={"action": "cancelled", "request_id": request_id},
            )
            return True

        return False

    def remove_restore_request(self, request_id: str) -> bool:
        """Remove a completed restore request.

        Args:
            request_id: Request identity to remove

        Returns:
            True if removed successfully
        """
        if not self._session.connection or not self._session.connection.is_connected:
            return False

        cmd = f"Remove-MailboxRestoreRequest -Identity '{request_id}' -Confirm:$false"
        ps_result = self._session.connection.execute_command(cmd, timeout=60)

        return ps_result.success

    def wait_for_completion(
        self,
        request_id: str,
        timeout: int = 3600,
        poll_interval: int = 30,
        progress_callback: Callable[[RestoreResult], None] | None = None,
    ) -> RestoreResult:
        """Wait for a restore request to complete.

        Args:
            request_id: Request identity
            timeout: Maximum wait time in seconds
            poll_interval: Time between status checks
            progress_callback: Optional callback for progress updates

        Returns:
            Final RestoreResult
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            result = self.get_restore_status(request_id)

            if progress_callback:
                progress_callback(result)

            if result.is_complete:
                return result

            logger.debug(
                f"Restore {request_id}: {result.status} ({result.percent_complete:.1f}%)"
            )
            time.sleep(poll_interval)

        # Timeout
        result = self.get_restore_status(request_id)
        result.error = f"Timeout waiting for restore after {timeout}s"
        return result

    def estimate_restore_time(self, source_size_mb: float) -> int:
        """Estimate time needed for restore operation.

        Args:
            source_size_mb: Source mailbox size in MB

        Returns:
            Estimated time in seconds
        """
        # Rough estimate: ~1 minute per GB plus overhead
        base_overhead = 60  # 1 minute for setup
        per_gb = 60  # 1 minute per GB

        size_gb = source_size_mb / 1024
        return int(base_overhead + (size_gb * per_gb))

    def get_recommended_folder_name(self, source_display_name: str) -> str:
        """Generate recommended target folder name.

        Args:
            source_display_name: Source mailbox display name

        Returns:
            Recommended folder name
        """
        timestamp = datetime.now().strftime("%Y-%m-%d")
        # Clean display name for folder
        clean_name = "".join(
            c for c in source_display_name if c.isalnum() or c in " -_"
        ).strip()
        return f"Restored-{clean_name}-{timestamp}"
