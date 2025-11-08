# TeamAI Voice Platform - Phased Implementation Plan

## Executive Summary

Building **AI teammates who talk back, remember everything, and actually do work**. This is not another chatbot - it's the first AI that feels like a coworker, combining voice interaction, persistent memory, and tool execution.

**Core Innovation**: Voice + persistent MCP memory + tool-using Claude agents = real AI teammates

---

## Phase 1: Foundation (Sprint 1) - 2 Weeks
**Theme: "Memory That Actually Works"**

### Goals
- ✅ Voice-bot with real fact memory (not chat logs)
- ✅ Zero latency surprises
- ✅ Persistent memory across restarts
- ✅ Container-ready deployment

### Epic 1: Container & Infrastructure (4 SP)
```yaml
1.1 Voice-Bot Service Setup (45 min)
   - Create voice-bot/ directory structure
   - FastAPI application skeleton
   - Dockerfile with Python 3.11
   - .env template (LIVEKIT_KEY, MCP_URL)

1.2 Docker Compose Integration (1 hour)
   - Add voice-bot to existing docker-compose
   - Configure shared network with mcp-server
   - Health check endpoint: GET /health
   - Environment variable injection

1.3 CI/CD Pipeline (1 hour)
   - GitHub Actions workflow
   - Build and test on PR
   - Deploy on merge to main
   - No additional secrets needed
```

### Epic 2: MCP Fact Storage Integration (5 SP)
```yaml
2.1 Memory Client Implementation (2 hours)
   - VoiceBotMemory class wrapping MCP client
   - store_fact(user_id, key, value)
   - get_user_facts(user_id, keys=[])
   - Namespace: voicebot_{user_id}

2.2 Retrieval Strategy (1.5 hours)
   - Primary: Direct key lookup (facts:namespace:user:key)
   - Fallback: Semantic search (last 5 facts only)
   - No chat history pollution
   - Return structured dict

2.3 Testing & Validation (1 hour)
   - Unit tests with mock MCP
   - Integration tests with real MCP
   - Expected: {'name': 'Matt', 'color': 'blue'}
   - Raise ValueError on missing critical facts

2.4 Observability (30 min)
   - Log all MCP requests/responses
   - Metrics: fact hit rate, retrieval time
   - Alert on fact miss patterns
```

### Epic 3: LiveKit Voice Integration (4 SP)
```yaml
3.1 LiveKit Server Setup (1 hour)
   - Docker: livekit/livekit-server:latest
   - Port configuration: 7880, 7881
   - Token generation endpoint
   - TURN server included (coturn)

3.2 Voice Echo Test (2 hours)
   - WebSocket client connection
   - STT → Process → TTS pipeline
   - Test phrase: "Hi {name}, {color} still your color?"
   - No LLM yet - pure memory recall

3.3 Mobile Support (30 min)
   - TURN/STUN configuration
   - WebRTC optimization
   - Network traversal testing
```

### Epic 4: Validation Gate (1 SP)
```yaml
4.1 Persistence Test (30 min)
   - Kill container → Restart
   - Say "What's my name?"
   - Must answer from stored facts
   - RED FLAG if fails - no merge

4.2 Documentation
   - Update README with test results
   - Record validation video
   - Performance metrics
```

### Deliverables
- Single docker service: `docker-compose up voice-bot`
- Recalls explicit facts across reboots
- Speaks them back via LiveKit
- No Claude, no fluff - just working memory

### Success Metrics
- ✅ Fact recall accuracy: 100%
- ✅ Memory persistence: Survives restart
- ✅ Latency: <500ms fact retrieval
- ✅ Voice quality: Clear TTS output

---

## Phase 2: Intelligence (Sprint 2) - 2 Weeks
**Theme: "Code Reviewer That Remembers"**

### Goals
- Claude integration for reasoning
- Code review capabilities
- Context-aware responses
- Memory of past reviews

### Epic 5: Claude Agent Integration (8 SP)
```yaml
5.1 Claude SDK Setup (2 hours)
   - Anthropic Python SDK
   - Agent configuration
   - Tool definitions
   - Rate limiting

5.2 Code Review Agent (3 hours)
   - Read file capability
   - AST parsing for Python
   - Review generation
   - Suggestion prioritization

5.3 Memory-Augmented Prompts (2 hours)
   - System prompt injection: "User is {name}, role: {role}"
   - Past review context
   - Project preferences
   - Code style memory

5.4 Voice Command Parser (1 hour)
   - "Review main.py" → action
   - Intent classification
   - Parameter extraction
   - Error handling
```

