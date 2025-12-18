"""Recovery wizard screen for mailbox recovery operations."""

from enum import Enum, auto
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Input, Label, ProgressBar, Static

from src.core.dashboard_service import format_size
from src.data.models import InactiveMailbox
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.data.session import SessionManager

logger = get_logger(__name__)


class WizardStep(Enum):
    """Recovery wizard steps."""

    REVIEW = auto()
    OPTIONS = auto()
    CONFIRM = auto()
    PROGRESS = auto()
    COMPLETE = auto()


class RecoveryWizardScreen(Screen):
    """Multi-step wizard for mailbox recovery.

    Guides users through the recovery process with
    validation, options, and progress tracking.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("enter", "next_step", "Next", show=False),
    ]

    def __init__(
        self,
        mailbox: InactiveMailbox,
        session: "SessionManager | None" = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the recovery wizard.

        Args:
            mailbox: Mailbox to recover
            session: Session manager for operations
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._mailbox = mailbox
        self._session = session
        self._current_step = WizardStep.REVIEW
        self._recovery_in_progress = False

        # Recovery options
        self._target_mailbox: str = ""
        self._include_archive: bool = False
        self._remove_holds: bool = False

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        with Vertical():
            # Header
            yield Static("[bold]Recovery Wizard[/bold]", classes="title")

            # Step indicator
            with Horizontal(id="step-indicator"):
                yield Static("1. Review", id="step-1", classes="wizard-step wizard-step-active")
                yield Static("2. Options", id="step-2", classes="wizard-step wizard-step-pending")
                yield Static("3. Confirm", id="step-3", classes="wizard-step wizard-step-pending")
                yield Static("4. Complete", id="step-4", classes="wizard-step wizard-step-pending")

            # Step content container
            with Container(id="step-content", classes="panel"):
                yield from self._compose_review_step()

            # Progress bar (hidden initially)
            yield ProgressBar(id="progress-bar", total=100, show_eta=True)

            # Navigation buttons
            with Horizontal(classes="button-row"):
                yield Button("Cancel", id="btn-cancel")
                yield Button("Back", id="btn-back", disabled=True)
                yield Button("Next", id="btn-next", variant="primary")

    def _compose_review_step(self) -> ComposeResult:
        """Compose the review step content."""
        yield Static("[bold]Review Mailbox[/bold]", classes="section-title")
        yield Static(f"Display Name: {self._mailbox.display_name}")
        yield Static(f"Email: {self._mailbox.primary_smtp}")
        yield Static(f"Size: {format_size(self._mailbox.size_mb)}")
        yield Static(f"Items: {self._mailbox.item_count:,}")
        yield Static(f"Age: {self._mailbox.age_days} days")

        # Hold status
        if self._mailbox.litigation_hold or self._mailbox.hold_types:
            yield Static("")
            yield Static("[warning]Warning: This mailbox has holds[/warning]")
            if self._mailbox.litigation_hold:
                yield Static("  - Litigation Hold enabled", classes="hold-litigation")
            if self._mailbox.hold_types:
                yield Static(f"  - {len(self._mailbox.hold_types)} in-place holds", classes="hold-ediscovery")

        # Recovery eligibility
        yield Static("")
        if self._mailbox.recovery_eligible:
            yield Static("[success]This mailbox is eligible for recovery[/success]")
        else:
            yield Static("[error]This mailbox may not be eligible for recovery[/error]")
            if self._mailbox.recovery_blockers:
                for blocker in self._mailbox.recovery_blockers:
                    yield Static(f"  - {blocker}", classes="error")

    def _compose_options_step(self) -> ComposeResult:
        """Compose the options step content."""
        yield Static("[bold]Recovery Options[/bold]", classes="section-title")

        yield Label("Target Mailbox (leave empty to restore to original):")
        yield Input(
            placeholder="user@contoso.com",
            id="input-target",
            value=self._target_mailbox,
        )

        yield Static("")
        yield Checkbox("Include archive mailbox (if exists)", id="chk-archive", value=self._include_archive)
        yield Checkbox("Remove holds after recovery", id="chk-holds", value=self._remove_holds)

        yield Static("")
        yield Static("[info]Note: Recovery may take several minutes depending on mailbox size.[/info]")

    def _compose_confirm_step(self) -> ComposeResult:
        """Compose the confirmation step content."""
        yield Static("[bold]Confirm Recovery[/bold]", classes="section-title")

        yield Static("You are about to recover:")
        yield Static(f"  Mailbox: {self._mailbox.display_name}")
        yield Static(f"  Email: {self._mailbox.primary_smtp}")
        yield Static(f"  Size: {format_size(self._mailbox.size_mb)}")

        yield Static("")
        target = self._target_mailbox or "Original location"
        yield Static(f"  Target: {target}")
        yield Static(f"  Include archive: {'Yes' if self._include_archive else 'No'}")
        yield Static(f"  Remove holds: {'Yes' if self._remove_holds else 'No'}")

        yield Static("")
        yield Static("[warning]This operation cannot be undone.[/warning]")
        yield Static("Press 'Recover' to proceed or 'Back' to modify options.")

    def _compose_complete_step(self, success: bool, message: str) -> ComposeResult:
        """Compose the completion step content.

        Args:
            success: Whether recovery was successful
            message: Status message
        """
        if success:
            yield Static("[bold][success]Recovery Complete[/success][/bold]", classes="section-title")
            yield Static(f"Successfully recovered: {self._mailbox.display_name}")
        else:
            yield Static("[bold][error]Recovery Failed[/error][/bold]", classes="section-title")
            yield Static(f"Failed to recover: {self._mailbox.display_name}")

        yield Static("")
        yield Static(f"Status: {message}")

        yield Static("")
        yield Static("Press 'Close' to return to the main screen.")

    def on_mount(self) -> None:
        """Handle screen mount."""
        logger.debug(f"RecoveryWizardScreen mounted for {self._mailbox.display_name}")
        self._update_progress_bar(False)

    def _update_step_indicators(self) -> None:
        """Update the step indicator widgets."""
        steps = [
            (WizardStep.REVIEW, "#step-1"),
            (WizardStep.OPTIONS, "#step-2"),
            (WizardStep.CONFIRM, "#step-3"),
            (WizardStep.COMPLETE, "#step-4"),
        ]

        for step, selector in steps:
            widget = self.query_one(selector, Static)
            widget.remove_class("wizard-step-active", "wizard-step-complete", "wizard-step-pending")

            if step == self._current_step:
                widget.add_class("wizard-step-active")
            elif step.value < self._current_step.value:
                widget.add_class("wizard-step-complete")
            else:
                widget.add_class("wizard-step-pending")

    def _update_buttons(self) -> None:
        """Update navigation button states."""
        btn_back = self.query_one("#btn-back", Button)
        btn_next = self.query_one("#btn-next", Button)

        if self._current_step == WizardStep.REVIEW:
            btn_back.disabled = True
            btn_next.label = "Next"
            btn_next.disabled = False
        elif self._current_step == WizardStep.OPTIONS:
            btn_back.disabled = False
            btn_next.label = "Next"
            btn_next.disabled = False
        elif self._current_step == WizardStep.CONFIRM:
            btn_back.disabled = False
            btn_next.label = "Recover"
            btn_next.disabled = False
        elif self._current_step == WizardStep.PROGRESS:
            btn_back.disabled = True
            btn_next.label = "Please wait..."
            btn_next.disabled = True
        elif self._current_step == WizardStep.COMPLETE:
            btn_back.disabled = True
            btn_next.label = "Close"
            btn_next.disabled = False

    def _update_progress_bar(self, show: bool, progress: int = 0) -> None:
        """Update progress bar visibility and value.

        Args:
            show: Whether to show the progress bar
            progress: Current progress value (0-100)
        """
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        if show:
            progress_bar.remove_class("hidden")
            progress_bar.update(progress=progress)
        else:
            progress_bar.add_class("hidden")

    def _refresh_step_content(self) -> None:
        """Refresh the step content container."""
        content = self.query_one("#step-content", Container)
        content.remove_children()

        if self._current_step == WizardStep.REVIEW:
            content.mount_all(self._compose_review_step())
        elif self._current_step == WizardStep.OPTIONS:
            content.mount_all(self._compose_options_step())
        elif self._current_step == WizardStep.CONFIRM:
            content.mount_all(self._compose_confirm_step())

        self._update_step_indicators()
        self._update_buttons()

    def action_cancel(self) -> None:
        """Cancel the wizard and return to main screen."""
        if self._recovery_in_progress:
            self.app.notify("Cannot cancel during recovery", severity="warning")
            return

        self.app.pop_screen()

    def action_next_step(self) -> None:
        """Proceed to the next step."""
        self._handle_next()

    def _handle_next(self) -> None:
        """Handle the next button click."""
        if self._current_step == WizardStep.REVIEW:
            self._current_step = WizardStep.OPTIONS
            self._refresh_step_content()

        elif self._current_step == WizardStep.OPTIONS:
            # Save options
            self._target_mailbox = self.query_one("#input-target", Input).value.strip()
            self._include_archive = self.query_one("#chk-archive", Checkbox).value
            self._remove_holds = self.query_one("#chk-holds", Checkbox).value

            self._current_step = WizardStep.CONFIRM
            self._refresh_step_content()

        elif self._current_step == WizardStep.CONFIRM:
            self._start_recovery()

        elif self._current_step == WizardStep.COMPLETE:
            self.app.pop_screen()

    def _handle_back(self) -> None:
        """Handle the back button click."""
        if self._current_step == WizardStep.OPTIONS:
            self._current_step = WizardStep.REVIEW
            self._refresh_step_content()
        elif self._current_step == WizardStep.CONFIRM:
            self._current_step = WizardStep.OPTIONS
            self._refresh_step_content()

    def _start_recovery(self) -> None:
        """Start the recovery operation."""
        self._recovery_in_progress = True
        self._current_step = WizardStep.PROGRESS
        self._update_buttons()
        self._update_progress_bar(True, 0)

        content = self.query_one("#step-content", Container)
        content.remove_children()
        content.mount(Static("[bold]Recovery in Progress[/bold]", classes="section-title"))
        content.mount(Static(f"Recovering: {self._mailbox.display_name}"))
        content.mount(Static("Please wait..."))

        # Simulate recovery progress (in real implementation, this would be async)
        self._simulate_recovery()

    def _simulate_recovery(self) -> None:
        """Simulate recovery for demo purposes.

        In a real implementation, this would call the actual recovery
        service and update progress based on real status.
        """
        import asyncio

        async def run_recovery():
            for i in range(0, 101, 10):
                self._update_progress_bar(True, i)
                await asyncio.sleep(0.2)

            self._complete_recovery(True, "Recovery completed successfully")

        # Schedule the async operation
        self.app.call_later(0.1, lambda: asyncio.create_task(run_recovery()))

    def _complete_recovery(self, success: bool, message: str) -> None:
        """Complete the recovery and show results.

        Args:
            success: Whether recovery succeeded
            message: Status message
        """
        self._recovery_in_progress = False
        self._current_step = WizardStep.COMPLETE
        self._update_progress_bar(False)

        content = self.query_one("#step-content", Container)
        content.remove_children()
        content.mount_all(self._compose_complete_step(success, message))

        self._update_step_indicators()
        self._update_buttons()

        if success:
            self.app.notify("Recovery completed successfully", severity="information")
        else:
            self.app.notify(f"Recovery failed: {message}", severity="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: Button press event
        """
        if event.button.id == "btn-cancel":
            self.action_cancel()
        elif event.button.id == "btn-back":
            self._handle_back()
        elif event.button.id == "btn-next":
            self._handle_next()
