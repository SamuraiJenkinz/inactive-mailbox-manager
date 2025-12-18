"""Filter and search service for mailbox inventory."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from src.data.models import InactiveMailbox
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.data.database import DatabaseManager

logger = get_logger(__name__)


@dataclass
class FilterCriteria:
    """Criteria for filtering mailboxes."""

    # Hold filters
    hold_types: list[str] | None = None
    has_any_hold: bool | None = None

    # Age filters (days)
    age_min_days: int | None = None
    age_max_days: int | None = None

    # License filters
    license_types: list[str] | None = None

    # Organization filters
    operating_companies: list[str] | None = None

    # Size filters (MB)
    size_min_mb: float | None = None
    size_max_mb: float | None = None

    # Recovery status
    recovery_eligible: bool | None = None

    # Search query (searches display_name, primary_smtp, user_principal_name)
    search_query: str | None = None

    def is_empty(self) -> bool:
        """Check if no criteria are set."""
        return all(
            [
                self.hold_types is None,
                self.has_any_hold is None,
                self.age_min_days is None,
                self.age_max_days is None,
                self.license_types is None,
                self.operating_companies is None,
                self.size_min_mb is None,
                self.size_max_mb is None,
                self.recovery_eligible is None,
                self.search_query is None,
            ]
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert criteria to dictionary for logging/export."""
        return {
            k: v for k, v in {
                "hold_types": self.hold_types,
                "has_any_hold": self.has_any_hold,
                "age_min_days": self.age_min_days,
                "age_max_days": self.age_max_days,
                "license_types": self.license_types,
                "operating_companies": self.operating_companies,
                "size_min_mb": self.size_min_mb,
                "size_max_mb": self.size_max_mb,
                "recovery_eligible": self.recovery_eligible,
                "search_query": self.search_query,
            }.items() if v is not None
        }


@dataclass
class SortCriteria:
    """Criteria for sorting mailbox results."""

    field: str = "display_name"
    ascending: bool = True

    # Valid sort fields
    VALID_FIELDS = [
        "display_name",
        "primary_smtp",
        "when_soft_deleted",
        "age_days",
        "size_mb",
        "item_count",
        "license_type",
        "operating_company",
        "recovery_eligible",
    ]

    def __post_init__(self) -> None:
        """Validate sort field."""
        if self.field not in self.VALID_FIELDS:
            logger.warning(f"Invalid sort field '{self.field}', using 'display_name'")
            self.field = "display_name"


