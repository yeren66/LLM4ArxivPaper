"""Configuration validation and environment variable checking."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ValidationError:
	"""Represents a configuration validation error."""
	
	field_path: str
	message: str
	severity: str  # 'error' or 'warning'
	
	def __str__(self) -> str:
		prefix = "❌ ERROR" if self.severity == "error" else "⚠️  WARNING"
		return f"{prefix}: {self.field_path} - {self.message}"


@dataclass
class ValidationResult:
	"""Result of configuration validation."""
	
	errors: List[ValidationError]
	warnings: List[ValidationError]
	
	@property
	def is_valid(self) -> bool:
		"""Returns True if there are no errors (warnings are acceptable)."""
		return len(self.errors) == 0
	
	def print_summary(self) -> None:
		"""Print validation summary to console."""
		if self.is_valid and not self.warnings:
			print("✅ Configuration validation passed!")
			return
		
		if self.errors:
			print("\n" + "=" * 70)
			print("❌ Configuration Validation Errors:")
			print("=" * 70)
			for error in self.errors:
				print(f"\n  Field: {error.field_path}")
				print(f"  Issue: {error.message}")
		
		if self.warnings:
			print("\n" + "=" * 70)
			print("⚠️  Configuration Validation Warnings:")
			print("=" * 70)
			for warning in self.warnings:
				print(f"\n  Field: {warning.field_path}")
				print(f"  Issue: {warning.message}")
		
		print("\n" + "=" * 70)


class ConfigValidator:
	"""Validates pipeline configuration with environment variable expansion."""
	
	# Default values for optional environment variables
	DEFAULTS = {
		"BASE_URL": "https://api.openai.com/v1",
	}
	
	# Environment variables that are required in specific contexts
	REQUIRED_IN_ONLINE_MODE = ["API_KEY"]
	REQUIRED_FOR_EMAIL = ["MAIL_USERNAME", "MAIL_PASSWORD"]
	
	def __init__(self, config_dict: Dict[str, Any], expanded_dict: Dict[str, Any]):
		"""
		Initialize validator with both original and expanded config.
		
		Args:
			config_dict: Original config dict before environment variable expansion
			expanded_dict: Config dict after environment variable expansion
		"""
		self.config_dict = config_dict
		self.expanded_dict = expanded_dict
		self.errors: List[ValidationError] = []
		self.warnings: List[ValidationError] = []
	
	def validate(self) -> ValidationResult:
		"""
		Run all validation checks.
		
		Returns:
			ValidationResult containing errors and warnings
		"""
		self.errors = []
		self.warnings = []
		
		# Check environment variable expansion
		self._check_env_vars()
		
		# Check mode-specific requirements
		self._check_online_mode_requirements()
		
		# Check email configuration
		self._check_email_requirements()
		
		# Check for unexpanded variables
		self._check_unexpanded_vars()
		
		return ValidationResult(errors=self.errors, warnings=self.warnings)
	
	def _check_env_vars(self) -> None:
		"""Check if environment variables are properly set."""
		# Find all ${VAR} patterns in config
		env_vars_found = self._find_env_vars(self.config_dict)
		
		for var_name, field_path in env_vars_found:
			if var_name not in os.environ:
				if var_name in self.DEFAULTS:
					# Has default value
					self.warnings.append(ValidationError(
						field_path=field_path,
						message=f"Environment variable ${{{var_name}}} not set, using default: {self.DEFAULTS[var_name]}",
						severity="warning"
					))
				else:
					# Check if it's required based on context
					# We'll do context-specific checks in separate methods
					pass
	
	def _check_online_mode_requirements(self) -> None:
		"""Check requirements for online mode."""
		mode = self.expanded_dict.get("runtime", {}).get("mode", "offline")
		
		if mode == "online":
			api_key = self.expanded_dict.get("openai", {}).get("api_key")
			
			# Check if API_KEY is missing or unexpanded
			if not api_key or api_key.startswith("${"):
				self.errors.append(ValidationError(
					field_path="openai.api_key",
					message="API_KEY environment variable is required in online mode. Please set it with: export API_KEY='your-api-key'",
					severity="error"
				))
			elif api_key.strip() == "":
				self.errors.append(ValidationError(
					field_path="openai.api_key",
					message="API_KEY is empty. Please provide a valid OpenAI API key.",
					severity="error"
				))
	
	def _check_email_requirements(self) -> None:
		"""Check requirements for email configuration."""
		email_config = self.expanded_dict.get("email", {})
		enabled = email_config.get("enabled", False)
		
		if not enabled:
			return
		
		# Check sender
		sender = email_config.get("sender")
		if not sender or sender.startswith("${"):
			self.errors.append(ValidationError(
				field_path="email.sender",
				message="MAIL_USERNAME environment variable is required when email is enabled. Please set it with: export MAIL_USERNAME='your-email@example.com'",
				severity="error"
			))
		
		# Check username
		username = email_config.get("username")
		if not username or username.startswith("${"):
			self.errors.append(ValidationError(
				field_path="email.username",
				message="MAIL_USERNAME environment variable is required when email is enabled.",
				severity="error"
			))
		
		# Check password
		password = email_config.get("password")
		if not password or password.startswith("${"):
			self.errors.append(ValidationError(
				field_path="email.password",
				message="MAIL_PASSWORD environment variable is required when email is enabled. Please set it with: export MAIL_PASSWORD='your-password'",
				severity="error"
			))
		
		# Check SMTP host
		smtp_host = email_config.get("smtp_host")
		if not smtp_host:
			self.errors.append(ValidationError(
				field_path="email.smtp_host",
				message="SMTP host must be configured when email is enabled.",
				severity="error"
			))
		
		# Check recipients
		recipients = email_config.get("recipients", [])
		if not recipients:
			self.warnings.append(ValidationError(
				field_path="email.recipients",
				message="No email recipients configured. Email will not be sent.",
				severity="warning"
			))
	
	def _check_unexpanded_vars(self) -> None:
		"""Check for any unexpanded ${VAR} patterns that might cause issues."""
		unexpanded = self._find_unexpanded_vars(self.expanded_dict)
		
		for var_name, field_path, value in unexpanded:
			self.warnings.append(ValidationError(
				field_path=field_path,
				message=f"Value contains unexpanded variable: {value}. Environment variable ${{{var_name}}} may not be set.",
				severity="warning"
			))
	
	def _find_env_vars(self, obj: Any, path: str = "") -> List[tuple[str, str]]:
		"""
		Recursively find all ${VAR} patterns in the config.
		
		Returns:
			List of (var_name, field_path) tuples
		"""
		results = []
		
		if isinstance(obj, str):
			# Find all ${VAR} patterns
			matches = re.findall(r'\$\{([A-Z_][A-Z0-9_]*)\}', obj)
			for var_name in matches:
				results.append((var_name, path))
		
		elif isinstance(obj, dict):
			for key, value in obj.items():
				new_path = f"{path}.{key}" if path else key
				results.extend(self._find_env_vars(value, new_path))
		
		elif isinstance(obj, list):
			for i, item in enumerate(obj):
				new_path = f"{path}[{i}]"
				results.extend(self._find_env_vars(item, new_path))
		
		return results
	
	def _find_unexpanded_vars(self, obj: Any, path: str = "") -> List[tuple[str, str, str]]:
		"""
		Find unexpanded ${VAR} patterns in the expanded config.
		
		Returns:
			List of (var_name, field_path, value) tuples
		"""
		results = []
		
		if isinstance(obj, str):
			# Check if string still contains ${VAR} pattern
			matches = re.findall(r'\$\{([A-Z_][A-Z0-9_]*)\}', obj)
			for var_name in matches:
				results.append((var_name, path, obj))
		
		elif isinstance(obj, dict):
			for key, value in obj.items():
				new_path = f"{path}.{key}" if path else key
				results.extend(self._find_unexpanded_vars(value, new_path))
		
		elif isinstance(obj, list):
			for i, item in enumerate(obj):
				new_path = f"{path}[{i}]"
				results.extend(self._find_unexpanded_vars(item, new_path))
		
		return results


def apply_defaults(config_dict: Dict[str, Any]) -> Dict[str, Any]:
	"""
	Apply default values for missing environment variables before expansion.
	
	Args:
		config_dict: Configuration dictionary
	
	Returns:
		Modified config dictionary with defaults applied
	"""
	# Apply BASE_URL default if not set in environment
	if "BASE_URL" not in os.environ:
		base_url_value = config_dict.get("openai", {}).get("base_url", "")
		if base_url_value == "${BASE_URL}":
			os.environ["BASE_URL"] = ConfigValidator.DEFAULTS["BASE_URL"]
			print(f"[INFO] BASE_URL not set, using default: {ConfigValidator.DEFAULTS['BASE_URL']}")
	
	return config_dict
