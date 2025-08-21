# Security Documentation for Phase 3 Automation

## 🔐 Claude API Key Management

### Overview
Phase 3 automation requires secure management of Claude API keys for emergency session authentication. This document outlines secure practices for key management, rotation, and access control.

### Key Storage Requirements

#### GitHub Secrets Configuration
```bash
# Required secrets in GitHub repository settings
CLAUDE_API_KEY=<your_claude_api_key>
HETZNER_HOST=<production_server_host>
HETZNER_USER=<ssh_username>
HETZNER_SSH_KEY=<ssh_private_key>
```

#### Security Standards
- **Encryption**: All keys stored encrypted in GitHub Secrets
- **Access Control**: Limited to repository administrators
- **Audit Trail**: All secret access logged in GitHub audit logs
- **Rotation**: Keys rotated every 90 days minimum

### Key Rotation Procedures

#### Monthly Health Check
```bash
# 1. Verify key functionality
curl -H "Authorization: Bearer ${CLAUDE_API_KEY}" \
     -H "Content-Type: application/json" \
     https://api.anthropic.com/v1/messages

# 2. Check expiration status
# (Keys should be rotated before expiration)

# 3. Test emergency session functionality
python scripts/sentinel/test_phase3_components.py
```

#### Key Rotation Process
1. **Generate New Key**: Create new Claude API key in Anthropic console
2. **Test New Key**: Verify functionality in staging environment
3. **Update GitHub Secret**: Replace CLAUDE_API_KEY in repository settings
4. **Verify Deployment**: Test emergency session with new key
5. **Revoke Old Key**: Disable old key in Anthropic console
6. **Document Rotation**: Log rotation in security audit trail

#### Emergency Key Revocation
```bash
# If key compromise is suspected:
# 1. Immediately revoke in Anthropic console
# 2. Update GitHub secret with new key
# 3. Force redeploy all automation
# 4. Audit all recent API usage
```

### Access Policies

#### Authorized Personnel
- **Repository Administrators**: Full access to all secrets
- **Security Team**: Read access to audit logs
- **Emergency Responders**: Limited access during incidents

#### Usage Restrictions
- Keys ONLY used for emergency automation
- No manual/interactive API usage with automation keys
- Separate keys for development/testing environments

## 🔄 Rollback Procedures

### Overview
Phase 3 automation includes comprehensive rollback capabilities for safe operation. All changes are tracked and can be automatically or manually reversed.

### Automated Rollback Features

#### SSH Security Manager Rollback
```python
# Automatic rollback on validation failure
if not validation_result["success"]:
    await self._rollback_fix(fix)
    results["failed"].append({
        "error": "Validation failed",
        "validation_result": validation_result
    })
```

#### Fix Application Rollback
```python
# Each fix includes rollback commands
fix = {
    "commands": ["systemctl restart nginx"],
    "validation_commands": ["systemctl is-active nginx"],
    "rollback_commands": ["systemctl stop nginx; systemctl start nginx"]
}
```

### Manual Rollback Procedures

#### Emergency Session Rollback
```bash
# 1. Access production server
ssh -i ${HETZNER_SSH_KEY} ${HETZNER_USER}@${HETZNER_HOST}

# 2. Check recent automated changes
grep "AUTOMATION" /var/log/audit.log | tail -20

# 3. Identify changes to rollback
journalctl --since "1 hour ago" | grep "systemctl\|docker\|ufw"

# 4. Execute manual rollback
systemctl stop <service>
systemctl start <service>
```

#### Service-Specific Rollback

##### Docker Container Rollback
```bash
# 1. Check recent container changes
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.CreatedAt}}"

# 2. Rollback to previous image
docker stop <container>
docker run -d --name <container> <previous_image>

# 3. Verify rollback
docker ps | grep <container>
```

##### Firewall Configuration Rollback
```bash
# 1. Check current UFW rules
ufw status numbered

# 2. Remove automated rules (if needed)
ufw delete <rule_number>

# 3. Reset to safe defaults
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw --force enable
```

