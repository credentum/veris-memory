#!/usr/bin/env python3
"""
Test script for Telegram alerting functionality.

This script tests the Telegram bot integration and alert manager
without running the full Sentinel system.

Author: Workspace 002
Date: 2025-08-19
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.monitoring.sentinel.telegram_alerter import TelegramAlerter, AlertSeverity
from src.monitoring.sentinel.alert_manager import AlertManager
from src.monitoring.sentinel.models import CheckResult


async def test_telegram_connection():
    """Test basic Telegram bot connection."""
    print("\n=== Testing Telegram Connection ===")
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("❌ Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
        print("Please set these environment variables first.")
        return False
    
    alerter = TelegramAlerter(token, chat_id)
    connected = await alerter.test_connection()
    
    if connected:
        print("✅ Successfully connected to Telegram bot")
        return True
    else:
        print("❌ Failed to connect to Telegram bot")
        return False


async def test_send_alerts():
    """Test sending different types of alerts."""
    print("\n=== Testing Alert Sending ===")
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("❌ Missing credentials")
        return False
    
    alerter = TelegramAlerter(token, chat_id)
    
    # Test different severity levels
    test_cases = [
        {
            "check_id": "TEST-info",
            "status": "pass",
            "message": "This is a test INFO alert",
            "severity": AlertSeverity.INFO,
            "details": {"test": "info_level", "timestamp": datetime.utcnow().isoformat()}
        },
        {
            "check_id": "TEST-warning",
            "status": "warn",
            "message": "This is a test WARNING alert",
            "severity": AlertSeverity.WARNING,
            "details": {"test": "warning_level", "response_time": 150.5}
        },
        {
            "check_id": "TEST-high",
            "status": "fail",
            "message": "This is a test HIGH severity alert",
            "severity": AlertSeverity.HIGH,
            "details": {"test": "high_level", "failures": 5, "affected_service": "test-service"}
        },
        {
            "check_id": "TEST-critical",
            "status": "fail",
            "message": "This is a test CRITICAL alert - immediate action required!",
            "severity": AlertSeverity.CRITICAL,
            "details": {"test": "critical_level", "error": "Service completely down", "impact": "All users affected"}
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nSending alert {i}/{len(test_cases)}: {test_case['severity'].value}")
        success = await alerter.send_alert(
            check_id=test_case["check_id"],
            status=test_case["status"],
            message=test_case["message"],
            severity=test_case["severity"],
            details=test_case["details"],
            latency_ms=100.0 + (i * 50)
        )
        
        if success:
            print(f"✅ {test_case['severity'].value} alert sent successfully")
        else:
            print(f"❌ Failed to send {test_case['severity'].value} alert")
        
        # Small delay between messages
        await asyncio.sleep(2)
    
    return True


async def test_summary():
    """Test sending a summary report."""
    print("\n=== Testing Summary Report ===")
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("❌ Missing credentials")
        return False
    
    alerter = TelegramAlerter(token, chat_id)
    
    # Send a test summary
    success = await alerter.send_summary(
        period_hours=24,
        total_checks=1440,
        passed_checks=1420,
        failed_checks=20,
        top_failures=[
            {"check_id": "S8-capacity-smoke", "count": 10},
            {"check_id": "S3-paraphrase-robustness", "count": 5},
            {"check_id": "S4-metrics-wiring", "count": 5}
        ],
        avg_latency_ms=45.2,
        uptime_percent=98.6
    )
    
    if success:
        print("✅ Summary report sent successfully")
    else:
        print("❌ Failed to send summary report")
    
    return success


async def test_alert_manager():
    """Test the complete alert manager flow."""
    print("\n=== Testing Alert Manager ===")
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    github_token = os.getenv("GITHUB_TOKEN")
    
    if not token or not chat_id:
        print("❌ Missing Telegram credentials")
        return False
    
    # Create alert manager
    manager = AlertManager(
        telegram_token=token,
        telegram_chat_id=chat_id,
        github_token=github_token,
        github_repo="credentum/veris-memory",
        dedup_window_minutes=1,  # Short window for testing
        alert_threshold_failures=2
    )
    
    # Test alerting channels
    print("\nTesting configured channels...")
    results = await manager.test_alerting()
    for channel, status in results.items():
        emoji = "✅" if status else "❌"
        print(f"{emoji} {channel}: {'Connected' if status else 'Not configured/Failed'}")
    
    # Simulate check failures
    print("\nSimulating check failures...")
    
    # First failure - should not alert (below threshold)
    result1 = CheckResult(
        check_id="S5-security-negatives",
        timestamp=datetime.utcnow(),
        status="fail",
        latency_ms=250.5,
        message="Unauthorized access detected - 10 attempts",
        details={"attempts": 10, "source": "192.168.1.100"}
    )
    
    print("Sending first failure (below threshold)...")
    await manager.process_check_result(result1)
    await asyncio.sleep(1)
    
    # Second failure - should trigger alert
    result2 = CheckResult(
        check_id="S5-security-negatives",
        timestamp=datetime.utcnow(),
        status="fail",
        latency_ms=300.2,
        message="Unauthorized access detected - 15 attempts",
        details={"attempts": 15, "source": "192.168.1.100"}
    )
    
    print("Sending second failure (should trigger alert)...")
    await manager.process_check_result(result2)
    await asyncio.sleep(1)
    
    # Third failure - should be deduplicated
    result3 = CheckResult(
        check_id="S5-security-negatives",
        timestamp=datetime.utcnow(),
        status="fail",
        latency_ms=280.1,
        message="Unauthorized access detected - 15 attempts",  # Same message
        details={"attempts": 20, "source": "192.168.1.100"}
    )
    
    print("Sending third failure (should be deduplicated)...")
    await manager.process_check_result(result3)
    
    print("\n✅ Alert manager test completed")
    return True


async def main():
    """Run all tests."""
    print("=" * 50)
    print("Veris Sentinel Telegram Alerting Test")
    print("=" * 50)
    
    # Load environment variables from .env.sentinel if it exists
    env_file = Path(__file__).parent.parent / ".env.sentinel"
    if env_file.exists():
        print(f"Loading configuration from {env_file}")
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    os.environ[key] = value
    else:
        print("No .env.sentinel file found, using existing environment variables")
    
    # Run tests
    tests = [
        ("Connection Test", test_telegram_connection),
        ("Send Alerts Test", test_send_alerts),
        ("Summary Report Test", test_summary),
        ("Alert Manager Test", test_alert_manager)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            print(f"\n{'=' * 50}")
            print(f"Running: {name}")
            print("=" * 50)
            
            result = await test_func()
            results.append((name, result))
            
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            results.append((name, False))
    
    # Print summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    for name, result in results:
        emoji = "✅" if result else "❌"
        print(f"{emoji} {name}: {'PASSED' if result else 'FAILED'}")
    
    all_passed = all(r for _, r in results)
    
    if all_passed:
        print("\n🎉 All tests passed! Telegram alerting is ready to use.")
    else:
        print("\n⚠️ Some tests failed. Please check the configuration.")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
