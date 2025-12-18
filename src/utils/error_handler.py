"""
Centralized error handling service for Inactive Mailbox Manager.

Provides consistent error handling, logging, and user feedback across the application.
"""

import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from src.utils.exceptions import (
    AppException,
    AuthenticationError,
    BulkOperationError,
    ConfigurationError,
    ConnectionError,
    ErrorCode,
    PowerShellError,
    RecoveryError,
    RestoreError,
    ValidationError,
)


class ErrorSeverity(Enum):
    """Severity levels for errors."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ErrorResult:
    """Result of error handling with user-friendly information."""

    success: bool
    message: str
    code: ErrorCode | None = None
    severity: ErrorSeverity = ErrorSeverity.ERROR
    suggestions: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    can_retry: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "message": self.message,
            "code": self.code.value if self.code else None,
            "severity": self.severity.value,
            "suggestions": self.suggestions,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "can_retry": self.can_retry,
        }


class ErrorHandler:
    """
    Centralized error handler for the application.

    Catches exceptions, logs appropriately, and returns user-friendly error information.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._error_callbacks: list[Callable[[ErrorResult], None]] = []

    def register_callback(self, callback: Callable[[ErrorResult], None]) -> None:
        """Register a callback to be notified of errors."""
        self._error_callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[ErrorResult], None]) -> None:
        """Unregister an error callback."""
        if callback in self._error_callbacks:
            self._error_callbacks.remove(callback)

    def _notify_callbacks(self, result: ErrorResult) -> None:
        """Notify all registered callbacks of an error."""
        for callback in self._error_callbacks:
            try:
                callback(result)
            except Exception as e:
                self._logger.warning(f"Error callback failed: {e}")

    def handle(self, exception: Exception) -> ErrorResult:
        """
        Handle an exception and return user-friendly error information.

        Args:
            exception: The exception to handle

        Returns:
            ErrorResult with user-friendly message and suggestions
        """
        result = self._create_error_result(exception)
        self._log_error(exception, result)
        self._notify_callbacks(result)
        return result

    def _create_error_result(self, exception: Exception) -> ErrorResult:
        """Create an ErrorResult from an exception."""
        if isinstance(exception, AppException):
            return self._handle_app_exception(exception)
        else:
            return self._handle_unknown_exception(exception)

    def _handle_app_exception(self, exception: AppException) -> ErrorResult:
        """Handle application-specific exceptions."""
        severity = self._determine_severity(exception)
        can_retry = self._can_retry(exception)

        return ErrorResult(
            success=False,
            message=exception.user_message,
            code=exception.code,
            severity=severity,
            suggestions=exception.suggestions,
            details=exception.details,
            can_retry=can_retry,
        )

    def _handle_unknown_exception(self, exception: Exception) -> ErrorResult:
        """Handle unknown/unexpected exceptions."""
        # Map common Python exceptions to appropriate error codes
        code = self._map_exception_to_code(exception)
        message = self._get_user_message_for_exception(exception, code)

        return ErrorResult(
            success=False,
            message=message,
            code=code,
            severity=ErrorSeverity.ERROR,
            suggestions=["Check the logs for more details", "Try the operation again"],
            details={"exception_type": type(exception).__name__},
            can_retry=True,
        )

    def _map_exception_to_code(self, exception: Exception) -> ErrorCode:
        """Map standard Python exceptions to error codes."""
        exception_type = type(exception).__name__

        mapping = {
            "TimeoutError": ErrorCode.CONNECTION_TIMEOUT,
            "ConnectionError": ErrorCode.CONNECTION_FAILED,
            "FileNotFoundError": ErrorCode.CONFIG_NOT_FOUND,
            "PermissionError": ErrorCode.CONFIG_PERMISSION_DENIED,
            "ValueError": ErrorCode.VALIDATION_FAILED,
            "KeyError": ErrorCode.CONFIG_MISSING_REQUIRED,
            "OSError": ErrorCode.INTERNAL_ERROR,
        }

        return mapping.get(exception_type, ErrorCode.UNKNOWN_ERROR)

    def _get_user_message_for_exception(
        self, exception: Exception, code: ErrorCode
    ) -> str:
        """Get a user-friendly message for a standard exception."""
        from src.utils.exceptions import ERROR_MESSAGES

        # Use template message if available
        if code in ERROR_MESSAGES:
            return ERROR_MESSAGES[code]

        # Otherwise, create a generic message
        return f"An error occurred: {str(exception)}"

    def _determine_severity(self, exception: AppException) -> ErrorSeverity:
        """Determine the severity level of an exception."""
        critical_codes = {
            ErrorCode.INTERNAL_ERROR,
            ErrorCode.POWERSHELL_NOT_FOUND,
            ErrorCode.SERVICE_UNAVAILABLE,
        }

        warning_codes = {
            ErrorCode.AUTH_EXPIRED,
            ErrorCode.CONNECTION_LOST,
            ErrorCode.RATE_LIMITED,
            ErrorCode.BULK_PARTIAL_FAILURE,
        }

        if exception.code in critical_codes:
            return ErrorSeverity.CRITICAL
        elif exception.code in warning_codes:
            return ErrorSeverity.WARNING
        else:
            return ErrorSeverity.ERROR

    def _can_retry(self, exception: AppException) -> bool:
        """Determine if the operation can be retried."""
        retryable_codes = {
            ErrorCode.CONNECTION_FAILED,
            ErrorCode.CONNECTION_TIMEOUT,
            ErrorCode.CONNECTION_LOST,
            ErrorCode.AUTH_EXPIRED,
            ErrorCode.RATE_LIMITED,
            ErrorCode.SERVICE_UNAVAILABLE,
        }

        return exception.code in retryable_codes

    def _log_error(self, exception: Exception, result: ErrorResult) -> None:
        """Log the error with appropriate level."""
        log_message = f"[{result.code.name if result.code else 'UNKNOWN'}] {result.message}"

        if result.severity == ErrorSeverity.CRITICAL:
            self._logger.critical(log_message, exc_info=exception)
        elif result.severity == ErrorSeverity.ERROR:
            self._logger.error(log_message, exc_info=exception)
        elif result.severity == ErrorSeverity.WARNING:
            self._logger.warning(log_message)
        else:
            self._logger.info(log_message)

    def wrap(
        self, func: Callable, default_return: Any = None
    ) -> Callable[..., tuple[Any, ErrorResult | None]]:
        """
        Wrap a function with error handling.

        Returns a tuple of (result, error) where error is None on success.
        """

        def wrapper(*args: Any, **kwargs: Any) -> tuple[Any, ErrorResult | None]:
            try:
                result = func(*args, **kwargs)
                return result, None
            except Exception as e:
                error_result = self.handle(e)
                return default_return, error_result

        return wrapper

    def safe_execute(
        self, func: Callable, *args: Any, **kwargs: Any
    ) -> tuple[Any, ErrorResult | None]:
        """
        Safely execute a function with error handling.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Tuple of (result, error) where error is None on success
        """
        try:
            result = func(*args, **kwargs)
            return result, None
        except Exception as e:
            error_result = self.handle(e)
            return None, error_result


