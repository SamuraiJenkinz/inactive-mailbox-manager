"""Cache management utilities for mailbox data."""

from datetime import datetime
from typing import TYPE_CHECKING

from src.data.models import CacheStats
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.data.database import DatabaseManager
    from src.utils.config import Config

logger = get_logger(__name__)


class CacheManager:
    """Manages cache validity and refresh logic for mailbox data.

    Provides centralized cache management including validity checking,
    age calculation, and cache statistics.
    """

    def __init__(self, db: "DatabaseManager", config: "Config") -> None:
        """Initialize cache manager.

        Args:
            db: Database manager instance
            config: Application configuration
        """
        self._db = db
        self._config = config
        self._cache_duration_hours = config.cache.cache_duration_hours

        logger.debug(
            f"CacheManager initialized with {self._cache_duration_hours}h duration"
        )

    def is_cache_valid(self) -> bool:
        """Check if the cache is still valid based on age.

        Returns:
            True if cache is fresh enough to use, False otherwise
        """
        stats = self._db.get_cache_stats()

        # Empty cache is not valid
        if stats.total_count == 0:
            logger.debug("Cache invalid: empty")
            return False

        # No refresh timestamp means cache is stale
        if stats.last_refresh is None:
            logger.debug("Cache invalid: no refresh timestamp")
            return False

        # Check age against configured duration
        age_hours = self.get_cache_age_hours()
        is_valid = age_hours <= self._cache_duration_hours

        if is_valid:
            logger.debug(
                f"Cache valid: {age_hours:.1f}h old, max {self._cache_duration_hours}h"
            )
        else:
            logger.debug(
                f"Cache invalid: {age_hours:.1f}h old, max {self._cache_duration_hours}h"
            )

        return is_valid

    def get_cache_age_hours(self) -> float:
        """Get the age of the cache in hours.

        Returns:
            Cache age in hours, or infinity if no refresh timestamp
        """
        stats = self._db.get_cache_stats()

        if stats.last_refresh is None:
            return float("inf")

        age_delta = datetime.now() - stats.last_refresh
        return age_delta.total_seconds() / 3600

    def should_refresh(self) -> bool:
        """Determine if cache should be refreshed.

        This is the inverse of is_cache_valid() but provides
        semantic clarity for calling code.

        Returns:
            True if cache should be refreshed, False otherwise
        """
        return not self.is_cache_valid()

    def invalidate_cache(self) -> None:
        """Invalidate the cache by clearing all cached data.

        This forces a refresh on the next data access.
        """
        logger.info("Invalidating cache")
        self._db.clear_cache()
        logger.debug("Cache invalidated")

    def get_stats(self) -> CacheStats:
        """Get current cache statistics.

        Returns:
            CacheStats with current cache state
        """
        return self._db.get_cache_stats()

    def get_cache_info(self) -> dict:
        """Get detailed cache information for display.

        Returns:
            Dictionary with cache details including validity, age, and counts
        """
        stats = self.get_stats()
        age_hours = self.get_cache_age_hours()
        is_valid = self.is_cache_valid()

        return {
            "is_valid": is_valid,
            "total_count": stats.total_count,
            "age_hours": age_hours if age_hours != float("inf") else None,
            "max_age_hours": self._cache_duration_hours,
            "last_refresh": stats.last_refresh.isoformat() if stats.last_refresh else None,
            "size_bytes": stats.size_bytes,
            "oldest_entry": stats.oldest_entry.isoformat() if stats.oldest_entry else None,
            "newest_entry": stats.newest_entry.isoformat() if stats.newest_entry else None,
        }

    def set_cache_duration(self, hours: float) -> None:
        """Update the cache duration setting.

        Args:
            hours: New cache duration in hours
        """
        if hours <= 0:
            raise ValueError("Cache duration must be positive")

        logger.info(f"Updating cache duration: {self._cache_duration_hours}h -> {hours}h")
        self._cache_duration_hours = hours

    def estimate_refresh_time(self, mailbox_count: int) -> float:
        """Estimate time needed to refresh cache.

        Args:
            mailbox_count: Number of mailboxes to refresh

        Returns:
            Estimated time in seconds
        """
        # Rough estimate: ~0.5 seconds per mailbox for network + parsing
        # Plus fixed overhead for connection setup
        base_overhead = 5.0  # Connection and initial setup
        per_mailbox = 0.05  # Per-mailbox processing with bulk retrieval

        return base_overhead + (mailbox_count * per_mailbox)
