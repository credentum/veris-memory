# IMPLEMENTATION NEEDED: Issue #1762

**IMPORTANT**: The workflow has reached the implementation phase but needs the Task tool to proceed.

## What to do:

### Option 1: Use Task Tool (Recommended)

Run the following in Claude Code with Task tool access:

```python
# Use the Task tool to implement the code changes
task_prompt = """
You are implementing code changes for GitHub Issue #1762.

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

Please implement the required changes now.
"""

# Execute with Task tool
# task --description "Implement issue #1762" \
#      --prompt task_prompt --subagent_type "general-purpose"
```

### Option 2: Manual Implementation

1. Review the acceptance criteria below
2. Identify files that need modification based on the requirements
3. Implement the code changes following existing patterns
4. Create appropriate test files
5. Commit with conventional commit messages

## Issue Details:

- **Number**: #1762
- **Title**: [SPRINT-6.1] Deploy veris-memory context-store to Hetzner dedicated server with Ubuntu 24.04 optimization

## Implementation Requirements:

You are implementing code changes for GitHub Issue #1762.

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

Please implement the required changes now.

## Verification:

After implementation, the workflow will continue with:

- Phase 3: Testing & Validation
- Phase 4: PR Creation
- Phase 5: Monitoring
