"""
Veris Memory Operations

Functions for storing and retrieving context from Veris Memory API.
"""

import json
import time
from typing import Any, Dict, List

import requests

from config import (
    client,
    DEBUG_MEMORY,
    VERIS_API_KEY,
    MEMORY_API_BASE,
    USER_ID,
    SESSION_ID,
    DEFAULT_EXCLUDE_SOURCES,
)


def mem_headers() -> dict:
    """Headers for Veris API requests - sends only the key portion"""
    return {"X-API-Key": VERIS_API_KEY, "Content-Type": "application/json"}


def get_user_facts(user_id: str = None, limit: int = 50) -> List[Dict[str, str]]:
    """
    Get ALL facts for a user directly from Neo4j (no semantic similarity).
    Returns list of {"fact_key": str, "fact_value": str}.
    """
    if not VERIS_API_KEY:
        return []

    user_id = user_id or USER_ID

    try:
        if DEBUG_MEMORY:
            print(f"→ Getting all facts for user: {user_id}")

        r = requests.post(
            f"{MEMORY_API_BASE}/tools/get_user_facts",
            headers=mem_headers(),
            json={"user_id": user_id, "limit": limit},
            timeout=5,
        )

        if r.status_code == 200:
            data = r.json()
            facts = data.get("facts", [])
            if DEBUG_MEMORY:
                print(f"→ Got {len(facts)} facts for user {user_id}")
            return facts
        else:
            if DEBUG_MEMORY:
                print(f"→ get_user_facts failed: {r.status_code}")
            return []

    except Exception as e:
        if DEBUG_MEMORY:
            print(f"→ get_user_facts error: {e}")
        return []


def expand_query(query: str) -> str:
    """
    Expand query with synonyms and related terms for better semantic matching.
    Helps bridge the gap between user's shorthand and stored document titles.
    """
    lower = query.lower()
    expansions = []

    # TD items -> technical debt
    if "td item" in lower or "td-" in lower:
        expansions.append("technical debt improvements backlog")

    # Common project terms
    if "voicebot" in lower or "voice bot" in lower:
        expansions.append("VoiceBot voice assistant")

    # Memory/search related
    if "memory" in lower or "search" in lower:
        expansions.append("stored context retrieval")

    # Roadmap/planning
    if "roadmap" in lower or "plan" in lower:
        expansions.append("future improvements features")

    # Bug/issue tracking
    if "bug" in lower or "issue" in lower:
        expansions.append("problem fix error")

    if expansions:
        return f"{query} {' '.join(expansions)}"
    return query


def retrieve_context(query: str, limit: int = 5, exclude_sources: List[str] = None) -> List[Dict[str, Any]]:
    """Call /tools/retrieve_context. Returns list of results (possibly empty)."""
    if not VERIS_API_KEY:
        return []

    # Use server-side filtering to exclude test/system noise
    if exclude_sources is None:
        exclude_sources = DEFAULT_EXCLUDE_SOURCES

    # Expand query for better semantic matching
    expanded_query = expand_query(query)

    payload = {
        "query": expanded_query,
        "limit": limit,
        "search_mode": "hybrid",
        "exclude_sources": exclude_sources  # Server-side filtering (PR #352)
    }

    try:
        if DEBUG_MEMORY:
            if expanded_query != query:
                print(f"→ Query expanded: '{query}' → '{expanded_query}'")
            print(f"→ Retrieve request: {payload}")

        r = requests.post(
            f"{MEMORY_API_BASE}/tools/retrieve_context",
            headers=mem_headers(),
            json=payload,
            timeout=6,
        )

        if DEBUG_MEMORY:
            print(f"→ Retrieve response status: {r.status_code}")

        r.raise_for_status()
        data = r.json()

        if DEBUG_MEMORY:
            print(f"→ Retrieve response data: {data}")

        results = data.get("results", [])
        if not results and data.get("success") is False:
            print(f"Memory retrieve failed: {data.get('error', 'Unknown error')}")

        return results
    except Exception as e:
        print(f"Memory retrieve error: {e}")
        if DEBUG_MEMORY:
            import traceback
            traceback.print_exc()
        return []


# ---- Smart Storage Decisions ----

