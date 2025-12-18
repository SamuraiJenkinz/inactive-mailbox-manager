"""Recovery wizard dialog for mailbox recovery operations."""

from typing import TYPE_CHECKING

import customtkinter as ctk

from src.gui.theme import COLORS, get_button_colors
from src.core.dashboard_service import format_size

if TYPE_CHECKING:
    from src.data.session import SessionManager
    from src.data.models import InactiveMailbox


class RecoveryDialog(ctk.CTkToplevel):
    """Multi-step recovery wizard dialog.

    Guides users through the mailbox recovery process
    with validation, options, and progress tracking.
    """

    def __init__(
        self,
        parent,
        mailbox: "InactiveMailbox",
        session: "SessionManager | None" = None,
    ) -> None:
        """Initialize the recovery dialog.

        Args:
            parent: Parent widget
            mailbox: Mailbox to recover
            session: Session manager for operations
        """
        super().__init__(parent)

        self._mailbox = mailbox
        self._session = session
        self._current_step = 0
        self._steps = ["Review", "Options", "Confirm", "Progress", "Complete"]

        # Options
        self._target_var = ctk.StringVar()
        self._include_archive_var = ctk.BooleanVar(value=False)
        self._remove_holds_var = ctk.BooleanVar(value=False)

        # Configure window
        self.title("Recovery Wizard")
        self.geometry("650x550")
        self.minsize(600, 500)
        self.resizable(False, False)

        self.configure(fg_color=COLORS["background"])

        self._create_widgets()

        # Center on parent
        self.transient(parent)
        self.update_idletasks()

    def _create_widgets(self) -> None:
        """Create dialog widgets."""
        # Step indicator
        self._create_step_indicator()

        # Content area
        self._content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._content_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Progress bar (hidden initially)
        self._progress_bar = ctk.CTkProgressBar(
            self,
            fg_color=COLORS["surface"],
            progress_color=COLORS["primary"],
        )
        self._progress_bar.set(0)

        # Navigation buttons
        self._create_navigation()

        # Show first step
        self._show_step(0)

    def _create_step_indicator(self) -> None:
        """Create the step indicator."""
        indicator = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=50)
        indicator.pack(fill="x")
        indicator.pack_propagate(False)

        self._step_labels = []
        for i, step in enumerate(self._steps):
            label = ctk.CTkLabel(
                indicator,
                text=f"{i + 1}. {step}",
                text_color=COLORS["text_muted"],
            )
            label.pack(side="left", padx=20, pady=15)
            self._step_labels.append(label)

    def _create_navigation(self) -> None:
        """Create navigation buttons."""
        nav_frame = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=60)
        nav_frame.pack(fill="x", side="bottom")
        nav_frame.pack_propagate(False)

        inner = ctk.CTkFrame(nav_frame, fg_color="transparent")
        inner.pack(expand=True)

        self._cancel_btn = ctk.CTkButton(
            inner,
            text="Cancel",
            width=100,
            command=self.destroy,
            **get_button_colors(),
        )
        self._cancel_btn.pack(side="left", padx=10, pady=15)

        self._back_btn = ctk.CTkButton(
            inner,
            text="Back",
            width=100,
            command=self._go_back,
            state="disabled",
            **get_button_colors(),
        )
        self._back_btn.pack(side="left", padx=10, pady=15)

        self._next_btn = ctk.CTkButton(
            inner,
            text="Next",
            width=100,
            command=self._go_next,
            **get_button_colors("primary"),
        )
        self._next_btn.pack(side="left", padx=10, pady=15)

    def _update_step_indicator(self) -> None:
        """Update step indicator colors."""
        for i, label in enumerate(self._step_labels):
            if i < self._current_step:
                label.configure(text_color=COLORS["success"])
            elif i == self._current_step:
                label.configure(text_color=COLORS["primary"])
            else:
                label.configure(text_color=COLORS["text_muted"])

    def _show_step(self, step: int) -> None:
        """Show a specific step.

        Args:
            step: Step index to show
        """
        self._current_step = step
        self._update_step_indicator()

        # Clear content
        for widget in self._content_frame.winfo_children():
            widget.destroy()

        # Update buttons
        self._back_btn.configure(state="normal" if step > 0 and step < 4 else "disabled")

        if step == 0:
            self._show_review_step()
            self._next_btn.configure(text="Next", state="normal")
        elif step == 1:
            self._show_options_step()
            self._next_btn.configure(text="Next", state="normal")
        elif step == 2:
            self._show_confirm_step()
            self._next_btn.configure(text="Recover", state="normal")
        elif step == 3:
            self._show_progress_step()
            self._next_btn.configure(text="Please wait...", state="disabled")
            self._cancel_btn.configure(state="disabled")
        elif step == 4:
            self._show_complete_step()
            self._next_btn.configure(text="Close", state="normal")
            self._back_btn.configure(state="disabled")

    def _show_review_step(self) -> None:
        """Show the review step."""
        ctk.CTkLabel(
            self._content_frame,
            text="Review Mailbox",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["primary"],
        ).pack(anchor="w", pady=(0, 15))

        info_frame = ctk.CTkFrame(self._content_frame, fg_color=COLORS["surface"])
        info_frame.pack(fill="x", pady=10)

        info = [
            ("Display Name", self._mailbox.display_name),
            ("Email", self._mailbox.primary_smtp),
            ("Size", format_size(self._mailbox.size_mb)),
            ("Items", f"{self._mailbox.item_count:,}"),
            ("Age", f"{self._mailbox.age_days} days"),
        ]

        for label, value in info:
            row = ctk.CTkFrame(info_frame, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=5)

            ctk.CTkLabel(row, text=f"{label}:", width=100, anchor="w", text_color=COLORS["text_muted"]).pack(side="left")
            ctk.CTkLabel(row, text=value, anchor="w", text_color=COLORS["text"]).pack(side="left")

        ctk.CTkFrame(info_frame, height=10, fg_color="transparent").pack()

        # Warnings
        if self._mailbox.litigation_hold or self._mailbox.hold_types:
            warn_frame = ctk.CTkFrame(self._content_frame, fg_color=COLORS["surface"])
            warn_frame.pack(fill="x", pady=10)

            ctk.CTkLabel(
                warn_frame,
                text="Warning: This mailbox has holds",
                text_color=COLORS["warning"],
                font=ctk.CTkFont(weight="bold"),
            ).pack(anchor="w", padx=15, pady=10)

        # Eligibility
        if self._mailbox.recovery_eligible:
            ctk.CTkLabel(
                self._content_frame,
                text="This mailbox is eligible for recovery",
                text_color=COLORS["success"],
            ).pack(anchor="w", pady=10)
        else:
            ctk.CTkLabel(
                self._content_frame,
                text="Warning: This mailbox may not be eligible",
                text_color=COLORS["error"],
            ).pack(anchor="w", pady=10)

    def _show_options_step(self) -> None:
        """Show the options step."""
        ctk.CTkLabel(
            self._content_frame,
            text="Recovery Options",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["primary"],
        ).pack(anchor="w", pady=(0, 15))

        # Target mailbox
        ctk.CTkLabel(
            self._content_frame,
            text="Target Mailbox (leave empty to restore to original):",
            text_color=COLORS["text"],
        ).pack(anchor="w", pady=(10, 5))

        self._target_entry = ctk.CTkEntry(
            self._content_frame,
            textvariable=self._target_var,
            placeholder_text="user@contoso.com",
            width=400,
            fg_color=COLORS["surface"],
        )
        self._target_entry.pack(anchor="w", pady=(0, 20))

        # Options
        options_frame = ctk.CTkFrame(self._content_frame, fg_color=COLORS["surface"])
        options_frame.pack(fill="x", pady=10)

        archive_check = ctk.CTkCheckBox(
            options_frame,
            text="Include archive mailbox (if exists)",
            variable=self._include_archive_var,
            fg_color=COLORS["primary"],
        )
        archive_check.pack(anchor="w", padx=15, pady=10)

        holds_check = ctk.CTkCheckBox(
            options_frame,
            text="Remove holds after recovery",
            variable=self._remove_holds_var,
            fg_color=COLORS["primary"],
        )
        holds_check.pack(anchor="w", padx=15, pady=(0, 15))

        # Note
        ctk.CTkLabel(
            self._content_frame,
            text="Note: Recovery may take several minutes depending on mailbox size.",
            text_color=COLORS["text_muted"],
        ).pack(anchor="w", pady=20)

    def _show_confirm_step(self) -> None:
        """Show the confirmation step."""
        ctk.CTkLabel(
            self._content_frame,
            text="Confirm Recovery",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["primary"],
        ).pack(anchor="w", pady=(0, 15))

        # Summary
        summary_frame = ctk.CTkFrame(self._content_frame, fg_color=COLORS["surface"])
        summary_frame.pack(fill="x", pady=10)

        target = self._target_var.get() or "Original location"

        summary = [
            ("Mailbox", self._mailbox.display_name),
            ("Email", self._mailbox.primary_smtp),
            ("Target", target),
            ("Include Archive", "Yes" if self._include_archive_var.get() else "No"),
            ("Remove Holds", "Yes" if self._remove_holds_var.get() else "No"),
        ]

        for label, value in summary:
            row = ctk.CTkFrame(summary_frame, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=5)

            ctk.CTkLabel(row, text=f"{label}:", width=120, anchor="w", text_color=COLORS["text_muted"]).pack(side="left")
            ctk.CTkLabel(row, text=value, anchor="w", text_color=COLORS["text"]).pack(side="left")

        ctk.CTkFrame(summary_frame, height=10, fg_color="transparent").pack()

        # Warning
        ctk.CTkLabel(
            self._content_frame,
            text="This operation cannot be undone.",
            text_color=COLORS["warning"],
            font=ctk.CTkFont(weight="bold"),
        ).pack(anchor="w", pady=20)

    def _show_progress_step(self) -> None:
        """Show the progress step."""
        ctk.CTkLabel(
            self._content_frame,
            text="Recovery in Progress",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["primary"],
        ).pack(anchor="w", pady=(0, 15))

        ctk.CTkLabel(
            self._content_frame,
            text=f"Recovering: {self._mailbox.display_name}",
            text_color=COLORS["text"],
        ).pack(anchor="w", pady=5)

        self._progress_label = ctk.CTkLabel(
            self._content_frame,
            text="Please wait...",
            text_color=COLORS["text_muted"],
        )
        self._progress_label.pack(anchor="w", pady=20)

        # Progress bar
        self._progress_bar.pack(fill="x", padx=20, pady=10)

        # Start simulation
        self._simulate_recovery()

    def _show_complete_step(self) -> None:
        """Show the completion step."""
        self._progress_bar.pack_forget()

        ctk.CTkLabel(
            self._content_frame,
            text="Recovery Complete",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["success"],
        ).pack(anchor="w", pady=(0, 15))

        ctk.CTkLabel(
            self._content_frame,
            text=f"Successfully recovered: {self._mailbox.display_name}",
            text_color=COLORS["text"],
        ).pack(anchor="w", pady=5)

        ctk.CTkLabel(
            self._content_frame,
            text="The mailbox has been recovered successfully.",
            text_color=COLORS["text_muted"],
        ).pack(anchor="w", pady=20)

    def _simulate_recovery(self) -> None:
        """Simulate recovery progress."""
        progress = [0]

        def update():
            progress[0] += 5
            self._progress_bar.set(progress[0] / 100)
            self._progress_label.configure(text=f"Progress: {progress[0]}%")

            if progress[0] < 100:
                self.after(100, update)
            else:
                self._show_step(4)

        self.after(200, update)

    def _go_back(self) -> None:
        """Go to previous step."""
        if self._current_step > 0:
            self._show_step(self._current_step - 1)

    def _go_next(self) -> None:
        """Go to next step."""
        if self._current_step < len(self._steps) - 1:
            self._show_step(self._current_step + 1)
        else:
            self.destroy()
