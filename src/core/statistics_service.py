"""Statistics service for mailbox inventory aggregations."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.data.database import DatabaseManager

logger = get_logger(__name__)


@dataclass
class SummaryStats:
    """Summary statistics for the mailbox inventory."""

    total_mailboxes: int = 0
    with_holds: int = 0
    without_holds: int = 0
    recovery_eligible: int = 0
    recovery_blocked: int = 0
    total_size_gb: float = 0.0
    total_items: int = 0
    avg_age_days: float = 0.0
    oldest_mailbox_days: int = 0
    newest_mailbox_days: int = 0

    @property
    def hold_percentage(self) -> float:
        """Percentage of mailboxes with holds."""
        if self.total_mailboxes == 0:
            return 0.0
        return (self.with_holds / self.total_mailboxes) * 100

    @property
    def recovery_percentage(self) -> float:
        """Percentage of mailboxes eligible for recovery."""
        if self.total_mailboxes == 0:
            return 0.0
        return (self.recovery_eligible / self.total_mailboxes) * 100


class StatisticsService:
    """Service for generating statistics and aggregations on mailbox data.

    Provides efficient SQL-based aggregations for dashboard and reporting.
    """

    # Age bracket definitions (same as FilterService for consistency)
    AGE_BRACKETS = {
        "< 30 days": (0, 29),
        "30-90 days": (30, 89),
        "90-180 days": (90, 179),
        "180-365 days": (180, 364),
        "> 1 year": (365, 729),
        "> 2 years": (730, None),
    }

    # Size bracket definitions (in MB)
    SIZE_BRACKETS = {
        "< 100 MB": (0, 99),
        "100 MB - 1 GB": (100, 1023),
        "1-5 GB": (1024, 5119),
        "5-10 GB": (5120, 10239),
        "> 10 GB": (10240, None),
    }

    def __init__(self, db: "DatabaseManager") -> None:
        """Initialize statistics service.

        Args:
            db: Database manager instance
        """
        self._db = db
        logger.debug("StatisticsService initialized")

    def get_summary_stats(self) -> SummaryStats:
        """Get summary statistics for all mailboxes.

        Returns:
            SummaryStats with aggregated data
        """
        stats = SummaryStats()

        # Get total count
        result = self._db.execute_query(
            "SELECT COUNT(*) as count FROM inactive_mailboxes", []
        )
        stats.total_mailboxes = result[0]["count"] if result else 0

        if stats.total_mailboxes == 0:
            return stats

        # Get hold counts
        result = self._db.execute_query(
            """
            SELECT
                SUM(CASE WHEN hold_types != '[]' AND hold_types IS NOT NULL AND hold_types != '' THEN 1 ELSE 0 END) as with_holds,
                SUM(CASE WHEN hold_types = '[]' OR hold_types IS NULL OR hold_types = '' THEN 1 ELSE 0 END) as without_holds
            FROM inactive_mailboxes
            """,
            [],
        )
        if result:
            stats.with_holds = result[0]["with_holds"] or 0
            stats.without_holds = result[0]["without_holds"] or 0

        # Get recovery eligibility counts
        result = self._db.execute_query(
            """
            SELECT
                SUM(CASE WHEN recovery_eligible = 1 THEN 1 ELSE 0 END) as eligible,
                SUM(CASE WHEN recovery_eligible = 0 THEN 1 ELSE 0 END) as blocked
            FROM inactive_mailboxes
            """,
            [],
        )
        if result:
            stats.recovery_eligible = result[0]["eligible"] or 0
            stats.recovery_blocked = result[0]["blocked"] or 0

        # Get size and item totals
        result = self._db.execute_query(
            """
            SELECT
                COALESCE(SUM(size_mb), 0) as total_size_mb,
                COALESCE(SUM(item_count), 0) as total_items
            FROM inactive_mailboxes
            """,
            [],
        )
        if result:
            total_mb = result[0]["total_size_mb"] or 0
            stats.total_size_gb = total_mb / 1024
            stats.total_items = result[0]["total_items"] or 0

        # Get age statistics
        result = self._db.execute_query(
            """
            SELECT
                COALESCE(AVG(age_days), 0) as avg_age,
                COALESCE(MAX(age_days), 0) as oldest,
                COALESCE(MIN(age_days), 0) as newest
            FROM inactive_mailboxes
            """,
            [],
        )
        if result:
            stats.avg_age_days = result[0]["avg_age"] or 0
            stats.oldest_mailbox_days = result[0]["oldest"] or 0
            stats.newest_mailbox_days = result[0]["newest"] or 0

        return stats

    def get_stats_by_hold_type(self) -> dict[str, int]:
        """Get mailbox count by hold type.

        Returns:
            Dictionary mapping hold type to count
        """
        # This requires parsing the JSON hold_types column
        # For efficiency, we'll count common hold patterns
        stats: dict[str, int] = {}

        # Litigation hold count
        result = self._db.execute_query(
            "SELECT COUNT(*) as count FROM inactive_mailboxes WHERE litigation_hold = 1",
            [],
        )
        stats["Litigation Hold"] = result[0]["count"] if result else 0

        # eDiscovery holds (UniH prefix in hold_types)
        result = self._db.execute_query(
            "SELECT COUNT(*) as count FROM inactive_mailboxes WHERE hold_types LIKE '%UniH%'",
            [],
        )
        stats["eDiscovery Hold"] = result[0]["count"] if result else 0

        # In-Place holds (mbx prefix)
        result = self._db.execute_query(
            "SELECT COUNT(*) as count FROM inactive_mailboxes WHERE hold_types LIKE '%mbx%'",
            [],
        )
        stats["In-Place Hold"] = result[0]["count"] if result else 0

        # Retention policy (any GUID-like pattern, excluding specific prefixes)
        result = self._db.execute_query(
            """
            SELECT COUNT(*) as count FROM inactive_mailboxes
            WHERE hold_types != '[]'
            AND hold_types NOT LIKE '%UniH%'
            AND hold_types NOT LIKE '%mbx%'
            AND hold_types NOT LIKE '%skp%'
            AND hold_types NOT LIKE '%grp%'
            AND hold_types IS NOT NULL
            AND hold_types != ''
            """,
            [],
        )
        stats["Retention Policy"] = result[0]["count"] if result else 0

        # No holds
        result = self._db.execute_query(
            """
            SELECT COUNT(*) as count FROM inactive_mailboxes
            WHERE (hold_types = '[]' OR hold_types IS NULL OR hold_types = '')
            AND litigation_hold = 0
            """,
            [],
        )
        stats["No Holds"] = result[0]["count"] if result else 0

        return stats

    def get_stats_by_age_bracket(self) -> dict[str, int]:
        """Get mailbox count by age bracket.

        Returns:
            Dictionary mapping age bracket to count
        """
        stats: dict[str, int] = {}

        for bracket_name, (min_days, max_days) in self.AGE_BRACKETS.items():
            if max_days is None:
                query = "SELECT COUNT(*) as count FROM inactive_mailboxes WHERE age_days >= ?"
                params = [min_days]
            else:
                query = "SELECT COUNT(*) as count FROM inactive_mailboxes WHERE age_days >= ? AND age_days <= ?"
                params = [min_days, max_days]

            result = self._db.execute_query(query, params)
            stats[bracket_name] = result[0]["count"] if result else 0

        return stats

    def get_stats_by_license(self) -> dict[str, int]:
        """Get mailbox count by license type.

        Returns:
            Dictionary mapping license type to count
        """
        result = self._db.execute_query(
            """
            SELECT
                COALESCE(license_type, 'Unknown') as license_type,
                COUNT(*) as count
            FROM inactive_mailboxes
            GROUP BY COALESCE(license_type, 'Unknown')
            ORDER BY count DESC
            """,
            [],
        )

        return {row["license_type"]: row["count"] for row in result}

    def get_stats_by_company(self) -> dict[str, int]:
        """Get mailbox count by operating company.

        Returns:
            Dictionary mapping company to count
        """
        result = self._db.execute_query(
            """
            SELECT
                COALESCE(operating_company, 'Unknown') as operating_company,
                COUNT(*) as count
            FROM inactive_mailboxes
            GROUP BY COALESCE(operating_company, 'Unknown')
            ORDER BY count DESC
            """,
            [],
        )

        return {row["operating_company"]: row["count"] for row in result}

    def get_stats_by_size_bracket(self) -> dict[str, int]:
        """Get mailbox count by size bracket.

        Returns:
            Dictionary mapping size bracket to count
        """
        stats: dict[str, int] = {}

        for bracket_name, (min_mb, max_mb) in self.SIZE_BRACKETS.items():
            if max_mb is None:
                query = "SELECT COUNT(*) as count FROM inactive_mailboxes WHERE size_mb >= ?"
                params = [min_mb]
            else:
                query = "SELECT COUNT(*) as count FROM inactive_mailboxes WHERE size_mb >= ? AND size_mb <= ?"
                params = [min_mb, max_mb]

            result = self._db.execute_query(query, params)
            stats[bracket_name] = result[0]["count"] if result else 0

        return stats

    def get_stats_by_recovery_status(self) -> dict[str, int]:
        """Get mailbox count by recovery eligibility.

        Returns:
            Dictionary mapping status to count
        """
        result = self._db.execute_query(
            """
            SELECT
                CASE WHEN recovery_eligible = 1 THEN 'Eligible' ELSE 'Blocked' END as status,
                COUNT(*) as count
            FROM inactive_mailboxes
            GROUP BY recovery_eligible
            """,
            [],
        )

        return {row["status"]: row["count"] for row in result}

    def get_all_stats(self) -> dict:
        """Get all statistics in a single call.

        Returns:
            Dictionary with all statistics
        """
        return {
            "summary": self.get_summary_stats(),
            "by_hold_type": self.get_stats_by_hold_type(),
            "by_age_bracket": self.get_stats_by_age_bracket(),
            "by_license": self.get_stats_by_license(),
            "by_company": self.get_stats_by_company(),
            "by_size_bracket": self.get_stats_by_size_bracket(),
            "by_recovery_status": self.get_stats_by_recovery_status(),
        }

    def get_cost_summary(self, license_costs: dict[str, float] | None = None) -> dict:
        """Get cost summary based on license types.

        Args:
            license_costs: Optional mapping of license type to monthly cost

        Returns:
            Dictionary with cost analysis
        """
        # Default license costs if not provided
        default_costs = {
            "E5": 57.00,
            "E3": 36.00,
            "E1": 10.00,
            "F3": 8.00,
            "Exchange Online Plan 1": 4.00,
            "Exchange Online Plan 2": 8.00,
        }
        costs = license_costs or default_costs

        license_stats = self.get_stats_by_license()

        total_monthly = 0.0
        cost_breakdown: dict[str, dict] = {}

        for license_type, count in license_stats.items():
            monthly_cost = costs.get(license_type, 0.0)
            total_cost = monthly_cost * count

            cost_breakdown[license_type] = {
                "count": count,
                "unit_cost": monthly_cost,
                "monthly_total": total_cost,
                "annual_total": total_cost * 12,
            }

            total_monthly += total_cost

        return {
            "total_monthly_cost": total_monthly,
            "total_annual_cost": total_monthly * 12,
            "breakdown_by_license": cost_breakdown,
        }
