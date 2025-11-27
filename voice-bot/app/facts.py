"""
Fact Extraction and Storage

Functions for extracting personal facts from user speech and storing them to Veris.
"""

import json
import re
from typing import Any, Dict, List

import requests

from config import (
    client,
    DEBUG_MEMORY,
    VERIS_API_KEY,
    MEMORY_API_BASE,
    USER_ID,
    SESSION_ID,
)


def mem_headers() -> dict:
    """Headers for Veris API requests - sends only the key portion"""
    return {"X-API-Key": VERIS_API_KEY, "Content-Type": "application/json"}


def store_fact(fact_key: str, fact_value: str):
    """
    Upsert a single fact to Veris memory using the upsert_fact endpoint.

    This endpoint atomically:
    1. Searches for existing facts with the same key
    2. Soft-deletes old facts (30-day retention)
    3. Stores the new fact value

    Veris generates searchable text like "first name is Matt"
    from the fact_key/fact_value pair.
    """
    if not VERIS_API_KEY:
        return

    payload = {
        "fact_key": fact_key,
        "fact_value": fact_value,
        "user_id": USER_ID,  # Stable user ID for fact persistence across sessions
        "metadata": {
            "source": "voice_bot",
            "session_id": SESSION_ID,
        },
        "create_relationships": True,  # Create graph relationships
    }

    try:
        if DEBUG_MEMORY:
            print(f"→ Upserting fact: {fact_key} = {fact_value}")

        r = requests.post(
            f"{MEMORY_API_BASE}/tools/upsert_fact",
            headers=mem_headers(),
            json=payload,
            timeout=6,
        )
        r.raise_for_status()
        result = r.json()

        if DEBUG_MEMORY:
            replaced = result.get("replaced_count", 0)
            if replaced > 0:
                print(f"✓ Updated fact: {fact_key} = {fact_value} (replaced {replaced} old value(s))")
            else:
                print(f"✓ Stored new fact: {fact_key} = {fact_value}")
    except Exception as e:
        print(f"Fact upsert error: {e}")


# Patterns that indicate user is stating a personal fact
FACT_TRIGGER_PATTERNS = [
    r"\bmy\s+\w+\s+is\b",              # my X is Y
    r"\bmy\s+\w+",                      # my X (name, dog, wife, etc.)
    r"\bmy\s+favorite\b",              # my favorite X (color, food, etc.)
    r"\bi\s+am\s+\w+",                  # I am X
    r"\bi['']m\s+\w+",                  # I'm X
    r"\bcall\s+me\b",                   # call me X
    r"\bi\s+live\s+in\b",               # I live in X
    r"\bi['']m\s+from\b",               # I'm from X
    r"\bi\s+was\s+born\b",              # I was born in X
    r"\bi\s+work\s+(at|for)\b",         # I work at/for X
    r"\bi\s+(like|love|prefer|hate)\b", # I like/love/prefer/hate X
    r"\bremember\s+(that|my)\b",        # remember that/my
    r"\bfrom\s+now\s+on\b",             # from now on
    r"\bchange\s+my\b",                 # change my X to Y
    r"\b\d+['′]?\s*\d*[\"″]?\b",        # heights: 5'11", 5′11″, 5 11
    r"\b\d+\s+feet\b",                  # 5 feet
    r"\b\d+\s+years\s+old\b",           # 30 years old
]


def extract_facts_semantic(user_text: str) -> List[Dict[str, Any]]:
    """
    Use an LLM to semantically extract stable personal facts from a single utterance.

    Returns a list of dicts:
      { "fact_key": str, "fact_value": str, "confidence": float }

    Only runs when the utterance looks like the user is stating a personal fact.
    """
    text = (user_text or "").strip()
    if not text:
        return []

    # Quick length guard - skip very short utterances that might match patterns
    # but aren't real facts (e.g., "mine too", "me as well")
    if len(text) < 10:
        return []

    # Cheap guard: only call LLM when utterance looks like a personal fact
    lowered = text.lower()
    if not any(re.search(p, lowered) for p in FACT_TRIGGER_PATTERNS):
        return []

    system_msg = (
        "You extract stable personal facts about the user from a SINGLE utterance.\n"
        "Only extract facts that are clearly about the user and likely to remain true for a while "
        "(name, preferences, location, relationships, hobbies, etc.).\n"
        "Do NOT invent facts. If no clear fact is present, return an empty list.\n"
        "Return JSON matching the provided schema."
    )

    schema = {
        "name": "fact_extraction_result",
        "schema": {
            "type": "object",
            "properties": {
                "facts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "fact_key": {
                                "type": "string",
                                "description": (
                                    "A short snake_case key describing the fact, "
                                    "e.g. 'favorite_color', 'home_city', 'first_name'."
                                ),
                            },
                            "fact_value": {
                                "type": "string",
                                "description": (
                                    "The value of the fact, cleanly extracted, "
                                    "e.g. 'green', 'San Francisco', 'Matt'."
                                ),
                            },
                            "confidence": {
                                "type": "number",
                                "description": "Confidence from 0.0 to 1.0 that this is a correct personal fact.",
                            },
                        },
                        "required": ["fact_key", "fact_value", "confidence"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["facts"],
            "additionalProperties": False,
        },
        "strict": True,
    }

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": text},
            ],
            temperature=0,
            response_format={
                "type": "json_schema",
                "json_schema": schema,
            },
        )
        content = resp.choices[0].message.content
        data = json.loads(content)
    except Exception as e:
        if DEBUG_MEMORY:
            print(f"Fact extraction error: {e}")
        return []

    raw_facts = data.get("facts", []) if isinstance(data, dict) else []
    results: List[Dict[str, Any]] = []

    for f in raw_facts:
        try:
            key = str(f.get("fact_key", "")).strip()
            value = str(f.get("fact_value", "")).strip()
            conf = f.get("confidence", 0.0)
            # Safely convert confidence to float and clamp to [0.0, 1.0]
            try:
                conf = float(conf)
            except (TypeError, ValueError):
                conf = 0.0
            conf = max(0.0, min(conf, 1.0))
        except Exception:
            continue

        # Basic validation / guardrails
        if not key or not value:
            continue
        if conf < 0.7:
            # Don't store low-confidence guesses
            continue

        # Normalize fact_key to lowercase snake_case
        norm_key = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
        if not norm_key:
            continue

        # Avoid junk like 'just', 'thing', etc.
        if value.lower() in {"just", "thing", "stuff", "something", "anything"}:
            continue

        # Strip trailing punctuation like '?' or '.' from the value
        value = value.rstrip(" .!?")

        # Avoid absurdly long values
        if len(value) > 80:
            continue

        results.append({
            "fact_key": norm_key,
            "fact_value": value,
            "confidence": conf,
        })

    return results
