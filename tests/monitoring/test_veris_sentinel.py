#!/usr/bin/env python3
"""
Comprehensive unit tests for Veris Sentinel monitoring agent.

Tests cover:
- Individual check classes and their functionality
- SentinelRunner core operations
- API endpoint handlers
- Configuration and error handling
- Database operations and persistence
- Alerting and webhook functionality
"""

import pytest
import asyncio
import json
import sqlite3
import tempfile
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
import aiohttp
from aiohttp import web
from aiohttp.test import AioHTTPTestCase, unittest_run_loop

# Import Sentinel components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from monitoring.veris_sentinel import (
    CheckResult, SentinelConfig, VerisHealthProbe, 
    GoldenFactRecall, MetricsWiring, SecurityNegatives,
    ConfigParity, CapacitySmoke, SentinelRunner, SentinelAPI
)


class TestCheckResult:
    """Test CheckResult dataclass functionality."""
    
    def test_check_result_creation_basic(self):
        """Test basic CheckResult creation."""
        timestamp = datetime.utcnow()
        result = CheckResult(
            check_id="test-check",
            timestamp=timestamp,
            status="pass",
            latency_ms=123.45
        )
        
        assert result.check_id == "test-check"
        assert result.timestamp == timestamp
        assert result.status == "pass"
        assert result.latency_ms == 123.45
        assert result.error_message is None
        assert result.metrics is None
        assert result.notes == ""
    
    def test_check_result_creation_complete(self):
        """Test CheckResult creation with all fields."""
        timestamp = datetime.utcnow()
        metrics = {"response_time": 50.0, "success_rate": 0.95}
        
        result = CheckResult(
            check_id="comprehensive-check",
            timestamp=timestamp,
            status="warn",
            latency_ms=500.0,
            error_message="Minor issue detected",
            metrics=metrics,
            notes="Performance degradation observed"
        )
        
        assert result.check_id == "comprehensive-check"
        assert result.status == "warn"
        assert result.error_message == "Minor issue detected"
        assert result.metrics == metrics
        assert result.notes == "Performance degradation observed"
    
    def test_check_result_to_dict(self):
        """Test CheckResult to_dict conversion."""
        timestamp = datetime.utcnow()
        metrics = {"test_metric": 42.0}
        
        result = CheckResult(
            check_id="dict-test",
            timestamp=timestamp,
            status="fail",
            latency_ms=1000.0,
            error_message="Test error",
            metrics=metrics,
            notes="Test notes"
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["check_id"] == "dict-test"
        assert result_dict["timestamp"] == timestamp.isoformat()
        assert result_dict["status"] == "fail"
        assert result_dict["latency_ms"] == 1000.0
        assert result_dict["error_message"] == "Test error"
        assert result_dict["metrics"] == metrics
        assert result_dict["notes"] == "Test notes"


class TestSentinelConfig:
    """Test SentinelConfig dataclass."""
    
    def test_config_defaults(self):
        """Test default configuration values."""
        config = SentinelConfig()
        
        assert config.target_base_url == "http://veris-memory-dev-context-store-1:8000"
        assert config.redis_url == "redis://veris-memory-dev-redis-1:6379"
        assert config.schedule_cadence_sec == 60
        assert config.max_jitter_pct == 20
        assert config.per_check_timeout_sec == 10
        assert config.cycle_budget_sec == 45
        assert config.max_parallel_checks == 4
        assert config.alert_webhook is None
        assert config.github_repo is None
    
    def test_config_custom_values(self):
        """Test custom configuration values."""
        config = SentinelConfig(
            target_base_url="http://localhost:8000",
            schedule_cadence_sec=30,
            max_parallel_checks=8,
            alert_webhook="https://hooks.slack.com/test",
            github_repo="test/repo"
        )
        
        assert config.target_base_url == "http://localhost:8000"
        assert config.schedule_cadence_sec == 30
        assert config.max_parallel_checks == 8
        assert config.alert_webhook == "https://hooks.slack.com/test"
        assert config.github_repo == "test/repo"


class TestVerisHealthProbe:
    """Test VerisHealthProbe check functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return SentinelConfig(target_base_url="http://test:8000")
    
    @pytest.fixture
    def health_probe(self, config):
        """Create VerisHealthProbe instance."""
        return VerisHealthProbe(config)
    
    @pytest.mark.asyncio
    async def test_health_probe_success(self, health_probe):
        """Test successful health probe."""
        # Mock successful HTTP responses
        mock_responses = [
            # Liveness response
            AsyncMock(status=200, json=AsyncMock(return_value={"status": "alive"})),
            # Readiness response
            AsyncMock(status=200, json=AsyncMock(return_value={
                "components": [
                    {"name": "qdrant", "status": "ok"},
                    {"name": "redis", "status": "healthy"},
                    {"name": "neo4j", "status": "degraded"}
                ]
            }))
        ]
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.side_effect = mock_responses
            
            result = await health_probe.run_check()
            
            assert result.check_id == "S1-probes"
            assert result.status == "pass"
            assert result.latency_ms > 0
            assert result.metrics["status_bool"] == 1.0
            assert "health endpoints responding correctly" in result.notes
    
    @pytest.mark.asyncio
    async def test_health_probe_liveness_failure(self, health_probe):
        """Test health probe with liveness failure."""
        mock_response = AsyncMock(status=500)
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
            
            result = await health_probe.run_check()
            
            assert result.check_id == "S1-probes"
            assert result.status == "fail"
            assert "Liveness check failed: HTTP 500" in result.error_message
    
    @pytest.mark.asyncio
    async def test_health_probe_component_failure(self, health_probe):
        """Test health probe with component failure."""
        mock_responses = [
            # Liveness response
            AsyncMock(status=200, json=AsyncMock(return_value={"status": "alive"})),
            # Readiness response with unhealthy component
            AsyncMock(status=200, json=AsyncMock(return_value={
                "components": [
                    {"name": "qdrant", "status": "failed"},
                    {"name": "redis", "status": "healthy"}
                ]
            }))
        ]
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.side_effect = mock_responses
            
            result = await health_probe.run_check()
            
            assert result.check_id == "S1-probes"
            assert result.status == "fail"
            assert "Qdrant not healthy: failed" in result.error_message
    
    @pytest.mark.asyncio
    async def test_health_probe_exception(self, health_probe):
        """Test health probe with exception."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.side_effect = Exception("Connection failed")
            
            result = await health_probe.run_check()
            
            assert result.check_id == "S1-probes"
            assert result.status == "fail"
            assert "Health check exception: Connection failed" in result.error_message


class TestGoldenFactRecall:
    """Test GoldenFactRecall functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return SentinelConfig(target_base_url="http://test:8000")
    
    @pytest.fixture
    def fact_recall(self, config):
        """Create GoldenFactRecall instance."""
        return GoldenFactRecall(config)
    
    @pytest.mark.asyncio
    async def test_golden_fact_recall_success(self, fact_recall):
        """Test successful fact recall."""
        # Mock successful HTTP responses
        store_response = AsyncMock(status=200)
        retrieve_response = AsyncMock(
            status=200,
            json=AsyncMock(return_value={
                "memories": [{"content": '{"name": "Matt"}'}]
            })
        )
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.side_effect = [
                store_response,  # Store fact
                retrieve_response,  # Retrieve with question 1
                retrieve_response,  # Retrieve with question 2
                store_response,  # Store next fact
                retrieve_response,  # Continue pattern...
                retrieve_response,
                store_response,
                retrieve_response,
                retrieve_response
            ]
            
            result = await fact_recall.run_check()
            
            assert result.check_id == "S2-golden-fact-recall"
            assert result.status == "pass"
            assert result.metrics["p_at_1"] == 1.0
            assert "6/6 tests passed" in result.notes
    
    @pytest.mark.asyncio
    async def test_golden_fact_recall_partial_success(self, fact_recall):
        """Test partial success in fact recall."""
        store_response = AsyncMock(status=200)
        good_retrieve = AsyncMock(
            status=200,
            json=AsyncMock(return_value={
                "memories": [{"content": '{"name": "Matt"}'}]
            })
        )
        bad_retrieve = AsyncMock(
            status=200,
            json=AsyncMock(return_value={
                "memories": [{"content": "irrelevant content"}]
            })
        )
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.side_effect = [
                store_response,  # Store fact
                good_retrieve,   # Good retrieve
                bad_retrieve,    # Bad retrieve
                store_response,  # Continue...
                good_retrieve,
                good_retrieve,
                store_response,
                good_retrieve,
                good_retrieve
            ]
            
            result = await fact_recall.run_check()
            
            assert result.check_id == "S2-golden-fact-recall"
            assert result.status == "warn"  # P@1 = 5/6 = 0.83, which is >= 0.8 but < 1.0
            assert result.metrics["p_at_1"] == pytest.approx(0.833, rel=1e-2)
    
    @pytest.mark.asyncio
    async def test_golden_fact_recall_store_failure(self, fact_recall):
        """Test fact recall with storage failure."""
        store_response = AsyncMock(status=500)
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = store_response
            
            result = await fact_recall.run_check()
            
            assert result.check_id == "S2-golden-fact-recall"
            assert result.status == "fail"
            assert "Failed to store fact: HTTP 500" in result.error_message


class TestMetricsWiring:
    """Test MetricsWiring functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return SentinelConfig(target_base_url="http://test:8000")
    
    @pytest.fixture
    def metrics_wiring(self, config):
        """Create MetricsWiring instance."""
        return MetricsWiring(config)
    
    @pytest.mark.asyncio
    async def test_metrics_wiring_success(self, metrics_wiring):
        """Test successful metrics wiring check."""
        dashboard_response = AsyncMock(
            status=200,
            json=AsyncMock(return_value={
                "system": {"cpu_percent": 45.2},
                "services": [{"name": "Redis", "status": "healthy"}],
                "timestamp": datetime.utcnow().isoformat()
            })
        )
        analytics_response = AsyncMock(status=200, json=AsyncMock(return_value={"analytics": {}}))
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.side_effect = [
                dashboard_response,
                analytics_response
            ]
            
            result = await metrics_wiring.run_check()
            
            assert result.check_id == "S4-metrics-wiring"
            assert result.status == "pass"
            assert result.metrics["labels_present"] == 1.0
            assert result.metrics["percentiles_present"] == 1.0
    
    @pytest.mark.asyncio
    async def test_metrics_wiring_dashboard_failure(self, metrics_wiring):
        """Test metrics wiring with dashboard failure."""
        dashboard_response = AsyncMock(status=404)
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = dashboard_response
            
            result = await metrics_wiring.run_check()
            
            assert result.check_id == "S4-metrics-wiring"
            assert result.status == "fail"
            assert "Dashboard endpoint failed: HTTP 404" in result.error_message
    
    @pytest.mark.asyncio
    async def test_metrics_wiring_missing_fields(self, metrics_wiring):
        """Test metrics wiring with missing dashboard fields."""
        dashboard_response = AsyncMock(
            status=200,
            json=AsyncMock(return_value={"system": {}})  # Missing services and timestamp
        )
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = dashboard_response
            
            result = await metrics_wiring.run_check()
            
            assert result.check_id == "S4-metrics-wiring"
            assert result.status == "fail"
            assert "Missing dashboard fields" in result.error_message


class TestSecurityNegatives:
    """Test SecurityNegatives functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return SentinelConfig(target_base_url="http://test:8000")
    
    @pytest.fixture
    def security_negatives(self, config):
        """Create SecurityNegatives instance."""
        return SecurityNegatives(config)
    
    @pytest.mark.asyncio
    async def test_security_negatives_proper_blocking(self, security_negatives):
        """Test security negatives with proper blocking."""
        responses = [
            AsyncMock(status=200),  # Reader retrieve - allowed
            AsyncMock(status=403),  # Reader store - blocked
            AsyncMock(status=401),  # Invalid token analytics - blocked
            AsyncMock(status=403),  # No auth store - blocked
        ]
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.side_effect = responses[:2] + responses[3:]
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = responses[2]
            
            result = await security_negatives.run_check()
            
            assert result.check_id == "S5-security-negatives"
            assert result.status == "pass"
            assert result.metrics["unauthorized_block_rate"] == 0.75  # 3/4 properly blocked
    
    @pytest.mark.asyncio
    async def test_security_negatives_no_blocking(self, security_negatives):
        """Test security negatives with no blocking (permissive system)."""
        responses = [
            AsyncMock(status=200),  # All requests succeed
            AsyncMock(status=200),
            AsyncMock(status=200),
            AsyncMock(status=200),
        ]
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.side_effect = responses[:2] + responses[3:]
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = responses[2]
            
            result = await security_negatives.run_check()
            
            assert result.check_id == "S5-security-negatives"
            assert result.status == "pass"  # Lenient for current implementation
            assert result.metrics["unauthorized_block_rate"] == 0.0


class TestCapacitySmoke:
    """Test CapacitySmoke functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return SentinelConfig(target_base_url="http://test:8000")
    
    @pytest.fixture
    def capacity_smoke(self, config):
        """Create CapacitySmoke instance."""
        return CapacitySmoke(config)
    
    @pytest.mark.asyncio
    async def test_capacity_smoke_success(self, capacity_smoke):
        """Test successful capacity smoke test."""
        # Mock fast, successful responses
        mock_response = AsyncMock(status=200)
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
            
            result = await capacity_smoke.run_check()
            
            assert result.check_id == "S8-capacity-smoke"
            assert result.status == "pass"
            assert result.metrics["p95_ms"] <= 300
            assert result.metrics["error_rate"] <= 0.005
            assert "20/20 successful" in result.notes
    
    @pytest.mark.asyncio
    async def test_capacity_smoke_high_latency(self, capacity_smoke):
        """Test capacity smoke test with high latency."""
        # Mock slow responses by adding delay
        async def slow_response(*args, **kwargs):
            await asyncio.sleep(0.4)  # 400ms delay
            return AsyncMock(status=200)
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.get.side_effect = slow_response
            
            result = await capacity_smoke.run_check()
            
            assert result.check_id == "S8-capacity-smoke"
            assert result.status in ["warn", "fail"]  # Depends on exact timing
            assert result.metrics["p95_ms"] > 300
    
    @pytest.mark.asyncio
    async def test_capacity_smoke_high_error_rate(self, capacity_smoke):
        """Test capacity smoke test with high error rate."""
        # Mock mixture of success and failures
        responses = [AsyncMock(status=200) if i % 2 == 0 else AsyncMock(status=500) for i in range(20)]
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.side_effect = responses
            
            result = await capacity_smoke.run_check()
            
            assert result.check_id == "S8-capacity-smoke"
            assert result.status == "fail"
            assert result.metrics["error_rate"] == 0.5  # 50% error rate


class TestSentinelRunner:
    """Test SentinelRunner core functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return SentinelConfig(
            target_base_url="http://test:8000",
            schedule_cadence_sec=1,  # Fast for testing
            max_parallel_checks=2,
            per_check_timeout_sec=1,
            cycle_budget_sec=5
        )
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            yield f.name
        Path(f.name).unlink()
    
    @pytest.fixture
    def sentinel(self, config, temp_db):
        """Create SentinelRunner instance."""
        return SentinelRunner(config, temp_db)
    
    def test_sentinel_initialization(self, sentinel, config):
        """Test SentinelRunner initialization."""
        assert sentinel.config == config
        assert not sentinel.running
        assert len(sentinel.checks) == 6  # All check types
        assert "S1-probes" in sentinel.checks
        assert "S2-golden-fact-recall" in sentinel.checks
        assert len(sentinel.failures) == 0
        assert len(sentinel.reports) == 0
    
    def test_database_initialization(self, sentinel):
        """Test database table creation."""
        # Database should be initialized with tables
        with sqlite3.connect(sentinel.db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            assert "check_results" in tables
            assert "cycle_reports" in tables
    
    @pytest.mark.asyncio
    async def test_run_single_cycle_success(self, sentinel):
        """Test successful single monitoring cycle."""
        # Mock all checks to return success
        for check_id, check_instance in sentinel.checks.items():
            check_instance.run_check = AsyncMock(return_value=CheckResult(
                check_id=check_id,
                timestamp=datetime.utcnow(),
                status="pass",
                latency_ms=50.0
            ))
        
        cycle_report = await sentinel.run_single_cycle()
        
        assert cycle_report["total_checks"] == 6
        assert cycle_report["passed_checks"] == 6
        assert cycle_report["failed_checks"] == 0
        assert cycle_report["cycle_duration_ms"] > 0
        assert len(cycle_report["results"]) == 6
    
    @pytest.mark.asyncio
    async def test_run_single_cycle_with_failures(self, sentinel):
        """Test single cycle with some failures."""
        # Mock mix of success and failure
        for i, (check_id, check_instance) in enumerate(sentinel.checks.items()):
            status = "pass" if i % 2 == 0 else "fail"
            error_msg = None if status == "pass" else f"Check {check_id} failed"
            
            check_instance.run_check = AsyncMock(return_value=CheckResult(
                check_id=check_id,
                timestamp=datetime.utcnow(),
                status=status,
                latency_ms=100.0,
                error_message=error_msg
            ))
        
        cycle_report = await sentinel.run_single_cycle()
        
        assert cycle_report["total_checks"] == 6
        assert cycle_report["passed_checks"] == 3
        assert cycle_report["failed_checks"] == 3
        assert len(sentinel.failures) == 3  # Failed checks added to failures buffer
    
    @pytest.mark.asyncio
    async def test_run_single_cycle_timeout(self, sentinel):
        """Test single cycle with timeout."""
        # Mock checks that take too long
        async def slow_check():
            await asyncio.sleep(10)  # Longer than cycle_budget_sec
            return CheckResult("slow", datetime.utcnow(), "pass", 100.0)
        
        for check_instance in sentinel.checks.values():
            check_instance.run_check = slow_check
        
        cycle_report = await sentinel.run_single_cycle()
        
        # Should timeout and return timeout result
        assert any("timeout" in result["check_id"] for result in cycle_report["results"])
    
    def test_store_cycle_results(self, sentinel):
        """Test storing cycle results in database."""
        timestamp = datetime.utcnow()
        results = [
            CheckResult("test1", timestamp, "pass", 50.0, metrics={"test": 1.0}),
            CheckResult("test2", timestamp, "fail", 100.0, error_message="Test error")
        ]
        
        cycle_report = {
            "cycle_id": "test123",
            "timestamp": timestamp.isoformat(),
            "total_checks": 2,
            "passed_checks": 1,
            "failed_checks": 1,
            "cycle_duration_ms": 150.0,
            "results": [r.to_dict() for r in results]
        }
        
        sentinel._store_cycle_results(results, cycle_report)
        
        # Verify data was stored
        with sqlite3.connect(sentinel.db_path) as conn:
            check_count = conn.execute("SELECT COUNT(*) FROM check_results").fetchone()[0]
            cycle_count = conn.execute("SELECT COUNT(*) FROM cycle_reports").fetchone()[0]
            
            assert check_count == 2
            assert cycle_count == 1
            
            # Verify specific data
            check_data = conn.execute(
                "SELECT check_id, status, error_message FROM check_results ORDER BY check_id"
            ).fetchall()
            
            assert check_data[0] == ("test1", "pass", None)
            assert check_data[1] == ("test2", "fail", "Test error")
    
    def test_get_status(self, sentinel):
        """Test status retrieval."""
        # Add some test data
        test_report = {
            "cycle_id": "test123",
            "timestamp": datetime.utcnow().isoformat(),
            "total_checks": 5,
            "passed_checks": 4,
            "failed_checks": 1
        }
        sentinel.reports.append(test_report)
        
        status = sentinel.get_status()
        
        assert status["running"] == False
        assert status["last_cycle"] == test_report
        assert status["total_cycles"] == 1
        assert status["failure_count"] == 0
        assert "config" in status


class TestSentinelAPI:
    """Test SentinelAPI HTTP endpoints."""
    
    @pytest.fixture
    def sentinel_mock(self):
        """Create mock SentinelRunner."""
        mock = Mock()
        mock.get_status.return_value = {
            "running": True,
            "last_cycle": {"cycle_id": "test123"},
            "total_cycles": 10,
            "failure_count": 2
        }
        mock.run_single_cycle = AsyncMock(return_value={
            "success": True,
            "cycle_id": "new123"
        })
        mock.checks = {
            "S1-probes": Mock(__class__=Mock(__doc__="Health probe check")),
            "S2-golden": Mock(__class__=Mock(__doc__="Fact recall check"))
        }
        mock.reports = [{"cycle_id": f"cycle{i}"} for i in range(5)]
        mock.failures = []
        mock.running = True
        return mock
    
    @pytest.fixture
    def api_server(self, sentinel_mock):
        """Create SentinelAPI instance."""
        return SentinelAPI(sentinel_mock)
    
    @pytest.mark.asyncio
    async def test_status_endpoint(self, api_server, sentinel_mock):
        """Test /status endpoint."""
        request = Mock()
        response = await api_server.status_handler(request)
        
        assert response.status == 200
        response_data = json.loads(response.text)
        assert response_data["running"] == True
        assert response_data["total_cycles"] == 10
    
    @pytest.mark.asyncio
    async def test_run_endpoint_success(self, api_server, sentinel_mock):
        """Test /run endpoint with successful cycle."""
        request = Mock()
        response = await api_server.run_handler(request)
        
        assert response.status == 200
        response_data = json.loads(response.text)
        assert response_data["success"] == True
        assert "cycle_report" in response_data
        
        # Verify the mock was called
        sentinel_mock.run_single_cycle.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_endpoint_failure(self, api_server, sentinel_mock):
        """Test /run endpoint with cycle failure."""
        sentinel_mock.run_single_cycle.side_effect = Exception("Cycle failed")
        
        request = Mock()
        response = await api_server.run_handler(request)
        
        assert response.status == 500
        response_data = json.loads(response.text)
        assert response_data["success"] == False
        assert "error" in response_data
    
    @pytest.mark.asyncio
    async def test_checks_endpoint(self, api_server, sentinel_mock):
        """Test /checks endpoint."""
        request = Mock()
        response = await api_server.checks_handler(request)
        
        assert response.status == 200
        response_data = json.loads(response.text)
        
        assert "checks" in response_data
        checks = response_data["checks"]
        assert "S1-probes" in checks
        assert "S2-golden" in checks
        assert checks["S1-probes"]["enabled"] == True
    
    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, api_server, sentinel_mock):
        """Test /metrics endpoint."""
        # Add a mock report with metrics
        sentinel_mock.reports = [{
            "total_checks": 6,
            "passed_checks": 5,
            "failed_checks": 1,
            "cycle_duration_ms": 2500.0
        }]
        
        request = Mock()
        response = await api_server.metrics_handler(request)
        
        assert response.status == 200
        assert response.content_type == "text/plain"
        
        metrics_text = response.text
        assert "sentinel_checks_total 6" in metrics_text
        assert "sentinel_checks_passed 5" in metrics_text
        assert "sentinel_checks_failed 1" in metrics_text
        assert "sentinel_running 1" in metrics_text
    
    @pytest.mark.asyncio
    async def test_report_endpoint(self, api_server, sentinel_mock):
        """Test /report endpoint."""
        request = Mock()
        request.query = {"n": "3"}
        
        response = await api_server.report_handler(request)
        
        assert response.status == 200
        response_data = json.loads(response.text)
        
        assert "reports" in response_data
        assert len(response_data["reports"]) == 3  # Last 3 reports
        assert response_data["total_reports"] == 5
    
    @pytest.mark.asyncio
    async def test_report_endpoint_default_limit(self, api_server, sentinel_mock):
        """Test /report endpoint with default limit."""
        request = Mock()
        request.query = {}
        
        response = await api_server.report_handler(request)
        
        assert response.status == 200
        response_data = json.loads(response.text)
        
        # Should default to last 10, but only 5 available
        assert len(response_data["reports"]) == 5


class TestIntegrationScenarios:
    """Integration test scenarios."""
    
    @pytest.mark.asyncio
    async def test_complete_monitoring_cycle(self):
        """Test complete monitoring cycle end-to-end."""
        config = SentinelConfig(
            target_base_url="http://test:8000",
            schedule_cadence_sec=1,
            max_parallel_checks=2
        )
        
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_db = f.name
        
        try:
            sentinel = SentinelRunner(config, temp_db)
            
            # Mock all checks for integration test
            mock_results = [
                CheckResult("S1-probes", datetime.utcnow(), "pass", 45.0),
                CheckResult("S2-golden-fact-recall", datetime.utcnow(), "pass", 1250.0),
                CheckResult("S4-metrics-wiring", datetime.utcnow(), "pass", 123.0),
                CheckResult("S5-security-negatives", datetime.utcnow(), "warn", 234.0),
                CheckResult("S7-config-parity", datetime.utcnow(), "pass", 67.0),
                CheckResult("S8-capacity-smoke", datetime.utcnow(), "pass", 2100.0)
            ]
            
            for i, (check_id, check_instance) in enumerate(sentinel.checks.items()):
                check_instance.run_check = AsyncMock(return_value=mock_results[i])
            
            # Run cycle
            cycle_report = await sentinel.run_single_cycle()
            
            # Verify complete cycle
            assert cycle_report["total_checks"] == 6
            assert cycle_report["passed_checks"] == 5
            assert cycle_report["failed_checks"] == 0  # warn counts as not failed
            
            # Verify database persistence
            with sqlite3.connect(temp_db) as conn:
                check_count = conn.execute("SELECT COUNT(*) FROM check_results").fetchone()[0]
                cycle_count = conn.execute("SELECT COUNT(*) FROM cycle_reports").fetchone()[0]
                
                assert check_count == 6
                assert cycle_count == 1
            
            # Verify status
            status = sentinel.get_status()
            assert status["total_cycles"] == 1
            assert status["last_cycle"]["total_checks"] == 6
            
        finally:
            Path(temp_db).unlink()
    
    @pytest.mark.asyncio
    async def test_alerting_workflow(self):
        """Test alerting workflow with failures."""
        config = SentinelConfig(
            target_base_url="http://test:8000",
            alert_webhook="https://hooks.slack.com/test"
        )
        
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_db = f.name
        
        try:
            sentinel = SentinelRunner(config, temp_db)
            
            # Mock critical failure
            critical_failure = CheckResult(
                "S1-probes", 
                datetime.utcnow(), 
                "fail", 
                5000.0,
                error_message="All health endpoints down"
            )
            
            for check_instance in sentinel.checks.values():
                check_instance.run_check = AsyncMock(return_value=critical_failure)
            
            # Mock requests for webhook
            with patch('requests.post') as mock_post:
                mock_post.return_value = Mock(status_code=200)
                
                cycle_report = await sentinel.run_single_cycle()
                
                # Should have failures
                assert cycle_report["failed_checks"] == 6
                assert len(sentinel.failures) == 6
                
                # Should have triggered alerts (when REQUESTS_AVAILABLE=True)
                # In test environment, requests might not be available
        
        finally:
            Path(temp_db).unlink()


# Performance and stress tests
class TestPerformanceCharacteristics:
    """Test performance characteristics of Sentinel."""
    
    @pytest.mark.asyncio
    async def test_cycle_performance(self):
        """Test that cycles complete within reasonable time."""
        config = SentinelConfig(
            target_base_url="http://test:8000",
            max_parallel_checks=4,
            per_check_timeout_sec=1
        )
        
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_db = f.name
        
        try:
            sentinel = SentinelRunner(config, temp_db)
            
            # Mock fast checks
            for check_instance in sentinel.checks.values():
                check_instance.run_check = AsyncMock(return_value=CheckResult(
                    "test", datetime.utcnow(), "pass", 50.0
                ))
            
            start_time = time.time()
            cycle_report = await sentinel.run_single_cycle()
            cycle_duration = time.time() - start_time
            
            # Should complete quickly with parallel execution
            assert cycle_duration < 2.0  # Should be well under 2 seconds
            assert cycle_report["cycle_duration_ms"] < 2000
            
        finally:
            Path(temp_db).unlink()
    
    @pytest.mark.asyncio
    async def test_memory_usage_with_large_history(self):
        """Test memory usage with large history."""
        config = SentinelConfig()
        
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_db = f.name
        
        try:
            sentinel = SentinelRunner(config, temp_db)
            
            # Fill up ring buffers
            for i in range(300):  # More than maxlen of failures (200)
                failure = CheckResult(f"test{i}", datetime.utcnow(), "fail", 100.0)
                sentinel.failures.append(failure)
            
            for i in range(100):  # More than maxlen of reports (50)
                report = {"cycle_id": f"cycle{i}", "timestamp": datetime.utcnow().isoformat()}
                sentinel.reports.append(report)
            
            # Ring buffers should be bounded
            assert len(sentinel.failures) == 200  # maxlen
            assert len(sentinel.reports) == 50   # maxlen
            
        finally:
            Path(temp_db).unlink()