##### System Service Rollback
```bash
# 1. Stop problematic service
systemctl stop <service>

# 2. Check service configuration
systemctl cat <service>

# 3. Restore from backup (if available)
cp /etc/systemd/system/<service>.backup /etc/systemd/system/<service>
systemctl daemon-reload

# 4. Start service
systemctl start <service>
```

### Rollback Verification

#### Health Check After Rollback
```bash
# 1. Verify service status
systemctl status veris-memory-api
systemctl status veris-memory-mcp
systemctl status veris-memory-sentinel

# 2. Check service connectivity
curl -f http://localhost:8001/api/v1/health
curl -f http://localhost:8000/
curl -f http://localhost:9090/status

# 3. Verify database connectivity
timeout 5 bash -c '</dev/tcp/localhost/6333'  # Qdrant
timeout 5 bash -c '</dev/tcp/localhost/7474'  # Neo4j
timeout 5 bash -c '</dev/tcp/localhost/6379'  # Redis

# 4. Check system resources
df -h
free -h
uptime
```

#### Rollback Documentation
```bash
# Create rollback report
cat > /tmp/rollback_report.txt << EOF
Rollback Report - $(date)
========================

Alert ID: ${ALERT_ID}
Session ID: ${SESSION_ID}
Rollback Reason: ${REASON}

Changes Rolled Back:
$(cat /tmp/automation_changes.log)

Verification Results:
$(systemctl status veris-memory-* --no-pager)

System Status:
$(uptime && free -h && df -h /)
EOF
```

### Emergency Procedures

#### Complete System Rollback
```bash
# 1. Stop all automation
pkill -f "claude-code-launcher"
pkill -f "automated-debugging"

# 2. Reset services to known good state
systemctl restart veris-memory-api
systemctl restart veris-memory-mcp
systemctl restart veris-memory-sentinel

# 3. Reset firewall to default
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 8000,8001,9090,8080/tcp
ufw --force enable

# 4. Clear automation state
rm -f /tmp/ssh_audit_*.log
rm -f /tmp/claude_sessions_state.json

# 5. Verify system health
bash /path/to/health_check_script.sh
```

#### Incident Response Contact
```
Emergency Contacts:
- Primary: System Administrator
- Secondary: Security Team
- Escalation: Senior Engineering Team

Emergency Procedures:
1. Stop all automation immediately
2. Isolate affected systems if needed
3. Contact emergency response team
4. Document all actions taken
5. Perform post-incident review
```

## 🛡️ Security Monitoring

### Audit Log Locations
```bash
# SSH Security Manager logs
/tmp/ssh_audit_*.log
/tmp/ssh_session_*.log

# Session rate limiter logs
/tmp/claude_sessions_state.json

# System audit logs
/var/log/audit.log
/var/log/auth.log

# Service logs
journalctl -u veris-memory-*
```

### Security Alerts
- Failed authentication attempts
- Rate limit violations
- Emergency brake activations
- Rollback events
- Security validation failures

### Monitoring Commands
```bash
# Monitor active sessions
python -c "
from scripts.sentinel.session_rate_limiter import SessionRateLimiter
limiter = SessionRateLimiter({})
print(limiter.get_session_stats())
"

# Check security events
grep "SECURITY\|EMERGENCY\|ROLLBACK" /var/log/*.log

# Verify automation health
python scripts/sentinel/test_phase3_components.py
```

## 📋 Security Checklist

### Daily Security Checks
- [ ] Verify Claude API key functionality
- [ ] Check session rate limits and stats
- [ ] Review audit logs for anomalies
- [ ] Verify SSH key integrity
- [ ] Test emergency rollback procedures

### Weekly Security Review
- [ ] Rotate SSH keys if needed
- [ ] Review and update allowlists
- [ ] Test complete emergency procedures
- [ ] Audit session success/failure rates
- [ ] Update security documentation

### Monthly Security Audit
- [ ] Rotate Claude API keys
- [ ] Review all security configurations
- [ ] Penetration test automation endpoints
- [ ] Update emergency contact information
- [ ] Train team on new procedures

---

**Document Version**: 1.0  
**Last Updated**: 2025-08-21  
**Next Review**: 2025-09-21  
**Owner**: Security Team  
**Approval**: System Administrator