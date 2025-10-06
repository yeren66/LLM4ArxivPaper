#!/usr/bin/env python3
"""Test configuration validation."""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config_loader import load_pipeline_config


def test_validation():
	"""Test configuration validation with different scenarios."""
	
	print("=" * 70)
	print("Testing Configuration Validation")
	print("=" * 70)
	
	# Get current environment state
	has_api_key = "API_KEY" in os.environ
	has_base_url = "BASE_URL" in os.environ
	has_mail_user = "MAIL_USERNAME" in os.environ
	has_mail_pass = "MAIL_PASSWORD" in os.environ
	
	print("\n📋 Current Environment Variables:")
	print(f"   API_KEY: {'✓ Set' if has_api_key else '✗ Not set'}")
	print(f"   BASE_URL: {'✓ Set' if has_base_url else '✗ Not set (will use default)'}")
	print(f"   MAIL_USERNAME: {'✓ Set' if has_mail_user else '✗ Not set'}")
	print(f"   MAIL_PASSWORD: {'✓ Set' if has_mail_pass else '✗ Not set'}")
	print()
	
	# Load config with validation
	config_path = Path(__file__).parent.parent / "config" / "pipeline.yaml"
	
	try:
		config = load_pipeline_config(config_path, validate=True)
		print("\n✅ Configuration loaded successfully!")
		print(f"\n📊 Configuration Summary:")
		print(f"   Runtime Mode: {config.runtime.mode}")
		print(f"   OpenAI Model (Relevance): {config.openai.relevance_model}")
		print(f"   OpenAI Model (Summary): {config.openai.summarization_model}")
		print(f"   Base URL: {config.openai.base_url or 'Default (OpenAI)'}")
		print(f"   Email Enabled: {config.email.enabled}")
		print(f"   Topics: {len(config.topics)}")
		for topic in config.topics:
			print(f"      - {topic.label} ({topic.name})")
		
	except SystemExit as e:
		print("\n❌ Configuration validation failed!")
		print("\nPlease fix the errors above and try again.")
		sys.exit(e.code)


if __name__ == "__main__":
	test_validation()
