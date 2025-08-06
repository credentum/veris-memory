#!/usr/bin/env python3
"""
Comprehensive tests for the MCP performance benchmark script.
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from mcp_performance_benchmark import MCPBenchmark  # noqa: E402


class TestMCPBenchmark:
    """Test class for MCP Benchmark functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.benchmark = MCPBenchmark("http://test:8000/mcp")

    def test_initialization(self):
        """Test benchmark initialization."""
        assert self.benchmark.mcp_url == "http://test:8000/mcp"
        assert "mcp_response_times" in self.benchmark.results
        assert "direct_db_times" in self.benchmark.results
        assert "concurrent_test_results" in self.benchmark.results
        assert "memory_usage" in self.benchmark.results
        assert "timestamp" in self.benchmark.results

    def test_memory_measurement(self):
        """Test memory usage measurement."""
        memory = self.benchmark.measure_memory_usage()

        required_keys = ["rss_mb", "vms_mb", "percent", "available_system_mb"]
        for key in required_keys:
            assert key in memory
            assert isinstance(memory[key], (int, float))
            assert memory[key] >= 0

    def test_report_generation_empty(self):
        """Test report generation with empty results."""
        report = self.benchmark.generate_report()

        assert "MCP PERFORMANCE BENCHMARK REPORT" in report
        assert "INDIVIDUAL OPERATION PERFORMANCE" in report
        assert "CONCURRENT CONNECTIONS PERFORMANCE" in report
        assert "MEMORY USAGE" in report
        assert "SUMMARY AND RECOMMENDATIONS" in report

    def test_report_generation_with_data(self):
        """Test report generation with sample data."""
        # Add sample data
        self.benchmark.results["mcp_response_times"] = [
            {
                "operation": "test_op",
                "count": 10,
                "min_ms": 10.0,
                "max_ms": 50.0,
                "avg_ms": 30.0,
                "median_ms": 25.0,
                "p95_ms": 45.0,
                "meets_target": True,
            }
        ]

        self.benchmark.results["concurrent_test_results"] = [
            {
                "num_connections": 10,
                "successful": 10,
                "failed": 0,
                "avg_total_time_ms": 100.0,
                "p95_total_time_ms": 150.0,
                "memory_delta_mb": 5.0,
            }
        ]

        report = self.benchmark.generate_report()

        # Check that data appears in report
        assert "test_op" in report
        assert "10" in report  # connections
        assert "✅ All operations meet the <50ms response time target" in report

    def test_save_results(self):
        """Test saving results to files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Add some test data
            self.benchmark.results["test_data"] = "test_value"

            json_file, report_file = self.benchmark.save_results(temp_dir)

            # Check files exist
            assert json_file.exists()
            assert report_file.exists()

            # Check JSON content
            with open(json_file) as f:
                data = json.load(f)
                assert data["test_data"] == "test_value"

            # Check report content
            with open(report_file) as f:
                content = f.read()
                assert "MCP PERFORMANCE BENCHMARK REPORT" in content

    @patch("aiohttp.ClientSession")
    @pytest.mark.asyncio
    async def test_measure_mcp_response_time_success(self, mock_session):
        """Test successful MCP response time measurement."""
        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"result": {"success": True}}

        mock_session_instance = AsyncMock()
        mock_session_instance.post.return_value.__aenter__.return_value = mock_response
        mock_session.return_value = mock_session_instance

        response_time = await self.benchmark.measure_mcp_response_time(
            "test_tool", {"arg": "value"}
        )

        assert response_time > 0
        assert isinstance(response_time, float)

    @patch("aiohttp.ClientSession")
    @pytest.mark.asyncio
    async def test_measure_mcp_response_time_failure(self, mock_session):
        """Test failed MCP response time measurement."""
        # Mock failed response
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.json.return_value = {"error": "Server error"}

        mock_session_instance = AsyncMock()
        mock_session_instance.post.return_value.__aenter__.return_value = mock_response
        mock_session.return_value = mock_session_instance

        response_time = await self.benchmark.measure_mcp_response_time(
            "test_tool", {"arg": "value"}
        )

        assert response_time == -1

    @patch("aiohttp.ClientSession")
    @pytest.mark.asyncio
    async def test_measure_mcp_response_time_exception(self, mock_session):
        """Test MCP response time measurement with exception."""
        # Mock exception
        mock_session_instance = AsyncMock()
        mock_session_instance.post.side_effect = Exception("Connection error")
        mock_session.return_value = mock_session_instance

        response_time = await self.benchmark.measure_mcp_response_time(
            "test_tool", {"arg": "value"}
        )

        assert response_time == -1

    @pytest.mark.asyncio
    async def test_measure_direct_db_access_store_context(self):
        """Test direct database access measurement for store_context."""
        with patch("mcp_performance_benchmark.Neo4jInitializer") as mock_neo4j:
            mock_client = AsyncMock()
            mock_neo4j.return_value = mock_client

            response_time = await self.benchmark.measure_direct_db_access("store_context")

            assert response_time > 0
            mock_client.execute_query.assert_called_once()
            mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_measure_direct_db_access_retrieve_context(self):
        """Test direct database access measurement for retrieve_context."""
        with patch("mcp_performance_benchmark.VectorDBInitializer") as mock_qdrant:
            mock_client = AsyncMock()
            mock_qdrant.return_value = mock_client

            response_time = await self.benchmark.measure_direct_db_access("retrieve_context")

            assert response_time > 0
            mock_client.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_measure_direct_db_access_exception(self):
        """Test direct database access measurement with exception."""
        with patch("mcp_performance_benchmark.Neo4jInitializer", side_effect=Exception("DB error")):
            response_time = await self.benchmark.measure_direct_db_access("store_context")
            assert response_time == -1

    @pytest.mark.asyncio
    async def test_concurrent_connections_test(self):
        """Test concurrent connections testing."""
        with patch.object(self.benchmark, "measure_mcp_response_time") as mock_measure:
            # Mock successful responses
            mock_measure.return_value = 25.0  # 25ms response time

            result = await self.benchmark.run_concurrent_connections_test(2)

            assert result["num_connections"] == 2
            assert result["successful"] == 2
            assert result["failed"] == 0
            assert result["avg_total_time_ms"] > 0

    @pytest.mark.asyncio
    async def test_concurrent_connections_test_with_failures(self):
        """Test concurrent connections testing with some failures."""
        with patch.object(self.benchmark, "measure_mcp_response_time") as mock_measure:
            # Mock mixed responses (some failures)
            mock_measure.side_effect = [25.0, -1, 30.0]  # Success, failure, success

            result = await self.benchmark.run_concurrent_connections_test(2)

            assert result["num_connections"] == 2
            assert result["successful"] <= 2
            assert result["failed"] >= 0

    def test_has_required_methods(self):
        """Test that benchmark has all required methods."""
        required_methods = [
            "measure_mcp_response_time",
            "measure_direct_db_access",
            "run_concurrent_connections_test",
            "run_comprehensive_benchmark",
            "generate_report",
            "save_results",
            "measure_memory_usage",
        ]

        for method in required_methods:
            assert hasattr(self.benchmark, method)
            assert callable(getattr(self.benchmark, method))

    def test_results_structure(self):
        """Test that results dictionary has correct structure."""
        required_keys = [
            "mcp_response_times",
            "direct_db_times",
            "concurrent_test_results",
            "memory_usage",
            "timestamp",
        ]

        for key in required_keys:
            assert key in self.benchmark.results

    @pytest.mark.asyncio
    async def test_comprehensive_benchmark_structure(self):
        """Test comprehensive benchmark method structure."""
        # Mock all dependencies to avoid actual network calls
        with (
            patch.object(self.benchmark, "measure_mcp_response_time", return_value=25.0),
            patch.object(self.benchmark, "measure_direct_db_access", return_value=15.0),
            patch.object(self.benchmark, "run_concurrent_connections_test") as mock_concurrent,
        ):
            mock_concurrent.return_value = {
                "num_connections": 1,
                "successful": 1,
                "failed": 0,
                "avg_total_time_ms": 50.0,
                "p95_total_time_ms": 50.0,
                "individual_results": [],
            }

            # Run with minimal parameters to speed up test
            results = await self.benchmark.run_comprehensive_benchmark(
                iterations=2, concurrent_tests=[1]
            )

            assert results is not None
            assert "mcp_response_times" in results
            assert "concurrent_test_results" in results


def run_tests():
    """Run all tests."""
    import pytest

    # Try to use pytest if available
    try:
        pytest.main([__file__, "-v"])
    except ImportError:
        # Fallback to manual test runner
        print("Running comprehensive benchmark tests...")
        print("=" * 60)

        test_class = TestMCPBenchmark()

        # Sync tests
        sync_tests = [
            test_class.test_initialization,
            test_class.test_memory_measurement,
            test_class.test_report_generation_empty,
            test_class.test_report_generation_with_data,
            test_class.test_save_results,
            test_class.test_has_required_methods,
            test_class.test_results_structure,
        ]

        # Async tests
        async_tests = [
            test_class.test_measure_mcp_response_time_success,
            test_class.test_measure_mcp_response_time_failure,
            test_class.test_measure_mcp_response_time_exception,
            test_class.test_measure_direct_db_access_store_context,
            test_class.test_measure_direct_db_access_retrieve_context,
            test_class.test_measure_direct_db_access_exception,
            test_class.test_concurrent_connections_test,
            test_class.test_concurrent_connections_test_with_failures,
            test_class.test_comprehensive_benchmark_structure,
        ]

        passed = 0
        failed = 0

        # Run sync tests
        for test in sync_tests:
            try:
                test_class.setup_method()
                test()
                print(f"✅ {test.__name__}")
                passed += 1
            except Exception as e:
                print(f"❌ {test.__name__}: {e}")
                failed += 1

        # Run async tests
        for test in async_tests:
            try:
                test_class.setup_method()
                asyncio.run(test())
                print(f"✅ {test.__name__}")
                passed += 1
            except Exception as e:
                print(f"❌ {test.__name__}: {e}")
                failed += 1

        print(f"\nResults: {passed} passed, {failed} failed")

        if failed > 0:
            sys.exit(1)
        else:
            print("All tests passed! 🎉")


if __name__ == "__main__":
    run_tests()
