"""Exchange Online connection management with auto-reconnect and retry logic."""

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Generator

from src.core.powershell_executor import PowerShellExecutor, PowerShellResult
from src.utils.config import Config
from src.utils.logging import get_logger, log_operation

logger = get_logger(__name__)


class ConnectionState(Enum):
    """Exchange Online connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RECONNECTING = "reconnecting"


class ExchangeConnectionError(Exception):
    """Raised when Exchange Online connection fails."""

    def __init__(self, message: str, state: ConnectionState, details: str | None = None) -> None:
        self.message = message
        self.state = state
        self.details = details
        super().__init__(message)


@dataclass
class ConnectionInfo:
    """Information about the current connection."""

    state: ConnectionState = ConnectionState.DISCONNECTED
    tenant_id: str | None = None
    connected_at: datetime | None = None
    last_activity: datetime | None = None
    retry_count: int = 0
    error_message: str | None = None


class ExchangeConnection:
    """Manage Exchange Online PowerShell connections.

    Handles connection lifecycle, auto-reconnect on timeout, and retry logic
    with exponential backoff.
    """

    # Common session timeout errors from Exchange Online
    SESSION_EXPIRED_ERRORS = [
        "session has expired",
        "session is no longer valid",
        "runspace is not in the opened state",
        "connection has been closed",
        "remote session was closed",
        "token has expired",
    ]

    def __init__(self, executor: PowerShellExecutor, config: Config) -> None:
        """Initialize Exchange connection manager.

        Args:
            executor: PowerShell executor instance
            config: Application configuration
        """
        self._executor = executor
        self._config = config
        self._info = ConnectionInfo()
        self._access_token: str | None = None

        # Retry settings from config
        self._max_retries = config.connection.max_retries
        self._base_delay = 1.0  # seconds
        self._max_delay = 30.0  # seconds

        logger.debug("Exchange connection manager initialized")

    @property
    def state(self) -> ConnectionState:
        """Get current connection state."""
        return self._info.state

    @property
    def is_connected(self) -> bool:
        """Check if currently connected to Exchange Online."""
        return self._info.state == ConnectionState.CONNECTED

    @property
    def connection_info(self) -> ConnectionInfo:
        """Get connection information."""
        return self._info

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for exponential backoff.

        Args:
            attempt: Current retry attempt (0-based)

        Returns:
            Delay in seconds
        """
        delay = min(self._base_delay * (2**attempt), self._max_delay)
        return delay

    def _is_session_expired_error(self, error: str) -> bool:
        """Check if error indicates session expiration.

        Args:
            error: Error message to check

        Returns:
            True if error indicates session expired
        """
        error_lower = error.lower()
        return any(exp in error_lower for exp in self.SESSION_EXPIRED_ERRORS)

    def _update_activity(self) -> None:
        """Update last activity timestamp."""
        self._info.last_activity = datetime.now(timezone.utc)

    def connect(self, access_token: str, tenant_id: str | None = None) -> bool:
        """Connect to Exchange Online using access token.

        Args:
            access_token: OAuth access token from MSAL
            tenant_id: Azure AD tenant ID (uses config if not specified)

        Returns:
            True if connection successful

        Raises:
            ExchangeConnectionError: If connection fails after all retries
        """
        tenant = tenant_id or self._config.connection.tenant_id
        if not tenant:
            raise ExchangeConnectionError(
                "Tenant ID is required for connection",
                ConnectionState.ERROR,
            )

        self._info.state = ConnectionState.CONNECTING
        self._info.tenant_id = tenant
        self._access_token = access_token

        log_operation(logger, "CONNECT", details={"tenant": tenant}, result="started")

        for attempt in range(self._max_retries + 1):
            try:
                # Check if Exchange Online module is available
                if not self._executor.check_module("ExchangeOnlineManagement"):
                    raise ExchangeConnectionError(
                        "ExchangeOnlineManagement module not installed. "
                        "Run: Install-Module -Name ExchangeOnlineManagement",
                        ConnectionState.ERROR,
                    )

                # Build connection command
                # Note: Using -AccessToken requires the token and organization
                connect_cmd = f"""
$token = '{access_token}'
Connect-ExchangeOnline -AccessToken $token -Organization '{tenant}' -ShowBanner:$false
Write-Output 'Connected'
"""

                result = self._executor.execute(connect_cmd, timeout=60)

                if result.success and "Connected" in result.output:
                    self._info.state = ConnectionState.CONNECTED
                    self._info.connected_at = datetime.now(timezone.utc)
                    self._info.last_activity = self._info.connected_at
                    self._info.retry_count = 0
                    self._info.error_message = None

                    log_operation(
                        logger,
                        "CONNECT",
                        details={"tenant": tenant, "attempts": attempt + 1},
                        result="success",
                    )
                    logger.info(f"Connected to Exchange Online (tenant: {tenant})")
                    return True

                # Connection failed
                error_msg = result.error or "Unknown connection error"
                logger.warning(f"Connection attempt {attempt + 1} failed: {error_msg}")

                if attempt < self._max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.info(f"Retrying in {delay:.1f}s...")
                    time.sleep(delay)

            except ExchangeConnectionError:
                raise
            except Exception as e:
                logger.error(f"Connection error: {e}")
                if attempt >= self._max_retries:
                    raise ExchangeConnectionError(
                        f"Connection failed after {attempt + 1} attempts: {e}",
                        ConnectionState.ERROR,
                        str(e),
                    )

        # All retries exhausted
        self._info.state = ConnectionState.ERROR
        self._info.error_message = "Connection failed after maximum retries"
        log_operation(
            logger,
            "CONNECT",
            details={"tenant": tenant},
            result="failure",
            error=self._info.error_message,
        )
        raise ExchangeConnectionError(
            self._info.error_message,
            ConnectionState.ERROR,
        )

    def disconnect(self) -> None:
        """Disconnect from Exchange Online."""
        if self._info.state == ConnectionState.DISCONNECTED:
            logger.debug("Already disconnected")
            return

        log_operation(logger, "DISCONNECT", result="started")

        try:
            result = self._executor.execute(
                "Disconnect-ExchangeOnline -Confirm:$false -ErrorAction SilentlyContinue",
                timeout=30,
            )

            # Always mark as disconnected, even if command errors
            # (session may already be closed)
            self._info.state = ConnectionState.DISCONNECTED
            self._info.connected_at = None
            self._access_token = None

            if result.success:
                log_operation(logger, "DISCONNECT", result="success")
                logger.info("Disconnected from Exchange Online")
            else:
                # Non-fatal - session may have already expired
                logger.debug(f"Disconnect returned error (may be expected): {result.error}")
                log_operation(logger, "DISCONNECT", result="success")

        except Exception as e:
            # Force disconnected state even on error
            self._info.state = ConnectionState.DISCONNECTED
            self._info.connected_at = None
            logger.warning(f"Disconnect error (session may have expired): {e}")

    def check_connection(self) -> bool:
        """Check if connection is still valid.

        Performs a lightweight test command to verify the session is active.

        Returns:
            True if connection is valid
        """
        if self._info.state != ConnectionState.CONNECTED:
            return False

        # Quick health check with minimal result
        result = self._executor.execute(
            "Get-EXOMailbox -ResultSize 1 -ErrorAction Stop | Select-Object -First 1",
            timeout=30,
        )

        if result.success:
            self._update_activity()
            return True

        # Check if session expired
        if self._is_session_expired_error(result.error):
            logger.warning("Exchange Online session has expired")
            self._info.state = ConnectionState.DISCONNECTED
            self._info.error_message = "Session expired"
            return False

        # Other error - may still be connected
        logger.warning(f"Connection check failed: {result.error}")
        return False

    def ensure_connected(self) -> None:
        """Ensure connection is active, reconnecting if necessary.

        Raises:
            ExchangeConnectionError: If unable to establish connection
        """
        if self.is_connected:
            # Verify connection is still valid
            if self.check_connection():
                return

        # Need to reconnect
        if not self._access_token:
            raise ExchangeConnectionError(
                "Cannot reconnect: no access token available. "
                "Call connect() with a valid token first.",
                ConnectionState.DISCONNECTED,
            )

        logger.info("Reconnecting to Exchange Online...")
        self._info.state = ConnectionState.RECONNECTING
        self._info.retry_count += 1

        self.connect(self._access_token, self._info.tenant_id)

    def execute_command(self, command: str, timeout: int = 120) -> PowerShellResult:
        """Execute a PowerShell command with connection management.

        Automatically handles session expiration and reconnection.

        Args:
            command: PowerShell command to execute
            timeout: Command timeout in seconds

        Returns:
            PowerShellResult from command execution

        Raises:
            ExchangeConnectionError: If not connected and cannot reconnect
        """
        self.ensure_connected()

        result = self._executor.execute(command, timeout=timeout)

        if result.success:
            self._update_activity()
            return result

        # Check for session expiration
        if self._is_session_expired_error(result.error):
            logger.info("Session expired during command, reconnecting...")
            self.ensure_connected()
            # Retry the command once after reconnection
            result = self._executor.execute(command, timeout=timeout)
            if result.success:
                self._update_activity()

        return result


@contextmanager
def exchange_session(
    executor: PowerShellExecutor,
    config: Config,
    access_token: str,
    tenant_id: str | None = None,
) -> Generator[ExchangeConnection, None, None]:
    """Context manager for Exchange Online sessions.

    Automatically connects on entry and disconnects on exit.

    Args:
        executor: PowerShell executor instance
        config: Application configuration
        access_token: OAuth access token
        tenant_id: Azure AD tenant ID (optional)

    Yields:
        Connected ExchangeConnection instance

    Example:
        with exchange_session(executor, config, token) as conn:
            result = conn.execute_command("Get-EXOMailbox -ResultSize 10")
    """
    connection = ExchangeConnection(executor, config)
    try:
        connection.connect(access_token, tenant_id)
        yield connection
    finally:
        connection.disconnect()