class FilterService:
    """Service for filtering and searching mailbox inventory.

    Provides SQL-based filtering for efficient queries on large datasets.
    """

    # Age bracket definitions
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
        """Initialize filter service.

        Args:
            db: Database manager instance
        """
        self._db = db
        logger.debug("FilterService initialized")

    def filter_mailboxes(
        self,
        criteria: FilterCriteria,
        sort: SortCriteria | None = None,
    ) -> list[InactiveMailbox]:
        """Filter mailboxes based on criteria.

        Args:
            criteria: Filter criteria to apply
            sort: Optional sort criteria

        Returns:
            List of matching mailboxes
        """
        where_clause, params = self._build_filter_query(criteria)

        # Build sort clause
        sort_clause = ""
        if sort:
            direction = "ASC" if sort.ascending else "DESC"
            sort_clause = f"ORDER BY {sort.field} {direction}"

        # Build full query
        query = f"""
            SELECT * FROM inactive_mailboxes
            WHERE {where_clause}
            {sort_clause}
        """

        logger.debug(f"Filter query: {query}")
        logger.debug(f"Filter params: {params}")

        # Execute query
        results = self._db.execute_query(query, params)

        # Convert to InactiveMailbox objects
        mailboxes = [InactiveMailbox.from_dict(row) for row in results]

        logger.info(f"Filter returned {len(mailboxes)} mailboxes")
        return mailboxes

    def search_mailboxes(self, query: str) -> list[InactiveMailbox]:
        """Search mailboxes by display name or email.

        Args:
            query: Search query string

        Returns:
            List of matching mailboxes
        """
        criteria = FilterCriteria(search_query=query)
        return self.filter_mailboxes(criteria)

    def _build_filter_query(
        self, criteria: FilterCriteria
    ) -> tuple[str, list[Any]]:
        """Build SQL WHERE clause from filter criteria.

        Args:
            criteria: Filter criteria

        Returns:
            Tuple of (where_clause, params)
        """
        conditions: list[str] = []
        params: list[Any] = []

        # Age filters
        if criteria.age_min_days is not None:
            conditions.append("age_days >= ?")
            params.append(criteria.age_min_days)

        if criteria.age_max_days is not None:
            conditions.append("age_days <= ?")
            params.append(criteria.age_max_days)

        # Size filters
        if criteria.size_min_mb is not None:
            conditions.append("size_mb >= ?")
            params.append(criteria.size_min_mb)

        if criteria.size_max_mb is not None:
            conditions.append("size_mb <= ?")
            params.append(criteria.size_max_mb)

        # License type filter
        if criteria.license_types:
            placeholders = ", ".join("?" for _ in criteria.license_types)
            conditions.append(f"license_type IN ({placeholders})")
            params.extend(criteria.license_types)

        # Operating company filter
        if criteria.operating_companies:
            placeholders = ", ".join("?" for _ in criteria.operating_companies)
            conditions.append(f"operating_company IN ({placeholders})")
            params.extend(criteria.operating_companies)

        # Recovery eligible filter
        if criteria.recovery_eligible is not None:
            conditions.append("recovery_eligible = ?")
            params.append(1 if criteria.recovery_eligible else 0)

        # Hold filters
        if criteria.has_any_hold is not None:
            if criteria.has_any_hold:
                # Has at least one hold
                conditions.append(
                    "(hold_types != '[]' AND hold_types IS NOT NULL AND hold_types != '')"
                )
            else:
                # No holds
                conditions.append(
                    "(hold_types = '[]' OR hold_types IS NULL OR hold_types = '')"
                )

        if criteria.hold_types:
            # Check if any of the specified hold types are present
            hold_conditions = []
            for hold_type in criteria.hold_types:
                hold_conditions.append("hold_types LIKE ?")
                params.append(f"%{hold_type}%")
            conditions.append(f"({' OR '.join(hold_conditions)})")

        # Search query
        if criteria.search_query:
            pattern = f"%{criteria.search_query}%"
            conditions.append(
                "(display_name LIKE ? OR primary_smtp LIKE ? OR user_principal_name LIKE ?)"
            )
            params.extend([pattern, pattern, pattern])

        # Build final WHERE clause
        where_clause = " AND ".join(conditions) if conditions else "1=1"

        return where_clause, params

    def get_distinct_values(self, field: str) -> list[str]:
        """Get distinct values for a field (for filter dropdowns).

        Args:
            field: Field name to get values for

        Returns:
            List of distinct values
        """
        # Validate field name
        valid_fields = [
            "license_type",
            "operating_company",
            "department",
            "archive_status",
        ]

        if field not in valid_fields:
            logger.warning(f"Invalid field for distinct values: {field}")
            return []

        query = f"""
            SELECT DISTINCT {field}
            FROM inactive_mailboxes
            WHERE {field} IS NOT NULL AND {field} != ''
            ORDER BY {field}
        """

        results = self._db.execute_query(query, [])
        return [row[field] for row in results if row[field]]

    def get_filter_counts(self, base_criteria: FilterCriteria | None = None) -> dict[str, dict[str, int]]:
        """Get counts for each filter dimension.

        Args:
            base_criteria: Optional base criteria to apply first

        Returns:
            Dictionary with counts per filter dimension
        """
        counts: dict[str, dict[str, int]] = {}

        # Get base WHERE clause if criteria provided
        base_where = "1=1"
        base_params: list[Any] = []
        if base_criteria and not base_criteria.is_empty():
            base_where, base_params = self._build_filter_query(base_criteria)

        # Age bracket counts
        counts["age_brackets"] = {}
        for bracket_name, (min_days, max_days) in self.AGE_BRACKETS.items():
            conditions = [base_where]
            params = list(base_params)

            conditions.append("age_days >= ?")
            params.append(min_days)

            if max_days is not None:
                conditions.append("age_days <= ?")
                params.append(max_days)

            query = f"""
                SELECT COUNT(*) as count
                FROM inactive_mailboxes
                WHERE {' AND '.join(conditions)}
            """
            result = self._db.execute_query(query, params)
            counts["age_brackets"][bracket_name] = result[0]["count"] if result else 0

        # Size bracket counts
        counts["size_brackets"] = {}
        for bracket_name, (min_mb, max_mb) in self.SIZE_BRACKETS.items():
            conditions = [base_where]
            params = list(base_params)

            conditions.append("size_mb >= ?")
            params.append(min_mb)

            if max_mb is not None:
                conditions.append("size_mb <= ?")
                params.append(max_mb)

            query = f"""
                SELECT COUNT(*) as count
                FROM inactive_mailboxes
                WHERE {' AND '.join(conditions)}
            """
            result = self._db.execute_query(query, params)
            counts["size_brackets"][bracket_name] = result[0]["count"] if result else 0

        # Hold status counts
        counts["hold_status"] = {}
        for has_hold, label in [(True, "Has Holds"), (False, "No Holds")]:
            conditions = [base_where]
            params = list(base_params)

            if has_hold:
                conditions.append(
                    "(hold_types != '[]' AND hold_types IS NOT NULL AND hold_types != '')"
                )
            else:
                conditions.append(
                    "(hold_types = '[]' OR hold_types IS NULL OR hold_types = '')"
                )

            query = f"""
                SELECT COUNT(*) as count
                FROM inactive_mailboxes
                WHERE {' AND '.join(conditions)}
            """
            result = self._db.execute_query(query, params)
            counts["hold_status"][label] = result[0]["count"] if result else 0

        # Recovery status counts
        counts["recovery_status"] = {}
        for eligible, label in [(True, "Eligible"), (False, "Blocked")]:
            conditions = [base_where]
            params = list(base_params)

            conditions.append("recovery_eligible = ?")
            params.append(1 if eligible else 0)

            query = f"""
                SELECT COUNT(*) as count
                FROM inactive_mailboxes
                WHERE {' AND '.join(conditions)}
            """
            result = self._db.execute_query(query, params)
            counts["recovery_status"][label] = result[0]["count"] if result else 0

        # License type counts
        counts["license_types"] = {}
        query = f"""
            SELECT license_type, COUNT(*) as count
            FROM inactive_mailboxes
            WHERE {base_where} AND license_type IS NOT NULL AND license_type != ''
            GROUP BY license_type
            ORDER BY count DESC
        """
        results = self._db.execute_query(query, base_params)
        for row in results:
            counts["license_types"][row["license_type"]] = row["count"]

        # Operating company counts
        counts["operating_companies"] = {}
        query = f"""
            SELECT operating_company, COUNT(*) as count
            FROM inactive_mailboxes
            WHERE {base_where} AND operating_company IS NOT NULL AND operating_company != ''
            GROUP BY operating_company
            ORDER BY count DESC
        """
        results = self._db.execute_query(query, base_params)
        for row in results:
            counts["operating_companies"][row["operating_company"]] = row["count"]

        return counts

    def get_age_bracket(self, age_days: int) -> str:
        """Get the age bracket name for a given age.

        Args:
            age_days: Age in days

        Returns:
            Age bracket name
        """
        for bracket_name, (min_days, max_days) in self.AGE_BRACKETS.items():
            if max_days is None:
                if age_days >= min_days:
                    return bracket_name
            elif min_days <= age_days <= max_days:
                return bracket_name
        return "Unknown"

    def get_size_bracket(self, size_mb: float) -> str:
        """Get the size bracket name for a given size.

        Args:
            size_mb: Size in megabytes

        Returns:
            Size bracket name
        """
        for bracket_name, (min_mb, max_mb) in self.SIZE_BRACKETS.items():
            if max_mb is None:
                if size_mb >= min_mb:
                    return bracket_name
            elif min_mb <= size_mb <= max_mb:
                return bracket_name
        return "Unknown"
