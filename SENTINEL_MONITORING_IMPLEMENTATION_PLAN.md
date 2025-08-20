# Sentinel Monitoring Implementation Plan

## Executive Summary

The Veris Memory Sentinel monitoring system is partially implemented. Only 2 of 10 checks (S1 Health Probes and S2 Golden Fact Recall) are functional. The remaining 8 checks are placeholders, and external alerting (webhook/GitHub) is not implemented. This plan provides a phased approach to complete the Sentinel system with Telegram alerting integration.

## Current State Analysis

### ✅ Working Components
- **S1 Health Probes**: Fully functional, checks /health/live and /health/ready endpoints
- **S2 Golden Fact Recall**: Functional, tests core fact storage/retrieval
- **Infrastructure**: SQLite storage, API endpoints, scheduling system all working
- **Internal Alerting**: Logs and database storage of alerts

### ✅ Recently Completed (Phase 1 & 2)
- **Telegram Alerting**: Fully implemented with deduplication and GitHub issue creation
- **S5 Security Negatives**: ✅ COMPLETE - Comprehensive security testing with 7 test categories
- **S6 Backup/Restore**: ✅ COMPLETE - Full backup validation with 7 validation checks  
- **S8 Capacity Smoke**: ✅ COMPLETE - Performance testing with 6 capacity test categories
- **External Alerting**: ✅ COMPLETE - Telegram bot and GitHub integration working

### ❌ Remaining Placeholder Components
- **S3 Paraphrase Robustness**: Placeholder - needs semantic similarity testing
- **S4 Metrics Wiring**: Placeholder - needs dashboard/analytics validation
- **S7 Config Parity**: Placeholder - needs drift detection
- **S9 Graph Intent**: Placeholder - needs graph query validation
- **S10 Content Pipeline**: Placeholder - needs pipeline monitoring

## Proposed Architecture

### Telegram Bot Integration
```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Sentinel       │────▶│  Alert Manager   │────▶│ Telegram Bot │
│  Checks         │     │  (New Component) │     │  API         │
└─────────────────┘     └──────────────────┘     └──────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │  GitHub API  │
                        └──────────────┘
```

## Implementation Phases

### Phase 1: Telegram Alerting Infrastructure (Week 1)
**Priority: CRITICAL**
**Effort: 3-4 days**

#### 1.1 Telegram Bot Setup
```python
# New file: src/monitoring/sentinel/telegram_alerter.py
class TelegramAlerter:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
    
    async def send_alert(self, message: str, severity: str):
        # Format message with emojis based on severity
        # Send to Telegram API
        # Handle rate limiting
```

#### 1.2 Alert Manager Component
```python
# New file: src/monitoring/sentinel/alert_manager.py
class AlertManager:
    def __init__(self, config: SentinelConfig):
        self.telegram = TelegramAlerter(...)
        self.github = GitHubIssueCreator(...)
        self.deduplication = AlertDeduplicator()
    
    async def process_alert(self, check_result: CheckResult):
        # Deduplicate alerts
        # Route based on severity
        # Format for different channels
        # Track alert history
```

#### 1.3 Configuration Updates
```yaml
# Environment variables
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=yyy
TELEGRAM_ENABLED=true
GITHUB_ISSUES_ENABLED=true
ALERT_DEDUP_WINDOW_MIN=30
```

#### Deliverables:
- ✅ Telegram bot created and configured
- ✅ Alert manager with deduplication
- ✅ Integration with existing runner.py
- ✅ Test alerts working

### Phase 2: Critical Check Implementations (Week 1-2)
**Priority: HIGH**
**Effort: 5-6 days**

#### 2.1 S5 Security Negatives Check
```python
# Critical for security validation
async def run_check(self):
    tests = [
        self._test_unauthorized_access(),
        self._test_invalid_tokens(),
        self._test_rate_limiting(),
        self._test_sql_injection()
    ]
    results = await asyncio.gather(*tests)
    return CheckResult(...)
```

#### 2.2 S8 Capacity Smoke Check
```python
# Critical for performance validation
async def run_check(self):
    # Concurrent request testing
    # Response time validation
    # Memory usage checks
    # Throughput testing
```

#### 2.3 S6 Backup/Restore Check
```python
# Critical for data integrity
async def run_check(self):
    # Test backup creation
    # Validate backup files
    # Test restore capability
    # Verify data consistency
```

