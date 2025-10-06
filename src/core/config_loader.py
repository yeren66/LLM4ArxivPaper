"""Helpers for loading pipeline configuration."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict

import yaml

from .config_validator import ConfigValidator, apply_defaults
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


def load_pipeline_config(path: str | Path, validate: bool = True) -> PipelineConfig:
	"""
	Load YAML config and return a :class:`PipelineConfig` instance.
	
	Args:
		path: Path to the configuration YAML file
		validate: Whether to perform configuration validation (default: True)
	
	Returns:
		PipelineConfig instance
	
	Raises:
		FileNotFoundError: If config file doesn't exist
		SystemExit: If validation fails with errors
	"""

	config_path = Path(path)
	if not config_path.exists():
		raise FileNotFoundError(f"Config file not found: {config_path}")

	with config_path.open("r", encoding="utf-8") as handle:
		data: Dict[str, Any] = yaml.safe_load(handle) or {}

	# Apply default values for optional environment variables
	data = apply_defaults(data)
	
	# Expand environment variables
	expanded = _expand_env(data)
	
	# Validate configuration if requested
	if validate:
		validator = ConfigValidator(config_dict=data, expanded_dict=expanded)
		result = validator.validate()
		
		# Print validation results
		result.print_summary()
		
		# Exit if there are errors
		if not result.is_valid:
			print("\n💡 Tip: Set missing environment variables using:")
			print("   export VARIABLE_NAME='your-value'")
			print("\n   Or add them to your shell profile (~/.zshrc, ~/.bashrc, etc.)")
			sys.exit(1)
	
	return PipelineConfig.from_dict(expanded)
