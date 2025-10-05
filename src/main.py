"""Backward compatible entry point forwarding to the new CLI."""

from workflow.cli import main


if __name__ == "__main__":
    main()
