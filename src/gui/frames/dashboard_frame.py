"""Dashboard frame showing overview metrics and statistics."""

from typing import TYPE_CHECKING

import customtkinter as ctk

from src.gui.frames.base_frame import BaseFrame
from src.gui.theme import COLORS
from src.core.dashboard_service import DashboardService, format_size
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.data.session import SessionManager

logger = get_logger(__name__)


class MetricCard(ctk.CTkFrame):
    """A card widget displaying a metric value and label."""

    def __init__(
        self,
        master,
        value: str,
        label: str,
        **kwargs,
    ) -> None:
        """Initialize the metric card.

        Args:
            master: Parent widget
            value: Metric value to display
            label: Label for the metric
            **kwargs: Additional frame arguments
        """
        super().__init__(
            master,
            fg_color=COLORS["surface"],
            corner_radius=10,
            **kwargs,
        )

        # Value label
        self._value_label = ctk.CTkLabel(
            self,
            text=value,
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color=COLORS["primary"],
        )
        self._value_label.pack(pady=(20, 5))

        # Description label
        self._label = ctk.CTkLabel(
            self,
            text=label,
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_muted"],
        )
        self._label.pack(pady=(0, 20))

    def set_value(self, value: str) -> None:
        """Update the metric value.

        Args:
            value: New value to display
        """
        self._value_label.configure(text=value)