# Global error handler instance
_error_handler: ErrorHandler | None = None


def get_error_handler() -> ErrorHandler:
    """Get the global error handler instance."""
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler()
    return _error_handler


def handle_error(exception: Exception) -> ErrorResult:
    """Convenience function to handle an error using the global handler."""
    return get_error_handler().handle(exception)


def format_error_for_display(result: ErrorResult) -> str:
    """
    Format an error result for display in the UI.

    Returns a multi-line string suitable for display.
    """
    lines = [
        f"Error: {result.message}",
        "",
    ]

    if result.code:
        lines.append(f"Error Code: {result.code.name} ({result.code.value})")

    if result.suggestions:
        lines.append("")
        lines.append("Suggestions:")
        for suggestion in result.suggestions:
            lines.append(f"  - {suggestion}")

    if result.can_retry:
        lines.append("")
        lines.append("This operation can be retried.")

    return "\n".join(lines)


def format_error_for_log(result: ErrorResult, include_traceback: bool = True) -> str:
    """
    Format an error result for logging.

    Returns a detailed string suitable for log files.
    """
    lines = [
        f"Timestamp: {result.timestamp.isoformat()}",
        f"Severity: {result.severity.value.upper()}",
        f"Code: {result.code.name if result.code else 'UNKNOWN'} ({result.code.value if result.code else 'N/A'})",
        f"Message: {result.message}",
    ]

    if result.details:
        lines.append("Details:")
        for key, value in result.details.items():
            lines.append(f"  {key}: {value}")

    return "\n".join(lines)
