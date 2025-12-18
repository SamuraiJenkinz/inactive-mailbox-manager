"""Dashboard service for preparing visualization data."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from src.core.cost_calculator import CostCalculator, CostConfig
from src.core.statistics_service import StatisticsService
from src.data.models import InactiveMailbox
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.data.session import SessionManager

logger = get_logger(__name__)


class ChartType(Enum):
    """Types of charts for visualization."""

    PIE = "pie"
    BAR = "bar"
    LINE = "line"
    DONUT = "donut"
    TABLE = "table"
    GAUGE = "gauge"


# Color schemes for charts
CHART_COLORS = {
    "primary": ["#3498db", "#2ecc71", "#e74c3c", "#f39c12", "#9b59b6", "#1abc9c"],
    "cool": ["#1abc9c", "#3498db", "#9b59b6", "#34495e", "#7f8c8d", "#16a085"],
    "warm": ["#e74c3c", "#e67e22", "#f1c40f", "#d35400", "#c0392b", "#f39c12"],
    "neutral": ["#2c3e50", "#7f8c8d", "#95a5a6", "#bdc3c7", "#ecf0f1", "#34495e"],
}

HOLD_TYPE_COLORS = {
    "Litigation Hold": "#e74c3c",
    "eDiscovery Hold": "#9b59b6",
    "Retention Policy": "#3498db",
    "In-Place Hold": "#e67e22",
    "Delay Hold": "#f39c12",
    "No Hold": "#2ecc71",
    "Other Hold": "#7f8c8d",
}

STATUS_COLORS = {
    "success": "#2ecc71",
    "warning": "#f39c12",
    "error": "#e74c3c",
    "info": "#3498db",
    "default": "#7f8c8d",
}

LICENSE_COLORS = {
    "Exchange Online Plan 1": "#3498db",
    "Exchange Online Plan 2": "#2ecc71",
    "Microsoft 365 E3": "#9b59b6",
    "Microsoft 365 E5": "#e74c3c",
    "Microsoft 365 F3": "#f39c12",
    "Unknown": "#7f8c8d",
}


@dataclass
class ChartDataPoint:
    """Single data point for a chart."""

    label: str
    value: float
    color: str | None = None
    percentage: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "label": self.label,
            "value": self.value,
            "color": self.color,
            "percentage": self.percentage,
            "metadata": self.metadata,
        }


@dataclass
class ChartData:
    """Data for a single chart."""

    chart_type: ChartType
    title: str
    data_points: list[ChartDataPoint]
    total: float | None = None
    unit: str = ""  # "$", "GB", "count", "%"
    subtitle: str | None = None

    @property
    def labels(self) -> list[str]:
        """Get all labels."""
        return [dp.label for dp in self.data_points]

    @property
    def values(self) -> list[float]:
        """Get all values."""
        return [dp.value for dp in self.data_points]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "chart_type": self.chart_type.value,
            "title": self.title,
            "subtitle": self.subtitle,
            "data_points": [dp.to_dict() for dp in self.data_points],
            "total": self.total,
            "unit": self.unit,
            "labels": self.labels,
            "values": self.values,
        }


@dataclass
class MetricCard:
    """Data for a metric display card."""

    title: str
    value: str
    subtitle: str | None = None
    trend: str | None = None  # "up", "down", "stable"
    trend_value: str | None = None
    color: str = "default"  # "success", "warning", "error", "info"
    icon: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "value": self.value,
            "subtitle": self.subtitle,
            "trend": self.trend,
            "trend_value": self.trend_value,
            "color": self.color,
            "icon": self.icon,
        }


@dataclass
class DashboardData:
    """Complete dashboard data."""

    generated_at: datetime
    metrics: list[MetricCard]
    charts: dict[str, ChartData]
    top_lists: dict[str, list[dict]]
    health_indicators: dict[str, float]
    summary_text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "generated_at": self.generated_at.isoformat(),
            "metrics": [m.to_dict() for m in self.metrics],
            "charts": {k: v.to_dict() for k, v in self.charts.items()},
            "top_lists": self.top_lists,
            "health_indicators": self.health_indicators,
            "summary_text": self.summary_text,
        }


class DashboardServiceError(Exception):
    """Raised when dashboard generation fails."""

    pass


class DashboardService:
    """Service for generating dashboard visualization data.

    Provides structured data for dashboards and charts in both
    terminal and desktop UIs.
    """

    def __init__(
        self,
        session: "SessionManager",
        cost_config: CostConfig | None = None,
    ) -> None:
        """Initialize dashboard service.

        Args:
            session: Session manager for data access
            cost_config: Optional cost configuration
        """
        self._session = session
        self._db = session.db
        self._cost_calculator = CostCalculator(session, cost_config)
        self._stats_service = StatisticsService(session)

        logger.debug("DashboardService initialized")

    def generate_dashboard(
        self,
        mailboxes: list[InactiveMailbox] | None = None,
    ) -> DashboardData:
        """Generate complete dashboard data.

        Args:
            mailboxes: Optional list of mailboxes (loads from DB if not provided)

        Returns:
            DashboardData with all visualization data
        """
        if mailboxes is None:
            mailboxes = self._db.get_all_mailboxes()

        logger.info(f"Generating dashboard for {len(mailboxes)} mailboxes")

        # Get metrics
        metrics = self.get_executive_metrics(mailboxes)

        # Get charts
        charts = {
            "cost_by_license": self.get_cost_breakdown_chart(mailboxes),
            "hold_distribution": self.get_hold_distribution_chart(mailboxes),
            "age_distribution": self.get_age_distribution_chart(mailboxes),
            "size_distribution": self.get_size_distribution_chart(mailboxes),
        }

        # Get top lists
        top_lists = {
            "top_cost": self.get_top_cost_mailboxes(mailboxes),
            "oldest": self.get_oldest_mailboxes(mailboxes),
            "largest": self.get_largest_mailboxes(mailboxes),
        }

        # Get health indicators
        health = self.get_health_indicators(mailboxes)

        # Generate summary text
        summary = self._generate_summary_text(mailboxes, health)

        return DashboardData(
            generated_at=datetime.now(),
            metrics=metrics,
            charts=charts,
            top_lists=top_lists,
            health_indicators=health,
            summary_text=summary,
        )

    def get_executive_metrics(
        self,
        mailboxes: list[InactiveMailbox] | None = None,
    ) -> list[MetricCard]:
        """Get executive summary metrics.

        Args:
            mailboxes: Optional list of mailboxes

        Returns:
            List of MetricCard objects
        """
        if mailboxes is None:
            mailboxes = self._db.get_all_mailboxes()

        cost_summary = self._cost_calculator.calculate_total_costs(mailboxes)
        stats = self._stats_service.get_summary_stats()

        metrics = []

        # Total mailboxes
        metrics.append(MetricCard(
            title="Total Inactive Mailboxes",
            value=format_number(len(mailboxes)),
            subtitle="In inventory",
            color="info",
            icon="mailbox",
        ))

        # Monthly cost
        metrics.append(MetricCard(
            title="Monthly Cost",
            value=format_currency(cost_summary.total_monthly_cost),
            subtitle=f"{format_currency(cost_summary.total_annual_cost)}/year",
            color="warning",
            icon="dollar",
        ))

        # Recovery eligible
        recovery_count = stats.recovery_eligible
        recovery_pct = (recovery_count / len(mailboxes) * 100) if mailboxes else 0
        metrics.append(MetricCard(
            title="Recovery Eligible",
            value=format_number(recovery_count),
            subtitle=f"{recovery_pct:.1f}% of total",
            color="success",
            icon="check",
        ))

        # With holds
        with_holds = stats.with_holds
        holds_pct = (with_holds / len(mailboxes) * 100) if mailboxes else 0
        metrics.append(MetricCard(
            title="With Legal Holds",
            value=format_number(with_holds),
            subtitle=f"{holds_pct:.1f}% of total",
            color="error" if holds_pct > 50 else "warning",
            icon="lock",
        ))

        # Potential savings
        savings = cost_summary.potential_savings
        metrics.append(MetricCard(
            title="Potential Savings",
            value=format_currency(savings),
            subtitle="Monthly (no holds)",
            trend="up" if savings > cost_summary.total_monthly_cost * 0.1 else None,
            color="success",
            icon="savings",
        ))

        # Total storage
        total_size_gb = stats.total_size_gb
        metrics.append(MetricCard(
            title="Total Storage",
            value=format_size(total_size_gb * 1024),  # Convert to MB
            subtitle=f"{len(mailboxes)} mailboxes",
            color="info",
            icon="storage",
        ))

        return metrics

    def get_cost_breakdown_chart(
        self,
        mailboxes: list[InactiveMailbox] | None = None,
    ) -> ChartData:
        """Get cost breakdown by license type as pie chart.

        Args:
            mailboxes: Optional list of mailboxes

        Returns:
            ChartData for pie chart
        """
        cost_summary = self._cost_calculator.calculate_total_costs(mailboxes)
        by_license = cost_summary.by_license_type

        total = sum(by_license.values())
        data_points = []

        for i, (license_type, cost) in enumerate(sorted(by_license.items(), key=lambda x: x[1], reverse=True)):
            pct = (cost / total * 100) if total > 0 else 0
            color = LICENSE_COLORS.get(license_type, CHART_COLORS["primary"][i % len(CHART_COLORS["primary"])])

            data_points.append(ChartDataPoint(
                label=license_type,
                value=cost,
                color=color,
                percentage=pct,
            ))

        return ChartData(
            chart_type=ChartType.DONUT,
            title="Cost by License Type",
            subtitle="Monthly cost distribution",
            data_points=data_points,
            total=total,
            unit="$",
        )

    def get_hold_distribution_chart(
        self,
        mailboxes: list[InactiveMailbox] | None = None,
    ) -> ChartData:
        """Get hold type distribution as donut chart.

        Args:
            mailboxes: Optional list of mailboxes

        Returns:
            ChartData for donut chart
        """
        if mailboxes is None:
            mailboxes = self._db.get_all_mailboxes()

        # Count by hold type
        hold_counts: dict[str, int] = {}
        for mailbox in mailboxes:
            hold_types = self._get_hold_types(mailbox)
            if not hold_types:
                hold_counts["No Hold"] = hold_counts.get("No Hold", 0) + 1
            else:
                for hold in hold_types:
                    hold_counts[hold] = hold_counts.get(hold, 0) + 1

        total = sum(hold_counts.values())
        data_points = []

        for hold_type, count in sorted(hold_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total * 100) if total > 0 else 0
            color = HOLD_TYPE_COLORS.get(hold_type, CHART_COLORS["primary"][0])

            data_points.append(ChartDataPoint(
                label=hold_type,
                value=count,
                color=color,
                percentage=pct,
            ))

        return ChartData(
            chart_type=ChartType.DONUT,
            title="Hold Type Distribution",
            subtitle="Mailboxes by hold status",
            data_points=data_points,
            total=total,
            unit="count",
        )

    def get_age_distribution_chart(
        self,
        mailboxes: list[InactiveMailbox] | None = None,
    ) -> ChartData:
        """Get age distribution as bar chart.

        Args:
            mailboxes: Optional list of mailboxes

        Returns:
            ChartData for bar chart
        """
        if mailboxes is None:
            mailboxes = self._db.get_all_mailboxes()

        # Age brackets
        brackets = {
            "0-90 days": 0,
            "91-180 days": 0,
            "181-365 days": 0,
            "1-2 years": 0,
            "2+ years": 0,
        }

        for mailbox in mailboxes:
            if mailbox.disconnected_date:
                age_days = (datetime.now() - mailbox.disconnected_date).days
                if age_days <= 90:
                    brackets["0-90 days"] += 1
                elif age_days <= 180:
                    brackets["91-180 days"] += 1
                elif age_days <= 365:
                    brackets["181-365 days"] += 1
                elif age_days <= 730:
                    brackets["1-2 years"] += 1
                else:
                    brackets["2+ years"] += 1

        data_points = []
        colors = CHART_COLORS["cool"]

        for i, (bracket, count) in enumerate(brackets.items()):
            data_points.append(ChartDataPoint(
                label=bracket,
                value=count,
                color=colors[i % len(colors)],
            ))

        return ChartData(
            chart_type=ChartType.BAR,
            title="Age Distribution",
            subtitle="Mailboxes by time since disconnection",
            data_points=data_points,
            unit="count",
        )

    def get_size_distribution_chart(
        self,
        mailboxes: list[InactiveMailbox] | None = None,
    ) -> ChartData:
        """Get size distribution as bar chart.

        Args:
            mailboxes: Optional list of mailboxes

        Returns:
            ChartData for bar chart
        """
        if mailboxes is None:
            mailboxes = self._db.get_all_mailboxes()

        # Size brackets
        brackets = {
            "< 100 MB": 0,
            "100 MB - 1 GB": 0,
            "1 GB - 5 GB": 0,
            "5 GB - 25 GB": 0,
            "> 25 GB": 0,
        }

        for mailbox in mailboxes:
            size_mb = mailbox.total_item_size_mb
            if size_mb < 100:
                brackets["< 100 MB"] += 1
            elif size_mb < 1024:
                brackets["100 MB - 1 GB"] += 1
            elif size_mb < 5120:
                brackets["1 GB - 5 GB"] += 1
            elif size_mb < 25600:
                brackets["5 GB - 25 GB"] += 1
            else:
                brackets["> 25 GB"] += 1

        data_points = []
        colors = CHART_COLORS["warm"]

        for i, (bracket, count) in enumerate(brackets.items()):
            data_points.append(ChartDataPoint(
                label=bracket,
                value=count,
                color=colors[i % len(colors)],
            ))

        return ChartData(
            chart_type=ChartType.BAR,
            title="Size Distribution",
            subtitle="Mailboxes by storage size",
            data_points=data_points,
            unit="count",
        )

    def get_top_cost_mailboxes(
        self,
        mailboxes: list[InactiveMailbox] | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Get mailboxes with highest monthly cost.

        Args:
            mailboxes: Optional list of mailboxes
            limit: Number to return

        Returns:
            List of mailbox dictionaries
        """
        top_cost = self._cost_calculator.get_top_cost_mailboxes(mailboxes, limit)

        return [
            {
                "display_name": info.display_name,
                "identity": info.identity,
                "monthly_cost": format_currency(info.monthly_cost),
                "license_type": info.license_type.value,
                "age_days": info.age_days,
                "size_mb": format_size(info.size_mb),
            }
            for info in top_cost
        ]

    def get_oldest_mailboxes(
        self,
        mailboxes: list[InactiveMailbox] | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Get oldest inactive mailboxes.

        Args:
            mailboxes: Optional list of mailboxes
            limit: Number to return

        Returns:
            List of mailbox dictionaries
        """
        if mailboxes is None:
            mailboxes = self._db.get_all_mailboxes()

        # Sort by disconnected date
        sorted_mailboxes = sorted(
            mailboxes,
            key=lambda m: m.disconnected_date or datetime.min,
        )[:limit]

        return [
            {
                "display_name": m.display_name,
                "identity": m.identity,
                "disconnected_date": m.disconnected_date.strftime("%Y-%m-%d") if m.disconnected_date else "Unknown",
                "age_days": (datetime.now() - m.disconnected_date).days if m.disconnected_date else 0,
                "size_mb": format_size(m.total_item_size_mb),
            }
            for m in sorted_mailboxes
        ]

    def get_largest_mailboxes(
        self,
        mailboxes: list[InactiveMailbox] | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Get largest inactive mailboxes.

        Args:
            mailboxes: Optional list of mailboxes
            limit: Number to return

        Returns:
            List of mailbox dictionaries
        """
        if mailboxes is None:
            mailboxes = self._db.get_all_mailboxes()

        # Sort by size
        sorted_mailboxes = sorted(
            mailboxes,
            key=lambda m: m.total_item_size_mb,
            reverse=True,
        )[:limit]

        return [
            {
                "display_name": m.display_name,
                "identity": m.identity,
                "size_mb": format_size(m.total_item_size_mb),
                "item_count": format_number(m.total_item_count),
            }
            for m in sorted_mailboxes
        ]

    def get_health_indicators(
        self,
        mailboxes: list[InactiveMailbox] | None = None,
    ) -> dict[str, float]:
        """Get health indicator percentages.

        Args:
            mailboxes: Optional list of mailboxes

        Returns:
            Dictionary of indicator names to percentages
        """
        if mailboxes is None:
            mailboxes = self._db.get_all_mailboxes()

        if not mailboxes:
            return {
                "pct_with_holds": 0.0,
                "pct_recovery_eligible": 0.0,
                "avg_age_days": 0.0,
                "avg_size_mb": 0.0,
            }

        total = len(mailboxes)

        # Count with holds
        with_holds = sum(
            1 for m in mailboxes
            if m.litigation_hold_enabled or (m.in_place_holds and len(m.in_place_holds) > 0)
        )

        # Count recovery eligible
        recovery_eligible = total - with_holds

        # Average age
        ages = [
            (datetime.now() - m.disconnected_date).days
            for m in mailboxes
            if m.disconnected_date
        ]
        avg_age = sum(ages) / len(ages) if ages else 0

        # Average size
        avg_size = sum(m.total_item_size_mb for m in mailboxes) / total

        return {
            "pct_with_holds": (with_holds / total) * 100,
            "pct_recovery_eligible": (recovery_eligible / total) * 100,
            "avg_age_days": avg_age,
            "avg_size_mb": avg_size,
        }

    def _get_hold_types(self, mailbox: InactiveMailbox) -> list[str]:
        """Extract hold types from mailbox."""
        holds = []

        if mailbox.litigation_hold_enabled:
            holds.append("Litigation Hold")

        if mailbox.in_place_holds:
            for hold in mailbox.in_place_holds:
                if hold.startswith("UniH"):
                    holds.append("eDiscovery Hold")
                elif hold.startswith("mbx"):
                    holds.append("In-Place Hold")
                elif hold.startswith("cld"):
                    holds.append("Retention Policy")
                elif "delay" in hold.lower():
                    holds.append("Delay Hold")
                else:
                    holds.append("Other Hold")

        return list(set(holds))

    def _generate_summary_text(
        self,
        mailboxes: list[InactiveMailbox],
        health: dict[str, float],
    ) -> str:
        """Generate summary text for dashboard.

        Args:
            mailboxes: List of mailboxes
            health: Health indicators

        Returns:
            Summary text string
        """
        total = len(mailboxes)
        if total == 0:
            return "No inactive mailboxes found in the system."

        pct_holds = health["pct_with_holds"]
        avg_age = health["avg_age_days"]

        summary_parts = [
            f"Managing {format_number(total)} inactive mailboxes.",
        ]

        if pct_holds > 50:
            summary_parts.append(f"Note: {pct_holds:.1f}% are under legal hold.")
        elif pct_holds < 20:
            summary_parts.append(f"Good: Only {pct_holds:.1f}% are under legal hold.")

        if avg_age > 365:
            summary_parts.append(f"Average age: {avg_age:.0f} days ({avg_age/365:.1f} years).")
        else:
            summary_parts.append(f"Average age: {avg_age:.0f} days.")

        return " ".join(summary_parts)


# Formatting helper functions

def format_currency(value: float, symbol: str = "$", decimals: int = 2) -> str:
    """Format a currency value.

    Args:
        value: Currency amount
        symbol: Currency symbol
        decimals: Decimal places

    Returns:
        Formatted string
    """
    return f"{symbol}{value:,.{decimals}f}"


def format_size(size_mb: float) -> str:
    """Format a size value.

    Args:
        size_mb: Size in megabytes

    Returns:
        Formatted string
    """
    if size_mb < 1:
        return f"{size_mb * 1024:.0f} KB"
    elif size_mb < 1024:
        return f"{size_mb:.1f} MB"
    elif size_mb < 1024 * 1024:
        return f"{size_mb / 1024:.2f} GB"
    else:
        return f"{size_mb / (1024 * 1024):.2f} TB"


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format a percentage value.

    Args:
        value: Percentage value (0-100)
        decimals: Decimal places

    Returns:
        Formatted string
    """
    return f"{value:.{decimals}f}%"


def format_number(value: int | float) -> str:
    """Format a number with thousands separator.

    Args:
        value: Numeric value

    Returns:
        Formatted string
    """
    if isinstance(value, float):
        return f"{value:,.2f}"
    return f"{value:,}"


def format_date(dt: datetime | None) -> str:
    """Format a datetime value.

    Args:
        dt: Datetime value

    Returns:
        Formatted string
    """
    if dt is None:
        return "N/A"
    return dt.strftime("%Y-%m-%d")


def format_duration(days: int) -> str:
    """Format a duration in days.

    Args:
        days: Number of days

    Returns:
        Human-readable duration
    """
    if days < 30:
        return f"{days} days"
    elif days < 365:
        months = days // 30
        return f"{months} month{'s' if months > 1 else ''}"
    else:
        years = days // 365
        months = (days % 365) // 30
        if months > 0:
            return f"{years} year{'s' if years > 1 else ''}, {months} month{'s' if months > 1 else ''}"
        return f"{years} year{'s' if years > 1 else ''}"