### Epic 6: Conversation Management (5 SP)
```yaml
6.1 Session State (2 hours)
   - Scratchpad for active context
   - Conversation threading
   - Topic transitions
   - TTL management

6.2 Multi-turn Dialogue (2 hours)
   - Context window optimization
   - Fact vs conversation separation
   - Follow-up questions
   - Clarification loops

6.3 Voice UX Improvements (1 hour)
   - Interrupt handling
   - Thinking indicators
   - Confirmation sounds
   - Error recovery
```

### Deliverables
- Code review via voice: "Review main.py"
- Remembers past reviews and preferences
- Context-aware suggestions
- Natural conversation flow

### Success Metrics
- ✅ Code review accuracy: >80% useful suggestions
- ✅ Context retention: References past reviews
- ✅ Response time: <2s for simple reviews
- ✅ User satisfaction: Clear, actionable feedback

---

## Phase 3: Execution (Sprint 3) - 2 Weeks
**Theme: "AI That Actually Does Work"**

### Goals
- Tool execution capabilities
- Git operations
- Ticket management
- Autonomous task completion

### Epic 7: Tool Framework (6 SP)
```yaml
7.1 Tool Registry (2 hours)
   - Dynamic tool loading
   - Permission management
   - Execution sandbox
   - Result formatting

7.2 Core Developer Tools (3 hours)
   - git: pull, commit, push, status
   - lint: flake8, black, mypy
   - test: pytest execution
   - build: docker, npm

7.3 Integration Tools (2 hours)
   - Jira: ticket creation, updates
   - GitHub: PR creation, reviews
   - Slack: notifications
   - Documentation updates
```

### Epic 8: Autonomous Execution (8 SP)
```yaml
8.1 Task Planning (3 hours)
   - Break down voice requests
   - Dependency resolution
   - Execution ordering
   - Rollback strategies

8.2 Safe Execution (2 hours)
   - Confirmation protocols
   - Dry-run mode
   - Audit logging
   - Revert capabilities

8.3 Progress Reporting (1 hour)
   - Real-time status updates
   - Voice progress indicators
   - Completion notifications
   - Error explanations

8.4 Learning Loop (2 hours)
   - Success/failure tracking
   - Pattern recognition
   - Preference learning
   - Optimization suggestions
```

### Deliverables
- Voice-triggered git operations
- Automated testing and linting
- Ticket creation and linking
- Safe, auditable execution

### Success Metrics
- ✅ Tool execution success: >95%
- ✅ Safety: Zero destructive operations
- ✅ Automation value: 10x faster than manual
- ✅ Trust: Users comfortable with autonomous execution

---

## Phase 4: Platform (Sprint 4) - 3 Weeks
**Theme: "100 PMs Paying $99/month"**

### Goals
- Multi-tenant architecture
- Subscription management
- Team collaboration
- Enterprise features

### Epic 9: Multi-Tenancy (10 SP)
```yaml
9.1 User Management (3 hours)
   - Authentication (Auth0/Clerk)
   - Organization structure
   - Role-based access
   - Namespace isolation

9.2 Memory Isolation (2 hours)
   - Per-org namespaces
   - Shared team facts
   - Private user facts
   - Cross-tenant security

9.3 Voice Profiles (2 hours)
   - Custom wake words
   - Voice preferences
   - Language support
   - Accent adaptation

9.4 Resource Management (2 hours)
   - Rate limiting per org
   - Storage quotas
   - Compute allocation
   - Priority queuing
```

### Epic 10: Monetization (8 SP)
```yaml
10.1 Subscription System (3 hours)
   - Stripe integration
   - Plan management ($99/month)
   - Usage tracking
   - Billing portal

10.2 Feature Tiers (2 hours)
   - Free: 100 commands/month
   - Pro: Unlimited + tools
   - Team: Shared memory
   - Enterprise: Custom deployment

10.3 Usage Analytics (2 hours)
   - Command tracking
   - Memory utilization
   - Tool usage
   - ROI reporting

10.4 Growth Features (1 hour)
   - Referral system
   - Team invites
   - Public templates
   - Community showcase
```

### Epic 11: Team Collaboration (6 SP)
```yaml
11.1 Shared Context (2 hours)
   - Team knowledge base
   - Project memory
   - Decision history
   - Best practices

11.2 Handoffs (2 hours)
   - Context transfer
   - Task delegation
   - Progress sharing
   - Async collaboration

11.3 Specialized Agents (2 hours)
   - DevOps specialist
   - Security reviewer
   - Architecture advisor
   - PM assistant
```

