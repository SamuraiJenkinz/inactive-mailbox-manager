"""Structured logging with Rich console output and JSON file logging."""

import json
import logging
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

# Custom theme matching brutalist dark branding
BRUTALIST_THEME = Theme(
    {
        "logging.level.debug": "dim cyan",
        "logging.level.info": "green",
        "logging.level.warning": "yellow",
        "logging.level.error": "red bold",
        "logging.level.critical": "red bold reverse",
        "log.time": "dim green",
        "log.message": "green",
        "log.path": "dim green",
    }
)

# Global console instance
console = Console(theme=BRUTALIST_THEME, force_terminal=True)

# Track if logging has been set up
_logging_initialized = False


class JSONFormatter(logging.Formatter):
    """JSON formatter for file logging - enables SIEM integration."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data

        return json.dumps(log_data, default=str)


class ContextLogger(logging.Logger):
    """Extended logger with context support."""

    def _log_with_context(
        self,
        level: int,
        msg: str,
        args: tuple[Any, ...],
        extra_data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Log with optional extra context data."""
        if extra_data:
            kwargs.setdefault("extra", {})["extra_data"] = extra_data
        super()._log(level, msg, args, **kwargs)

    def debug_ctx(self, msg: str, *args: Any, ctx: dict[str, Any] | None = None) -> None:
        """Debug log with context."""
        self._log_with_context(logging.DEBUG, msg, args, ctx)

    def info_ctx(self, msg: str, *args: Any, ctx: dict[str, Any] | None = None) -> None:
        """Info log with context."""
        self._log_with_context(logging.INFO, msg, args, ctx)

    def warning_ctx(self, msg: str, *args: Any, ctx: dict[str, Any] | None = None) -> None:
        """Warning log with context."""
        self._log_with_context(logging.WARNING, msg, args, ctx)

    def error_ctx(self, msg: str, *args: Any, ctx: dict[str, Any] | None = None) -> None:
        """Error log with context."""
        self._log_with_context(logging.ERROR, msg, args, ctx)

    def critical_ctx(self, msg: str, *args: Any, ctx: dict[str, Any] | None = None) -> None:
        """Critical log with context."""
        self._log_with_context(logging.CRITICAL, msg, args, ctx)


# Register custom logger class
logging.setLoggerClass(ContextLogger)


def setup_logging(
    level: str = "INFO",
    log_file: Path | str | None = None,
    json_file: Path | str | None = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> None:
    """Set up logging with Rich console and optional file handlers.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to plain text log file (optional)
        json_file: Path to JSON format log file for SIEM (optional)
        max_bytes: Maximum size per log file before rotation (default 10MB)
        backup_count: Number of backup files to keep (default 5)
    """
    global _logging_initialized

    if _logging_initialized:
        return

    # Convert level string to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Rich console handler with beautiful formatting
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_level=True,
        show_path=True,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        markup=True,
    )
    rich_handler.setLevel(numeric_level)
    rich_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(rich_handler)

    # Plain text file handler (optional)
    if log_file:
        log_path = Path(log_file) if isinstance(log_file, str) else log_file
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root_logger.addHandler(file_handler)

    # JSON file handler for SIEM integration (optional)
    if json_file:
        json_path = Path(json_file) if isinstance(json_file, str) else json_file
        json_path.parent.mkdir(parents=True, exist_ok=True)

        json_handler = RotatingFileHandler(
            json_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        json_handler.setLevel(numeric_level)
        json_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(json_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("msal").setLevel(logging.WARNING)

    _logging_initialized = True


def get_logger(name: str) -> ContextLogger:
    """Get a logger instance with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)  # type: ignore


def log_exception(logger: logging.Logger, exc: Exception, context: str = "") -> None:
    """Log an exception with full traceback.

    Args:
        logger: Logger instance to use
        exc: Exception to log
        context: Additional context about what was happening
    """
    if context:
        logger.exception(f"{context}: {exc}")
    else:
        logger.exception(str(exc))


def log_operation(
    logger: logging.Logger,
    operation: str,
    identity: str | None = None,
    details: dict[str, Any] | None = None,
    result: str = "success",
    error: str | None = None,
) -> None:
    """Log an operation for audit purposes.

    Args:
        logger: Logger instance to use
        operation: Operation type (e.g., CONNECT, RECOVER_MAILBOX)
        identity: Target mailbox identity (optional)
        details: Additional operation details (optional)
        result: Operation result (success, failure, warning)
        error: Error message if operation failed (optional)
    """
    msg_parts = [f"Operation: {operation}"]
    if identity:
        msg_parts.append(f"Identity: {identity}")
    msg_parts.append(f"Result: {result}")
    if error:
        msg_parts.append(f"Error: {error}")

    msg = " | ".join(msg_parts)

    extra_data = {
        "operation": operation,
        "identity": identity,
        "details": details,
        "result": result,
        "error": error,
    }

    if result == "success":
        if hasattr(logger, "info_ctx"):
            logger.info_ctx(msg, ctx=extra_data)  # type: ignore
        else:
            logger.info(msg, extra={"extra_data": extra_data})
    elif result == "warning":
        if hasattr(logger, "warning_ctx"):
            logger.warning_ctx(msg, ctx=extra_data)  # type: ignore
        else:
            logger.warning(msg, extra={"extra_data": extra_data})
    else:
        if hasattr(logger, "error_ctx"):
            logger.error_ctx(msg, ctx=extra_data)  # type: ignore
        else:
            logger.error(msg, extra={"extra_data": extra_data})
