"""Screen modules for Terminal UI."""

from src.ui.screens.bulk_screen import BulkOperationsScreen
from src.ui.screens.connection_screen import ConnectionScreen
from src.ui.screens.dashboard_screen import DashboardScreen
from src.ui.screens.detail_screen import MailboxDetailScreen
from src.ui.screens.help_screen import HelpScreen
from src.ui.screens.holds_screen import HoldsScreen
from src.ui.screens.main_screen import MainScreen
from src.ui.screens.recovery_wizard_screen import RecoveryWizardScreen

__all__ = [
    "BulkOperationsScreen",
    "ConnectionScreen",
    "DashboardScreen",
    "HelpScreen",
    "HoldsScreen",
    "MailboxDetailScreen",
    "MainScreen",
    "RecoveryWizardScreen",
]
