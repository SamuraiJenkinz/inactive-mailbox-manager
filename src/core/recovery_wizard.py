"""Recovery wizard for guided mailbox recovery operations."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from src.core.recovery_service import RecoveryRequest, RecoveryResult, RecoveryService
from src.core.recovery_validator import RecoveryValidator, ValidationResult
from src.data.models import InactiveMailbox
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.data.session import SessionManager

logger = get_logger(__name__)


class WizardStep(Enum):
    """Steps in the recovery wizard."""

    SELECT_MAILBOX = auto()
    VALIDATE_RECOVERY = auto()
    ENTER_DETAILS = auto()
    CONFIRM_RECOVERY = auto()
    EXECUTE_RECOVERY = auto()
    SHOW_RESULT = auto()
    CANCELLED = auto()
    ERROR = auto()


@dataclass
class WizardState:
    """Current state of the recovery wizard."""

    current_step: WizardStep = WizardStep.SELECT_MAILBOX
    selected_mailbox: InactiveMailbox | None = None
    validation_result: ValidationResult | None = None
    recovery_request: RecoveryRequest | None = None
    recovery_result: RecoveryResult | None = None
    errors: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)

    # Suggested values for user
    suggested_upn: str = ""
    suggested_smtp: str = ""
    suggested_display_name: str = ""
    suggested_first_name: str = ""
    suggested_last_name: str = ""

    @property
    def can_proceed(self) -> bool:
        """Check if user can proceed to next step."""
        if self.current_step == WizardStep.SELECT_MAILBOX:
            return self.selected_mailbox is not None

        if self.current_step == WizardStep.VALIDATE_RECOVERY:
            return (
                self.validation_result is not None
                and self.validation_result.can_proceed
            )

        if self.current_step == WizardStep.ENTER_DETAILS:
            return self.recovery_request is not None

        if self.current_step == WizardStep.CONFIRM_RECOVERY:
            return True

        if self.current_step == WizardStep.EXECUTE_RECOVERY:
            return self.recovery_result is not None

        return False

    @property
    def can_go_back(self) -> bool:
        """Check if user can go back to previous step."""
        return self.current_step not in [
            WizardStep.SELECT_MAILBOX,
            WizardStep.EXECUTE_RECOVERY,
            WizardStep.SHOW_RESULT,
            WizardStep.CANCELLED,
            WizardStep.ERROR,
        ]

    @property
    def is_complete(self) -> bool:
        """Check if wizard is complete."""
        return self.current_step in [
            WizardStep.SHOW_RESULT,
            WizardStep.CANCELLED,
            WizardStep.ERROR,
        ]

    def get_step_number(self) -> int:
        """Get current step number (1-based)."""
        step_order = [
            WizardStep.SELECT_MAILBOX,
            WizardStep.VALIDATE_RECOVERY,
            WizardStep.ENTER_DETAILS,
            WizardStep.CONFIRM_RECOVERY,
            WizardStep.EXECUTE_RECOVERY,
            WizardStep.SHOW_RESULT,
        ]
        try:
            return step_order.index(self.current_step) + 1
        except ValueError:
            return 0

    @property
    def total_steps(self) -> int:
        """Get total number of steps."""
        return 6

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary for display/logging."""
        return {
            "step": self.current_step.name,
            "step_number": self.get_step_number(),
            "total_steps": self.total_steps,
            "can_proceed": self.can_proceed,
            "can_go_back": self.can_go_back,
            "is_complete": self.is_complete,
            "selected_mailbox": (
                self.selected_mailbox.identity if self.selected_mailbox else None
            ),
            "has_validation": self.validation_result is not None,
            "has_request": self.recovery_request is not None,
            "has_result": self.recovery_result is not None,
            "errors": self.errors,
        }


