"""
Custom exception hierarchy for Inactive Mailbox Manager.

Provides categorized exceptions with error codes, user-friendly messages,
and recovery suggestions.
"""

from enum import Enum
from typing import Any


class ErrorCode(Enum):
    """Error codes for categorizing exceptions."""

    # Connection errors (1xxx)
    CONNECTION_FAILED = 1001
    CONNECTION_TIMEOUT = 1002
    CONNECTION_LOST = 1003
    NETWORK_UNAVAILABLE = 1004

    # Authentication errors (2xxx)
    AUTH_FAILED = 2001
    AUTH_EXPIRED = 2002
    AUTH_INVALID_CREDENTIALS = 2003
    AUTH_CERTIFICATE_ERROR = 2004
    AUTH_MFA_REQUIRED = 2005
    AUTH_INSUFFICIENT_PERMISSIONS = 2006

    # Configuration errors (3xxx)
    CONFIG_NOT_FOUND = 3001
    CONFIG_INVALID = 3002
    CONFIG_MISSING_REQUIRED = 3003
    CONFIG_PERMISSION_DENIED = 3004

    # Validation errors (4xxx)
    VALIDATION_FAILED = 4001
    VALIDATION_UPN_EXISTS = 4002
    VALIDATION_SMTP_CONFLICT = 4003
    VALIDATION_MAILBOX_NOT_FOUND = 4004
    VALIDATION_HOLD_BLOCKING = 4005
    VALIDATION_AUXPRIMARY_DETECTED = 4006

    # Recovery errors (5xxx)
    RECOVERY_FAILED = 5001
    RECOVERY_MAILBOX_LOCKED = 5002
    RECOVERY_INSUFFICIENT_QUOTA = 5003
    RECOVERY_ARCHIVE_ERROR = 5004

    # Restore errors (6xxx)
    RESTORE_FAILED = 6001
    RESTORE_TARGET_NOT_FOUND = 6002
    RESTORE_CONFLICT = 6003
    RESTORE_QUOTA_EXCEEDED = 6004

    # Bulk operation errors (7xxx)
    BULK_OPERATION_FAILED = 7001
    BULK_CSV_INVALID = 7002
    BULK_PARTIAL_FAILURE = 7003

    # PowerShell errors (8xxx)
    POWERSHELL_NOT_FOUND = 8001
    POWERSHELL_MODULE_MISSING = 8002
    POWERSHELL_EXECUTION_FAILED = 8003
    POWERSHELL_PARSE_ERROR = 8004

    # General errors (9xxx)
    UNKNOWN_ERROR = 9001
    INTERNAL_ERROR = 9002
    RATE_LIMITED = 9003
    SERVICE_UNAVAILABLE = 9004


