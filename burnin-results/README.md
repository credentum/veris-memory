# Burn-In Test Results

This directory contains historical burn-in test results for the Veris Memory deployment.

## Latest Results

### ✅ Server Burn-In Test (2025-08-11 18:52:29)

**Status**: PASSED

- **File**: [`server-burnin-report.json`](server-burnin-report.json)
- **Tag**: `burnin-stable-20250811-185229`
- **Performance**: p95 = 1.4ms baseline, 2.4ms under load
- **Stability**: 5/5 cycles passed
- **Error Rate**: 0%

### Key Metrics from Latest Test

```json
{
  "status": "PASSED",
  "baseline": {
    "p50_ms": 1.1,
    "p95_ms": 1.4,
    "p99_ms": 2.2
  },
  "stable_cycles": 5,
  "tag": "burnin-stable-20250811-185229"
}
```

## Test History

| Date | Status | Cycles | p95 (ms) | Report |
|------|--------|--------|----------|--------|
| 2025-08-11 18:52 | ✅ PASSED | 5/5 | 1.4 | [server-burnin-report.json](server-burnin-report.json) |
| 2025-08-11 16:47 | ✅ PASSED | 5/5 | 95 | [COMPREHENSIVE-BURNIN-REPORT.json](COMPREHENSIVE-BURNIN-REPORT.json) |
| 2025-08-11 16:26 | ✅ PASSED | 3/3 | 95 | [BURNIN-REPORT.md](BURNIN-REPORT.md) |

## Directory Structure

```
burnin-results/
├── README.md                           # This file
├── server-burnin-report.json          # Latest production test
├── COMPREHENSIVE-BURNIN-REPORT.json   # Detailed test report
├── BURNIN-REPORT.md                   # Initial test summary
├── comprehensive/                     # Comprehensive test artifacts
│   └── *.json                         # Cycle-by-cycle results
└── run-20250811-162502/              # Historical run data
    └── *.json                         # Test snapshots
```

## How to Run New Tests

1. **Quick Test** (Recommended):
   ```bash
   ssh hetzner-server "cd /opt/veris-memory && python3 server_burnin.py"
   ```

2. **Fetch Results**:
   ```bash
   scp hetzner-server:/opt/veris-memory/burnin-report.json ./new-burnin-report.json
   ```

3. **Archive Results**:
   - Save JSON report with timestamp
   - Update this README with new entry
   - Tag git if test passes

## Understanding Results

### Success Criteria

- **Status**: "PASSED" indicates all cycles succeeded
- **Stable Cycles**: Must be ≥ 5 for full pass
- **p95 Latency**: Should be < 10ms
- **Error Rate**: Should be < 0.5%

### Performance Benchmarks

| Metric | Excellent | Good | Acceptable | Warning |
|--------|-----------|------|------------|---------|
| p95 Latency | < 3ms | < 5ms | < 10ms | > 10ms |
| Error Rate | 0% | < 0.1% | < 0.5% | > 0.5% |
| Stability | 5/5 cycles | 4/5 | 3/5 | < 3/5 |

## Notes

- All tests run directly on the Hetzner server (135.181.4.118)
- Tests use localhost connections (not external IP)
- Each test validates Qdrant configuration (384 dims, Cosine)
- Service restart resilience is tested every 4th cycle

---

*Last Updated: 2025-08-11*