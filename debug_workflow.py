#!/usr/bin/env python3
"""
Debug script to test the complete workflow step by step
"""

import os
import sys
import yaml
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_configuration():
    """Test configuration loading"""
    print("=== Configuration Test ===")
    try:
        config_path = "config/config.yaml"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        print("✅ Configuration loaded successfully")
        
        # Check key sections
        sections = ['arxiv', 'llm', 'github', 'email']
        for section in sections:
            if section in config:
                print(f"✅ {section} section found")
            else:
                print(f"❌ {section} section missing")
        
        return config
    except Exception as e:
        print(f"❌ Configuration loading failed: {e}")
        return None

def test_environment_variables():
    """Test required environment variables"""
    print("\n=== Environment Variables Test ===")
    
    required_vars = {
        'LLM_API_KEY': 'LLM API key',
        'GH_TOKEN': 'GitHub token',
        'EMAIL_PASSWORD': 'Email password'
    }
    
    missing_vars = []
    for var, description in required_vars.items():
        if os.getenv(var):
            print(f"✅ {var} ({description}) is set")
        else:
            print(f"❌ {var} ({description}) is missing")
            missing_vars.append(var)
    
    return len(missing_vars) == 0

def test_arxiv_crawler(config):
    """Test arXiv crawler"""
    print("\n=== arXiv Crawler Test ===")
    try:
        from paper_fetcher.arxiv_crawler import ArxivCrawler
        
        arxiv_config = config.get('arxiv', {})
        crawler = ArxivCrawler(arxiv_config)
        
        print("✅ ArxivCrawler initialized successfully")
        print(f"   Keyword groups: {len(crawler.keyword_groups)}")
        print(f"   Categories: {len(crawler.categories)}")
        
        # Test a simple search
        print("   Testing paper search...")
        papers = crawler.get_recent_papers(start_date=datetime.now() - timedelta(days=2), 
                                         end_date=datetime.now())
        
        print(f"✅ Found {len(papers)} papers")
        if papers:
            print(f"   Sample paper: {papers[0]['title'][:50]}...")
        
        return papers
        
    except Exception as e:
        print(f"❌ ArxivCrawler test failed: {e}")
        import traceback
        traceback.print_exc()
        return []

def test_llm_summarizer(config):
    """Test LLM summarizer"""
    print("\n=== LLM Summarizer Test ===")
    try:
        from llm_summarizer.openai_summarizer import OpenAISummarizer
        
        llm_config = config.get('llm', {})
        summarizer = OpenAISummarizer(llm_config)
        
        print("✅ OpenAISummarizer initialized successfully")
        print(f"   Provider: {llm_config.get('provider', 'openai')}")
        print(f"   Model: {llm_config.get('model', 'gpt-4')}")
        
        return summarizer
        
    except Exception as e:
        print(f"❌ LLM Summarizer test failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_github_client(config):
    """Test GitHub client"""
    print("\n=== GitHub Client Test ===")
    try:
        from github_uploader.github_client import GitHubClient
        
        github_config = config.get('github', {})
        client = GitHubClient(github_config)
        
        print("✅ GitHubClient initialized successfully")
        print(f"   Repository: {github_config.get('repository', 'unknown')}")
        print(f"   Branch: {github_config.get('branch', 'main')}")
        
        return client
        
    except Exception as e:
        print(f"❌ GitHub Client test failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_complete_workflow():
    """Test the complete workflow"""
    print("\n=== Complete Workflow Test ===")
    try:
        from main import LLM4Reading
        
        app = LLM4Reading()
        print("✅ LLM4Reading app initialized successfully")
        
        # Test with a small date range to avoid too many papers
        yesterday = datetime.now() - timedelta(days=1)
        today = datetime.now()
        
        print(f"   Testing with date range: {yesterday.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}")
        
        # This will test the complete workflow
        app.run_date_range(yesterday.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d'))
        
        print("✅ Complete workflow test completed")
        return True
        
    except Exception as e:
        print(f"❌ Complete workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main debug function"""
    print("🔍 LLM4Reading Workflow Debug Tool")
    print("=" * 50)
    
    # Test 1: Configuration
    config = test_configuration()
    if not config:
        print("\n❌ Cannot proceed without valid configuration")
        return False
    
    # Test 2: Environment variables
    env_ok = test_environment_variables()
    if not env_ok:
        print("\n⚠️  Some environment variables are missing. This may cause failures.")
    
    # Test 3: Individual components
    papers = test_arxiv_crawler(config)
    summarizer = test_llm_summarizer(config)
    github_client = test_github_client(config)
    
    # Test 4: Complete workflow (only if all components work)
    if papers and summarizer and github_client:
        print("\n🚀 All components working, testing complete workflow...")
        workflow_ok = test_complete_workflow()
        
        if workflow_ok:
            print("\n✅ All tests passed! The workflow should work correctly.")
        else:
            print("\n❌ Workflow test failed. Check the error messages above.")
    else:
        print("\n❌ Some components failed. Cannot test complete workflow.")
        print("   Fix the component issues first.")
    
    print("\n" + "=" * 50)
    print("Debug completed. Check the results above.")

if __name__ == "__main__":
    main()