class RecoveryWizard:
    """Guided wizard for recovering inactive mailboxes.

    Provides a step-by-step process for safely recovering
    inactive mailboxes with validation and confirmation.
    """

    def __init__(self, session: "SessionManager") -> None:
        """Initialize recovery wizard.

        Args:
            session: Session manager with active connection
        """
        self._session = session
        self._validator = RecoveryValidator(session)
        self._recovery_service = RecoveryService(session, self._validator)
        self._state = WizardState()

        logger.debug("RecoveryWizard initialized")

    def start(self) -> WizardState:
        """Start a new recovery wizard session.

        Returns:
            Initial wizard state
        """
        self._state = WizardState()
        self._state.messages.append("Select an inactive mailbox to recover")
        logger.info("Recovery wizard started")
        return self._state

    def get_state(self) -> WizardState:
        """Get current wizard state.

        Returns:
            Current WizardState
        """
        return self._state

    def select_mailbox(self, mailbox: InactiveMailbox) -> WizardState:
        """Select a mailbox for recovery.

        Args:
            mailbox: Mailbox to recover

        Returns:
            Updated wizard state
        """
        if self._state.current_step != WizardStep.SELECT_MAILBOX:
            self._state.errors.append("Cannot select mailbox at this step")
            return self._state

        self._state.selected_mailbox = mailbox
        self._state.messages.clear()
        self._state.messages.append(f"Selected: {mailbox.display_name}")

        # Populate suggested values
        self._populate_suggestions(mailbox)

        # Auto-advance to validation
        self._state.current_step = WizardStep.VALIDATE_RECOVERY
        self._state.messages.append("Validating recovery eligibility...")

        logger.info(f"Mailbox selected: {mailbox.identity}")
        return self._state

    def select_mailbox_by_identity(self, identity: str) -> WizardState:
        """Select a mailbox by identity (GUID or email).

        Args:
            identity: Mailbox identity

        Returns:
            Updated wizard state
        """
        # Look up mailbox from cache
        mailbox = self._session.database.get_mailbox(identity)

        if mailbox is None:
            self._state.errors.append(f"Mailbox not found: {identity}")
            return self._state

        return self.select_mailbox(mailbox)

    def _populate_suggestions(self, mailbox: InactiveMailbox) -> None:
        """Populate suggested values from mailbox data.

        Args:
            mailbox: Selected mailbox
        """
        self._state.suggested_display_name = mailbox.display_name
        self._state.suggested_upn = mailbox.user_principal_name or mailbox.primary_smtp
        self._state.suggested_smtp = mailbox.primary_smtp

        # Parse name parts
        if mailbox.display_name:
            parts = mailbox.display_name.split(" ", 1)
            self._state.suggested_first_name = parts[0] if parts else ""
            self._state.suggested_last_name = parts[1] if len(parts) > 1 else ""

    def validate(self) -> WizardState:
        """Perform validation on selected mailbox.

        Returns:
            Updated wizard state
        """
        if self._state.current_step != WizardStep.VALIDATE_RECOVERY:
            self._state.errors.append("Cannot validate at this step")
            return self._state

        if self._state.selected_mailbox is None:
            self._state.errors.append("No mailbox selected")
            return self._state

        try:
            # Perform validation
            self._state.validation_result = self._validator.validate_recovery(
                self._state.selected_mailbox.identity
            )

            self._state.messages.clear()

            if self._state.validation_result.is_valid:
                self._state.messages.append("Validation passed - mailbox can be recovered")
                self._state.current_step = WizardStep.ENTER_DETAILS
            elif self._state.validation_result.can_proceed:
                self._state.messages.append(
                    f"Validation passed with {len(self._state.validation_result.warnings)} warning(s)"
                )
                self._state.current_step = WizardStep.ENTER_DETAILS
            else:
                self._state.messages.append("Validation failed - see errors below")
                for blocker in self._state.validation_result.blockers:
                    self._state.errors.append(blocker)

            logger.info(
                f"Validation complete: valid={self._state.validation_result.is_valid}, "
                f"can_proceed={self._state.validation_result.can_proceed}"
            )

        except Exception as e:
            self._state.errors.append(f"Validation failed: {str(e)}")
            logger.error(f"Validation exception: {e}")

        return self._state

    def set_recovery_details(
        self,
        target_upn: str,
        target_smtp: str | None = None,
        display_name: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        password: str | None = None,
    ) -> WizardState:
        """Set recovery target details.

        Args:
            target_upn: Target UPN for new mailbox
            target_smtp: Target SMTP address (defaults to UPN)
            display_name: Display name for new mailbox
            first_name: First name
            last_name: Last name
            password: Password (auto-generated if not provided)

        Returns:
            Updated wizard state
        """
        if self._state.current_step != WizardStep.ENTER_DETAILS:
            self._state.errors.append("Cannot set details at this step")
            return self._state

        if self._state.selected_mailbox is None:
            self._state.errors.append("No mailbox selected")
            return self._state

        # Validate target conflicts
        conflict_result = self._validator.validate_recovery(
            self._state.selected_mailbox.identity,
            target_upn=target_upn,
            target_smtp=target_smtp or target_upn,
        )

        if not conflict_result.can_proceed:
            self._state.messages.clear()
            for error in conflict_result.errors:
                self._state.errors.append(error.message)
            return self._state

        # Create recovery request
        self._state.recovery_request = RecoveryRequest(
            source_identity=self._state.selected_mailbox.identity,
            target_upn=target_upn,
            target_smtp=target_smtp,
            display_name=display_name or self._state.suggested_display_name,
            first_name=first_name or self._state.suggested_first_name,
            last_name=last_name or self._state.suggested_last_name,
            password=password,
        )

        self._state.messages.clear()
        self._state.messages.append("Recovery details configured")
        self._state.current_step = WizardStep.CONFIRM_RECOVERY

        logger.info(f"Recovery details set: {target_upn}")
        return self._state

    def confirm(self) -> WizardState:
        """Confirm recovery and prepare for execution.

        Returns:
            Updated wizard state
        """
        if self._state.current_step != WizardStep.CONFIRM_RECOVERY:
            self._state.errors.append("Cannot confirm at this step")
            return self._state

        self._state.messages.clear()
        self._state.messages.append("Ready to execute recovery")
        self._state.current_step = WizardStep.EXECUTE_RECOVERY

        logger.info("Recovery confirmed, ready to execute")
        return self._state

    def execute(self) -> WizardState:
        """Execute the recovery operation.

        Returns:
            Updated wizard state
        """
        if self._state.current_step != WizardStep.EXECUTE_RECOVERY:
            self._state.errors.append("Cannot execute at this step")
            return self._state

        if self._state.recovery_request is None:
            self._state.errors.append("No recovery request configured")
            return self._state

        try:
            self._state.messages.clear()
            self._state.messages.append("Executing recovery...")

            # Execute recovery (skip validation - already done)
            self._state.recovery_result = self._recovery_service.recover_mailbox(
                self._state.recovery_request,
                skip_validation=True,
            )

            if self._state.recovery_result.success:
                self._state.messages.append(
                    f"Recovery successful! New mailbox: {self._state.recovery_result.new_upn}"
                )
            else:
                self._state.errors.append(
                    f"Recovery failed: {self._state.recovery_result.error}"
                )

            self._state.current_step = WizardStep.SHOW_RESULT
            logger.info(f"Recovery executed: success={self._state.recovery_result.success}")

        except Exception as e:
            self._state.errors.append(f"Recovery failed: {str(e)}")
            self._state.current_step = WizardStep.ERROR
            logger.error(f"Recovery exception: {e}")

        return self._state

    def go_back(self) -> WizardState:
        """Go back to previous step.

        Returns:
            Updated wizard state
        """
        if not self._state.can_go_back:
            self._state.errors.append("Cannot go back from this step")
            return self._state

        step_order = [
            WizardStep.SELECT_MAILBOX,
            WizardStep.VALIDATE_RECOVERY,
            WizardStep.ENTER_DETAILS,
            WizardStep.CONFIRM_RECOVERY,
        ]

        try:
            current_index = step_order.index(self._state.current_step)
            if current_index > 0:
                self._state.current_step = step_order[current_index - 1]
                self._state.errors.clear()
                self._state.messages.clear()
                logger.debug(f"Went back to step: {self._state.current_step.name}")
        except ValueError:
            pass

        return self._state

    def cancel(self) -> WizardState:
        """Cancel the recovery wizard.

        Returns:
            Cancelled wizard state
        """
        self._state.current_step = WizardStep.CANCELLED
        self._state.messages.clear()
        self._state.messages.append("Recovery cancelled")
        logger.info("Recovery wizard cancelled")
        return self._state

    def reset(self) -> WizardState:
        """Reset wizard to start a new recovery.

        Returns:
            Fresh wizard state
        """
        return self.start()

    def get_summary(self) -> dict[str, Any]:
        """Get summary of current wizard state for display.

        Returns:
            Summary dictionary
        """
        summary = {
            "step": self._state.current_step.name,
            "step_number": self._state.get_step_number(),
            "total_steps": self._state.total_steps,
            "can_proceed": self._state.can_proceed,
            "can_go_back": self._state.can_go_back,
        }

        if self._state.selected_mailbox:
            summary["source"] = {
                "identity": self._state.selected_mailbox.identity,
                "display_name": self._state.selected_mailbox.display_name,
                "email": self._state.selected_mailbox.primary_smtp,
            }

        if self._state.recovery_request:
            summary["target"] = {
                "upn": self._state.recovery_request.target_upn,
                "smtp": self._state.recovery_request.target_smtp,
                "display_name": self._state.recovery_request.display_name,
            }

        if self._state.validation_result:
            summary["validation"] = {
                "is_valid": self._state.validation_result.is_valid,
                "can_proceed": self._state.validation_result.can_proceed,
                "errors": len(self._state.validation_result.errors),
                "warnings": len(self._state.validation_result.warnings),
            }

        if self._state.recovery_result:
            summary["result"] = {
                "success": self._state.recovery_result.success,
                "new_guid": self._state.recovery_result.new_mailbox_guid,
                "duration": self._state.recovery_result.execution_time_seconds,
            }

        return summary
