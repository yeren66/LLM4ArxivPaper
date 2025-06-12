#!/usr/bin/env python3
"""
Test script to simulate GitHub Actions behavior
"""

import os
import sys
import subprocess
from datetime import datetime, timedelta

def test_command(cmd, description):
    """Test a command and return success status"""
    print(f"\n🧪 Testing: {description}")
    print(f"Command: {cmd}")
    print("-" * 50)
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        print(f"Return code: {result.returncode}")
        
        if result.returncode == 0:
            print(f"✅ {description} - SUCCESS")
            return True
        else:
            print(f"❌ {description} - FAILED")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} - TIMEOUT (5 minutes)")
        return False
    except Exception as e:
        print(f"❌ {description} - ERROR: {e}")
        return False

def check_environment():
    """Check if environment is properly set up"""
    print("🔍 Checking Environment Setup")
    print("=" * 50)
    
    # Check if config files exist
    config_files = ['config/config.yaml', 'config/secrets.env']
    for file in config_files:
        if os.path.exists(file):
            print(f"✅ {file} exists")
        else:
            print(f"❌ {file} missing")
    
    # Check environment variables
    env_vars = ['LLM_API_KEY', 'GH_TOKEN', 'EMAIL_PASSWORD']
    for var in env_vars:
        if os.getenv(var):
            print(f"✅ {var} is set")
        else:
            print(f"❌ {var} is missing")
    
    # Check Python dependencies
    try:
        import yaml, requests, openai
        print("✅ Key Python packages available")
    except ImportError as e:
        print(f"❌ Missing Python packages: {e}")

def main():
    """Main test function"""
    print("🚀 GitHub Actions Behavior Test")
    print("=" * 50)
    
    # Check environment first
    check_environment()
    
    # Test different command modes that GitHub Actions would use
    tests = [
        {
            'cmd': 'python src/main.py --email-only',
            'desc': 'Email-only mode (should send email report based on existing files)'
        },
        {
            'cmd': f'python src/main.py --date-range --start-date {(datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")} --end-date {(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")}',
            'desc': 'Date range mode (should crawl, summarize, and upload)'
        },
        {
            'cmd': 'python src/main.py --daily --days-back 1',
            'desc': 'Daily mode (should crawl, summarize, and upload for last 1 day)'
        },
        {
            'cmd': 'python src/main.py --arxiv',
            'desc': 'ArXiv mode (should crawl, summarize, and upload)'
        }
    ]
    
    results = []
    
    for test in tests:
        success = test_command(test['cmd'], test['desc'])
        results.append((test['desc'], success))
        
        # Add a delay between tests
        import time
        time.sleep(2)
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    for desc, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {desc}")
    
    # Check if any files were created
    print("\n📁 Checking for generated files:")
    
    dirs_to_check = ['logs', 'summaries', 'source/paper_note']
    for dir_path in dirs_to_check:
        if os.path.exists(dir_path):
            files = os.listdir(dir_path)
            print(f"✅ {dir_path}: {len(files)} files")
            if files:
                print(f"   Sample files: {files[:3]}")
        else:
            print(f"❌ {dir_path}: directory not found")
    
    # Recommendations
    print("\n💡 Recommendations:")
    
    failed_tests = [desc for desc, success in results if not success]
    if failed_tests:
        print("❌ Some tests failed. Common issues:")
        print("   1. Missing API keys (LLM_API_KEY, GH_TOKEN, EMAIL_PASSWORD)")
        print("   2. Network connectivity issues")
        print("   3. Invalid configuration in config/config.yaml")
        print("   4. Missing dependencies")
        print("\n🔧 To fix:")
        print("   1. Run: python debug_workflow.py")
        print("   2. Check logs/llm4reading.log for detailed errors")
        print("   3. Verify all environment variables are set")
    else:
        print("✅ All tests passed! GitHub Actions should work correctly.")
        print("   The workflow will crawl papers, generate summaries, and upload to GitHub.")

if __name__ == "__main__":
    main()
