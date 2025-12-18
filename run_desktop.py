#!/usr/bin/env python3
"""
Entry point for Desktop GUI.

Launches the CustomTkinter-based desktop interface for Inactive Mailbox Manager.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))


def check_dependencies() -> bool:
    """Check if required dependencies are installed."""
    missing = []

    try:
        import customtkinter
    except ImportError:
        missing.append("customtkinter")

    try:
        import yaml
    except ImportError:
        missing.append("PyYAML")

    try:
        import tkinter
    except ImportError:
        missing.append("tkinter (usually included with Python)")

    if missing:
        print("Missing required dependencies:")
        for dep in missing:
            print(f"  - {dep}")
        print("\nInstall with: pip install -r requirements.txt")
        return False

    return True


def run_onboarding_if_needed() -> bool:
    """Check config and offer onboarding if needed."""
    from src.core.onboarding import OnboardingWizard

    wizard = OnboardingWizard()
    if wizard.needs_onboarding():
        # The GUI will handle onboarding
        return True

    return True


def main() -> int:
    """Main entry point."""
    print("Inactive Mailbox Manager - Desktop GUI")
    print("-" * 40)

    if not check_dependencies():
        return 1

    run_onboarding_if_needed()

    try:
        from src.gui.app import DesktopApp

        # Create and run the application
        app = DesktopApp()
        app.mainloop()
        return 0

    except KeyboardInterrupt:
        print("\nExiting...")
        return 0

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        print("\nCheck logs/app.log for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
