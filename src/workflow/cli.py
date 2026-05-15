"""Command-line entry for the pipeline.

Two subcommands:

* ``run`` (default — used by the weekly cron and ``python src/main.py`` with
  no args for backwards compatibility) — execute the full topic-driven
  pipeline, optionally over a historical date range (backfill mode).
* ``analyse-one`` — analyse a single arXiv paper by id and write the result
  to ``data/analyses/<id>.json``. Used by the on-demand URL-ingest workflow
  that the Vercel front end triggers.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .pipeline import (
	AnalyseOneResult,
	PipelineOverrides,
	run_analyse_one,
	run_pipeline,
)


_KNOWN_COMMANDS = {"run", "analyse-one"}


def _parse_date(value: str) -> datetime:
	"""Parse YYYY-MM-DD or YYYY-MM-DDTHH:MM into a datetime (UTC, naive)."""
	for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
		try:
			return datetime.strptime(value, fmt)
		except ValueError:
			continue
	raise argparse.ArgumentTypeError(
		f"Invalid date '{value}'. Expected YYYY-MM-DD or YYYY-MM-DDTHH:MM."
	)


def _add_run_flags(p: argparse.ArgumentParser) -> None:
	p.add_argument("--mode", choices=["online", "offline"], help="Override runtime mode")
	p.add_argument("--paper-limit", type=int, help="Limit number of papers per topic")
	p.add_argument("--email", dest="email", action="store_true", help="Force enable email sending")
	p.add_argument("--no-email", dest="email", action="store_false", help="Force disable email sending")
	p.set_defaults(email=None)
	# Backfill mode: when both dates are present, the pipeline walks the
	# window in `chunk-days` slices and merges into the existing site/.
	p.add_argument(
		"--start-date",
		type=_parse_date,
		help="Backfill start (YYYY-MM-DD). Requires --end-date.",
	)
	p.add_argument(
		"--end-date",
		type=_parse_date,
		help="Backfill end (YYYY-MM-DD, exclusive). Requires --start-date.",
	)
	p.add_argument(
		"--chunk-days",
		type=int,
		default=7,
		help="Backfill window size in days (default 7).",
	)
	p.add_argument(
		"--dry-run",
		action="store_true",
		help="Only fetch and count candidates; skip LLM calls. Use to estimate cost.",
	)


def _add_analyse_one_flags(p: argparse.ArgumentParser) -> None:
	p.add_argument("--arxiv-id", required=True, help="arXiv ID, e.g. 2401.12345")
	p.add_argument(
		"--topic",
		help=(
			"Topic name (from pipeline.yaml) to associate with this paper. "
			"Determines which interest_prompt is used. Defaults to the first "
			"topic in the config."
		),
	)
	p.add_argument(
		"--write-db",
		action="store_true",
		help="Persist the result to data/analyses/<id>.json (and update data/index.json).",
	)
	p.add_argument(
		"--output-file",
		help="Also write the analysis JSON to this path (in addition to stdout).",
	)


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="LLM4ArxivPaper")
	parser.add_argument(
		"--config", default="config/pipeline.yaml", help="Path to pipeline YAML config"
	)
	sub = parser.add_subparsers(dest="command")

	p_run = sub.add_parser("run", help="Run the full topic-driven pipeline (default)")
	_add_run_flags(p_run)

	p_one = sub.add_parser("analyse-one", help="Analyse a single arXiv paper by ID")
	_add_analyse_one_flags(p_one)

	return parser


def _normalise_argv(argv: Optional[List[str]]) -> List[str]:
	"""Make legacy invocations work alongside subparsers.

	``python src/main.py`` → ``["run"]``
	``python src/main.py --paper-limit 1`` → ``["run", "--paper-limit", "1"]``
	``python src/main.py --config x run --paper-limit 1`` → unchanged
	``python src/main.py run --paper-limit 1`` → unchanged
	``python src/main.py analyse-one --arxiv-id X`` → unchanged

	The only top-level option is ``--config``; we walk past it (and its value),
	then insert ``run`` before the first token we don't recognise as either a
	known subcommand or a top-level option.
	"""
	argv_list = list(argv) if argv is not None else sys.argv[1:]
	scan = 0
	while scan < len(argv_list):
		token = argv_list[scan]
		if token in _KNOWN_COMMANDS:
			return argv_list  # explicit subcommand present
		if token == "--config":
			# `--config <value>` — skip the option AND its value if present.
			scan += 2 if scan + 1 < len(argv_list) else 1
			continue
		if token.startswith("--config="):
			scan += 1
			continue
		# First sub-command-specific token (or just no args at all) → inject "run" here.
		break
	return [*argv_list[:scan], "run", *argv_list[scan:]]


def main(argv: list[str] | None = None) -> None:
	argv_list = _normalise_argv(argv)
	parser = build_parser()
	args = parser.parse_args(argv_list)

	if args.command == "run":
		_dispatch_run(args, parser)
	elif args.command == "analyse-one":
		_dispatch_analyse_one(args)
	else:  # pragma: no cover - argparse should make this unreachable
		parser.print_help()
		sys.exit(2)


def _dispatch_run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
	if bool(args.start_date) != bool(args.end_date):
		parser.error("--start-date and --end-date must be provided together")
	if args.start_date and args.end_date and args.start_date >= args.end_date:
		parser.error("--start-date must be earlier than --end-date")

	overrides = PipelineOverrides(
		mode=args.mode,
		paper_limit=args.paper_limit,
		email_enabled=args.email,
		start_date=args.start_date,
		end_date=args.end_date,
		chunk_days=args.chunk_days,
		dry_run=args.dry_run,
	)

	result = run_pipeline(args.config, overrides=overrides)

	print("[INFO] Pipeline completed")
	print(f"[INFO] Topics processed: {result.stats.topics_processed}")
	print(f"[INFO] Papers fetched: {result.stats.papers_fetched}")
	print(f"[INFO] Papers selected: {result.stats.papers_selected}")
	print(f"[INFO] Output directory: {Path('site').resolve()}")


def _dispatch_analyse_one(args: argparse.Namespace) -> None:
	result: AnalyseOneResult = run_analyse_one(
		config_path=args.config,
		arxiv_id=args.arxiv_id,
		topic_name=args.topic,
		write_db=args.write_db,
	)

	payload = json.dumps(result.payload, ensure_ascii=False, indent=2, default=str)
	if args.output_file:
		Path(args.output_file).write_text(payload, encoding="utf-8")
		print(f"[INFO] analyse-one wrote JSON to {args.output_file}")
	else:
		print(payload)


if __name__ == "__main__":
	main()
