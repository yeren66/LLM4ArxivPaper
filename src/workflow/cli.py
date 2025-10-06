"""Command-line entry for the pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import PipelineOverrides, run_pipeline


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="LLM4ArxivPaper pipeline")
	parser.add_argument("run", nargs="?", help="Execute the pipeline", default="run")
	parser.add_argument("--config", default="config/pipeline.yaml", help="Path to pipeline YAML config")
	parser.add_argument("--mode", choices=["online", "offline"], help="Override runtime mode")
	parser.add_argument("--paper-limit", type=int, help="Limit number of papers per topic")
	parser.add_argument("--email", dest="email", action="store_true", help="Force enable email sending")
	parser.add_argument("--no-email", dest="email", action="store_false", help="Force disable email sending")
	parser.set_defaults(email=None)
	return parser


def main(argv: list[str] | None = None) -> None:
	parser = build_parser()
	args = parser.parse_args(argv)

	overrides = PipelineOverrides(
		mode=args.mode,
		paper_limit=args.paper_limit,
		email_enabled=args.email,
	)

	result = run_pipeline(args.config, overrides=overrides)

	print("[INFO] Pipeline completed")
	print(f"[INFO] Topics processed: {result.stats.topics_processed}")
	print(f"[INFO] Papers fetched: {result.stats.papers_fetched}")
	print(f"[INFO] Papers selected: {result.stats.papers_selected}")
	print(f"[INFO] Output directory: {Path('site').resolve()}")


if __name__ == "__main__":
	main()
