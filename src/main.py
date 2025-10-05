from __future__ import annotations

"""Compatibility wrapper for legacy ``python src/main.py`` entry point."""

from workflow.cli import main as _main


def main() -> int:
    """Invoke the new workflow CLI."""

    return _main()


if __name__ == "__main__":
    raise SystemExit(main())
