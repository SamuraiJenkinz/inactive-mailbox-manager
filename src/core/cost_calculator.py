"""Cost calculator for inactive mailbox license cost analysis."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from src.data.models import InactiveMailbox
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.data.session import SessionManager

logger = get_logger(__name__)


class LicenseType(Enum):
    """Types of licenses that may be assigned to mailboxes."""

    EXCHANGE_ONLINE_P1 = "Exchange Online Plan 1"
    EXCHANGE_ONLINE_P2 = "Exchange Online Plan 2"
    M365_E3 = "Microsoft 365 E3"
    M365_E5 = "Microsoft 365 E5"
    M365_F3 = "Microsoft 365 F3"
    ARCHIVE_ADDON = "Exchange Online Archiving"
    UNKNOWN = "Unknown"


# Default monthly license costs (Exchange portion for M365)
DEFAULT_LICENSE_COSTS: dict[LicenseType, float] = {
    LicenseType.EXCHANGE_ONLINE_P1: 4.00,
    LicenseType.EXCHANGE_ONLINE_P2: 8.00,
    LicenseType.M365_E3: 8.00,  # Exchange portion
    LicenseType.M365_E5: 12.00,  # Exchange portion
    LicenseType.M365_F3: 4.00,  # Exchange portion
    LicenseType.ARCHIVE_ADDON: 3.00,
    LicenseType.UNKNOWN: 8.00,  # Default assumption
}


@dataclass
class LicenseCost:
    """License cost information."""

    license_type: LicenseType
    monthly_cost: float
    annual_cost: float
    description: str

    @classmethod
    def from_type(cls, license_type: LicenseType, monthly_cost: float | None = None) -> "LicenseCost":
        """Create LicenseCost from type with default or custom cost."""
        cost = monthly_cost if monthly_cost is not None else DEFAULT_LICENSE_COSTS.get(license_type, 8.00)
        return cls(
            license_type=license_type,
            monthly_cost=cost,
            annual_cost=cost * 12,
            description=license_type.value,
        )


@dataclass
class MailboxCostInfo:
    """Cost information for a single mailbox."""

    identity: str
    display_name: str
    license_type: LicenseType
    monthly_cost: float
    annual_cost: float
    age_days: int
    total_cost_to_date: float
    size_mb: float
    hold_types: list[str] = field(default_factory=list)
    department: str | None = None
    has_archive: bool = False
    archive_cost: float = 0.0

    @property
    def total_monthly_cost(self) -> float:
        """Get total monthly cost including archive."""
        return self.monthly_cost + self.archive_cost

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "identity": self.identity,
            "display_name": self.display_name,
            "license_type": self.license_type.value,
            "monthly_cost": self.monthly_cost,
            "annual_cost": self.annual_cost,
            "age_days": self.age_days,
            "total_cost_to_date": self.total_cost_to_date,
            "size_mb": self.size_mb,
            "hold_types": ", ".join(self.hold_types),
            "department": self.department or "",
            "has_archive": self.has_archive,
            "archive_cost": self.archive_cost,
            "total_monthly_cost": self.total_monthly_cost,
        }


@dataclass
class CostSummary:
    """Summary of costs across multiple mailboxes."""

    total_mailboxes: int = 0
    total_monthly_cost: float = 0.0
    total_annual_cost: float = 0.0
    by_license_type: dict[str, float] = field(default_factory=dict)
    by_hold_type: dict[str, float] = field(default_factory=dict)
    by_age_bracket: dict[str, float] = field(default_factory=dict)
    by_department: dict[str, float] = field(default_factory=dict)
    by_size_bracket: dict[str, float] = field(default_factory=dict)
    potential_savings: float = 0.0
    average_monthly_cost: float = 0.0
    average_age_days: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "total_mailboxes": self.total_mailboxes,
            "total_monthly_cost": self.total_monthly_cost,
            "total_annual_cost": self.total_annual_cost,
            "average_monthly_cost": self.average_monthly_cost,
            "average_age_days": self.average_age_days,
            "potential_savings": self.potential_savings,
            "by_license_type": self.by_license_type,
            "by_hold_type": self.by_hold_type,
            "by_age_bracket": self.by_age_bracket,
            "by_department": self.by_department,
            "by_size_bracket": self.by_size_bracket,
        }


@dataclass
class CostConfig:
    """Configuration for cost calculations."""

    license_costs: dict[LicenseType, float] = field(default_factory=lambda: dict(DEFAULT_LICENSE_COSTS))
    default_license_type: LicenseType = LicenseType.UNKNOWN
    include_archive_costs: bool = True
    archive_monthly_cost: float = 3.00
    currency_symbol: str = "$"
    decimal_places: int = 2


@dataclass
class CostReport:
    """Complete cost report with analysis and recommendations."""

    generated_at: datetime
    summary: CostSummary
    top_cost_mailboxes: list[MailboxCostInfo]
    oldest_mailboxes: list[MailboxCostInfo]
    largest_mailboxes: list[MailboxCostInfo]
    recommendations: list[str]
    config_used: CostConfig

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "generated_at": self.generated_at.isoformat(),
            "summary": self.summary.to_dict(),
            "top_cost_mailboxes": [m.to_dict() for m in self.top_cost_mailboxes],
            "oldest_mailboxes": [m.to_dict() for m in self.oldest_mailboxes],
            "largest_mailboxes": [m.to_dict() for m in self.largest_mailboxes],
            "recommendations": self.recommendations,
        }


class CostCalculatorError(Exception):
    """Raised when cost calculation fails."""

    pass


class CostCalculator:
    """Calculator for inactive mailbox license costs.

    Provides cost analysis, aggregation by multiple dimensions,
    and recommendations for cost optimization.
    """

    # Age brackets in days
    AGE_BRACKETS = {
        "0-90 days": (0, 90),
        "91-180 days": (91, 180),
        "181-365 days": (181, 365),
        "1-2 years": (366, 730),
        "2+ years": (731, float("inf")),
    }

    # Size brackets in MB
    SIZE_BRACKETS = {
        "< 100 MB": (0, 99),
        "100 MB - 1 GB": (100, 1023),
        "1 GB - 5 GB": (1024, 5119),
        "5 GB - 25 GB": (5120, 25599),
        "> 25 GB": (25600, float("inf")),
    }

    def __init__(
        self,
        session: "SessionManager",
        config: CostConfig | None = None,
    ) -> None:
        """Initialize cost calculator.

        Args:
            session: Session manager for data access
            config: Optional cost configuration
        """
        self._session = session
        self._config = config or CostConfig()
        self._db = session.db

        logger.debug("CostCalculator initialized")

    def calculate_mailbox_cost(self, mailbox: InactiveMailbox) -> MailboxCostInfo:
        """Calculate cost for a single mailbox.

        Args:
            mailbox: Inactive mailbox to analyze

        Returns:
            MailboxCostInfo with cost details
        """
        # Detect license type
        license_type = self._detect_license_type(mailbox)

        # Get monthly cost for license
        monthly_cost = self._config.license_costs.get(
            license_type,
            self._config.license_costs.get(LicenseType.UNKNOWN, 8.00),
        )

        # Calculate age
        age_days = 0
        if mailbox.disconnected_date:
            age_days = (datetime.now() - mailbox.disconnected_date).days

        # Calculate total cost to date
        months_inactive = max(1, age_days / 30)
        total_cost = monthly_cost * months_inactive

        # Archive cost
        archive_cost = 0.0
        has_archive = self._has_archive(mailbox)
        if has_archive and self._config.include_archive_costs:
            archive_cost = self._config.archive_monthly_cost
            total_cost += archive_cost * months_inactive

        # Extract hold types
        hold_types = self._extract_hold_types(mailbox)

        # Extract department
        department = self._extract_department(mailbox)

        return MailboxCostInfo(
            identity=mailbox.identity,
            display_name=mailbox.display_name,
            license_type=license_type,
            monthly_cost=monthly_cost,
            annual_cost=monthly_cost * 12,
            age_days=age_days,
            total_cost_to_date=total_cost,
            size_mb=mailbox.total_item_size_mb,
            hold_types=hold_types,
            department=department,
            has_archive=has_archive,
            archive_cost=archive_cost,
        )

    def calculate_total_costs(
        self,
        mailboxes: list[InactiveMailbox] | None = None,
    ) -> CostSummary:
        """Calculate total costs for all mailboxes.

        Args:
            mailboxes: Optional list of mailboxes (loads from DB if not provided)

        Returns:
            CostSummary with aggregated costs
        """
        if mailboxes is None:
            mailboxes = self._db.get_all_mailboxes()

        if not mailboxes:
            return CostSummary()

        summary = CostSummary()
        summary.total_mailboxes = len(mailboxes)

        # Initialize aggregation dicts
        by_license: dict[str, float] = {}
        by_hold: dict[str, float] = {}
        by_age: dict[str, float] = {}
        by_dept: dict[str, float] = {}
        by_size: dict[str, float] = {}

        total_age = 0
        recovery_eligible_cost = 0.0

        for mailbox in mailboxes:
            cost_info = self.calculate_mailbox_cost(mailbox)

            # Total costs
            summary.total_monthly_cost += cost_info.total_monthly_cost
            summary.total_annual_cost += cost_info.annual_cost + (cost_info.archive_cost * 12)

            # By license type
            license_key = cost_info.license_type.value
            by_license[license_key] = by_license.get(license_key, 0) + cost_info.total_monthly_cost

            # By hold type
            if cost_info.hold_types:
                for hold in cost_info.hold_types:
                    by_hold[hold] = by_hold.get(hold, 0) + cost_info.total_monthly_cost
            else:
                by_hold["No Hold"] = by_hold.get("No Hold", 0) + cost_info.total_monthly_cost

            # By age bracket
            age_bracket = self._get_age_bracket(cost_info.age_days)
            by_age[age_bracket] = by_age.get(age_bracket, 0) + cost_info.total_monthly_cost

            # By department
            dept = cost_info.department or "Unknown"
            by_dept[dept] = by_dept.get(dept, 0) + cost_info.total_monthly_cost

            # By size bracket
            size_bracket = self._get_size_bracket(cost_info.size_mb)
            by_size[size_bracket] = by_size.get(size_bracket, 0) + cost_info.total_monthly_cost

            # Track for averages
            total_age += cost_info.age_days

            # Potential savings (no holds = recovery eligible)
            if not cost_info.hold_types or cost_info.hold_types == ["No Hold"]:
                recovery_eligible_cost += cost_info.total_monthly_cost

        summary.by_license_type = by_license
        summary.by_hold_type = by_hold
        summary.by_age_bracket = by_age
        summary.by_department = by_dept
        summary.by_size_bracket = by_size

        summary.average_monthly_cost = summary.total_monthly_cost / summary.total_mailboxes
        summary.average_age_days = total_age / summary.total_mailboxes
        summary.potential_savings = recovery_eligible_cost

        return summary

    def calculate_potential_savings(
        self,
        mailboxes: list[InactiveMailbox] | None = None,
    ) -> float:
        """Calculate potential monthly savings from cleanup.

        Args:
            mailboxes: Optional list of mailboxes

        Returns:
            Potential monthly savings amount
        """
        if mailboxes is None:
            mailboxes = self._db.get_all_mailboxes()

        savings = 0.0
        for mailbox in mailboxes:
            cost_info = self.calculate_mailbox_cost(mailbox)
            # Only count mailboxes without legal holds
            if not cost_info.hold_types or cost_info.hold_types == ["No Hold"]:
                savings += cost_info.total_monthly_cost

        return savings

    def get_cost_by_dimension(
        self,
        dimension: str,
        mailboxes: list[InactiveMailbox] | None = None,
    ) -> dict[str, float]:
        """Get costs aggregated by a specific dimension.

        Args:
            dimension: "license_type", "hold_type", "age", "department", "size"
            mailboxes: Optional list of mailboxes

        Returns:
            Dictionary of dimension values to monthly costs
        """
        summary = self.calculate_total_costs(mailboxes)

        dimension_map = {
            "license_type": summary.by_license_type,
            "hold_type": summary.by_hold_type,
            "age": summary.by_age_bracket,
            "department": summary.by_department,
            "size": summary.by_size_bracket,
        }

        return dimension_map.get(dimension, {})

    def generate_cost_report(
        self,
        mailboxes: list[InactiveMailbox] | None = None,
        top_limit: int = 10,
    ) -> CostReport:
        """Generate a comprehensive cost report.

        Args:
            mailboxes: Optional list of mailboxes
            top_limit: Number of items for top lists

        Returns:
            CostReport with full analysis
        """
        if mailboxes is None:
            mailboxes = self._db.get_all_mailboxes()

        # Calculate summary
        summary = self.calculate_total_costs(mailboxes)

        # Get cost info for all mailboxes
        cost_infos = [self.calculate_mailbox_cost(m) for m in mailboxes]

        # Top by cost
        top_cost = sorted(cost_infos, key=lambda x: x.total_monthly_cost, reverse=True)[:top_limit]

        # Top by age
        oldest = sorted(cost_infos, key=lambda x: x.age_days, reverse=True)[:top_limit]

        # Top by size
        largest = sorted(cost_infos, key=lambda x: x.size_mb, reverse=True)[:top_limit]

        # Generate recommendations
        recommendations = self._generate_recommendations(summary, cost_infos)

        return CostReport(
            generated_at=datetime.now(),
            summary=summary,
            top_cost_mailboxes=top_cost,
            oldest_mailboxes=oldest,
            largest_mailboxes=largest,
            recommendations=recommendations,
            config_used=self._config,
        )

    def get_top_cost_mailboxes(
        self,
        mailboxes: list[InactiveMailbox] | None = None,
        limit: int = 10,
    ) -> list[MailboxCostInfo]:
        """Get mailboxes with highest monthly cost.

        Args:
            mailboxes: Optional list of mailboxes
            limit: Number of mailboxes to return

        Returns:
            List of MailboxCostInfo sorted by cost
        """
        if mailboxes is None:
            mailboxes = self._db.get_all_mailboxes()

        cost_infos = [self.calculate_mailbox_cost(m) for m in mailboxes]
        return sorted(cost_infos, key=lambda x: x.total_monthly_cost, reverse=True)[:limit]

    def format_cost(self, amount: float) -> str:
        """Format a cost amount for display.

        Args:
            amount: Cost amount

        Returns:
            Formatted string
        """
        symbol = self._config.currency_symbol
        places = self._config.decimal_places
        return f"{symbol}{amount:,.{places}f}"

    # Private helper methods

    def _detect_license_type(self, mailbox: InactiveMailbox) -> LicenseType:
        """Detect license type from mailbox properties.

        Args:
            mailbox: Mailbox to analyze

        Returns:
            Detected LicenseType
        """
        # Check for archive (indicates higher plan)
        if self._has_archive(mailbox):
            # E3/E5 typically include archive
            if mailbox.total_item_size_mb > 50000:  # >50GB suggests E5
                return LicenseType.M365_E5
            return LicenseType.M365_E3

        # Check size for plan hints
        size_mb = mailbox.total_item_size_mb

        if size_mb > 100000:  # >100GB
            return LicenseType.M365_E5
        elif size_mb > 50000:  # >50GB
            return LicenseType.M365_E3
        elif size_mb > 10000:  # >10GB
            return LicenseType.EXCHANGE_ONLINE_P2

        return self._config.default_license_type

    def _has_archive(self, mailbox: InactiveMailbox) -> bool:
        """Check if mailbox has an archive.

        Args:
            mailbox: Mailbox to check

        Returns:
            True if archive exists
        """
        # Check raw data for archive indicators
        if mailbox.raw_data:
            archive_status = mailbox.raw_data.get("ArchiveStatus", "")
            archive_guid = mailbox.raw_data.get("ArchiveGuid", "")
            return archive_status == "Active" or (archive_guid and archive_guid != "00000000-0000-0000-0000-000000000000")
        return False

    def _extract_hold_types(self, mailbox: InactiveMailbox) -> list[str]:
        """Extract hold types from mailbox.

        Args:
            mailbox: Mailbox to analyze

        Returns:
            List of hold type strings
        """
        holds = []

        if mailbox.litigation_hold_enabled:
            holds.append("Litigation Hold")

        if mailbox.in_place_holds:
            # Parse hold GUIDs
            for hold in mailbox.in_place_holds:
                if hold.startswith("UniH"):
                    holds.append("eDiscovery Hold")
                elif hold.startswith("mbx"):
                    holds.append("In-Place Hold")
                elif hold.startswith("grp"):
                    holds.append("Group Hold")
                elif hold.startswith("cld"):
                    holds.append("Retention Policy")
                elif hold.startswith("skp"):
                    holds.append("Skype Hold")
                elif "delay" in hold.lower():
                    holds.append("Delay Hold")
                else:
                    holds.append("Other Hold")

        # Deduplicate
        return list(set(holds)) if holds else []

    def _extract_department(self, mailbox: InactiveMailbox) -> str | None:
        """Extract department from mailbox.

        Args:
            mailbox: Mailbox to analyze

        Returns:
            Department name or None
        """
        # Try raw data first
        if mailbox.raw_data:
            dept = mailbox.raw_data.get("Department")
            if dept:
                return dept

            # Try custom attributes
            for i in range(1, 16):
                attr = mailbox.raw_data.get(f"CustomAttribute{i}")
                if attr and "dept" in attr.lower():
                    return attr

        # Try to parse from display name (e.g., "John Doe - IT")
        if " - " in mailbox.display_name:
            parts = mailbox.display_name.split(" - ")
            if len(parts) > 1:
                return parts[-1].strip()

        return None

    def _get_age_bracket(self, days: int) -> str:
        """Get age bracket for a number of days.

        Args:
            days: Age in days

        Returns:
            Age bracket string
        """
        for bracket, (min_days, max_days) in self.AGE_BRACKETS.items():
            if min_days <= days <= max_days:
                return bracket
        return "2+ years"

    def _get_size_bracket(self, size_mb: float) -> str:
        """Get size bracket for a size in MB.

        Args:
            size_mb: Size in megabytes

        Returns:
            Size bracket string
        """
        for bracket, (min_mb, max_mb) in self.SIZE_BRACKETS.items():
            if min_mb <= size_mb <= max_mb:
                return bracket
        return "> 25 GB"

    def _generate_recommendations(
        self,
        summary: CostSummary,
        cost_infos: list[MailboxCostInfo],
    ) -> list[str]:
        """Generate cost optimization recommendations.

        Args:
            summary: Cost summary
            cost_infos: Individual mailbox costs

        Returns:
            List of recommendation strings
        """
        recommendations = []

        # Check potential savings
        if summary.potential_savings > 0:
            annual_savings = summary.potential_savings * 12
            recommendations.append(
                f"Potential annual savings of {self.format_cost(annual_savings)} "
                f"by recovering/deleting {len([c for c in cost_infos if not c.hold_types])} "
                f"mailboxes without legal holds."
            )

        # Check for very old mailboxes
        very_old = [c for c in cost_infos if c.age_days > 730]  # >2 years
        if very_old:
            old_cost = sum(c.total_monthly_cost for c in very_old)
            recommendations.append(
                f"Review {len(very_old)} mailboxes inactive for over 2 years "
                f"(monthly cost: {self.format_cost(old_cost)}). "
                f"Verify business need for retention."
            )

        # Check for high-cost mailboxes without holds
        high_cost_no_holds = [
            c for c in cost_infos
            if c.total_monthly_cost > 15 and not c.hold_types
        ]
        if high_cost_no_holds:
            recommendations.append(
                f"Priority cleanup: {len(high_cost_no_holds)} high-cost mailboxes "
                f"(>${self.format_cost(15)}/month) without legal holds."
            )

        # Department-specific recommendations
        if summary.by_department:
            top_dept = max(summary.by_department.items(), key=lambda x: x[1])
            if top_dept[1] > summary.total_monthly_cost * 0.3:  # >30% of cost
                recommendations.append(
                    f"Department '{top_dept[0]}' accounts for {self.format_cost(top_dept[1])}/month "
                    f"({top_dept[1]/summary.total_monthly_cost*100:.1f}% of total). "
                    f"Consider departmental review."
                )

        # Archive recommendations
        with_archive = [c for c in cost_infos if c.has_archive]
        if with_archive and len(with_archive) > len(cost_infos) * 0.5:
            recommendations.append(
                f"{len(with_archive)} mailboxes ({len(with_archive)/len(cost_infos)*100:.1f}%) "
                f"have archives. Review if archive retention is still required."
            )

        return recommendations if recommendations else ["No immediate cost optimization opportunities identified."]
