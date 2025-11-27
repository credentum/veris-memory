"""
Claude Agent Integration

Functions for detecting code tasks and calling Claude CLI.
"""

import json
import subprocess
from typing import Optional

import requests

from config import (
    client,
    DEBUG_MEMORY,
    REPO_PATHS,
    DEFAULT_REPO,
    CODE_HINT_WORDS,
    MEMORY_API_BASE,
    USER_ID,
    SESSION_ID,
    mem_headers,
)


def detect_agent_task_llm(text: str) -> tuple[bool, str]:
    """
    Use LLM to detect if user wants a code/repo task.
    Returns: (is_code_task, detected_repo_name or None)
    """
    # Quick exit for very short or obvious chat messages
    lower = text.lower()
    if len(text) < 10 or any(greet in lower for greet in ["hello", "hi ", "hey ", "thanks", "bye", "good morning"]):
        return False, None

    # Build repo list for the prompt
    repo_names = list(REPO_PATHS.keys())

    prompt = f"""Classify this user message into one of two categories:

1. CODE_TASK: Needs to READ/ANALYZE actual source code files in a repository. Examples: review code, find bugs, explain implementation, check a function, look at files.

2. CHAT: Everything else - including memory/knowledge queries, personal questions, general chat, asking what you know or remember.

IMPORTANT: Asking about "memory", "what you know", "what's stored", or "search for information about X" is NOT a code task - these are memory queries that don't need file system access.

User said: "{text}"

Available repos: {repo_names}

Respond with ONLY a JSON object (no markdown):
{{"is_code_task": true/false, "repo": "repo_name or null", "confidence": 0.0-1.0}}

Examples:
- "Review the auth function in voicebot" -> {{"is_code_task": true, "repo": "voicebot", "confidence": 0.95}}
- "How does the TTS code work?" -> {{"is_code_task": true, "repo": null, "confidence": 0.9}}
- "Check the code in veris" -> {{"is_code_task": true, "repo": "veris", "confidence": 0.95}}
- "Search memory for voicebot updates" -> {{"is_code_task": false, "repo": null, "confidence": 0.95}}
- "What do you know about the project?" -> {{"is_code_task": false, "repo": null, "confidence": 0.95}}
- "What's stored about voicebot?" -> {{"is_code_task": false, "repo": null, "confidence": 0.9}}
- "What's my favorite color?" -> {{"is_code_task": false, "repo": null, "confidence": 0.99}}
- "Hello, how are you?" -> {{"is_code_task": false, "repo": null, "confidence": 0.99}}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=100,
        )
        result_text = response.choices[0].message.content.strip()

        # Parse JSON response
        result = json.loads(result_text)
        is_code = result.get("is_code_task", False)
        repo = result.get("repo")
        confidence = result.get("confidence", 0.5)

        if DEBUG_MEMORY:
            print(f"→ Intent detection: is_code={is_code}, repo={repo}, confidence={confidence}")

        # Only trigger for high confidence code tasks
        if is_code and confidence >= 0.7:
            return True, repo
        return False, None

    except Exception as e:
        if DEBUG_MEMORY:
            print(f"→ Intent detection error: {e}")
        # Fallback to keyword check on error
        if any(word in lower for word in CODE_HINT_WORDS):
            return True, None
        return False, None


def detect_agent_task(text: str) -> tuple[bool, str, str]:
    """
    Detect if user wants Claude to do a code task.
    Returns: (is_agent_task, repo_path, task_description)
    """
    lower = text.lower()

    # Use LLM for intent detection
    is_code_task, detected_repo = detect_agent_task_llm(text)

    if not is_code_task:
        return False, "", ""

    # Determine repo path
    repo_path = DEFAULT_REPO
    if detected_repo and detected_repo in REPO_PATHS:
        repo_path = REPO_PATHS[detected_repo]
    else:
        # Fallback: check text for repo names
        for repo_name, path in REPO_PATHS.items():
            if repo_name in lower:
                repo_path = path
                break

    return True, repo_path, text


def call_claude_agent(task: str, repo_path: str, timeout: int = 120) -> str:
    """
    Call Claude CLI to perform a code task.
    Returns the agent's response text.
    """
    try:
        if DEBUG_MEMORY:
            print(f"→ Calling Claude agent: {task}")
            print(f"→ Repo path: {repo_path}")

        result = subprocess.run(
            ["claude", "-p", task, "--output-format", "text"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=timeout,
        )

        response = result.stdout.strip()
        if result.returncode != 0 and result.stderr:
            response = f"Agent encountered an issue: {result.stderr.strip()}"

        if DEBUG_MEMORY:
            print(f"→ Agent response length: {len(response)} chars")

        # Truncate very long responses for TTS
        if len(response) > 2000:
            response = response[:2000] + "... (response truncated for voice output)"

        return response or "I completed the task but have nothing specific to report."

    except subprocess.TimeoutExpired:
        return "That's a broad request and my analysis hit its time limit. Try asking about a specific file, function, or feature - for example: 'Review the fact extraction in app.py' or 'Check the TTS code for issues'."
    except FileNotFoundError:
        return "I couldn't find the Claude CLI. Make sure it's installed and in your PATH."
    except Exception as e:
        return f"I encountered an error while analyzing: {str(e)}"


def store_agent_finding(task: str, response: str, repo_path: str) -> Optional[str]:
    """
    Auto-store significant agent findings to Veris as a report.
    Returns the stored ID or None.
    """
    if not VERIS_API_KEY:
        return None

    # Only store findings that look like they contain issues/bugs/suggestions
    lower_response = response.lower()
    is_significant = any(word in lower_response for word in [
        "bug", "issue", "error", "problem", "fix", "should", "could",
        "improvement", "suggestion", "recommend", "warning", "missing",
        "incorrect", "wrong", "broken", "fail"
    ])

    if not is_significant:
        if DEBUG_MEMORY:
            print("→ Agent response not significant enough to store as finding")
        return None

    # Extract a title from the task
    title = task[:80] + "..." if len(task) > 80 else task

    payload = {
        "type": "log",
        "content": {
            "title": f"Agent Finding: {title}",
            "task": task,
            "finding": response[:3000],  # Limit size
            "repo": repo_path,
            "finding_type": "code_review",
        },
        "metadata": {
            "source": "voicebot_agent",
            "user_id": USER_ID,
            "session_id": SESSION_ID,
            "auto_generated": True,
        }
    }

    try:
        r = requests.post(
            f"{MEMORY_API_BASE}/tools/store_context",
            headers=mem_headers(),
            json=payload,
            timeout=5,
        )
        if r.status_code == 200:
            data = r.json()
            finding_id = data.get("id")
            if DEBUG_MEMORY:
                print(f"→ Stored agent finding to Veris: {finding_id}")
            return finding_id
    except Exception as e:
        if DEBUG_MEMORY:
            print(f"→ Failed to store agent finding: {e}")

    return None