#### Deliverables: ✅ COMPLETED
- ✅ S5 Security testing with 7 comprehensive security test categories (authentication, authorization, SQL injection, CORS, input validation, rate limiting, admin endpoints)
- ✅ S8 Capacity testing with 6 performance test categories (concurrent requests, sustained load, system resources, database connections, memory usage, response times)
- ✅ S6 Backup validation with 7 backup validation checks (existence, freshness, integrity, format, restore procedure, storage space, retention policy)
- ✅ Full test coverage with comprehensive unit tests for all checks
- ✅ Alert triggers for failures integrated with existing alert manager

### Phase 3: Monitoring & Observability Checks (Week 2)
**Priority: MEDIUM**
**Effort: 3-4 days**

#### 3.1 S4 Metrics Wiring Check
```python
async def run_check(self):
    # Check Prometheus endpoint
    # Validate metric values
    # Check Grafana dashboards
    # Verify alert rules
```

#### 3.2 S7 Config Parity Check
```python
async def run_check(self):
    # Compare running config vs expected
    # Check environment variables
    # Validate service versions
    # Detect configuration drift
```

#### Deliverables:
- ✅ S4 Metrics validation with dashboard checks
- ✅ S7 Config drift detection
- ✅ Automated alerts for metric failures
- ✅ Configuration baseline management

### Phase 4: Advanced Semantic Checks (Week 3)
**Priority: LOW**
**Effort: 4-5 days**

#### 4.1 S3 Paraphrase Robustness
```python
async def run_check(self):
    paraphrase_sets = [
        ["What is X?", "Tell me about X", "Explain X"],
        ["How to do Y?", "Steps for Y", "Y tutorial"]
    ]
    # Test semantic consistency
    # Measure similarity scores
    # Validate result overlap
```

#### 4.2 S9 Graph Intent Validation
```python
async def run_check(self):
    # Test graph queries
    # Validate relationships
    # Check traversal performance
    # Verify intent classification
```

#### 4.3 S10 Content Pipeline
```python
async def run_check(self):
    # End-to-end content flow
    # Processing latency checks
    # Queue depth monitoring
    # Error rate tracking
```

#### Deliverables:
- ✅ S3 Paraphrase testing with similarity metrics
- ✅ S9 Graph validation with relationship checks
- ✅ S10 Pipeline monitoring with latency tracking
- ✅ Advanced alerting rules

## Alert Severity Levels & Routing

### Critical (Immediate Telegram + GitHub Issue)
- Health checks failing (S1)
- Security breaches detected (S5)
- Data loss/corruption (S6)
- Complete service unavailability

### High (Telegram Alert)
- Performance degradation >50% (S8)
- Core functionality errors (S2)
- Metric collection failures (S4)

### Warning (Telegram Summary)
- Config drift detected (S7)
- Semantic consistency issues (S3)
- Graph query slowness (S9)

### Info (Log Only)
- Successful checks
- Minor latency variations
- Routine status updates

## Telegram Message Formats

### Critical Alert
```
🚨 CRITICAL: Veris Memory Alert
━━━━━━━━━━━━━━━━━━━━━
Check: S5-security-negatives
Status: FAILED ❌
Time: 2025-08-19 23:45:00 UTC

Details:
• Unauthorized access detected
• 15 requests bypassed auth
• Source IP: 192.168.1.100

Action Required: Immediate investigation
GitHub Issue: #74 (auto-created)
━━━━━━━━━━━━━━━━━━━━━
```

### Daily Summary
```
📊 Veris Sentinel Daily Report
━━━━━━━━━━━━━━━━━━━━━
Period: Last 24 hours
Total Checks: 1,440
✅ Passed: 1,420 (98.6%)
❌ Failed: 20 (1.4%)

Top Issues:
1. S8 Capacity: 10 failures
2. S3 Paraphrase: 5 failures
3. S4 Metrics: 5 failures

Avg Response Time: 45ms
Uptime: 99.2%
━━━━━━━━━━━━━━━━━━━━━
```

## Implementation Priority Matrix

| Check | Business Impact | Implementation Effort | Priority | Phase |
|-------|----------------|----------------------|----------|--------|
| Telegram Alerting | Critical | Medium | P0 | 1 |
| S5 Security | Critical | Medium | P0 | 2 |
| S6 Backup | Critical | High | P0 | 2 |
| S8 Capacity | High | Medium | P1 | 2 |
| S4 Metrics | Medium | Low | P1 | 3 |
| S7 Config | Medium | Low | P1 | 3 |
| S3 Paraphrase | Low | High | P2 | 4 |
| S9 Graph | Low | Medium | P2 | 4 |
| S10 Pipeline | Low | Medium | P2 | 4 |