# User-friendly message templates
ERROR_MESSAGES: dict[ErrorCode, str] = {
    # Connection
    ErrorCode.CONNECTION_FAILED: "Unable to connect to Exchange Online. Please check your network connection and try again.",
    ErrorCode.CONNECTION_TIMEOUT: "Connection to Exchange Online timed out. The service may be busy - please try again.",
    ErrorCode.CONNECTION_LOST: "Lost connection to Exchange Online. Attempting to reconnect...",
    ErrorCode.NETWORK_UNAVAILABLE: "Network is unavailable. Please check your internet connection.",

    # Authentication
    ErrorCode.AUTH_FAILED: "Authentication failed. Please verify your credentials and try again.",
    ErrorCode.AUTH_EXPIRED: "Your session has expired. Please reconnect to continue.",
    ErrorCode.AUTH_INVALID_CREDENTIALS: "Invalid credentials. Please check your Application ID and certificate/secret.",
    ErrorCode.AUTH_CERTIFICATE_ERROR: "Certificate error. Please verify the certificate path and password.",
    ErrorCode.AUTH_MFA_REQUIRED: "Multi-factor authentication is required. Please use certificate-based authentication.",
    ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS: "Insufficient permissions. Please ensure the app has Exchange.ManageAsApp permission.",

    # Configuration
    ErrorCode.CONFIG_NOT_FOUND: "Configuration file not found. Please run the setup wizard to create one.",
    ErrorCode.CONFIG_INVALID: "Configuration file is invalid. Please check the format and try again.",
    ErrorCode.CONFIG_MISSING_REQUIRED: "Required configuration is missing. Please complete the setup.",
    ErrorCode.CONFIG_PERMISSION_DENIED: "Cannot access configuration file. Please check file permissions.",

    # Validation
    ErrorCode.VALIDATION_FAILED: "Validation failed. Please review the errors and try again.",
    ErrorCode.VALIDATION_UPN_EXISTS: "The target User Principal Name already exists. Please choose a different UPN.",
    ErrorCode.VALIDATION_SMTP_CONFLICT: "The email address is already in use. Please choose a different address.",
    ErrorCode.VALIDATION_MAILBOX_NOT_FOUND: "The specified mailbox was not found. It may have been deleted.",
    ErrorCode.VALIDATION_HOLD_BLOCKING: "Operation blocked by legal hold. Contact your compliance team.",
    ErrorCode.VALIDATION_AUXPRIMARY_DETECTED: "AuxPrimary shard detected. This mailbox may require special handling.",

    # Recovery
    ErrorCode.RECOVERY_FAILED: "Recovery operation failed. Please check the error details and try again.",
    ErrorCode.RECOVERY_MAILBOX_LOCKED: "Mailbox is locked and cannot be recovered at this time.",
    ErrorCode.RECOVERY_INSUFFICIENT_QUOTA: "Insufficient quota to recover this mailbox.",
    ErrorCode.RECOVERY_ARCHIVE_ERROR: "Error processing archive mailbox during recovery.",

    # Restore
    ErrorCode.RESTORE_FAILED: "Restore operation failed. Please check the target mailbox and try again.",
    ErrorCode.RESTORE_TARGET_NOT_FOUND: "Target mailbox not found. Please verify it exists and is active.",
    ErrorCode.RESTORE_CONFLICT: "Content conflict detected during restore. Check conflict resolution settings.",
    ErrorCode.RESTORE_QUOTA_EXCEEDED: "Target mailbox quota exceeded. Free up space or choose a different target.",

    # Bulk
    ErrorCode.BULK_OPERATION_FAILED: "Bulk operation failed. Check the detailed results for specific errors.",
    ErrorCode.BULK_CSV_INVALID: "CSV file is invalid. Please check the format and required columns.",
    ErrorCode.BULK_PARTIAL_FAILURE: "Some operations failed. Check the results for details.",

    # PowerShell
    ErrorCode.POWERSHELL_NOT_FOUND: "PowerShell not found. Please install PowerShell Core 7 or later.",
    ErrorCode.POWERSHELL_MODULE_MISSING: "Exchange Online Management module not installed. Run: Install-Module ExchangeOnlineManagement",
    ErrorCode.POWERSHELL_EXECUTION_FAILED: "PowerShell command failed. Check the logs for details.",
    ErrorCode.POWERSHELL_PARSE_ERROR: "Failed to parse PowerShell output. This may indicate a version mismatch.",

    # General
    ErrorCode.UNKNOWN_ERROR: "An unexpected error occurred. Please check the logs for details.",
    ErrorCode.INTERNAL_ERROR: "An internal error occurred. Please try again or contact support.",
    ErrorCode.RATE_LIMITED: "Request rate limit exceeded. Please wait a moment and try again.",
    ErrorCode.SERVICE_UNAVAILABLE: "Exchange Online service is temporarily unavailable. Please try again later.",
}

# Recovery suggestions for each error code
RECOVERY_SUGGESTIONS: dict[ErrorCode, list[str]] = {
    ErrorCode.CONNECTION_FAILED: [
        "Check your internet connection",
        "Verify the organization name in settings",
        "Try again in a few minutes",
        "Check Exchange Online service status",
    ],
    ErrorCode.AUTH_FAILED: [
        "Verify your Application ID is correct",
        "Check that admin consent was granted",
        "Ensure the certificate/secret hasn't expired",
        "Try re-authenticating",
    ],
    ErrorCode.AUTH_CERTIFICATE_ERROR: [
        "Verify the certificate file path",
        "Check the certificate password",
        "Ensure the certificate hasn't expired",
        "Verify the public key is uploaded to Azure AD",
    ],
    ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS: [
        "Add Exchange.ManageAsApp permission in Azure AD",
        "Grant admin consent for the permission",
        "Assign Exchange Administrator role to the app",
        "Wait a few minutes for permissions to propagate",
    ],
    ErrorCode.CONFIG_NOT_FOUND: [
        "Run the onboarding wizard to create configuration",
        "Copy config.example.yaml to config.yaml",
        "Check the application directory for config files",
    ],
    ErrorCode.VALIDATION_UPN_EXISTS: [
        "Choose a different User Principal Name",
        "Check for soft-deleted users with the same UPN",
        "Add a suffix to make the UPN unique (e.g., .recovered)",
    ],
    ErrorCode.VALIDATION_SMTP_CONFLICT: [
        "Check existing mailboxes for the email address",
        "Check groups and distribution lists",
        "Remove the address from conflicting objects first",
    ],
    ErrorCode.POWERSHELL_NOT_FOUND: [
        "Install PowerShell Core 7: https://github.com/PowerShell/PowerShell",
        "Add PowerShell to your system PATH",
        "Restart the application after installation",
    ],
    ErrorCode.POWERSHELL_MODULE_MISSING: [
        "Open PowerShell as administrator",
        "Run: Install-Module ExchangeOnlineManagement -Force",
        "Restart the application",
    ],
    ErrorCode.RATE_LIMITED: [
        "Wait 1-2 minutes before retrying",
        "Reduce the batch size for bulk operations",
        "Schedule large operations during off-peak hours",
    ],
}


