"""
Unit tests for exception handling.
"""

import pytest

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
    ERROR_MESSAGES,
    RECOVERY_SUGGESTIONS,
)
from src.utils.error_handler import (
    ErrorHandler,
    ErrorResult,
    ErrorSeverity,
    format_error_for_display,
    format_error_for_log,
    get_error_handler,
    handle_error,
)


class TestErrorCodes:
    """Tests for ErrorCode enum."""

    def test_connection_error_codes(self) -> None:
        """Test connection error codes are in 1xxx range."""
        assert ErrorCode.CONNECTION_FAILED.value == 1001
        assert ErrorCode.CONNECTION_TIMEOUT.value == 1002
        assert ErrorCode.CONNECTION_LOST.value == 1003

    def test_auth_error_codes(self) -> None:
        """Test auth error codes are in 2xxx range."""
        assert ErrorCode.AUTH_FAILED.value == 2001
        assert ErrorCode.AUTH_EXPIRED.value == 2002
        assert ErrorCode.AUTH_CERTIFICATE_ERROR.value == 2004

    def test_validation_error_codes(self) -> None:
        """Test validation error codes are in 4xxx range."""
        assert ErrorCode.VALIDATION_FAILED.value == 4001
        assert ErrorCode.VALIDATION_UPN_EXISTS.value == 4002

    def test_all_codes_have_messages(self) -> None:
        """Test all error codes have messages."""
        for code in ErrorCode:
            assert code in ERROR_MESSAGES, f"Missing message for {code.name}"


class TestAppException:
    """Tests for AppException base class."""

    def test_create_exception(self) -> None:
        """Test creating basic exception."""
        exc = AppException(message="Test error", code=ErrorCode.UNKNOWN_ERROR)
        assert str(exc) == "Test error"
        assert exc.code == ErrorCode.UNKNOWN_ERROR

    def test_default_message(self) -> None:
        """Test default message from templates."""
        exc = AppException(code=ErrorCode.CONNECTION_FAILED)
        assert "connect" in exc.message.lower()

    def test_exception_with_details(self) -> None:
        """Test exception with details."""
        exc = AppException(
            code=ErrorCode.VALIDATION_FAILED,
            details={"field": "email", "value": "invalid"},
        )
        assert exc.details["field"] == "email"

    def test_exception_with_cause(self) -> None:
        """Test exception chaining."""
        original = ValueError("Original error")
        exc = AppException(code=ErrorCode.INTERNAL_ERROR, cause=original)
        assert exc.cause is original

    def test_user_message_property(self) -> None:
        """Test user_message property."""
        exc = AppException(message="Custom message", code=ErrorCode.AUTH_FAILED)
        assert exc.user_message == "Custom message"

    def test_suggestions_property(self) -> None:
        """Test suggestions property."""
        exc = AppException(code=ErrorCode.AUTH_FAILED)
        suggestions = exc.suggestions
        assert isinstance(suggestions, list)

    def test_error_code_property(self) -> None:
        """Test error_code numeric property."""
        exc = AppException(code=ErrorCode.CONNECTION_TIMEOUT)
        assert exc.error_code == 1002

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        exc = AppException(
            message="Test",
            code=ErrorCode.CONFIG_INVALID,
            details={"path": "/config.yaml"},
        )
        data = exc.to_dict()
        assert data["code"] == ErrorCode.CONFIG_INVALID.value
        assert data["code_name"] == "CONFIG_INVALID"
        assert data["message"] == "Test"


class TestSpecializedExceptions:
    """Tests for specialized exception classes."""

    def test_connection_error(self) -> None:
        """Test ConnectionError."""
        exc = ConnectionError(code=ErrorCode.CONNECTION_TIMEOUT)
        assert exc.code == ErrorCode.CONNECTION_TIMEOUT

    def test_authentication_error(self) -> None:
        """Test AuthenticationError."""
        exc = AuthenticationError(code=ErrorCode.AUTH_CERTIFICATE_ERROR)
        assert exc.code == ErrorCode.AUTH_CERTIFICATE_ERROR

    def test_validation_error_with_field(self) -> None:
        """Test ValidationError with field."""
        exc = ValidationError(
            message="Invalid email",
            code=ErrorCode.VALIDATION_FAILED,
            field="email",
        )
        assert exc.details["field"] == "email"

    def test_recovery_error_with_mailbox(self) -> None:
        """Test RecoveryError with mailbox."""
        exc = RecoveryError(
            code=ErrorCode.RECOVERY_FAILED,
            mailbox="user@contoso.com",
        )
        assert exc.details["mailbox"] == "user@contoso.com"

    def test_restore_error_with_mailboxes(self) -> None:
        """Test RestoreError with source and target."""
        exc = RestoreError(
            code=ErrorCode.RESTORE_FAILED,
            source_mailbox="source@contoso.com",
            target_mailbox="target@contoso.com",
        )
        assert exc.details["source_mailbox"] == "source@contoso.com"
        assert exc.details["target_mailbox"] == "target@contoso.com"

    def test_bulk_operation_error(self) -> None:
        """Test BulkOperationError with counts."""
        exc = BulkOperationError(
            code=ErrorCode.BULK_PARTIAL_FAILURE,
            succeeded=8,
            failed=2,
        )
        assert exc.details["succeeded"] == 8
        assert exc.details["failed"] == 2

    def test_powershell_error(self) -> None:
        """Test PowerShellError with command."""
        exc = PowerShellError(
            code=ErrorCode.POWERSHELL_EXECUTION_FAILED,
            command="Get-Mailbox",
            stderr="Access denied",
        )
        assert exc.details["command"] == "Get-Mailbox"
        assert exc.details["stderr"] == "Access denied"


