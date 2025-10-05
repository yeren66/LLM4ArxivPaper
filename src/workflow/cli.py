"""Command-line entry point for the LLM4Reading pipeline."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

from core.config_loader import load_pipeline_config
from workflow.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llm4reading",
        description="Run the LLM4Reading arXiv processing pipeline",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/pipeline.yaml"),
        help="Path to the pipeline configuration file",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=None,
        help="Override fetch.days_back in configuration (optional)",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = load_pipeline_config(args.config)
    if args.days_back is not None:
        config.fetch.days_back = args.days_back

    logging.basicConfig(level=getattr(logging, config.runtime.console_level.upper(), logging.INFO))
    run_pipeline(config)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
