#!/usr/bin/env python3
"""
Simple Dashboard Test Script
Tests just the core dashboard functionality without external dependencies.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from monitoring.dashboard import UnifiedDashboard


async def test_core_dashboard():
    """Test core dashboard functionality."""
    print("🎯 TESTING CORE DASHBOARD FUNCTIONALITY")
    print("=" * 50)
    
    try:
        # Initialize dashboard
        print("1. Initializing UnifiedDashboard...")
        dashboard = UnifiedDashboard()
        
        # Test metrics collection
        print("2. Testing metrics collection...")
        metrics = await dashboard.collect_all_metrics(force_refresh=True)
        
        print(f"   ✅ Collected {len(metrics)} metric categories")
        print(f"   📊 Categories: {', '.join(metrics.keys())}")
        
        # Test JSON output
        print("3. Testing JSON output...")
        json_output = dashboard.generate_json_dashboard(metrics)
        print(f"   ✅ Generated {len(json_output)} character JSON output")
        
        # Test ASCII output  
        print("4. Testing ASCII output...")
        ascii_output = dashboard.generate_ascii_dashboard(metrics)
        print(f"   ✅ Generated {len(ascii_output)} character ASCII output")
        
        # Show ASCII dashboard
        print("\n5. Sample ASCII Dashboard:")
        print("-" * 50)
        print(ascii_output)
        print("-" * 50)
        
        # Test system metrics specifically
        print("6. System Metrics Details:")
        system_metrics = metrics.get('system', {})
        for key, value in system_metrics.items():
            print(f"   {key}: {value}")
        
        # Cleanup
        await dashboard.shutdown()
        
        print("\n✅ Core dashboard test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Dashboard test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run the dashboard test."""
    try:
        success = asyncio.run(test_core_dashboard())
        if success:
            print("\n🎉 All tests passed! Dashboard is functional.")
            return 0
        else:
            print("\n💥 Tests failed. Check output above.")
            return 1
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
        return 130
    except Exception as e:
        print(f"\n💥 Test crashed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())