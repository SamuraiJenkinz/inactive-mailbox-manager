"""Recovery service for executing mailbox recovery operations."""

import secrets
import string
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from src.core.recovery_validator import RecoveryValidator, ValidationResult
from src.data.audit_logger import OperationType
from src.utils.command_builder import CommandBuilder
from src.utils.logging import get_logger
from src.utils.ps_parser import parse_json_output

if TYPE_CHECKING:
    from src.data.session import SessionManager

logger = get_logger(__name__)


@dataclass
class RecoveryRequest:
    """Request parameters for mailbox recovery."""

    source_identity: str
    target_upn: str
    target_smtp: str | None = None
    display_name: str = ""
    first_name: str | None = None
    last_name: str | None = None
    password: str | None = None
    reset_password_on_logon: bool = True
    department: str | None = None
    company: str | None = None

    def __post_init__(self) -> None:
        """Set defaults after initialization."""
        if not self.target_smtp:
            self.target_smtp = self.target_upn
        if not self.display_name:
            self.display_name = self.target_upn.split("@")[0]


@dataclass
class RecoveryResult:
    """Result of a mailbox recovery operation."""

    success: bool = False
    new_mailbox_guid: str | None = None
    new_upn: str | None = None
    error: str | None = None
    validation_result: ValidationResult | None = None
    execution_time_seconds: float = 0.0
    audit_id: int | None = None
    raw_output: dict[str, Any] = field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def duration(self) -> float:
        """Get operation duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return self.execution_time_seconds


class RecoveryServiceError(Exception):
    """Raised when recovery operations fail."""

    pass


class RecoveryService:
    """Service for recovering inactive mailboxes to new active mailboxes.

    Handles validation, execution, and audit logging of recovery operations.
    """

    # Password generation settings
    PASSWORD_LENGTH = 16
    PASSWORD_CHARS = string.ascii_letters + string.digits + "!@#$%^&*"

    def __init__(
        self,
        session: "SessionManager",
        validator: RecoveryValidator | None = None,
    ) -> None:
        """Initialize recovery service.

        Args:
            session: Session manager with active connection
            validator: Optional pre-initialized validator
        """
        self._session = session
        self._validator = validator or RecoveryValidator(session)
        self._command_builder = CommandBuilder()
        self._audit = session.audit

        logger.debug("RecoveryService initialized")

    def recover_mailbox(
        self,
        request: RecoveryRequest,
        skip_validation: bool = False,
    ) -> RecoveryResult:
        """Recover an inactive mailbox to a new active mailbox.

        Args:
            request: Recovery request parameters
            skip_validation: Skip pre-flight validation (not recommended)

        Returns:
            RecoveryResult with operation outcome
        """
        result = RecoveryResult(started_at=datetime.now())

        logger.info(f"Starting recovery: {request.source_identity} -> {request.target_upn}")

        # Log recovery attempt
        self._audit.log_operation(
            OperationType.RECOVER_MAILBOX,
            identity=request.source_identity,
            details={
                "action": "start",
                "target_upn": request.target_upn,
                "skip_validation": skip_validation,
            },
        )

        try:
            # Validate recovery
            if not skip_validation:
                result.validation_result = self._validator.validate_recovery(
                    identity=request.source_identity,
                    target_upn=request.target_upn,
                    target_smtp=request.target_smtp,
                )

                if not result.validation_result.can_proceed:
                    result.error = "Validation failed: " + ", ".join(
                        result.validation_result.blockers
                    )
                    logger.warning(f"Recovery validation failed: {result.error}")

                    self._audit.log_operation(
                        OperationType.RECOVER_MAILBOX,
                        identity=request.source_identity,
                        result="failure",
                        error=result.error,
                        details={"validation_errors": len(result.validation_result.errors)},
                    )

                    result.completed_at = datetime.now()
                    return result

            # Generate password if not provided
            if not request.password:
                request.password = self._generate_password()

            # Execute recovery
            result = self._execute_recovery(request, result)

            result.completed_at = datetime.now()
            result.execution_time_seconds = result.duration

            # Log result
            if result.success:
                self._audit.log_operation(
                    OperationType.RECOVER_MAILBOX,
                    identity=request.source_identity,
                    details={
                        "action": "complete",
                        "new_mailbox_guid": result.new_mailbox_guid,
                        "new_upn": result.new_upn,
                        "duration_seconds": result.execution_time_seconds,
                    },
                )
            else:
                self._audit.log_operation(
                    OperationType.RECOVER_MAILBOX,
                    identity=request.source_identity,
                    result="failure",
                    error=result.error,
                    details={"action": "failed"},
                )

            return result

        except Exception as e:
            logger.error(f"Recovery failed with exception: {e}")
            result.error = str(e)
            result.completed_at = datetime.now()

            self._audit.log_operation(
                OperationType.RECOVER_MAILBOX,
                identity=request.source_identity,
                result="failure",
                error=str(e),
            )

            return result

    def _execute_recovery(
        self,
        request: RecoveryRequest,
        result: RecoveryResult,
    ) -> RecoveryResult:
        """Execute the actual recovery command.

        Args:
            request: Recovery request
            result: Result object to update

        Returns:
            Updated RecoveryResult
        """
        self._session.ensure_connected()

        # Build recovery command
        cmd = self._command_builder.build_new_mailbox_from_inactive(
            inactive_mailbox_guid=request.source_identity,
            display_name=request.display_name,
            upn=request.target_upn,
            password=request.password or self._generate_password(),
            first_name=request.first_name,
            last_name=request.last_name,
            reset_password=request.reset_password_on_logon,
        )

        logger.debug("Executing recovery command")

        # Execute with extended timeout for recovery operations
        ps_result = self._session.connection.execute_command(cmd, timeout=300)

        if not ps_result.success:
            result.success = False
            result.error = ps_result.error
            logger.error(f"Recovery command failed: {ps_result.error}")
            return result

        # Parse result
        try:
            data = parse_json_output(ps_result.output)
            if isinstance(data, list):
                data = data[0] if data else {}

            result.success = True
            result.new_mailbox_guid = data.get("ExchangeGuid") or data.get("Guid")
            result.new_upn = data.get("UserPrincipalName") or request.target_upn
            result.raw_output = data

            logger.info(f"Recovery successful: {result.new_upn} ({result.new_mailbox_guid})")

        except Exception as e:
            # Command succeeded but output parsing failed
            # Assume success if no error was raised
            result.success = True
            result.new_upn = request.target_upn
            logger.warning(f"Recovery likely succeeded but output parsing failed: {e}")

        return result

    def _generate_password(self) -> str:
        """Generate a secure random password.

        Returns:
            Random password string meeting complexity requirements
        """
        # Ensure at least one of each required character type
        password = [
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.digits),
            secrets.choice("!@#$%^&*"),
        ]

        # Fill remaining length with random characters
        remaining_length = self.PASSWORD_LENGTH - len(password)
        password.extend(
            secrets.choice(self.PASSWORD_CHARS) for _ in range(remaining_length)
        )

        # Shuffle to avoid predictable positions
        password_list = list(password)
        secrets.SystemRandom().shuffle(password_list)

        return "".join(password_list)

    def get_recovery_status(self, guid: str) -> str:
        """Check if a recovered mailbox is fully provisioned.

        Args:
            guid: Mailbox GUID to check

        Returns:
            Status string (Provisioning, Active, Failed)
        """
        if not self._session.connection or not self._session.connection.is_connected:
            return "Unknown"

        cmd = self._command_builder.build_check_mailbox_exists(guid)
        result = self._session.connection.execute_command(cmd, timeout=30)

        if result.success and result.output.strip():
            return "Active"
        return "Provisioning"

    def wait_for_provisioning(
        self,
        guid: str,
        timeout: int = 300,
        poll_interval: int = 10,
    ) -> bool:
        """Wait for mailbox provisioning to complete.

        Args:
            guid: Mailbox GUID
            timeout: Maximum wait time in seconds
            poll_interval: Time between status checks

        Returns:
            True if mailbox is active, False if timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = self.get_recovery_status(guid)
            if status == "Active":
                return True

            logger.debug(f"Mailbox {guid} status: {status}, waiting...")
            time.sleep(poll_interval)

        logger.warning(f"Mailbox {guid} provisioning timed out after {timeout}s")
        return False

    def suggest_target_details(self, source_mailbox: dict[str, Any]) -> dict[str, str]:
        """Suggest target details based on source mailbox.

        Args:
            source_mailbox: Source mailbox data

        Returns:
            Dictionary with suggested values
        """
        display_name = source_mailbox.get("DisplayName", "")
        primary_smtp = source_mailbox.get("PrimarySmtpAddress", "")
        upn = source_mailbox.get("UserPrincipalName", primary_smtp)

        # Extract name parts
        name_parts = display_name.split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        return {
            "display_name": display_name,
            "target_upn": upn,
            "target_smtp": primary_smtp,
            "first_name": first_name,
            "last_name": last_name,
        }
