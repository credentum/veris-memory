#!/usr/bin/env python3
"""
Auto-generated implementation script for issue #1762.
This script should be executed by Claude Code with Task tool access.
"""

# Task configuration
ISSUE_NUMBER = 1762
TASK_DESCRIPTION = "Implement issue #1762"
TASK_PROMPT = """You are implementing code changes for GitHub Issue #1762.

Issue Title: [SPRINT-6.1] Deploy veris-memory context-store to Hetzner dedicated server with Ubuntu 24.04 optimization

Problem Description:
Not specified

Acceptance Criteria:
- [ ] Create Dockerfile.hetzner with Ubuntu 24.04 and Tailscale integration
- [ ] Create docker-compose.hetzner.yml optimized for 64GB RAM / 6-core system
- [ ] Update .ctxrc.yaml with performance tuning for high-spec hardware
- [ ] Implement RAID1 storage integration for Docker volumes
- [ ] Add Tailscale networking for secure private access
- [ ] Create deployment automation scripts for Hetzner environment
- [ ] Add hardware monitoring and RAID health checks
- [ ] Implement backup strategies leveraging RAID1 redundancy
- [ ] Performance benchmarks show 10x+ improvement over current Fly.io setup
- [ ] Security hardening with firewall rules and Tailscale-only access

Task Template Location: /workspaces/agent-context-template/worktree/issue-1762/context-store/context/trace/task-templates/issue-1762-sprint-61-deploy-veris-memory-context-store-to-het.md

Instructions:
1. Analyze the issue requirements and acceptance criteria carefully
2. Identify the files that need to be modified based on the problem description
3. Implement the necessary code changes following existing patterns
4. Create meaningful commits with proper conventional commit messages
5. Ensure all acceptance criteria are met
6. Add appropriate error handling where needed

Important:
- Follow the existing code style and patterns in the repository
- Make minimal changes necessary to fix the issue
- Do not modify unrelated code or files
- Test your changes conceptually to ensure they work
- Use conventional commit format: type(scope): description

Please implement the required changes now."""

# When executed by Claude Code, this will trigger the Task tool
print("=" * 60)
print(f"TASK IMPLEMENTATION REQUEST FOR ISSUE #1762")
print("=" * 60)
print()
print("This script requires execution in Claude Code environment with Task tool access.")
print()
print("Task Description:", TASK_DESCRIPTION)
print()
print("Task Prompt:")
print("-" * 60)
print(TASK_PROMPT)
print("-" * 60)
print()
print("To execute: Run this script in Claude Code with the Task tool available")
print()