class TestErrorHandler:
    """Tests for ErrorHandler class."""

    def test_handle_app_exception(self) -> None:
        """Test handling AppException."""
        handler = ErrorHandler()
        exc = AuthenticationError(code=ErrorCode.AUTH_FAILED)
        result = handler.handle(exc)

        assert result.success is False
        assert result.code == ErrorCode.AUTH_FAILED
        assert isinstance(result.message, str)

    def test_handle_unknown_exception(self) -> None:
        """Test handling standard Python exception."""
        handler = ErrorHandler()
        exc = ValueError("Invalid value")
        result = handler.handle(exc)

        assert result.success is False
        assert result.code == ErrorCode.VALIDATION_FAILED

    def test_handle_timeout_error(self) -> None:
        """Test handling TimeoutError."""
        handler = ErrorHandler()
        exc = TimeoutError("Connection timed out")
        result = handler.handle(exc)

        assert result.code == ErrorCode.CONNECTION_TIMEOUT

    def test_severity_determination(self) -> None:
        """Test severity level determination."""
        handler = ErrorHandler()

        # Critical
        exc = AppException(code=ErrorCode.INTERNAL_ERROR)
        result = handler.handle(exc)
        assert result.severity == ErrorSeverity.CRITICAL

        # Warning
        exc = AppException(code=ErrorCode.RATE_LIMITED)
        result = handler.handle(exc)
        assert result.severity == ErrorSeverity.WARNING

    def test_can_retry(self) -> None:
        """Test retry capability detection."""
        handler = ErrorHandler()

        # Retryable
        exc = ConnectionError(code=ErrorCode.CONNECTION_TIMEOUT)
        result = handler.handle(exc)
        assert result.can_retry is True

        # Not retryable
        exc = ValidationError(code=ErrorCode.VALIDATION_UPN_EXISTS)
        result = handler.handle(exc)
        assert result.can_retry is False

    def test_safe_execute_success(self) -> None:
        """Test safe_execute with successful function."""
        handler = ErrorHandler()

        def success_func(x: int) -> int:
            return x * 2

        result, error = handler.safe_execute(success_func, 5)
        assert result == 10
        assert error is None

    def test_safe_execute_failure(self) -> None:
        """Test safe_execute with failing function."""
        handler = ErrorHandler()

        def fail_func() -> None:
            raise ValueError("Test error")

        result, error = handler.safe_execute(fail_func)
        assert result is None
        assert error is not None
        assert error.success is False

    def test_callback_registration(self) -> None:
        """Test error callback registration."""
        handler = ErrorHandler()
        received_errors: list[ErrorResult] = []

        def callback(result: ErrorResult) -> None:
            received_errors.append(result)

        handler.register_callback(callback)
        handler.handle(ValueError("Test"))

        assert len(received_errors) == 1
        assert received_errors[0].success is False


class TestErrorFormatting:
    """Tests for error formatting functions."""

    def test_format_for_display(self) -> None:
        """Test formatting for UI display."""
        result = ErrorResult(
            success=False,
            message="Connection failed",
            code=ErrorCode.CONNECTION_FAILED,
            suggestions=["Check network", "Try again"],
            can_retry=True,
        )
        output = format_error_for_display(result)

        assert "Connection failed" in output
        assert "Check network" in output
        assert "retried" in output.lower()

    def test_format_for_log(self) -> None:
        """Test formatting for log files."""
        result = ErrorResult(
            success=False,
            message="Auth failed",
            code=ErrorCode.AUTH_FAILED,
            severity=ErrorSeverity.ERROR,
            details={"user": "test@contoso.com"},
        )
        output = format_error_for_log(result)

        assert "AUTH_FAILED" in output
        assert "ERROR" in output
        assert "user" in output


class TestGlobalErrorHandler:
    """Tests for global error handler functions."""

    def test_get_error_handler_singleton(self) -> None:
        """Test global handler is singleton."""
        handler1 = get_error_handler()
        handler2 = get_error_handler()
        assert handler1 is handler2

    def test_handle_error_convenience(self) -> None:
        """Test handle_error convenience function."""
        result = handle_error(ValueError("Test"))
        assert result.success is False
        assert isinstance(result, ErrorResult)
