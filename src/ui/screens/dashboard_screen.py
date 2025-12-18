"""Dashboard screen with overview metrics and charts."""

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Grid, Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Static

from src.core.dashboard_service import DashboardService, format_size
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.data.session import SessionManager

logger = get_logger(__name__)


class MetricCardWidget(Static):
    """A metric card widget displaying a value and label."""

    def __init__(
        self,
        value: str,
        label: str,
        trend: str = "",
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the metric card.

        Args:
            value: The metric value to display
            label: The label describing the metric
            trend: Optional trend indicator
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes or "metric-card")
        self._value = value
        self._label = label
        self._trend = trend

    def compose(self) -> ComposeResult:
        """Compose the widget layout."""
        yield Static(self._value, classes="metric-value")
        yield Static(self._label, classes="metric-label")
        if self._trend:
            yield Static(self._trend, classes="metric-trend")


class DashboardScreen(Screen):
    """Dashboard screen showing overview metrics and statistics.

    Displays key metrics, charts, and summary information about
    inactive mailboxes in a grid layout.
    """

    BINDINGS = [
        Binding("escape", "back", "Back", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("e", "export", "Export", show=True),
    ]

    def __init__(
        self,
        session: "SessionManager | None" = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the dashboard screen.

        Args:
            session: Session manager for data access
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._session = session
        self._dashboard_service = DashboardService()

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        with VerticalScroll():
            # Header
            yield Static("[bold]Dashboard Overview[/bold]", classes="title")

            # Metrics Cards Row
            with Grid(id="metrics-grid"):
                yield MetricCardWidget("--", "Total Mailboxes", id="metric-total")
                yield MetricCardWidget("--", "Total Storage", id="metric-storage")
                yield MetricCardWidget("--", "Monthly Cost", id="metric-cost")
                yield MetricCardWidget("--", "On Hold", id="metric-holds")

            # Status Distribution Section
            with Container(classes="panel"):
                yield Static("[bold]Hold Distribution[/bold]", classes="section-title")
                yield Static("", id="hold-distribution")

            # Age Distribution Section
            with Container(classes="panel"):
                yield Static("[bold]Age Distribution[/bold]", classes="section-title")
                yield Static("", id="age-distribution")

            # Top Mailboxes by Size
            with Container(classes="panel"):
                yield Static("[bold]Top Mailboxes by Size[/bold]", classes="section-title")
                yield Static("", id="top-mailboxes")

            # Cost Summary
            with Container(classes="panel"):
                yield Static("[bold]Cost Summary[/bold]", classes="section-title")
                yield Static("", id="cost-summary")

    def on_mount(self) -> None:
        """Handle screen mount."""
        logger.debug("DashboardScreen mounted")
        self._load_dashboard_data()

    def _load_dashboard_data(self) -> None:
        """Load and display dashboard data."""
        if not self._session:
            self._show_no_data()
            return

        try:
            mailboxes = self._session.db.get_all_mailboxes()
            if not mailboxes:
                self._show_no_data()
                return

            # Generate dashboard data
            dashboard = self._dashboard_service.generate_dashboard(mailboxes)

            # Update metric cards
            self._update_metrics(dashboard.metrics, mailboxes)

            # Update hold distribution
            self._update_hold_distribution(mailboxes)

            # Update age distribution
            self._update_age_distribution(mailboxes)

            # Update top mailboxes
            self._update_top_mailboxes(mailboxes)

            # Update cost summary
            self._update_cost_summary(mailboxes)

        except Exception as e:
            logger.error(f"Failed to load dashboard: {e}")
            self.app.notify(f"Error loading dashboard: {e}", severity="error")

    def _show_no_data(self) -> None:
        """Show no data message."""
        self.query_one("#metric-total", MetricCardWidget).update("0")
        self.query_one("#metric-storage", MetricCardWidget).update("0 GB")
        self.query_one("#metric-cost", MetricCardWidget).update("$0")
        self.query_one("#metric-holds", MetricCardWidget).update("0")

    def _update_metrics(self, metrics: list, mailboxes: list) -> None:
        """Update the metric cards.

        Args:
            metrics: List of metric cards from dashboard service
            mailboxes: List of mailboxes for calculations
        """
        total = len(mailboxes)
        total_size_mb = sum(m.size_mb for m in mailboxes)
        total_cost = sum(m.monthly_cost for m in mailboxes)
        on_hold = sum(1 for m in mailboxes if m.litigation_hold or m.hold_types)

        # Update displays
        metric_total = self.query_one("#metric-total", Static)
        metric_total.update(f"{total:,}")

        metric_storage = self.query_one("#metric-storage", Static)
        metric_storage.update(format_size(total_size_mb))

        metric_cost = self.query_one("#metric-cost", Static)
        metric_cost.update(f"${total_cost:,.2f}")

        metric_holds = self.query_one("#metric-holds", Static)
        metric_holds.update(f"{on_hold:,}")

    def _update_hold_distribution(self, mailboxes: list) -> None:
        """Update the hold distribution display.

        Args:
            mailboxes: List of mailboxes
        """
        litigation = sum(1 for m in mailboxes if m.litigation_hold)
        in_place = sum(1 for m in mailboxes if m.hold_types and not m.litigation_hold)
        no_hold = len(mailboxes) - litigation - in_place

        distribution_text = (
            f"[hold-litigation]Litigation Hold: {litigation}[/hold-litigation]\n"
            f"[hold-ediscovery]In-Place Holds: {in_place}[/hold-ediscovery]\n"
            f"[hold-none]No Hold: {no_hold}[/hold-none]"
        )

        self.query_one("#hold-distribution", Static).update(distribution_text)

    def _update_age_distribution(self, mailboxes: list) -> None:
        """Update the age distribution display.

        Args:
            mailboxes: List of mailboxes
        """
        age_0_30 = sum(1 for m in mailboxes if m.age_days <= 30)
        age_31_90 = sum(1 for m in mailboxes if 30 < m.age_days <= 90)
        age_91_180 = sum(1 for m in mailboxes if 90 < m.age_days <= 180)
        age_180_plus = sum(1 for m in mailboxes if m.age_days > 180)

        distribution_text = (
            f"0-30 days: {age_0_30}\n"
            f"31-90 days: {age_31_90}\n"
            f"91-180 days: {age_91_180}\n"
            f"180+ days: {age_180_plus}"
        )

        self.query_one("#age-distribution", Static).update(distribution_text)

    def _update_top_mailboxes(self, mailboxes: list) -> None:
        """Update the top mailboxes display.

        Args:
            mailboxes: List of mailboxes
        """
        # Sort by size and take top 5
        sorted_mailboxes = sorted(mailboxes, key=lambda m: m.size_mb, reverse=True)[:5]

        lines = []
        for i, mailbox in enumerate(sorted_mailboxes, 1):
            lines.append(
                f"{i}. {mailbox.display_name[:30]} - {format_size(mailbox.size_mb)}"
            )

        self.query_one("#top-mailboxes", Static).update("\n".join(lines) or "No data")

    def _update_cost_summary(self, mailboxes: list) -> None:
        """Update the cost summary display.

        Args:
            mailboxes: List of mailboxes
        """
        total_monthly = sum(m.monthly_cost for m in mailboxes)
        total_annual = total_monthly * 12

        # Group by license type
        license_costs: dict[str, float] = {}
        for mailbox in mailboxes:
            license_type = mailbox.license_type or "Unknown"
            license_costs[license_type] = license_costs.get(license_type, 0) + mailbox.monthly_cost

        lines = [
            f"Total Monthly: ${total_monthly:,.2f}",
            f"Total Annual: ${total_annual:,.2f}",
            "",
            "By License Type:",
        ]

        for license_type, cost in sorted(license_costs.items(), key=lambda x: -x[1]):
            if cost > 0:
                lines.append(f"  {license_type}: ${cost:,.2f}/month")

        self.query_one("#cost-summary", Static).update("\n".join(lines))

    def action_back(self) -> None:
        """Go back to the main screen."""
        self.app.pop_screen()

    def action_refresh(self) -> None:
        """Refresh dashboard data."""
        self._load_dashboard_data()
        self.app.notify("Dashboard refreshed", timeout=2)

    def action_export(self) -> None:
        """Export dashboard data."""
        self.app.notify("Exporting dashboard report...", timeout=2)