class AppException(Exception):
    """Base exception for all application errors."""

    def __init__(
        self,
        message: str | None = None,
        code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.code = code
        self.details = details or {}
        self.cause = cause

        # Use provided message or default from templates
        self.message = message or ERROR_MESSAGES.get(code, "An error occurred")

        super().__init__(self.message)

    @property
    def user_message(self) -> str:
        """Get user-friendly error message."""
        return self.message

    @property
    def suggestions(self) -> list[str]:
        """Get recovery suggestions for this error."""
        return RECOVERY_SUGGESTIONS.get(self.code, [])

    @property
    def error_code(self) -> int:
        """Get numeric error code."""
        return self.code.value

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for serialization."""
        return {
            "code": self.code.value,
            "code_name": self.code.name,
            "message": self.message,
            "details": self.details,
            "suggestions": self.suggestions,
        }


class ConnectionError(AppException):
    """Raised when connection to Exchange Online fails."""

    def __init__(
        self,
        message: str | None = None,
        code: ErrorCode = ErrorCode.CONNECTION_FAILED,
        **kwargs: Any,
    ) -> None:
        super().__init__(message=message, code=code, **kwargs)


class AuthenticationError(AppException):
    """Raised when authentication fails."""

    def __init__(
        self,
        message: str | None = None,
        code: ErrorCode = ErrorCode.AUTH_FAILED,
        **kwargs: Any,
    ) -> None:
        super().__init__(message=message, code=code, **kwargs)


class ConfigurationError(AppException):
    """Raised when configuration is invalid or missing."""

    def __init__(
        self,
        message: str | None = None,
        code: ErrorCode = ErrorCode.CONFIG_INVALID,
        **kwargs: Any,
    ) -> None:
        super().__init__(message=message, code=code, **kwargs)


class ValidationError(AppException):
    """Raised when validation fails."""

    def __init__(
        self,
        message: str | None = None,
        code: ErrorCode = ErrorCode.VALIDATION_FAILED,
        field: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if field:
            details["field"] = field
        super().__init__(message=message, code=code, details=details, **kwargs)


class RecoveryError(AppException):
    """Raised when mailbox recovery fails."""

    def __init__(
        self,
        message: str | None = None,
        code: ErrorCode = ErrorCode.RECOVERY_FAILED,
        mailbox: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if mailbox:
            details["mailbox"] = mailbox
        super().__init__(message=message, code=code, details=details, **kwargs)


class RestoreError(AppException):
    """Raised when mailbox restore fails."""

    def __init__(
        self,
        message: str | None = None,
        code: ErrorCode = ErrorCode.RESTORE_FAILED,
        source_mailbox: str | None = None,
        target_mailbox: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if source_mailbox:
            details["source_mailbox"] = source_mailbox
        if target_mailbox:
            details["target_mailbox"] = target_mailbox
        super().__init__(message=message, code=code, details=details, **kwargs)


class BulkOperationError(AppException):
    """Raised when bulk operations fail."""

    def __init__(
        self,
        message: str | None = None,
        code: ErrorCode = ErrorCode.BULK_OPERATION_FAILED,
        succeeded: int = 0,
        failed: int = 0,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        details["succeeded"] = succeeded
        details["failed"] = failed
        super().__init__(message=message, code=code, details=details, **kwargs)


class PowerShellError(AppException):
    """Raised when PowerShell execution fails."""

    def __init__(
        self,
        message: str | None = None,
        code: ErrorCode = ErrorCode.POWERSHELL_EXECUTION_FAILED,
        command: str | None = None,
        stderr: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if command:
            details["command"] = command
        if stderr:
            details["stderr"] = stderr
        super().__init__(message=message, code=code, details=details, **kwargs)
