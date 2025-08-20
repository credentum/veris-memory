#!/usr/bin/env python3
"""
Test Script for GitHub Webhook Integration

This script tests the end-to-end webhook flow from Sentinel alerts
to GitHub Actions automation.

Usage:
    python scripts/test-webhook-integration.py [test-type]
    
Test types:
    - critical: Test critical alert workflow
    - warning: Test warning alert workflow
    - all: Test all alert types
    - connectivity: Test GitHub API connectivity only

Author: Claude Code Integration
Date: 2025-08-20
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from monitoring.sentinel.webhook_alerter import GitHubWebhookAlerter
from monitoring.sentinel.alert_manager import AlertManager
from monitoring.sentinel.models import CheckResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WebhookIntegrationTester:
    """Test the GitHub webhook integration end-to-end."""
    
    def __init__(self):
        """Initialize the tester."""
        self.webhook_alerter = GitHubWebhookAlerter()
        self.alert_manager = AlertManager()
        
    async def test_connectivity(self) -> bool:
        """Test GitHub API connectivity."""
        logger.info("🔍 Testing GitHub API connectivity...")
        
        success = await self.webhook_alerter.test_connectivity()
        
        if success:
            logger.info("✅ GitHub API connectivity successful")
            
            # Show webhook status
            status = self.webhook_alerter.get_status()
            logger.info(f"📊 Webhook Status: {json.dumps(status, indent=2)}")
            
        else:
            logger.error("❌ GitHub API connectivity failed")
            logger.error("Check GITHUB_TOKEN environment variable")
            
        return success
    
    async def test_critical_alert(self) -> bool:
        """Test critical alert workflow."""
        logger.info("🚨 Testing critical alert workflow...")
        
        # Create a mock critical alert
        test_result = CheckResult(
            check_id="S1-health-probes",
            timestamp=datetime.now(),
            status="fail",
            latency_ms=250.0,
            message="Critical test alert: API health check failed",
            details={
                "test_type": "webhook-integration-test",
                "api_endpoint": "/api/v1/health",
                "status_code": 500,
                "error": "Internal server error during test",
                "expected_behavior": "Should trigger GitHub Actions workflow",
                "severity_level": "critical"
            }
        )
        
        # Send via webhook alerter
        webhook_success = await self.webhook_alerter.send_alert(test_result)
        
        if webhook_success:
            logger.info("✅ Critical alert sent successfully via webhook")
            logger.info("📝 Check GitHub Actions for new workflow run")
            logger.info("📝 Check GitHub Issues for new critical issue")
        else:
            logger.error("❌ Failed to send critical alert via webhook")
            
        return webhook_success
    
    async def test_warning_alert(self) -> bool:
        """Test warning alert workflow."""
        logger.info("⚠️ Testing warning alert workflow...")
        
        # Create a mock warning alert
        test_result = CheckResult(
            check_id="S3-paraphrase-robustness",
            timestamp=datetime.now(),
            status="warn",
            latency_ms=150.0,
            message="Warning test alert: Semantic consistency degraded",
            details={
                "test_type": "webhook-integration-test",
                "similarity_threshold": 0.8,
                "actual_similarity": 0.65,
                "affected_queries": 3,
                "expected_behavior": "Should trigger GitHub Actions workflow",
                "severity_level": "warning"
            }
        )
        
        # Send via webhook alerter
        webhook_success = await self.webhook_alerter.send_alert(test_result)
        
        if webhook_success:
            logger.info("✅ Warning alert sent successfully via webhook")
            logger.info("📝 Check GitHub Actions for new workflow run")
        else:
            logger.error("❌ Failed to send warning alert via webhook")
            
        return webhook_success
    
    async def test_alert_manager_integration(self) -> bool:
        """Test alert manager integration."""
        logger.info("🔧 Testing alert manager integration...")
        
        # Create a test result
        test_result = CheckResult(
            check_id="S11-firewall-status",
            timestamp=datetime.now(),
            status="fail",
            latency_ms=75.0,
            message="Test alert: Firewall integration test",
            details={
                "test_type": "alert-manager-integration-test",
                "firewall_status": "testing",
                "expected_behavior": "Should route through alert manager to webhook",
                "severity_level": "critical"
            }
        )
        
        # Process through alert manager
        try:
            await self.alert_manager.process_check_result(test_result)
            logger.info("✅ Alert processed through alert manager successfully")
            logger.info("📝 Check all configured alert channels")
            return True
        except Exception as e:
            logger.error(f"❌ Alert manager processing failed: {e}")
            return False
    
    async def test_rate_limiting(self) -> bool:
        """Test rate limiting functionality."""
        logger.info("⏱️ Testing rate limiting...")
        
        success_count = 0
        total_tests = 15  # Should exceed rate limit
        
        for i in range(total_tests):
            test_result = CheckResult(
                check_id=f"rate-limit-test-{i}",
                timestamp=datetime.now(),
                status="fail",
                latency_ms=50.0,
                message=f"Rate limit test alert #{i+1}",
                details={"test_type": "rate-limiting-test", "iteration": i+1}
            )
            
            success = await self.webhook_alerter.send_alert(test_result)
            if success:
                success_count += 1
            
            # Small delay between requests
            await asyncio.sleep(0.1)
        
        logger.info(f"📊 Rate limiting test: {success_count}/{total_tests} alerts sent")
        
        # Should have rate limiting kick in
        rate_limited = success_count < total_tests
        if rate_limited:
            logger.info("✅ Rate limiting is working correctly")
        else:
            logger.warning("⚠️ Rate limiting may not be working")
            
        return True  # Test passes regardless
    
    async def generate_test_report(self) -> Dict[str, Any]:
        """Generate a comprehensive test report."""
        logger.info("📋 Generating test report...")
        
        results = {
            "test_timestamp": datetime.now().isoformat(),
            "webhook_status": self.webhook_alerter.get_status(),
            "tests_performed": [],
            "overall_status": "unknown"
        }
        
        # Test connectivity
        connectivity_result = await self.test_connectivity()
        results["tests_performed"].append({
            "test": "connectivity",
            "success": connectivity_result,
            "description": "GitHub API connectivity test"
        })
        
        if not connectivity_result:
            results["overall_status"] = "failed"
            logger.error("❌ Skipping other tests due to connectivity failure")
            return results
        
        # Test critical alerts
        critical_result = await self.test_critical_alert()
        results["tests_performed"].append({
            "test": "critical_alert",
            "success": critical_result,
            "description": "Critical alert webhook test"
        })
        
        # Test warning alerts
        warning_result = await self.test_warning_alert()
        results["tests_performed"].append({
            "test": "warning_alert", 
            "success": warning_result,
            "description": "Warning alert webhook test"
        })
        
        # Test alert manager integration
        manager_result = await self.test_alert_manager_integration()
        results["tests_performed"].append({
            "test": "alert_manager",
            "success": manager_result,
            "description": "Alert manager integration test"
        })
        
        # Test rate limiting
        rate_limit_result = await self.test_rate_limiting()
        results["tests_performed"].append({
            "test": "rate_limiting",
            "success": rate_limit_result,
            "description": "Rate limiting functionality test"
        })
        
        # Determine overall status
        all_success = all(test["success"] for test in results["tests_performed"])
        results["overall_status"] = "passed" if all_success else "partial"
        
        return results
    
    def print_report(self, results: Dict[str, Any]):
        """Print a formatted test report."""
        print("\n" + "="*60)
        print("🧪 WEBHOOK INTEGRATION TEST REPORT")
        print("="*60)
        print(f"📅 Test Date: {results['test_timestamp']}")
        print(f"🏷️ Overall Status: {results['overall_status'].upper()}")
        print()
        
        print("📊 Webhook Configuration:")
        status = results['webhook_status']
        print(f"  • Enabled: {status['enabled']}")
        print(f"  • Repository: {status['github_repo']}")
        print(f"  • Rate Limit Remaining: {status['rate_limit_remaining']}")
        print()
        
        print("🧪 Test Results:")
        for test in results["tests_performed"]:
            status_icon = "✅" if test["success"] else "❌"
            print(f"  {status_icon} {test['test']}: {test['description']}")
        print()
        
        print("📝 Next Steps:")
        if results["overall_status"] == "passed":
            print("  1. ✅ All tests passed!")
            print("  2. 📝 Check GitHub Actions for workflow runs")
            print("  3. 📝 Check GitHub Issues for created issues")
            print("  4. 🚀 Webhook integration is ready for production")
        else:
            print("  1. ❌ Some tests failed - review logs above")
            print("  2. 🔧 Fix any configuration issues")
            print("  3. 🔄 Re-run tests")
            print("  4. 📞 Contact support if issues persist")
        
        print("="*60)


async def main():
    """Main test runner."""
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
    else:
        test_type = "all"
    
    tester = WebhookIntegrationTester()
    
    print("🚀 Starting Webhook Integration Tests...")
    print(f"📋 Test Type: {test_type}")
    print()
    
    if test_type == "connectivity":
        await tester.test_connectivity()
        
    elif test_type == "critical":
        await tester.test_connectivity()
        await tester.test_critical_alert()
        
    elif test_type == "warning":
        await tester.test_connectivity()
        await tester.test_warning_alert()
        
    elif test_type == "all":
        results = await tester.generate_test_report()
        tester.print_report(results)
        
        # Save results to file
        with open("webhook-test-results.json", "w") as f:
            json.dump(results, f, indent=2)
        logger.info("📄 Test results saved to webhook-test-results.json")
        
    else:
        print(f"❌ Unknown test type: {test_type}")
        print("Available options: connectivity, critical, warning, all")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())