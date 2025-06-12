#!/usr/bin/env python3
"""
Test script to verify OpenAI client initialization fix
"""

import os
import sys
import yaml
from pathlib import Path

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_openai_initialization():
    """Test OpenAI client initialization"""
    try:
        from llm_summarizer.openai_summarizer import OpenAISummarizer

        # Load config
        config_path = "config/config.yaml"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        llm_config = config.get('llm', {})

        print(f"Testing OpenAI client initialization...")
        print(f"Provider: {llm_config.get('provider', 'openai')}")
        print(f"Model: {llm_config.get('model', 'gpt-4')}")
        print(f"Base URL: {llm_config.get('base_url', 'default')}")

        # Check if API key is available
        api_key = os.getenv('LLM_API_KEY') or os.getenv('DEEPSEEK_API_KEY') or os.getenv('OPENAI_API_KEY')
        print(f"API Key available: {bool(api_key)}")

        if not api_key:
            print("⚠️  No API key found. Testing initialization without API calls...")
            print("   Set LLM_API_KEY, DEEPSEEK_API_KEY, or OPENAI_API_KEY for full testing.")
            # Continue with test using a dummy key to test initialization logic
            os.environ['LLM_API_KEY'] = 'sk-dummy-key-for-testing'

        # Initialize summarizer
        summarizer = OpenAISummarizer(llm_config)

        print("✅ OpenAI client initialized successfully!")
        print(f"System prompt preview: {summarizer.get_system_prompt()[:100]}...")

        return True

    except Exception as e:
        print(f"❌ Failed to initialize OpenAI client: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_environment_variables():
    """Test environment variable handling"""
    print("\n=== Environment Variables Test ===")
    
    # Check for proxy environment variables
    proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']
    proxy_found = False
    
    for var in proxy_vars:
        if var in os.environ:
            print(f"Found proxy variable: {var} = {os.environ[var]}")
            proxy_found = True
    
    if not proxy_found:
        print("No proxy environment variables found.")
    
    # Check for required environment variables
    required_vars = ['LLM_API_KEY', 'GH_TOKEN', 'EMAIL_PASSWORD']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"Missing environment variables: {', '.join(missing_vars)}")
        print("Note: These are required for full functionality.")
    else:
        print("All required environment variables are set.")

def test_date_range_functionality():
    """Test date range functionality"""
    print("\n=== Date Range Functionality Test ===")
    try:
        from src.main import LLM4Reading

        app = LLM4Reading()
        print("✅ LLM4Reading app initialized successfully")

        # Test with the specific date range you mentioned (6.3~6.4)
        start_date = "2025-06-03"
        end_date = "2025-06-04"

        print(f"Testing date range: {start_date} to {end_date}")
        print("This should crawl papers from the specified date range...")

        # This will test the date range functionality
        app.run_date_range(start_date, end_date)

        print("✅ Date range test completed successfully")
        return True

    except Exception as e:
        print(f"❌ Date range test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    print("=== LLM4Reading OpenAI Fix Test ===")

    # Test environment variables
    test_environment_variables()

    # Test OpenAI initialization
    print("\n=== OpenAI Client Test ===")
    openai_success = test_openai_initialization()

    # Test date range functionality
    date_range_success = test_date_range_functionality()

    if openai_success and date_range_success:
        print("\n✅ All tests passed! The system should work correctly.")
        print("\n📋 Next steps:")
        print("1. Push the updated code to GitHub")
        print("2. Manually trigger GitHub Actions with date range 2025-06-03 to 2025-06-04")
        print("3. Check the logs for 'Manual date range mode detected'")
    else:
        print("\n❌ Some tests failed. Please check the error messages above.")

    return openai_success and date_range_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
