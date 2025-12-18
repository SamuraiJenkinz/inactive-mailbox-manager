"""Mailbox service for retrieving and caching inactive mailbox inventory."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

from src.data.audit_logger import OperationType
from src.data.models import InactiveMailbox, MailboxStatistics
from src.utils.command_builder import CommandBuilder
from src.utils.logging import get_logger
from src.utils.ps_parser import parse_json_output

if TYPE_CHECKING:
    from src.data.session import SessionManager

logger = get_logger(__name__)


class MailboxServiceError(Exception):
    """Raised when mailbox service operations fail."""

    pass


class MailboxService:
    """Service for retrieving and managing inactive mailbox inventory.

    Handles retrieval from Exchange Online, caching in SQLite, and
    providing efficient access to mailbox data.
    """

    # Default properties to retrieve from Exchange
    DEFAULT_PROPERTIES = [
        "ExchangeGuid",
        "Guid",
        "DisplayName",
        "PrimarySmtpAddress",
        "UserPrincipalName",
        "WhenSoftDeleted",
        "WhenCreated",
        "InPlaceHolds",
        "LitigationHoldEnabled",
        "LitigationHoldDate",
        "RetentionPolicy",
        "ArchiveStatus",
        "ArchiveGuid",
        "RecipientTypeDetails",
        "ExternalDirectoryObjectId",
    ]

    def __init__(self, session: "SessionManager") -> None:
        """Initialize mailbox service.

        Args:
            session: Session manager with active connection
        """
        self._session = session
        self._db = session.database
        self._audit = session.audit
        self._config = session._config
        self._command_builder = CommandBuilder()

        logger.debug("Mailbox service initialized")

    def get_mailbox_count(self) -> int:
        """Get total count of inactive mailboxes from Exchange Online.

        Returns:
            Total number of inactive mailboxes
        """
        self._session.ensure_connected()

        cmd = self._command_builder.build_count_inactive_mailboxes()
        result = self._session.connection.execute_command(cmd, timeout=60)

        if not result.success:
            raise MailboxServiceError(f"Failed to get mailbox count: {result.error}")

        try:
            count = int(result.output.strip())
            logger.info(f"Total inactive mailboxes: {count}")
            return count
        except ValueError as e:
            raise MailboxServiceError(f"Invalid count response: {result.output}") from e

    def get_cached_count(self) -> int:
        """Get count of mailboxes in local cache.

        Returns:
            Number of cached mailboxes
        """
        stats = self._db.get_cache_stats()
        return stats.total_count

    def get_all_mailboxes(
        self,
        force_refresh: bool = False,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[InactiveMailbox]:
        """Get all inactive mailboxes.

        Returns from cache if valid, otherwise fetches from Exchange Online.

        Args:
            force_refresh: Force refresh from Exchange even if cache is valid
            progress_callback: Optional callback for progress updates (current, total)

        Returns:
            List of all inactive mailboxes
        """
        # Check cache validity
        if not force_refresh and self._is_cache_valid():
            logger.info("Returning mailboxes from cache")
            self._audit.log_operation(
                OperationType.LIST_MAILBOXES,
                details={"source": "cache"},
            )
            return self._db.get_all_mailboxes()

        # Fetch from Exchange
        logger.info("Fetching mailboxes from Exchange Online...")
        mailboxes = self._fetch_all_from_exchange(progress_callback)

        self._audit.log_operation(
            OperationType.LIST_MAILBOXES,
            details={"source": "exchange", "count": len(mailboxes)},
        )

        return mailboxes

    def _is_cache_valid(self) -> bool:
        """Check if the cache is still valid.

        Returns:
            True if cache is fresh enough to use
        """
        stats = self._db.get_cache_stats()

        if stats.total_count == 0:
            logger.debug("Cache is empty")
            return False

        if stats.last_refresh is None:
            logger.debug("No last refresh timestamp")
            return False

        # Check age
        cache_age_hours = (datetime.now() - stats.last_refresh).total_seconds() / 3600
        max_age_hours = self._config.cache.cache_duration_hours

        if cache_age_hours > max_age_hours:
            logger.debug(f"Cache expired: {cache_age_hours:.1f}h > {max_age_hours}h")
            return False

        logger.debug(f"Cache valid: {cache_age_hours:.1f}h old, max {max_age_hours}h")
        return True

    def _fetch_all_from_exchange(
        self,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[InactiveMailbox]:
        """Fetch all inactive mailboxes from Exchange Online.

        Args:
            progress_callback: Optional callback for progress updates

        Returns:
            List of all inactive mailboxes
        """
        self._session.ensure_connected()

        # Get total count first (for progress)
        try:
            total = self.get_mailbox_count()
        except Exception:
            total = 0  # Unknown count

        if progress_callback and total > 0:
            progress_callback(0, total)

        # Build command to fetch all mailboxes
        cmd = self._command_builder.build_get_inactive_mailboxes(
            result_size="Unlimited",
            properties=self.DEFAULT_PROPERTIES,
        )

        # Execute with extended timeout for large tenants
        logger.info("Executing mailbox retrieval (this may take a while)...")
        result = self._session.connection.execute_command(cmd, timeout=600)

        if not result.success:
            raise MailboxServiceError(f"Failed to retrieve mailboxes: {result.error}")

        # Parse JSON response
        try:
            data = parse_json_output(result.output)
        except Exception as e:
            raise MailboxServiceError(f"Failed to parse mailbox data: {e}") from e

        # Handle single mailbox vs list
        if isinstance(data, dict):
            data = [data]

        # Convert to InactiveMailbox objects
        mailboxes = []
        for i, item in enumerate(data):
            try:
                mailbox = InactiveMailbox.from_exchange_data(item)
                mailboxes.append(mailbox)
            except Exception as e:
                logger.warning(f"Failed to parse mailbox {i}: {e}")

            # Progress callback
            if progress_callback and total > 0:
                progress_callback(i + 1, total)

        logger.info(f"Retrieved {len(mailboxes)} mailboxes from Exchange Online")

        # Cache results
        if mailboxes:
            self._db.upsert_mailboxes(mailboxes)
            self._db.set_last_refresh()
            logger.info(f"Cached {len(mailboxes)} mailboxes")

        return mailboxes

    def refresh_cache(
        self,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> int:
        """Force refresh of the mailbox cache.

        Args:
            progress_callback: Optional callback for progress updates

        Returns:
            Number of mailboxes cached
        """
        self._audit.log_operation(
            OperationType.REFRESH_CACHE,
            details={"action": "start"},
        )

        try:
            mailboxes = self._fetch_all_from_exchange(progress_callback)

            self._audit.log_operation(
                OperationType.REFRESH_CACHE,
                details={"action": "complete", "count": len(mailboxes)},
            )

            return len(mailboxes)

        except Exception as e:
            self._audit.log_operation(
                OperationType.REFRESH_CACHE,
                result="failure",
                error=str(e),
            )
            raise

    def get_mailbox(self, identity: str) -> InactiveMailbox | None:
        """Get a specific mailbox by identity.

        First checks cache, then fetches from Exchange if not found.

        Args:
            identity: Mailbox Exchange GUID or email

        Returns:
            Mailbox if found, None otherwise
        """
        # Check cache first
        mailbox = self._db.get_mailbox(identity)
        if mailbox:
            self._audit.log_mailbox_access(
                OperationType.GET_MAILBOX_DETAILS,
                identity,
                {"source": "cache"},
            )
            return mailbox

        # Try to fetch from Exchange
        try:
            return self._fetch_mailbox_from_exchange(identity)
        except Exception as e:
            logger.warning(f"Failed to fetch mailbox {identity}: {e}")
            return None

    def _fetch_mailbox_from_exchange(self, identity: str) -> InactiveMailbox | None:
        """Fetch a specific mailbox from Exchange Online.

        Args:
            identity: Mailbox identity

        Returns:
            Mailbox if found, None otherwise
        """
        self._session.ensure_connected()

        cmd = self._command_builder.build_get_mailbox_details(identity)
        result = self._session.connection.execute_command(cmd, timeout=60)

        if not result.success:
            if "couldn't be found" in result.error.lower():
                return None
            raise MailboxServiceError(f"Failed to get mailbox: {result.error}")

        try:
            data = parse_json_output(result.output)
            if isinstance(data, list):
                data = data[0] if data else None
            if not data:
                return None

            mailbox = InactiveMailbox.from_exchange_data(data)

            # Cache the result
            self._db.upsert_mailbox(mailbox)

            self._audit.log_mailbox_access(
                OperationType.GET_MAILBOX_DETAILS,
                identity,
                {"source": "exchange"},
            )

            return mailbox

        except Exception as e:
            raise MailboxServiceError(f"Failed to parse mailbox data: {e}") from e

    def search(self, query: str) -> list[InactiveMailbox]:
        """Search mailboxes by display name or email.

        Args:
            query: Search query string

        Returns:
            List of matching mailboxes
        """
        results = self._db.search_mailboxes(query)

        self._audit.log_operation(
            OperationType.SEARCH_MAILBOXES,
            details={"query": query, "results": len(results)},
        )

        return results

    def clear_cache(self) -> None:
        """Clear the mailbox cache."""
        self._db.clear_cache()

        self._audit.log_operation(
            OperationType.CLEAR_CACHE,
            details={"action": "mailbox_cache_cleared"},
        )

        logger.info("Mailbox cache cleared")

    def get_mailbox_statistics(self, identity: str) -> MailboxStatistics | None:
        """Get statistics for a specific mailbox.

        Args:
            identity: Mailbox identity (GUID or email)

        Returns:
            MailboxStatistics if found, None otherwise
        """
        self._session.ensure_connected()

        cmd = self._command_builder.build_get_mailbox_statistics(identity)
        result = self._session.connection.execute_command(cmd, timeout=60)

        if not result.success:
            if "couldn't be found" in result.error.lower():
                return None
            logger.warning(f"Failed to get mailbox statistics: {result.error}")
            return None

        try:
            data = parse_json_output(result.output)
            if isinstance(data, list):
                data = data[0] if data else None
            if not data:
                return None

            stats = MailboxStatistics.from_exchange_data(data)

            self._audit.log_mailbox_access(
                OperationType.GET_STATISTICS,
                identity,
                {"size_mb": stats.total_size_mb, "items": stats.item_count},
            )

            return stats

        except Exception as e:
            logger.warning(f"Failed to parse statistics: {e}")
            return None

    def enrich_mailbox(self, mailbox: InactiveMailbox) -> InactiveMailbox:
        """Enrich a mailbox with statistics data.

        Fetches statistics and updates the mailbox with size and item count.

        Args:
            mailbox: Mailbox to enrich

        Returns:
            Updated mailbox (same object, modified in place)
        """
        stats = self.get_mailbox_statistics(mailbox.identity)

        if stats:
            mailbox.size_mb = stats.total_size_mb
            mailbox.item_count = stats.item_count
            mailbox.last_updated = datetime.now()

            # Update cache
            self._db.upsert_mailbox(mailbox)

        return mailbox

    def get_mailbox_details(self, identity: str) -> InactiveMailbox | None:
        """Get full mailbox details with fresh data from Exchange.

        Unlike get_mailbox(), this always fetches from Exchange Online.

        Args:
            identity: Mailbox identity

        Returns:
            Mailbox with latest data, or None if not found
        """
        mailbox = self._fetch_mailbox_from_exchange(identity)

        if mailbox:
            # Also get statistics
            self.enrich_mailbox(mailbox)

        return mailbox
