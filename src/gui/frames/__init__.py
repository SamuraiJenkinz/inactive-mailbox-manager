"""GUI frames package."""

from src.gui.frames.base_frame import BaseFrame
from src.gui.frames.mailbox_frame import MailboxFrame
from src.gui.frames.dashboard_frame import DashboardFrame
from src.gui.frames.bulk_frame import BulkFrame
from src.gui.frames.settings_frame import SettingsFrame
from src.gui.frames.help_frame import HelpFrame

__all__ = [
    "BaseFrame",
    "MailboxFrame",
    "DashboardFrame",
    "BulkFrame",
    "SettingsFrame",
    "HelpFrame",
]
