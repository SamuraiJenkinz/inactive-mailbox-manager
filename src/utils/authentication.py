"""Azure AD authentication using MSAL with device code flow."""

import json
import sys
from pathlib import Path
from typing import Any, Callable

import msal

from src.utils.logging import get_logger, log_operation

logger = get_logger(__name__)


class AuthenticationError(Exception):
    """Raised when authentication fails."""

    def __init__(
        self,
        message: str,
        error_code: str = "unknown",
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class Authenticator:
    """Handle Azure AD authentication using MSAL device code flow.

    Device code flow is ideal for CLI applications as it:
    - Works with MFA and conditional access policies
    - Doesn't require a redirect URI
    - Allows authentication on a separate device (useful for headless servers)
    """

    # Default scopes for Exchange Online
    DEFAULT_SCOPES = ["https://outlook.office365.com/.default"]

    # Device code flow timeout (5 minutes)
    DEVICE_CODE_TIMEOUT = 300

    def __init__(
        self,
        client_id: str,
        tenant_id: str,
        cache_path: Path | str | None = None,
        scopes: list[str] | None = None,
    ) -> None:
        """Initialize authenticator.

        Args:
            client_id: Azure AD application (client) ID
            tenant_id: Azure AD tenant ID
            cache_path: Path to token cache file (defaults to ~/.imm/token_cache.bin)
            scopes: OAuth scopes to request (defaults to Exchange Online)
        """
        self._client_id = client_id
        self._tenant_id = tenant_id
        self._scopes = scopes or self.DEFAULT_SCOPES

        # Set up cache path
        if cache_path is None:
            self._cache_path = Path.home() / ".imm" / "token_cache.bin"
        else:
            self._cache_path = Path(cache_path)

        # Initialize token cache
        self._cache = msal.SerializableTokenCache()
        self._load_cache()

        # Create MSAL application
        self._app = msal.PublicClientApplication(
            client_id=self._client_id,
            authority=f"https://login.microsoftonline.com/{self._tenant_id}",
            token_cache=self._cache,
        )

        logger.debug(f"Authenticator initialized for tenant {tenant_id}")

    @property
    def client_id(self) -> str:
        """Get the client ID."""
        return self._client_id

    @property
    def tenant_id(self) -> str:
        """Get the tenant ID."""
        return self._tenant_id

    def _load_cache(self) -> None:
        """Load token cache from file if it exists."""
        if self._cache_path.exists():
            try:
                with open(self._cache_path, "r", encoding="utf-8") as f:
                    self._cache.deserialize(f.read())
                logger.debug("Token cache loaded")
            except Exception as e:
                logger.warning(f"Failed to load token cache: {e}")

    def _save_cache(self) -> None:
        """Save token cache to file."""
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._cache_path, "w", encoding="utf-8") as f:
                f.write(self._cache.serialize())
            logger.debug("Token cache saved")
        except Exception as e:
            logger.warning(f"Failed to save token cache: {e}")

    def _get_accounts(self) -> list[dict[str, Any]]:
        """Get cached accounts."""
        return self._app.get_accounts()

    def get_token_silent(self) -> str | None:
        """Try to get token silently from cache.

        Returns:
            Access token if available, None if interactive auth needed
        """
        accounts = self._get_accounts()
        if not accounts:
            logger.debug("No cached accounts found")
            return None

        # Try the first account (most recent)
        account = accounts[0]
        logger.debug(f"Attempting silent token acquisition for {account.get('username', 'unknown')}")

        result = self._app.acquire_token_silent(
            scopes=self._scopes,
            account=account,
        )

        if result and "access_token" in result:
            logger.info("Token acquired silently (from cache)")
            self._save_cache()
            return result["access_token"]

        if result and "error" in result:
            logger.debug(f"Silent acquisition failed: {result.get('error_description', result['error'])}")

        return None

    def _device_code_flow(
        self,
        callback: Callable[[str], None] | None = None,
    ) -> str:
        """Perform interactive device code flow authentication.

        Args:
            callback: Optional callback to display device code message
                     (defaults to printing to stdout)

        Returns:
            Access token

        Raises:
            AuthenticationError: If authentication fails
        """
        log_operation(logger, "AUTHENTICATE", details={"method": "device_code"}, result="started")

        # Initiate device code flow
        flow = self._app.initiate_device_flow(scopes=self._scopes)

        if "error" in flow:
            raise AuthenticationError(
                f"Failed to initiate device code flow: {flow.get('error_description', flow['error'])}",
                error_code=flow.get("error", "flow_error"),
                details=flow,
            )

        # Display the message to user
        message = flow.get("message", "")
        if callback:
            callback(message)
        else:
            # Default: print to stdout with formatting
            print("\n" + "=" * 60)
            print("AUTHENTICATION REQUIRED")
            print("=" * 60)
            print(message)
            print("=" * 60 + "\n")
            sys.stdout.flush()

        # Wait for user to complete authentication
        logger.info("Waiting for user to complete device code authentication...")

        result = self._app.acquire_token_by_device_flow(flow)

        if "access_token" in result:
            self._save_cache()
            log_operation(
                logger,
                "AUTHENTICATE",
                details={"method": "device_code", "username": result.get("id_token_claims", {}).get("preferred_username")},
                result="success",
            )
            logger.info("Authentication successful")
            return result["access_token"]

        # Handle errors
        error_code = result.get("error", "unknown")
        error_desc = result.get("error_description", "Authentication failed")

        # Map common errors to user-friendly messages
        if error_code == "authorization_pending":
            raise AuthenticationError(
                "Authentication timed out. Please try again.",
                error_code="timeout",
                details=result,
            )
        elif error_code == "authorization_declined":
            raise AuthenticationError(
                "Authentication was declined by the user.",
                error_code="user_cancelled",
                details=result,
            )
        elif error_code == "expired_token":
            raise AuthenticationError(
                "The device code has expired. Please try again.",
                error_code="expired",
                details=result,
            )
        elif "invalid_grant" in error_code or "invalid_grant" in error_desc.lower():
            # Token was revoked - clear cache
            self.logout()
            raise AuthenticationError(
                "Authentication token was revoked. Please authenticate again.",
                error_code="invalid_grant",
                details=result,
            )
        else:
            raise AuthenticationError(
                error_desc,
                error_code=error_code,
                details=result,
            )

    def authenticate(
        self,
        callback: Callable[[str], None] | None = None,
    ) -> str:
        """Authenticate and get access token.

        Tries silent authentication first, falls back to device code flow.

        Args:
            callback: Optional callback to display device code message

        Returns:
            Access token

        Raises:
            AuthenticationError: If authentication fails
        """
        # Try silent first
        token = self.get_token_silent()
        if token:
            return token

        # Fall back to device code
        return self._device_code_flow(callback)

    def is_authenticated(self) -> bool:
        """Check if there's a valid cached token.

        Returns:
            True if authenticated (has valid or refreshable token)
        """
        token = self.get_token_silent()
        return token is not None

    def get_current_user(self) -> str | None:
        """Get the username of the currently authenticated user.

        Returns:
            Username (email) or None if not authenticated
        """
        accounts = self._get_accounts()
        if accounts:
            return accounts[0].get("username")
        return None

    def logout(self) -> None:
        """Clear cached tokens and log out."""
        # Clear all accounts from cache
        accounts = self._get_accounts()
        for account in accounts:
            self._app.remove_account(account)

        # Delete cache file
        if self._cache_path.exists():
            try:
                self._cache_path.unlink()
                logger.info("Token cache cleared")
            except Exception as e:
                logger.warning(f"Failed to delete token cache: {e}")

        log_operation(logger, "LOGOUT", result="success")

    def refresh_token(self) -> str | None:
        """Force refresh of the access token.

        Returns:
            New access token or None if refresh fails
        """
        accounts = self._get_accounts()
        if not accounts:
            return None

        account = accounts[0]

        # Force token refresh by setting force_refresh
        result = self._app.acquire_token_silent(
            scopes=self._scopes,
            account=account,
            force_refresh=True,
        )

        if result and "access_token" in result:
            self._save_cache()
            logger.info("Token refreshed")
            return result["access_token"]

        return None


def create_authenticator_from_config(config: Any) -> Authenticator:
    """Create an authenticator from application configuration.

    Args:
        config: Application Config object

    Returns:
        Configured Authenticator instance

    Raises:
        AuthenticationError: If required configuration is missing
    """
    if not config.connection.client_id:
        raise AuthenticationError(
            "client_id is required in configuration",
            error_code="missing_config",
        )

    if not config.connection.tenant_id:
        raise AuthenticationError(
            "tenant_id is required in configuration",
            error_code="missing_config",
        )

    return Authenticator(
        client_id=config.connection.client_id,
        tenant_id=config.connection.tenant_id,
    )