### Deliverables
- Multi-tenant SaaS platform
- Subscription management
- Team collaboration features
- 100+ paying customers

### Success Metrics
- ✅ MRR: $10,000+ (100 customers)
- ✅ Churn: <5% monthly
- ✅ NPS: >50
- ✅ Uptime: 99.9%

---

## Technical Architecture

### System Components
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   LiveKit RTC   │────▶│   Voice Bot     │────▶│   MCP Server    │
│   (WebRTC)      │◀────│   (FastAPI)     │◀────│   (Veris)       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │                          │
                               ▼                          ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │  Claude Agent   │     │   Storage       │
                        │  (Anthropic)    │     │ Qdrant/Neo4j/   │
                        └─────────────────┘     │   Redis         │
                                                └─────────────────┘
```

### Data Flow
1. **Voice Input** → LiveKit STT → Text
2. **Memory Fetch** → MCP retrieve_context → Facts
3. **Processing** → Claude reasoning → Response
4. **Voice Output** → TTS → LiveKit → User
5. **Memory Store** → New facts → MCP store_context

### Key Design Decisions
- **Fact-based memory**: Store atomic facts, not conversations
- **Namespace isolation**: voicebot_{org}_{user}
- **Hybrid search**: Key lookup first, semantic fallback
- **Tool sandboxing**: Safe execution environment
- **Event sourcing**: Full audit trail

---

## Risk Mitigation

### Technical Risks
| Risk | Mitigation | Status |
|------|------------|--------|
| Memory corruption | Fact validation, backups | Phase 1 |
| Voice quality | LiveKit enterprise, fallbacks | Phase 1 |
| Claude latency | Caching, async processing | Phase 2 |
| Tool safety | Sandboxing, confirmations | Phase 3 |
| Scale issues | Horizontal scaling, CDN | Phase 4 |

### Business Risks
| Risk | Mitigation | Status |
|------|------------|--------|
| Slow adoption | Free tier, demos | Phase 4 |
| Churn | Onboarding, value metrics | Phase 4 |
| Competition | Unique memory model | Phase 1 |
| Pricing | A/B testing, surveys | Phase 4 |

---

## Success Criteria

### Phase 1 Gate (Sprint 1)
- ✅ Voice echo test passes
- ✅ Facts persist across restarts
- ✅ Docker deployment works
- ✅ Zero hallucinations on known facts

### Phase 2 Gate (Sprint 2)
- ✅ Code review generates useful feedback
- ✅ Remembers user preferences
- ✅ Natural conversation flow
- ✅ <2s response time

### Phase 3 Gate (Sprint 3)
- ✅ Git operations execute safely
- ✅ No destructive operations without confirmation
- ✅ Tool execution audit trail
- ✅ 95% success rate

### Phase 4 Gate (Sprint 4)
- ✅ 100 paying customers
- ✅ <5% monthly churn
- ✅ 99.9% uptime
- ✅ Positive unit economics

---

## Timeline

```
Week 1-2:  Sprint 1 - Foundation (Memory + Voice)
Week 3-4:  Sprint 2 - Intelligence (Claude Integration)
Week 5-6:  Sprint 3 - Execution (Tool Framework)
Week 7-9:  Sprint 4 - Platform (Multi-tenant SaaS)
Week 10:   Launch 🚀
```

---

## Next Immediate Steps

1. **Create new session for development**:
   ```bash
   export WORK_DIR=$(bash /claude-workspace/scripts/new-session.sh)
   cd $WORK_DIR
   ```

2. **Clone or create voice-bot repository**:
   ```bash
   gh repo create credentum/teamai-voice-platform --private
   git clone credentum/teamai-voice-platform
   cd teamai-voice-platform
   ```

3. **Start Sprint 1 implementation**:
   - Set up voice-bot service structure
   - Create Dockerfile and docker-compose
   - Implement MCP memory client
   - Deploy LiveKit server

---

## Conclusion

The TeamAI Voice Platform represents a paradigm shift in AI assistance - from typing to talking, from forgetting to remembering, from suggesting to executing. With the Veris memory system already production-ready, we can focus on building the voice layer and Claude integration to deliver a truly revolutionary product.

**The win condition is simple**: Say your name once, walk away, come back in 20 hours - it greets you correctly. No hallucinations. That's when we know we've built something real.