## Success Metrics

### Phase 1 Success
- ✅ Telegram alerts received within 30s of failure
- ✅ Zero duplicate alerts in 30-min window
- ✅ GitHub issues auto-created for critical failures
- ✅ Alert history searchable via API

### Phase 2 Success ✅ ACHIEVED
- ✅ Security vulnerabilities detected automatically - S5 check validates authentication, authorization, SQL injection protection, CORS policies, input validation, rate limiting, and admin endpoint protection
- ✅ Capacity issues identified before user impact - S8 check monitors concurrent request handling, sustained load performance, system resource usage, database connections, memory usage patterns, and response time distribution
- ✅ Backup integrity validated daily - S6 check validates backup existence, freshness, file integrity, format validation, restore procedures, storage space, and retention policy compliance

### Phase 3 Success
- ✅ Metrics collection >99% reliable
- ✅ Config drift detected within 5 minutes
- ✅ Dashboard availability monitoring

### Phase 4 Success
- ✅ Semantic consistency >95%
- ✅ Graph query performance tracked
- ✅ Pipeline bottlenecks identified

## Risk Mitigation

### Technical Risks
- **Telegram API Rate Limits**: Implement local queue and batching
- **Alert Fatigue**: Smart deduplication and severity-based routing
- **False Positives**: Configurable thresholds and confirmation checks

### Operational Risks
- **Bot Token Security**: Use secrets management, rotate regularly
- **Chat ID Privacy**: Environment variable, never in code
- **GitHub API Limits**: Cache issues, batch updates

## Testing Strategy

### Unit Tests
- Each check implementation with mocked dependencies
- Alert manager with various scenarios
- Telegram client with API mocking

### Integration Tests
- End-to-end alert flow
- Database persistence
- API endpoint validation

### Load Tests
- Alert deduplication under high volume
- Telegram rate limit handling
- Concurrent check execution

## Rollout Plan

### Week 1
- Day 1-2: Telegram bot setup and alert manager
- Day 3-4: Integration and testing
- Day 5: Deploy Phase 1 to staging

### Week 2
- Day 1-3: Implement S5, S6, S8 checks
- Day 4: Implement S4, S7 checks
- Day 5: Testing and staging deployment

### Week 3
- Day 1-2: Implement S3 paraphrase check
- Day 3-4: Implement S9, S10 checks
- Day 5: Final testing and production deployment

## Configuration Template

```bash
# .env.sentinel
# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
TELEGRAM_ENABLED=true
TELEGRAM_RATE_LIMIT=30  # messages per minute

# GitHub Integration
GITHUB_TOKEN=your_github_token
GITHUB_REPO=credentum/veris-memory
GITHUB_ISSUES_ENABLED=true
GITHUB_ISSUE_LABELS=sentinel,automated

# Alert Configuration
ALERT_DEDUP_WINDOW_MIN=30
ALERT_THRESHOLD_FAILURES=3
ALERT_SEVERITY_LEVELS=critical,high,warning,info

# Check-specific Configuration
S5_SECURITY_ENABLED=true
S5_SECURITY_TIMEOUT_SEC=30
S8_CAPACITY_CONCURRENT_REQUESTS=50
S8_CAPACITY_TIMEOUT_SEC=60
S6_BACKUP_MAX_AGE_HOURS=24
```

## Next Steps

### ✅ Completed Phases
1. ✅ **Phase 1 Complete**: Telegram alerting with deduplication and GitHub issue creation
2. ✅ **Phase 2 Complete**: Critical checks S5, S6, S8 with comprehensive test coverage

### 🔄 Next Priority: Phase 3
3. **Begin Phase 3 Implementation**: Start with S4 Metrics Wiring and S7 Config Parity checks
4. **Test Integration**: Ensure new checks work with existing alert manager
5. **Performance Validation**: Run load tests on all implemented checks

## Estimated Timeline

- **Phase 1**: 1 week (Telegram alerting)
- **Phase 2**: 1 week (Critical checks)
- **Phase 3**: 3-4 days (Monitoring checks)
- **Phase 4**: 1 week (Advanced checks)
- **Total**: 3-4 weeks for complete implementation

## Budget Estimate

- **Development**: 3 weeks × 1.5 developers = 180 hours
- **Testing**: 40 hours
- **Documentation**: 20 hours
- **Total**: ~240 hours (6 developer-weeks)