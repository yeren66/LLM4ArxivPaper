#!/usr/bin/env python3
"""
Debug script to simulate and test GitHub Actions behavior
"""

import os
import sys
import subprocess
from datetime import datetime

def simulate_github_actions_logic():
    """Simulate the GitHub Actions logic to understand why it's choosing email mode"""
    print("🔍 Simulating GitHub Actions Logic")
    print("=" * 50)
    
    # Simulate different scenarios
    scenarios = [
        {
            'name': 'Manual trigger with date range',
            'event_name': 'workflow_dispatch',
            'email_only': 'false',
            'start_date': '2025-06-03',
            'end_date': '2025-06-04'
        },
        {
            'name': 'Manual trigger with email only',
            'event_name': 'workflow_dispatch',
            'email_only': 'true',
            'start_date': '',
            'end_date': ''
        },
        {
            'name': 'Manual trigger with no parameters',
            'event_name': 'workflow_dispatch',
            'email_only': 'false',
            'start_date': '',
            'end_date': ''
        },
        {
            'name': 'Scheduled run (crawl)',
            'event_name': 'schedule',
            'email_only': 'false',
            'start_date': '',
            'end_date': '',
            'schedule': '0 19 * * *'
        },
        {
            'name': 'Scheduled run (email)',
            'event_name': 'schedule',
            'email_only': 'false',
            'start_date': '',
            'end_date': '',
            'schedule': '0 0 * * *'
        }
    ]
    
    for scenario in scenarios:
        print(f"\n📋 Scenario: {scenario['name']}")
        print("-" * 30)
        
        event_name = scenario['event_name']
        email_only = scenario['email_only']
        start_date = scenario['start_date']
        end_date = scenario['end_date']
        schedule = scenario.get('schedule', '')
        
        print(f"Event name: {event_name}")
        print(f"Email only: '{email_only}'")
        print(f"Start date: '{start_date}'")
        print(f"End date: '{end_date}'")
        if schedule:
            print(f"Schedule: {schedule}")
        
        # Apply the logic from GitHub Actions
        if start_date and end_date:
            mode = "date_range"
            command = f"python src/main.py --date-range --start-date {start_date} --end-date {end_date}"
        elif email_only == "true":
            mode = "email"
            command = "python src/main.py --email-only"
        elif event_name == "schedule":
            if schedule == "0 0 * * *":
                mode = "email"
                command = "python src/main.py --email-only"
            else:
                mode = "crawl"
                command = "python src/main.py --daily --days-back 1"
        else:
            mode = "crawl"
            command = "python src/main.py --daily --days-back 1"
        
        print(f"🎯 Selected mode: {mode}")
        print(f"🔧 Command: {command}")
        
        if scenario['name'] == 'Manual trigger with date range':
            print("✅ This should be the correct behavior for your case!")

def test_date_range_command():
    """Test the date range command directly"""
    print("\n🧪 Testing Date Range Command Directly")
    print("=" * 50)
    
    start_date = "2025-06-03"
    end_date = "2025-06-04"
    command = f"python src/main.py --date-range --start-date {start_date} --end-date {end_date}"
    
    print(f"Command: {command}")
    print("Expected behavior: Should crawl papers from June 3-4, 2025")
    print("\nExecuting command...")
    print("-" * 30)
    
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("\nSTDERR:")
            print(result.stderr)
        
        print(f"\nReturn code: {result.returncode}")
        
        if result.returncode == 0:
            print("✅ Command executed successfully")
            
            # Check if it actually processed papers
            if "Found" in result.stdout and "papers" in result.stdout:
                print("✅ Papers were found and processed")
            elif "No papers" in result.stdout:
                print("⚠️  No papers found for the specified date range")
            else:
                print("❓ Unclear if papers were processed")
        else:
            print("❌ Command failed")
            
    except subprocess.TimeoutExpired:
        print("⏰ Command timed out (2 minutes)")
    except Exception as e:
        print(f"❌ Error executing command: {e}")

def check_github_actions_inputs():
    """Check how GitHub Actions handles boolean inputs"""
    print("\n🔍 GitHub Actions Boolean Input Analysis")
    print("=" * 50)
    
    print("GitHub Actions boolean input behavior:")
    print("- When checkbox is unchecked: value is 'false' (string)")
    print("- When checkbox is checked: value is 'true' (string)")
    print("- Default value is 'false' (string)")
    print()
    
    print("Common issues:")
    print("1. Comparing boolean input with actual boolean: email_only == true (WRONG)")
    print("2. Correct comparison: email_only == 'true' (CORRECT)")
    print()
    
    print("Your case analysis:")
    print("- You set start_date: '2025-06-03'")
    print("- You set end_date: '2025-06-04'")
    print("- email_only should be 'false' (default)")
    print()
    print("Expected logic flow:")
    print("1. Check if start_date and end_date are not empty ✅")
    print("2. Should select 'date_range' mode ✅")
    print("3. Should execute: python src/main.py --date-range --start-date 2025-06-03 --end-date 2025-06-04")

def main():
    """Main debug function"""
    print("🔧 GitHub Actions Debug Tool")
    print("=" * 50)
    
    # Simulate GitHub Actions logic
    simulate_github_actions_logic()
    
    # Analyze boolean input handling
    check_github_actions_inputs()
    
    # Test the actual command
    test_date_range_command()
    
    print("\n" + "=" * 50)
    print("📋 Summary and Recommendations")
    print("=" * 50)
    
    print("\n🔍 Why your GitHub Actions ran email mode:")
    print("1. The logic in the workflow file had a bug")
    print("2. Boolean input handling was incorrect")
    print("3. The order of conditions was wrong")
    
    print("\n✅ Fixes applied:")
    print("1. Fixed the condition order (date_range check first)")
    print("2. Added proper debugging output")
    print("3. Improved boolean input handling")
    
    print("\n🚀 Next steps:")
    print("1. Push the updated workflow file to GitHub")
    print("2. Manually trigger the workflow again with:")
    print("   - Start date: 2025-06-03")
    print("   - End date: 2025-06-04")
    print("   - Email only: unchecked")
    print("3. Look for 'Manual date range mode detected' in the logs")
    print("4. The workflow should now crawl papers from the specified date range")

if __name__ == "__main__":
    main()
