#!/usr/bin/env python3
"""Inactive Mailbox Manager - Entry point for CLI execution."""

import argparse
import sys
from pathlib import Path


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="imm",
        description="Enterprise-grade M365 inactive mailbox management tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  imm                          Launch in terminal mode (default)
  imm --mode gui               Launch desktop GUI
  imm --test-connection        Test Exchange Online connection
  imm --refresh-cache          Force refresh of mailbox cache
  imm --config custom.yaml     Use custom configuration file
        """,
    )

    parser.add_argument(
        "--mode",
        choices=["terminal", "gui"],
        default="terminal",
        help="UI mode: terminal (Textual TUI) or gui (Desktop GUI). Default: terminal",
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/settings.yaml"),
        help="Path to configuration file. Default: config/settings.yaml",
    )

    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="Test Exchange Online connection and exit",
    )

    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Force refresh of mailbox cache on startup",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Increase output verbosity. Use -v, -vv, or -vvv",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point for the application."""
    args = parse_arguments()

    # Determine log level from verbosity
    log_levels = ["WARNING", "INFO", "DEBUG", "DEBUG"]
    log_level = log_levels[min(args.verbose, 3)]

    try:
        from src.utils.logging import setup_logging, get_logger
        from src.utils.config import load_config

        # Initialize logging
        setup_logging(level=log_level)
        logger = get_logger(__name__)
        logger.info("Inactive Mailbox Manager starting...")

        # Load configuration
        config = load_config(args.config)
        logger.debug(f"Configuration loaded from {args.config}")

        # Handle test connection mode
        if args.test_connection:
            logger.info("Testing Exchange Online connection...")
            # TODO: Implement connection test in Phase 01-02
            print("Connection test not yet implemented")
            return 0

        # Handle refresh cache flag
        if args.refresh_cache:
            logger.info("Cache refresh requested")
            config.cache.refresh_on_startup = True

        # Launch appropriate UI
        if args.mode == "terminal":
            logger.info("Launching terminal UI...")
            # TODO: Implement Textual TUI in Phase 5
            print("Terminal UI not yet implemented")
        else:
            logger.info("Launching desktop GUI...")
            # TODO: Implement Desktop GUI in Phase 6
            print("Desktop GUI not yet implemented")

        return 0

    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