class DashboardFrame(BaseFrame):
    """Dashboard frame with overview metrics and statistics.

    Displays key metrics, distribution charts, and
    summary information about inactive mailboxes.
    """

    def __init__(
        self,
        master,
        session: "SessionManager | None" = None,
        **kwargs,
    ) -> None:
        """Initialize the dashboard frame.

        Args:
            master: Parent widget
            session: Session manager for data access
            **kwargs: Additional frame arguments
        """
        super().__init__(master, session, **kwargs)

        self._dashboard_service = DashboardService()
        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create dashboard widgets."""
        # Configure grid
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Title
        title = ctk.CTkLabel(
            self,
            text="Dashboard Overview",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=COLORS["primary"],
        )
        title.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))

        # Metrics cards row
        self._create_metrics_row()

        # Content area with stats
        self._create_content_area()

    def _create_metrics_row(self) -> None:
        """Create the row of metric cards."""
        metrics_frame = ctk.CTkFrame(self, fg_color="transparent")
        metrics_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)

        # Configure equal columns
        for i in range(4):
            metrics_frame.grid_columnconfigure(i, weight=1)

        # Create metric cards
        self._card_total = MetricCard(metrics_frame, "--", "Total Mailboxes")
        self._card_total.grid(row=0, column=0, sticky="ew", padx=5)

        self._card_storage = MetricCard(metrics_frame, "--", "Total Storage")
        self._card_storage.grid(row=0, column=1, sticky="ew", padx=5)

        self._card_cost = MetricCard(metrics_frame, "--", "Monthly Cost")
        self._card_cost.grid(row=0, column=2, sticky="ew", padx=5)

        self._card_holds = MetricCard(metrics_frame, "--", "On Hold")
        self._card_holds.grid(row=0, column=3, sticky="ew", padx=5)

    def _create_content_area(self) -> None:
        """Create the main content area with statistics."""
        content = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
        )
        content.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=1)

        # Hold Distribution
        hold_frame = ctk.CTkFrame(content, fg_color=COLORS["surface"])
        hold_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        ctk.CTkLabel(
            hold_frame,
            text="Hold Distribution",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["primary"],
        ).pack(anchor="w", padx=15, pady=(15, 10))

        self._hold_content = ctk.CTkLabel(
            hold_frame,
            text="Loading...",
            text_color=COLORS["text"],
            justify="left",
        )
        self._hold_content.pack(anchor="w", padx=15, pady=(0, 15))

        # Age Distribution
        age_frame = ctk.CTkFrame(content, fg_color=COLORS["surface"])
        age_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        ctk.CTkLabel(
            age_frame,
            text="Age Distribution",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["primary"],
        ).pack(anchor="w", padx=15, pady=(15, 10))

        self._age_content = ctk.CTkLabel(
            age_frame,
            text="Loading...",
            text_color=COLORS["text"],
            justify="left",
        )
        self._age_content.pack(anchor="w", padx=15, pady=(0, 15))

        # Top Mailboxes
        top_frame = ctk.CTkFrame(content, fg_color=COLORS["surface"])
        top_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        ctk.CTkLabel(
            top_frame,
            text="Top Mailboxes by Size",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["primary"],
        ).pack(anchor="w", padx=15, pady=(15, 10))

        self._top_content = ctk.CTkLabel(
            top_frame,
            text="Loading...",
            text_color=COLORS["text"],
            justify="left",
        )
        self._top_content.pack(anchor="w", padx=15, pady=(0, 15))

        # Cost Summary
        cost_frame = ctk.CTkFrame(content, fg_color=COLORS["surface"])
        cost_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

        ctk.CTkLabel(
            cost_frame,
            text="Cost Summary",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["primary"],
        ).pack(anchor="w", padx=15, pady=(15, 10))

        self._cost_content = ctk.CTkLabel(
            cost_frame,
            text="Loading...",
            text_color=COLORS["text"],
            justify="left",
        )
        self._cost_content.pack(anchor="w", padx=15, pady=(0, 15))

    def refresh(self) -> None:
        """Refresh dashboard data."""
        logger.debug("Refreshing dashboard")

        if not self._session:
            self._show_no_data()
            return

        try:
            mailboxes = self._session.db.get_all_mailboxes()
            if not mailboxes:
                self._show_no_data()
                return

            self._update_metrics(mailboxes)
            self._update_hold_distribution(mailboxes)
            self._update_age_distribution(mailboxes)
            self._update_top_mailboxes(mailboxes)
            self._update_cost_summary(mailboxes)

        except Exception as e:
            logger.error(f"Failed to load dashboard: {e}")
            self.show_notification(f"Error loading dashboard: {e}", "error")

    def _show_no_data(self) -> None:
        """Show no data state."""
        self._card_total.set_value("0")
        self._card_storage.set_value("0 GB")
        self._card_cost.set_value("$0")
        self._card_holds.set_value("0")

        no_data = "No data available"
        self._hold_content.configure(text=no_data)
        self._age_content.configure(text=no_data)
        self._top_content.configure(text=no_data)
        self._cost_content.configure(text=no_data)

    def _update_metrics(self, mailboxes: list) -> None:
        """Update metric cards."""
        total = len(mailboxes)
        total_size_mb = sum(m.size_mb for m in mailboxes)
        total_cost = sum(m.monthly_cost for m in mailboxes)
        on_hold = sum(1 for m in mailboxes if m.litigation_hold or m.hold_types)

        self._card_total.set_value(f"{total:,}")
        self._card_storage.set_value(format_size(total_size_mb))
        self._card_cost.set_value(f"${total_cost:,.0f}")
        self._card_holds.set_value(f"{on_hold:,}")

    def _update_hold_distribution(self, mailboxes: list) -> None:
        """Update hold distribution display."""
        litigation = sum(1 for m in mailboxes if m.litigation_hold)
        in_place = sum(1 for m in mailboxes if m.hold_types and not m.litigation_hold)
        no_hold = len(mailboxes) - litigation - in_place

        text = (
            f"Litigation Hold: {litigation}\n"
            f"In-Place Holds: {in_place}\n"
            f"No Hold: {no_hold}"
        )
        self._hold_content.configure(text=text)

    def _update_age_distribution(self, mailboxes: list) -> None:
        """Update age distribution display."""
        age_0_30 = sum(1 for m in mailboxes if m.age_days <= 30)
        age_31_90 = sum(1 for m in mailboxes if 30 < m.age_days <= 90)
        age_91_180 = sum(1 for m in mailboxes if 90 < m.age_days <= 180)
        age_180_plus = sum(1 for m in mailboxes if m.age_days > 180)

        text = (
            f"0-30 days: {age_0_30}\n"
            f"31-90 days: {age_31_90}\n"
            f"91-180 days: {age_91_180}\n"
            f"180+ days: {age_180_plus}"
        )
        self._age_content.configure(text=text)

    def _update_top_mailboxes(self, mailboxes: list) -> None:
        """Update top mailboxes display."""
        sorted_mailboxes = sorted(mailboxes, key=lambda m: m.size_mb, reverse=True)[:5]

        lines = []
        for i, mailbox in enumerate(sorted_mailboxes, 1):
            lines.append(f"{i}. {mailbox.display_name[:25]} - {format_size(mailbox.size_mb)}")

        self._top_content.configure(text="\n".join(lines) or "No data")

    def _update_cost_summary(self, mailboxes: list) -> None:
        """Update cost summary display."""
        total_monthly = sum(m.monthly_cost for m in mailboxes)
        total_annual = total_monthly * 12

        text = (
            f"Monthly Cost: ${total_monthly:,.2f}\n"
            f"Annual Cost: ${total_annual:,.2f}"
        )
        self._cost_content.configure(text=text)
