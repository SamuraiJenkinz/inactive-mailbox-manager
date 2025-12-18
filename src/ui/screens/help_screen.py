"""Help screen showing keyboard shortcuts and feature overview."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.screen import Screen
from textual.widgets import Static

from src.utils.logging import get_logger

logger = get_logger(__name__)


class HelpScreen(Screen):
    """Help screen with keyboard shortcuts and feature documentation.

    Displays comprehensive help information including keyboard
    shortcuts, feature overview, and contact information.
    """

    BINDINGS = [
        Binding("escape", "back", "Back", show=True),
        Binding("q", "back", "Close", show=True),
    ]

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        with VerticalScroll():
            yield Static("[bold]Inactive Mailbox Manager - Help[/bold]", classes="title")
            yield Static("Microsoft 365 Management Tool", classes="subtitle")

            # Keyboard Shortcuts Section
            with Container(classes="panel"):
                yield Static("[bold]Global Keyboard Shortcuts[/bold]", classes="section-title")
                yield Static(self._format_shortcuts([
                    ("q", "Quit application"),
                    ("?", "Show this help screen"),
                    ("r", "Refresh current view"),
                    ("c", "Open connection screen"),
                    ("d", "Open dashboard"),
                    ("/", "Focus search input"),
                    ("Escape", "Go back / Clear search"),
                ]))

            # Main Screen Shortcuts
            with Container(classes="panel"):
                yield Static("[bold]Main Screen Shortcuts[/bold]", classes="section-title")
                yield Static(self._format_shortcuts([
                    ("Enter", "View mailbox details"),
                    ("r", "Start recovery wizard"),
                    ("s", "Start restore wizard"),
                    ("e", "Export data"),
                    ("f", "Open filter options"),
                    ("Up/Down", "Navigate mailbox list"),
                ]))

            # Wizard Navigation
            with Container(classes="panel"):
                yield Static("[bold]Wizard Navigation[/bold]", classes="section-title")
                yield Static(self._format_shortcuts([
                    ("Enter", "Next step"),
                    ("Tab", "Move between fields"),
                    ("Escape", "Cancel wizard"),
                ]))

            # Features Overview
            with Container(classes="panel"):
                yield Static("[bold]Features Overview[/bold]", classes="section-title")
                yield Static("""
[primary]Mailbox Management[/primary]
  - View all inactive mailboxes from your organization
  - Filter and search by name, email, or identity
  - View detailed mailbox information and hold status

[primary]Recovery Operations[/primary]
  - Recover mailbox to a new user account
  - Restore content to an existing mailbox
  - Bulk operations via CSV import

[primary]Analysis & Reporting[/primary]
  - Cost analysis with license tracking
  - Hold analysis with recommendations
  - Export reports in multiple formats

[primary]Dashboard[/primary]
  - Overview metrics and statistics
  - Age distribution analysis
  - Top mailboxes by size and cost
""")

            # About Section
            with Container(classes="panel"):
                yield Static("[bold]About[/bold]", classes="section-title")
                yield Static("""
Inactive Mailbox Manager v1.0.0

A tool for managing Microsoft 365 inactive mailboxes at scale,
designed for organizations with large mailbox counts that exceed
the Microsoft Purview portal limits.

[info]Developed for enterprise M365 administration[/info]
""")

            # Support Section
            with Container(classes="panel"):
                yield Static("[bold]Support & Resources[/bold]", classes="section-title")
                yield Static("""
Documentation:
  - README.md in project root
  - .planning/ directory for technical docs

Microsoft Resources:
  - docs.microsoft.com/exchange
  - Microsoft 365 Admin Center
  - Microsoft Purview Compliance Portal

Press [primary]Escape[/primary] or [primary]q[/primary] to close this help screen.
""")

    def _format_shortcuts(self, shortcuts: list[tuple[str, str]]) -> str:
        """Format keyboard shortcuts for display.

        Args:
            shortcuts: List of (key, description) tuples

        Returns:
            Formatted string for display
        """
        lines = []
        for key, description in shortcuts:
            # Pad key to align descriptions
            padded_key = f"[primary]{key}[/primary]".ljust(20)
            lines.append(f"  {padded_key} {description}")
        return "\n".join(lines)

    def action_back(self) -> None:
        """Go back to the previous screen."""
        self.app.pop_screen()
