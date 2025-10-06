#!/usr/bin/env python3
"""Demo script showing configuration validation in action."""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def demo_scenario(title: str, env_vars: dict, mode: str = "online", email_enabled: bool = False):
	"""Run a validation scenario."""
	print("\n" + "=" * 80)
	print(f"  SCENARIO: {title}")
	print("=" * 80)
	
	# Clear relevant env vars
	for var in ["API_KEY", "BASE_URL", "MAIL_USERNAME", "MAIL_PASSWORD"]:
		os.environ.pop(var, None)
	
	# Set provided env vars
	for key, value in env_vars.items():
		os.environ[key] = value
		print(f"  ✓ Set {key}")
	
	print(f"  Mode: {mode}")
	print(f"  Email: {'Enabled' if email_enabled else 'Disabled'}")
	print()
	
	# Try to load config
	try:
		from src.core.config_loader import load_pipeline_config
		
		# Create a temporary config for testing
		import yaml
		test_config = {
			"openai": {
				"api_key": "${API_KEY}",
				"base_url": "${BASE_URL}",
				"relevance_model": "gpt-4o-mini",
				"summarization_model": "gpt-4o",
				"temperature": 0.2,
				"language": "zh-CN"
			},
			"fetch": {
				"max_papers_per_topic": 10,
				"days_back": 7,
				"request_delay": 1.0
			},
			"topics": [{
				"name": "test",
				"label": "Test",
				"query": {
					"categories": ["cs.AI"],
					"include": ["test"],
					"exclude": []
				},
				"interest_prompt": "Test"
			}],
			"relevance": {
				"scoring_dimensions": [{
					"name": "test",
					"weight": 1.0,
					"description": "Test"
				}],
				"pass_threshold": 60
			},
			"summarization": {
				"task_list_size": 5,
				"max_sections": 4
			},
			"site": {
				"output_dir": "site",
				"base_url": "https://example.com"
			},
			"email": {
				"enabled": email_enabled,
				"sender": "${MAIL_USERNAME}",
				"recipients": ["test@example.com"],
				"smtp_host": "smtp.gmail.com",
				"smtp_port": 465,
				"username": "${MAIL_USERNAME}",
				"password": "${MAIL_PASSWORD}",
				"use_tls": False,
				"use_ssl": True,
				"timeout": 30,
				"subject_template": "Test"
			},
			"runtime": {
				"mode": mode,
				"paper_limit": None
			}
		}
		
		# Write temporary config
		temp_config_path = Path("/tmp/test_pipeline.yaml")
		with open(temp_config_path, 'w') as f:
			yaml.dump(test_config, f)
		
		# Load with validation
		config = load_pipeline_config(temp_config_path, validate=True)
		
		print("✅ RESULT: Configuration validated successfully!")
		print(f"   API Key: {'Set' if config.openai.api_key and not config.openai.api_key.startswith('${') else 'Not set'}")
		print(f"   Base URL: {config.openai.base_url or 'Default'}")
		
	except SystemExit as e:
		print("❌ RESULT: Validation failed (expected behavior)")
		return False
	except Exception as e:
		print(f"❌ ERROR: {e}")
		import traceback
		traceback.print_exc()
		return False
	
	return True


def main():
	"""Run validation demos."""
	print("=" * 80)
	print("  Configuration Validation Demo")
	print("  Demonstrating different scenarios")
	print("=" * 80)
	
	# Scenario 1: Valid online mode with API key
	demo_scenario(
		"Valid Online Mode",
		{"API_KEY": "sk-test-valid-key-12345"},
		mode="online",
		email_enabled=False
	)
	
	# Scenario 2: Online mode without API key (should fail)
	demo_scenario(
		"Online Mode - Missing API Key (Should Fail)",
		{},
		mode="online",
		email_enabled=False
	)
	
	# Scenario 3: Offline mode (no API key needed)
	demo_scenario(
		"Offline Mode - No API Key Needed",
		{},
		mode="offline",
		email_enabled=False
	)
	
	# Scenario 4: Email enabled without credentials (should fail)
	demo_scenario(
		"Email Enabled - Missing Credentials (Should Fail)",
		{"API_KEY": "sk-test-valid-key-12345"},
		mode="online",
		email_enabled=True
	)
	
	# Scenario 5: Email enabled with credentials
	demo_scenario(
		"Email Enabled - With Credentials",
		{
			"API_KEY": "sk-test-valid-key-12345",
			"MAIL_USERNAME": "test@example.com",
			"MAIL_PASSWORD": "test-password"
		},
		mode="online",
		email_enabled=True
	)
	
	# Scenario 6: Custom BASE_URL
	demo_scenario(
		"Custom API Base URL",
		{
			"API_KEY": "sk-test-valid-key-12345",
			"BASE_URL": "https://custom-api.example.com/v1"
		},
		mode="online",
		email_enabled=False
	)
	
	print("\n" + "=" * 80)
	print("  Demo Complete!")
	print("=" * 80)


if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		print("\n\n❌ Demo cancelled.")
		sys.exit(1)
