"""Helpers for loading pipeline configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml

from .models import PipelineConfig


def _expand_env(value: Any) -> Any:
	"""Recursively expand environment variables in strings."""

	if isinstance(value, str):
		return os.path.expandvars(value)
	if isinstance(value, list):
		return [_expand_env(item) for item in value]
	if isinstance(value, dict):
		return {key: _expand_env(val) for key, val in value.items()}
	return value


def load_pipeline_config(path: str | Path) -> PipelineConfig:
	"""Load YAML config and return a :class:`PipelineConfig` instance."""

	config_path = Path(path)
	if not config_path.exists():
		raise FileNotFoundError(f"Config file not found: {config_path}")

	with config_path.open("r", encoding="utf-8") as handle:
		data: Dict[str, Any] = yaml.safe_load(handle) or {}

	expanded = _expand_env(data)
	return PipelineConfig.from_dict(expanded)