# Patterns to skip (greetings, filler)
SKIP_PATTERNS = [
    "hello", "hi ", "hey ", "hi,", "hey,",
    "good morning", "good afternoon", "good evening", "good night",
    "thanks", "thank you", "okay", "ok ", "ok,", "got it", "sure",
    "bye", "goodbye", "see you", "talk later",
    "how are you", "what's up", "how's it going",
    "yes", "no", "yeah", "yep", "nope",
    "hmm", "uh", "um", "let me think",
]

# Patterns to always store (facts, actions)
STORE_PATTERNS = [
    "my name is", "i am ", "i'm ", "i live", "i work",
    "my favorite", "i like", "i love", "i prefer",
    "remember that", "don't forget", "note that",
    "the bug", "the issue", "the problem", "we should", "we need to",
    "let's implement", "please add", "please fix", "please update",
]


def should_store_turn(user_text: str, assistant_text: str) -> tuple[bool, str]:
    """
    Use LLM to decide if a conversation turn is worth storing to memory.
    Returns: (should_store: bool, reason: str)

    Stores: facts, decisions, findings, action items, substantive Q&A
    Skips: greetings, filler, repeated questions, trivial exchanges
    """
    # Quick filters - obvious skips (save API call)
    lower_user = user_text.lower().strip()

    # Very short messages are usually filler
    if len(user_text) < 12:
        return False, "too_short"

    if any(lower_user.startswith(p) or lower_user == p.strip() for p in SKIP_PATTERNS):
        # But if the full message is longer, it might have substance after the greeting
        if len(user_text) < 25:
            return False, "greeting_or_filler"

    # Quick store - obvious keeps (save API call)
    if any(p in lower_user for p in STORE_PATTERNS):
        return True, "contains_fact_or_action"

    # For ambiguous cases, ask LLM
    prompt = f"""Decide if this conversation turn should be stored in long-term memory.

STORE if it contains:
- Personal facts about the user (name, preferences, location, etc.)
- Decisions or action items
- Bug reports, issues, or findings
- Substantive technical discussion
- Important context for future conversations

SKIP if it's:
- Greetings, pleasantries, small talk
- Filler words or acknowledgments
- Questions without meaningful content
- Repeated/redundant information

User said: "{user_text}"
Bot replied: "{assistant_text[:200]}"

Respond with ONLY a JSON object:
{{"store": true/false, "reason": "brief explanation"}}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=50,
        )
        result_text = response.choices[0].message.content.strip()
        result = json.loads(result_text)
        should_store = result.get("store", True)  # Default to storing if unclear
        reason = result.get("reason", "llm_decision")
        return should_store, reason
    except Exception as e:
        if DEBUG_MEMORY:
            print(f"→ should_store_turn error: {e}")
        # Default to storing on error (safer)
        return True, "error_default_store"


# ---- Structured Tagging ----

def classify_content(user_text: str, assistant_text: str) -> Dict[str, Any]:
    """
    Classify conversation content and generate structured tags.
    Returns dict with: content_type, project, priority, topics
    """
    lower_user = user_text.lower()

    # Detect content type based on keywords
    content_type = "conversation"  # default

    if any(w in lower_user for w in ["bug", "error", "broken", "doesn't work", "failed", "crash"]):
        content_type = "bug_report"
    elif any(w in lower_user for w in ["should add", "would be nice", "feature", "could we", "can you add"]):
        content_type = "feature_request"
    elif any(w in lower_user for w in ["my name", "my favorite", "i am", "i live", "i work", "i like"]):
        content_type = "personal_fact"
    elif any(w in lower_user for w in ["review", "analyze", "check the code", "look at"]):
        content_type = "code_review"
    elif any(w in lower_user for w in ["how do", "how does", "what is", "explain", "why"]):
        content_type = "question"
    elif any(w in lower_user for w in ["let's", "we should", "need to", "todo", "action item"]):
        content_type = "action_item"
    elif any(w in lower_user for w in ["decided", "agree", "confirmed", "will do", "plan is"]):
        content_type = "decision"

    # Detect project references
    project = None
    if "voicebot" in lower_user or "voice bot" in lower_user:
        project = "voicebot"
    elif "veris" in lower_user or "memory" in lower_user:
        project = "veris"

    # Detect priority hints
    priority = "normal"
    if any(w in lower_user for w in ["urgent", "critical", "asap", "important", "blocking"]):
        priority = "high"
    elif any(w in lower_user for w in ["later", "eventually", "low priority", "nice to have"]):
        priority = "low"

    # Extract topic keywords (simple extraction)
    topics = []
    topic_keywords = [
        "memory", "search", "facts", "storage", "api", "auth", "tts", "stt",
        "intent", "agent", "claude", "openai", "neo4j", "vector", "graph"
    ]
    for kw in topic_keywords:
        if kw in lower_user:
            topics.append(kw)

    return {
        "content_type": content_type,
        "project": project,
        "priority": priority,
        "topics": topics if topics else None,
    }


def store_turn(
    user_text: str,
    assistant_text: str,
    intent: str = None,
    entities: Dict[str, Any] = None,
    duration_ms: int = None,
    confidence: float = None,
):
    """Call /tools/store_context to save a conversation turn with structured tags."""
    if not VERIS_API_KEY:
        return

    # Generate structured tags
    tags = classify_content(user_text, assistant_text)
    if DEBUG_MEMORY:
        print(f"→ Content tags: {tags}")

    payload = {
        "type": "trace",
        "content": {
            "title": "Voice Conversation Turn",
            "user_input": user_text,
            "bot_response": assistant_text,
            **({"intent": intent} if intent else {}),
            **({"entities": entities} if entities else {}),
        },
        "metadata": {
            "source": "voice_bot",
            "session_id": SESSION_ID,
            "user_id": USER_ID,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            **({"duration_ms": duration_ms} if duration_ms is not None else {}),
            **({"confidence": confidence} if confidence is not None else {}),
            # Structured tags for better retrieval
            "content_type": tags["content_type"],
            **({"project": tags["project"]} if tags["project"] else {}),
            **({"priority": tags["priority"]} if tags["priority"] != "normal" else {}),
            **({"topics": tags["topics"]} if tags["topics"] else {}),
        },
    }
    try:
        if DEBUG_MEMORY:
            print(f"→ Store request payload: {payload}")

        r = requests.post(
            f"{MEMORY_API_BASE}/tools/store_context",
            headers=mem_headers(),
            json=payload,
            timeout=6,
        )

        if DEBUG_MEMORY:
            print(f"→ Store response status: {r.status_code}")
            print(f"→ Store response: {r.text[:500]}")

        r.raise_for_status()
        print(f"✓ Stored turn to memory (session: {SESSION_ID})")
    except Exception as e:
        print(f"Memory store error: {e}")
        if DEBUG_MEMORY:
            import traceback
            traceback.print_exc()


# ---- Retrieval noise filters ----

def filter_memory_results(results: List[Dict[str, Any]], user_query: str) -> List[Dict[str, Any]]:
    """Secondary filter for edge cases not caught by server-side exclude_sources."""
    filtered = []
    for r in results:
        meta = r.get("metadata", {}) or {}
        content = r.get("content", {}) or {}

        # Drop entries with test_type metadata (belt-and-suspenders)
        if meta.get("test_type"):
            continue

        # Drop empty content entries
        if not content:
            continue

        filtered.append(r)

    return filtered


# ---- Memory compression ----

def compress_to_memory_block(memory_results: List[Dict[str, Any]], user_query: str, max_items: int = 5) -> str:
    """
    Transform complex Veris memory results into clean, LLM-friendly context.

    Filters out noise, extracts semantic meaning, explains relevance.
    Returns natural language memory block suitable for prompt injection.
    """
    if not memory_results:
        return ""

    # Sort by relevance score, but de-prioritize generic conversation turns from graph
    # Graph backend sometimes returns old conversations with score=1.0 that aren't truly relevant
    def adjusted_score(r):
        score = float(r.get("relevance_score", r.get("score", 0)))
        content = r.get("content", {}) or {}
        source = r.get("source", "")

        # If it's from graph with score 1.0 and is just a conversation turn, reduce priority
        if source == "graph" and score >= 1.0:
            # Check if it's a simple conversation vs substantive content
            if content.get("user_input") and not content.get("title", "").startswith(("VoiceBot", "Agent", "Bug", "Feature", "TD")):
                score = 0.3  # De-prioritize old chat turns

        return score

    sorted_results = sorted(
        memory_results,
        key=adjusted_score,
        reverse=True
    )[:max_items]

    contexts = []
    facts = set()  # Use set to deduplicate facts

    for r in sorted_results:
        content = r.get("content", {}) or {}
        meta = r.get("metadata", {}) or {}

        # Skip sentinel/test entries
        is_sentinel = meta.get("sentinel") is True or meta.get("test_type") == "golden_recall"
        if is_sentinel:
            continue

        # Skip facts that belong to other users (user_id scoping)
        fact_user_id = meta.get("user_id") or content.get("user_id")
        if fact_user_id and fact_user_id != USER_ID:
            continue

        # Check if this is a fact entry (from upsert_fact)
        is_fact = meta.get("content_type") == "fact" or content.get("content_type") == "fact"

        if is_fact:
            # Dynamically extract ALL fact key/value pairs from content
            # Skip metadata fields, format key as readable text
            skip_keys = {"content_type", "user_id"}
            for key, value in content.items():
                if key in skip_keys or not value:
                    continue
                # Convert snake_case to readable: "favorite_color" -> "Favorite color"
                readable_key = key.replace("_", " ").capitalize()
                facts.add(f"{readable_key}: {value}")

            # Skip adding to contexts list, we'll handle facts separately
            continue

        # Extract title
        title = content.get("title", "Memory")
        if isinstance(title, str):
            title = title[:100]  # Truncate long titles

        # Build summary from available fields (priority order)
        summary_parts = []

        # For conversation turns
        if content.get("user_input"):
            user_input = content['user_input'][:200]
            summary_parts.append(f"User said: {user_input}")

            # Extract name mentions from conversation
            if "my name is" in user_input.lower():
                # Try to extract the name
                words = user_input.lower().split("my name is")
                if len(words) > 1:
                    potential_name = words[1].strip().split()[0].rstrip('.,!?')
                    facts.add(f"User mentioned their name: {potential_name.title()}")

        if content.get("bot_response"):
            summary_parts.append(f"Bot replied: {content['bot_response'][:200]}")

        # For other content types (documents, reports, etc.)
        if content.get("summary"):
            summary_parts.append(content["summary"][:300])
        elif content.get("transcript"):
            summary_parts.append(content["transcript"][:300])
        elif content.get("text"):
            summary_parts.append(content["text"][:300])
        elif content.get("finding"):
            # Agent findings
            summary_parts.append(content["finding"][:500])

        # Handle structured documents with item_1, item_2, etc. (like TD items)
        item_summaries = []
        for key in sorted(content.keys()):
            if key.startswith("item_") and isinstance(content[key], dict):
                item = content[key]
                item_id = item.get("id", key)
                item_title = item.get("title", item.get("name", ""))
                item_priority = item.get("priority", "")
                if item_title:
                    item_str = f"{item_id}: {item_title}"
                    if item_priority:
                        item_str += f" ({item_priority})"
                    item_summaries.append(item_str)
            elif key.startswith("feature_") and isinstance(content[key], dict):
                feat = content[key]
                feat_name = feat.get("name", key)
                feat_priority = feat.get("priority", "")
                if feat_name:
                    feat_str = feat_name
                    if feat_priority:
                        feat_str += f" ({feat_priority})"
                    item_summaries.append(feat_str)

        if item_summaries:
            summary_parts.append("Items: " + ", ".join(item_summaries[:6]))

        # If nothing useful found, skip this result
        if not summary_parts:
            continue

        summary = " | ".join(summary_parts)

        # Determine relevance reason (simple heuristic)
        score = r.get("relevance_score", r.get("score", 0))
        if score > 0.9:
            why = "Highly relevant to your question"
        elif score > 0.7:
            why = "Related to your query"
        else:
            why = "Possibly relevant context"

        # Check if memory source helps explain relevance
        source = meta.get("source", "")
        if "voice_bot" in source:
            why = f"{why} from previous conversation"

        contexts.append({
            "title": title,
            "summary": summary,
            "why_relevant": why,
            "score": f"{score:.2f}" if isinstance(score, (int, float)) else score
        })

    # Format as natural language for LLM
    lines = []

    # Add facts first if we found any
    if facts:
        lines.append(f"Known facts about the user:")
        for fact in facts:
            lines.append(f"  • {fact}")
        lines.append("")  # Empty line separator

    # Add conversation context if any
    if contexts:
        lines.append(f"I found {len(contexts)} relevant conversation memories:")
        for i, ctx in enumerate(contexts, 1):
            lines.append(f"\n{i}. {ctx['title']} (relevance: {ctx['score']})")
            lines.append(f"   {ctx['summary']}")
            lines.append(f"   → {ctx['why_relevant']}")

    return "\n".join(lines) if lines else ""
