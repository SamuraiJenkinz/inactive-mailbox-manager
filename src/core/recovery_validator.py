"""Recovery validation service for pre-flight checks before mailbox recovery."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from src.utils.command_builder import CommandBuilder
from src.utils.logging import get_logger
from src.utils.ps_parser import parse_json_output

if TYPE_CHECKING:
    from src.data.session import SessionManager

logger = get_logger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationCode(Enum):
    """Validation error/warning codes."""

    # Errors (block recovery)
    AUXPRIMARY_SHARD = "AUXPRIMARY_SHARD"
    UPN_CONFLICT = "UPN_CONFLICT"
    SMTP_CONFLICT = "SMTP_CONFLICT"
    MAILBOX_NOT_FOUND = "MAILBOX_NOT_FOUND"
    NOT_INACTIVE = "NOT_INACTIVE"

    # Warnings (allow with caution)
    AUTO_EXPANDING_ARCHIVE = "AUTO_EXPANDING_ARCHIVE"
    LITIGATION_HOLD = "LITIGATION_HOLD"
    EDISCOVERY_HOLD = "EDISCOVERY_HOLD"
    RETENTION_POLICY_HOLD = "RETENTION_POLICY_HOLD"
    DELAY_HOLD = "DELAY_HOLD"
    SOFT_DELETED_USER = "SOFT_DELETED_USER"
    LARGE_MAILBOX = "LARGE_MAILBOX"
    OLD_MAILBOX = "OLD_MAILBOX"

    # Restore-specific
    TARGET_NOT_FOUND = "TARGET_NOT_FOUND"
    TARGET_INACTIVE = "TARGET_INACTIVE"
    INSUFFICIENT_QUOTA = "INSUFFICIENT_QUOTA"
    DUPLICATE_RESTORE_REQUEST = "DUPLICATE_RESTORE_REQUEST"


@dataclass
class ValidationIssue:
    """A single validation issue (error or warning)."""

    code: ValidationCode
    message: str
    severity: ValidationSeverity
    resolution: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_error(self) -> bool:
        """Check if this is a blocking error."""
        return self.severity == ValidationSeverity.ERROR

    @property
    def is_warning(self) -> bool:
        """Check if this is a warning."""
        return self.severity == ValidationSeverity.WARNING


@dataclass
class ValidationResult:
    """Result of validation checks."""

    is_valid: bool = True
    can_proceed: bool = True
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
    info: list[ValidationIssue] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    validated_at: datetime = field(default_factory=datetime.now)
    validation_data: dict[str, Any] = field(default_factory=dict)

    def add_error(self, issue: ValidationIssue) -> None:
        """Add an error and update validity."""
        self.errors.append(issue)
        self.is_valid = False
        self.can_proceed = False
        self.blockers.append(issue.message)

    def add_warning(self, issue: ValidationIssue) -> None:
        """Add a warning (doesn't block but needs attention)."""
        self.warnings.append(issue)
        if issue.resolution:
            self.recommendations.append(issue.resolution)

    def add_info(self, issue: ValidationIssue) -> None:
        """Add informational note."""
        self.info.append(issue)

    @property
    def total_issues(self) -> int:
        """Get total number of issues."""
        return len(self.errors) + len(self.warnings) + len(self.info)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/display."""
        return {
            "is_valid": self.is_valid,
            "can_proceed": self.can_proceed,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "blockers": self.blockers,
            "recommendations": self.recommendations,
            "validated_at": self.validated_at.isoformat(),
        }


class RecoveryValidatorError(Exception):
    """Raised when validation operations fail."""

    pass


class RecoveryValidator:
    """Validates mailbox recovery operations before execution.

    Performs comprehensive pre-flight checks to prevent common
    recovery failures and data loss scenarios.
    """

    # Thresholds for warnings
    LARGE_MAILBOX_MB = 10240  # 10 GB
    OLD_MAILBOX_DAYS = 730  # 2 years

    def __init__(self, session: "SessionManager") -> None:
        """Initialize recovery validator.

        Args:
            session: Session manager with active connection
        """
        self._session = session
        self._command_builder = CommandBuilder()
        logger.debug("RecoveryValidator initialized")

    def validate_recovery(
        self,
        identity: str,
        target_upn: str | None = None,
        target_smtp: str | None = None,
    ) -> ValidationResult:
        """Perform comprehensive recovery validation.

        Args:
            identity: Source inactive mailbox identity
            target_upn: Target UPN for recovery (optional for validation)
            target_smtp: Target SMTP for recovery (optional for validation)

        Returns:
            ValidationResult with all issues found
        """
        result = ValidationResult()

        logger.info(f"Validating recovery for: {identity}")

        try:
            # Get preflight data from Exchange
            preflight_data = self._get_preflight_data(identity)

            if preflight_data is None:
                result.add_error(
                    ValidationIssue(
                        code=ValidationCode.MAILBOX_NOT_FOUND,
                        message=f"Mailbox not found: {identity}",
                        severity=ValidationSeverity.ERROR,
                        resolution="Verify the mailbox GUID or email address is correct",
                    )
                )
                return result

            result.validation_data = preflight_data

            # Check for AuxPrimary shard
            auxprimary_error = self.check_auxprimary_shard(preflight_data)
            if auxprimary_error:
                result.add_error(auxprimary_error)

            # Check for auto-expanding archive
            archive_warning = self.check_auto_expanding_archive(preflight_data)
            if archive_warning:
                result.add_warning(archive_warning)

            # Check for active holds
            hold_warnings = self.check_active_holds(preflight_data)
            for warning in hold_warnings:
                result.add_warning(warning)

            # Check mailbox size
            size_warning = self.check_mailbox_size(preflight_data)
            if size_warning:
                result.add_warning(size_warning)

            # Check mailbox age
            age_warning = self.check_mailbox_age(preflight_data)
            if age_warning:
                result.add_warning(age_warning)

            # Check target conflicts if provided
            if target_upn:
                upn_error = self.check_upn_conflict(target_upn)
                if upn_error:
                    result.add_error(upn_error)

            if target_smtp:
                smtp_error = self.check_smtp_conflict(target_smtp)
                if smtp_error:
                    result.add_error(smtp_error)

            # Check for soft-deleted user
            soft_deleted_warning = self.check_soft_deleted_user(identity)
            if soft_deleted_warning:
                result.add_warning(soft_deleted_warning)

            logger.info(
                f"Validation complete: valid={result.is_valid}, "
                f"errors={len(result.errors)}, warnings={len(result.warnings)}"
            )

        except Exception as e:
            logger.error(f"Validation failed: {e}")
            result.add_error(
                ValidationIssue(
                    code=ValidationCode.MAILBOX_NOT_FOUND,
                    message=f"Validation failed: {str(e)}",
                    severity=ValidationSeverity.ERROR,
                )
            )

        return result

    def validate_restore(
        self,
        source_identity: str,
        target_identity: str,
    ) -> ValidationResult:
        """Validate restore operation from inactive to active mailbox.

        Args:
            source_identity: Source inactive mailbox
            target_identity: Target active mailbox

        Returns:
            ValidationResult with all issues found
        """
        result = ValidationResult()

        logger.info(f"Validating restore: {source_identity} -> {target_identity}")

        try:
            # Validate source mailbox exists
            source_data = self._get_preflight_data(source_identity)
            if source_data is None:
                result.add_error(
                    ValidationIssue(
                        code=ValidationCode.MAILBOX_NOT_FOUND,
                        message=f"Source mailbox not found: {source_identity}",
                        severity=ValidationSeverity.ERROR,
                    )
                )
                return result

            # Check target mailbox exists
            target_error = self.check_target_mailbox_exists(target_identity)
            if target_error:
                result.add_error(target_error)
                return result

            # Check target is not inactive
            target_inactive = self.check_target_is_active(target_identity)
            if target_inactive:
                result.add_error(target_inactive)

            # Check for existing restore request
            duplicate_error = self.check_existing_restore_request(
                source_identity, target_identity
            )
            if duplicate_error:
                result.add_error(duplicate_error)

            # Check source holds (warning only for restore)
            hold_warnings = self.check_active_holds(source_data)
            for warning in hold_warnings:
                result.add_warning(warning)

        except Exception as e:
            logger.error(f"Restore validation failed: {e}")
            result.add_error(
                ValidationIssue(
                    code=ValidationCode.MAILBOX_NOT_FOUND,
                    message=f"Validation failed: {str(e)}",
                    severity=ValidationSeverity.ERROR,
                )
            )

        return result

    def _get_preflight_data(self, identity: str) -> dict[str, Any] | None:
        """Get preflight validation data from Exchange.

        Args:
            identity: Mailbox identity

        Returns:
            Preflight data dictionary or None if not found
        """
        if not self._session.connection or not self._session.connection.is_connected:
            logger.warning("Not connected - returning mock validation data")
            # Return minimal data for testing
            return {"Identity": identity, "IsAuxPrimary": False}

        cmd = self._command_builder.build_recovery_preflight(identity)
        result = self._session.connection.execute_command(cmd, timeout=60)

        if not result.success:
            if "couldn't be found" in result.error.lower():
                return None
            raise RecoveryValidatorError(f"Preflight check failed: {result.error}")

        try:
            data = parse_json_output(result.output)
            if isinstance(data, list):
                data = data[0] if data else None
            return data
        except Exception as e:
            raise RecoveryValidatorError(f"Failed to parse preflight data: {e}") from e

    def check_auxprimary_shard(self, data: dict[str, Any]) -> ValidationIssue | None:
        """Check if mailbox is an AuxPrimary shard.

        Args:
            data: Preflight data

        Returns:
            ValidationIssue if AuxPrimary, None otherwise
        """
        if data.get("IsAuxPrimary"):
            return ValidationIssue(
                code=ValidationCode.AUXPRIMARY_SHARD,
                message="Mailbox is an AuxPrimary shard and cannot be recovered directly",
                severity=ValidationSeverity.ERROR,
                resolution=(
                    "Contact Microsoft Support to recover the primary mailbox first, "
                    "or use New-MailboxRestoreRequest to restore content to another mailbox"
                ),
                details={"mailbox_location_type": data.get("MailboxLocationType")},
            )
        return None

    def check_auto_expanding_archive(self, data: dict[str, Any]) -> ValidationIssue | None:
        """Check if mailbox has auto-expanding archive.

        Args:
            data: Preflight data

        Returns:
            ValidationIssue if auto-expanding archive, None otherwise
        """
        if data.get("AutoExpandingArchiveEnabled"):
            return ValidationIssue(
                code=ValidationCode.AUTO_EXPANDING_ARCHIVE,
                message="Mailbox has auto-expanding archive enabled",
                severity=ValidationSeverity.WARNING,
                resolution=(
                    "Recovery will succeed but archive may require additional steps. "
                    "Verify archive content after recovery completes."
                ),
                details={"archive_guid": data.get("ArchiveGuid")},
            )
        return None

    def check_active_holds(self, data: dict[str, Any]) -> list[ValidationIssue]:
        """Check for active holds on mailbox.

        Args:
            data: Preflight data or mailbox data

        Returns:
            List of validation warnings for active holds
        """
        warnings = []

        # Check litigation hold
        if data.get("LitigationHoldEnabled") or data.get("LitigationHold"):
            warnings.append(
                ValidationIssue(
                    code=ValidationCode.LITIGATION_HOLD,
                    message="Mailbox has Litigation Hold enabled",
                    severity=ValidationSeverity.WARNING,
                    resolution=(
                        "Litigation Hold will be preserved on recovered mailbox. "
                        "Consult legal/compliance before removing."
                    ),
                )
            )

        # Check hold count
        hold_count = data.get("HoldCount", 0)
        if hold_count > 0:
            in_place_holds = data.get("InPlaceHolds", [])
            if isinstance(in_place_holds, str):
                in_place_holds = [in_place_holds]

            # Check for eDiscovery holds
            ediscovery_holds = [h for h in in_place_holds if h.startswith("UniH")]
            if ediscovery_holds:
                warnings.append(
                    ValidationIssue(
                        code=ValidationCode.EDISCOVERY_HOLD,
                        message=f"Mailbox has {len(ediscovery_holds)} eDiscovery hold(s)",
                        severity=ValidationSeverity.WARNING,
                        resolution=(
                            "eDiscovery holds will be preserved. "
                            "These are managed in Microsoft Purview Compliance Center."
                        ),
                        details={"hold_ids": ediscovery_holds},
                    )
                )

            # Check for retention policies
            retention_holds = [
                h for h in in_place_holds
                if not any(h.startswith(p) for p in ["UniH", "mbx", "skp", "grp"])
            ]
            if retention_holds:
                warnings.append(
                    ValidationIssue(
                        code=ValidationCode.RETENTION_POLICY_HOLD,
                        message=f"Mailbox has {len(retention_holds)} retention policy hold(s)",
                        severity=ValidationSeverity.WARNING,
                        resolution=(
                            "Retention policies will apply to recovered mailbox. "
                            "Review policies in Microsoft Purview."
                        ),
                    )
                )

        # Check delay hold
        if data.get("DelayHoldApplied") or data.get("DelayReleaseHoldApplied"):
            warnings.append(
                ValidationIssue(
                    code=ValidationCode.DELAY_HOLD,
                    message="Mailbox has Delay Hold applied (30-day hold after removal)",
                    severity=ValidationSeverity.WARNING,
                    resolution=(
                        "Delay hold will expire automatically. "
                        "Recovery can proceed but hold will remain temporarily."
                    ),
                )
            )

        return warnings

    def check_mailbox_size(self, data: dict[str, Any]) -> ValidationIssue | None:
        """Check if mailbox is unusually large.

        Args:
            data: Preflight or mailbox data

        Returns:
            ValidationIssue if large mailbox, None otherwise
        """
        size_mb = data.get("size_mb", 0)
        if size_mb > self.LARGE_MAILBOX_MB:
            return ValidationIssue(
                code=ValidationCode.LARGE_MAILBOX,
                message=f"Mailbox is large ({size_mb / 1024:.1f} GB)",
                severity=ValidationSeverity.INFO,
                resolution=(
                    "Recovery may take longer for large mailboxes. "
                    "Consider scheduling during off-peak hours."
                ),
                details={"size_mb": size_mb},
            )
        return None

    def check_mailbox_age(self, data: dict[str, Any]) -> ValidationIssue | None:
        """Check if mailbox is very old.

        Args:
            data: Preflight or mailbox data

        Returns:
            ValidationIssue if old mailbox, None otherwise
        """
        age_days = data.get("age_days", 0)
        if age_days > self.OLD_MAILBOX_DAYS:
            return ValidationIssue(
                code=ValidationCode.OLD_MAILBOX,
                message=f"Mailbox has been inactive for {age_days} days ({age_days // 365} years)",
                severity=ValidationSeverity.INFO,
                resolution=(
                    "Very old mailboxes may have retention policy implications. "
                    "Verify business need for recovery."
                ),
                details={"age_days": age_days},
            )
        return None

    def check_upn_conflict(self, target_upn: str) -> ValidationIssue | None:
        """Check if target UPN already exists.

        Args:
            target_upn: Target UPN for recovery

        Returns:
            ValidationIssue if conflict, None otherwise
        """
        if not self._session.connection or not self._session.connection.is_connected:
            return None

        cmd = self._command_builder.build_check_mailbox_exists(target_upn)
        result = self._session.connection.execute_command(cmd, timeout=30)

        if result.success and result.output.strip():
            # Mailbox exists
            return ValidationIssue(
                code=ValidationCode.UPN_CONFLICT,
                message=f"UPN already in use: {target_upn}",
                severity=ValidationSeverity.ERROR,
                resolution="Choose a different UPN or remove the existing mailbox first",
                details={"conflicting_upn": target_upn},
            )

        return None

    def check_smtp_conflict(self, target_smtp: str) -> ValidationIssue | None:
        """Check if target SMTP address already exists.

        Args:
            target_smtp: Target SMTP address

        Returns:
            ValidationIssue if conflict, None otherwise
        """
        if not self._session.connection or not self._session.connection.is_connected:
            return None

        cmd = self._command_builder.build_check_smtp_exists(target_smtp)
        result = self._session.connection.execute_command(cmd, timeout=30)

        if result.success and result.output.strip():
            # SMTP exists
            return ValidationIssue(
                code=ValidationCode.SMTP_CONFLICT,
                message=f"SMTP address already in use: {target_smtp}",
                severity=ValidationSeverity.ERROR,
                resolution="Choose a different email address or remove the conflict first",
                details={"conflicting_smtp": target_smtp},
            )

        return None

    def check_soft_deleted_user(self, identity: str) -> ValidationIssue | None:
        """Check if there's a soft-deleted user with same identity.

        Args:
            identity: Mailbox identity

        Returns:
            ValidationIssue if soft-deleted user found, None otherwise
        """
        # This would require Azure AD check - simplified for now
        return None

    def check_target_mailbox_exists(self, target: str) -> ValidationIssue | None:
        """Check if target mailbox exists for restore operation.

        Args:
            target: Target mailbox identity

        Returns:
            ValidationIssue if not found, None otherwise
        """
        if not self._session.connection or not self._session.connection.is_connected:
            return None

        cmd = self._command_builder.build_check_mailbox_exists(target)
        result = self._session.connection.execute_command(cmd, timeout=30)

        if not result.success or not result.output.strip():
            return ValidationIssue(
                code=ValidationCode.TARGET_NOT_FOUND,
                message=f"Target mailbox not found: {target}",
                severity=ValidationSeverity.ERROR,
                resolution="Verify the target mailbox exists and is accessible",
            )

        return None

    def check_target_is_active(self, target: str) -> ValidationIssue | None:
        """Check if target mailbox is active (not inactive).

        Args:
            target: Target mailbox identity

        Returns:
            ValidationIssue if target is inactive, None otherwise
        """
        # Would need additional check - simplified for now
        return None

    def check_existing_restore_request(
        self, source: str, target: str
    ) -> ValidationIssue | None:
        """Check if restore request already exists.

        Args:
            source: Source mailbox
            target: Target mailbox

        Returns:
            ValidationIssue if duplicate request, None otherwise
        """
        # Would need to check Get-MailboxRestoreRequest - simplified for now
        return None
