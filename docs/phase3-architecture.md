# Phase 3: Claude Code Integration with SSH Access

## 🚀 Architecture Overview

Phase 3 leverages GitHub Actions' SSH access to the Veris Memory server, enabling Claude to perform comprehensive hands-on debugging and automated fix deployment directly on the production system.

## 🏗️ System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Sentinel      │    │   GitHub Actions │    │  Claude Code    │
│   Alert         │───▶│   Enhanced       │───▶│   Automated     │
│   System        │    │   Workflow       │    │   Session       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                │ SSH Connection         │ SSH Commands
                                ▼                        ▼
                       ┌─────────────────────────────────────────┐
                       │        Veris Memory Server              │
                       │  • Direct system access                │
                       │  • Live log analysis                   │
                       │  • Service debugging                   │
                       │  • Real-time diagnostics               │
                       │  • Automated fixes                     │
                       └─────────────────────────────────────────┘
```

## 🎯 Phase 3 Capabilities

### 1. **Automated Claude Code Session Launch**
- **Trigger**: Critical alerts from Sentinel
- **Context**: Complete Phase 2 diagnostic results + SSH access
- **Capability**: Direct server investigation and remediation

### 2. **Deep System Investigation**
- **Live Log Analysis**: Real-time log streaming and pattern analysis
- **Process Inspection**: Service status, resource usage, thread analysis
- **Network Diagnostics**: Port availability, connection testing
- **Database Investigation**: Query performance, connection health
- **File System Analysis**: Disk usage, permissions, configuration drift

### 3. **Intelligent Fix Generation**
- **Service Recovery**: Automatic restart with dependency ordering
- **Configuration Repair**: Fix configuration drift and validation errors
- **Resource Optimization**: Memory cleanup, disk space management
- **Security Hardening**: Firewall adjustments, permission corrections

### 4. **Automated Deployment Pipeline**
- **Hot Fixes**: Direct production fixes for critical issues
- **Configuration Updates**: Safe configuration changes with rollback
- **Service Updates**: Rolling updates with health verification
- **Emergency Procedures**: Rapid response for system-wide failures

## 🔧 Implementation Components

### 1. Claude Code Session Launcher
```yaml
# GitHub Actions Step
- name: 🤖 Launch Claude Code Emergency Session
  env:
    SSH_PRIVATE_KEY: ${{ secrets.VERIS_MEMORY_SSH_KEY }}
    CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}
  run: |
    # Setup SSH connection
    echo "$SSH_PRIVATE_KEY" > ssh_key
    chmod 600 ssh_key
    
    # Launch Claude Code with server access
    claude-code \
      --context-file claude-enhanced-context.json \
      --ssh-host 167.235.112.106 \
      --ssh-key ssh_key \
      --emergency-mode \
      --auto-debug \
      --fix-generation \
      --pr-creation
```

### 2. Enhanced Context Injection
```json
{
  "emergency_context": {
    "alert": "Phase 2 diagnostic results",
    "ssh_access": {
      "host": "167.235.112.106",
      "user": "root",
      "capabilities": ["log_access", "service_control", "system_diagnostics"]
    },
    "diagnostic_results": "Complete Phase 2 analysis",
    "authorized_actions": [
      "service_restart",
      "configuration_fix",
      "log_analysis", 
      "performance_optimization",
      "emergency_procedures"
    ]
  }
}
```

### 3. Automated Debugging Workflows

#### **Service Health Recovery**
```bash
# Claude Code automated workflow
1. SSH to server
2. Analyze service status: systemctl status veris-*
3. Check resource usage: htop, df -h, free -h
4. Examine recent logs: journalctl -u veris-* --since "10 minutes ago"
5. Identify root cause from Phase 2 diagnostics
6. Execute targeted fix (restart, config, resources)
7. Verify recovery with health checks
8. Generate PR with changes and analysis
```

#### **Database Connectivity Issues**
```bash
# Claude Code automated workflow  
1. SSH to server
2. Test database connections: telnet localhost 6333, 7474, 6379
3. Analyze connection pool status
4. Check database logs for errors
5. Verify network configuration
6. Execute connection pool reset if needed
7. Validate service recovery
8. Document fix in PR
```

#### **Performance Degradation**
```bash
# Claude Code automated workflow
1. SSH to server  
2. Analyze system performance: top, iotop, netstat
3. Identify resource bottlenecks
4. Check service-specific metrics
5. Optimize configurations based on findings
6. Apply memory/CPU optimizations
7. Monitor improvement
8. Create PR with performance tuning
```

## 🛡️ Security & Safety

### 1. **Controlled Access**
- SSH access only during critical alerts
- Time-limited sessions (30 minutes max)
- Audit logging of all commands executed
- Rollback mechanisms for all changes

### 2. **Safe Operations**
- Read-only investigation by default
- Write operations require explicit authorization
- Automatic backups before configuration changes
- Health verification after each modification

### 3. **Emergency Procedures**
- Immediate alert escalation if fixes fail
- Automatic rollback on error detection
- Manual override capabilities
- Emergency contact notifications

## 📊 Expected Outcomes

### **Response Time Reduction**
- **Phase 1**: 30+ minutes manual investigation
- **Phase 2**: 5-10 minutes diagnostic analysis  
- **Phase 3**: 2-3 minutes automated resolution

### **Resolution Capabilities**
- **90% of service failures**: Automated restart with dependency ordering
- **80% of configuration issues**: Automated detection and repair
- **70% of performance problems**: Automated optimization and tuning
- **95% of database connectivity**: Automated connection pool management

### **Learning & Improvement**
- Continuous learning from each incident
- Pattern recognition for proactive fixes
- Automated runbook generation
- Knowledge base expansion

## 🔄 Integration with Existing System

### **Phase 2 Enhancement**
- Phase 2 diagnostics provide root cause analysis
- Intelligence synthesis guides Claude's investigation
- Dependency mapping informs recovery order
- Performance metrics guide optimization strategies

### **GitHub Actions Workflow**
- Seamless integration with existing alert response
- Enhanced context from Phase 2 diagnostics
- Automated PR creation with fix documentation
- Continuous monitoring during and after fixes

## 🎯 Implementation Roadmap

### **Week 1**: Infrastructure Setup
- SSH key configuration and security hardening
- Claude Code CLI integration with GitHub Actions
- Emergency session launcher development

### **Week 2**: Core Debugging Workflows
- Service health recovery automation
- Database connectivity issue resolution
- Performance optimization workflows

### **Week 3**: Intelligent Fix Generation
- Configuration repair automation
- Resource optimization algorithms
- Security hardening procedures

### **Week 4**: Integration & Testing
- End-to-end testing with real scenarios
- Safety mechanism validation
- Performance benchmarking

## 🚀 Success Metrics

- **Mean Time to Recovery (MTTR)**: Target < 3 minutes
- **Automation Success Rate**: Target > 85%
- **False Positive Rate**: Target < 5%
- **Manual Intervention Required**: Target < 15%

---

**Phase 3 represents the evolution from intelligent diagnostics to autonomous incident response, leveraging SSH access for direct system remediation and creating a truly self-healing infrastructure.**