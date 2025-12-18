#!/usr/bin/env python3
"""
Entry point for Terminal UI.

Launches the Textual-based terminal interface for Inactive Mailbox Manager.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))


def check_dependencies() -> bool:
    """Check if required dependencies are installed."""
    missing = []

    try:
        import textual
    except ImportError:
        missing.append("textual")

    try:
        import rich
    except ImportError:
        missing.append("rich")

    try:
        import yaml
    except ImportError:
        missing.append("PyYAML")

    if missing:
        print("Missing required dependencies:")
        for dep in missing:
            print(f"  - {dep}")
        print("\nInstall with: pip install -r requirements.txt")
        return False

    return True


def check_config() -> bool:
    """Check if configuration exists or run onboarding."""
    from src.core.onboarding import OnboardingWizard

    wizard = OnboardingWizard()
    if wizard.needs_onboarding():
        print("=" * 60)
        print("  INACTIVE MAILBOX MANAGER - First Run Setup")
        print("=" * 60)
        print()
        print("Configuration not found. Please run the setup wizard.")
        print()
        print("Options:")
        print("  1. Copy config.example.yaml to config.yaml and edit manually")
        print("  2. Run the Desktop GUI for guided setup")
        print()
        return False

    return True


def main() -> int:
    """Main entry point."""
    print("Inactive Mailbox Manager - Terminal UI")
    print("-" * 40)

    if not check_dependencies():
        return 1

    if not check_config():
        return 1

    try:
        from src.ui.app import InactiveMailboxApp

        app = InactiveMailboxApp()
        app.run()
        return 0

    except KeyboardInterrupt:
        print("\nExiting...")
        return 0

    except Exception as e:
        print(f"\nError: {e}")
        print("\nCheck logs/app.log for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
