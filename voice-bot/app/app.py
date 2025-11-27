"""
VoiceBot Backend

FastAPI application with voice conversation capabilities.
Integrates with Veris Memory for persistent context and Claude CLI for code tasks.
"""

import tempfile
import time
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Import configuration
from config import (
    client,
    DEBUG_MEMORY,
    VERIS_API_KEY,
    SESSION_ID,
    CHAT_HISTORY,
    MAX_CHAT_HISTORY,
)

# Import modules
from agent import detect_agent_task, call_claude_agent, store_agent_finding
from memory import (
    get_user_facts,
    retrieve_context,
    filter_memory_results,
    compress_to_memory_block,
    should_store_turn,
    store_turn,
)
from facts import extract_facts_semantic, store_fact


# ---- FastAPI App ----

app = FastAPI(title="VoiceBot", description="Voice assistant with memory")

# CORS - allow same-origin and common dev ports
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8002",
        "http://127.0.0.1:8002",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def suffix_from_content_type(ctype: str) -> str:
    """Map content-type to file extension"""
    ctype = (ctype or "").lower()
    if "webm" in ctype:
        return ".webm"
    if "ogg" in ctype:
        return ".ogg"
    if "mp4" in ctype or "aac" in ctype:
        return ".mp4"
    return ".wav"


@app.post("/api/turn")
async def turn(audio: UploadFile = File(...)):
    """
    Handle one conversation turn with memory:
    1. Receive audio blob
    2. Transcribe (STT)
    3. Retrieve relevant memories from Veris
    4. Get LLM response with memory context
    5. Store turn to Veris
    6. Generate speech (TTS)
    7. Return audio
    """
    started = time.time()

    # 1) Save audio correctly
    suffix = suffix_from_content_type(audio.content_type)
    tmp_path = Path(tempfile.mktemp(suffix=suffix))
    tmp_path.write_bytes(await audio.read())

    try:
        # 2) STT - Transcribe audio
        with open(tmp_path, "rb") as f:
            stt = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="en",  # Force English to prevent wrong language detection from background noise
            )
        user_text = stt.text.strip()
        if DEBUG_MEMORY:
            print(f"User said: {user_text}")

        # 2b) Check if this is a Claude agent task (code review, analysis, etc.)
        is_agent_task, repo_path, task = detect_agent_task(user_text)
        if is_agent_task:
            if DEBUG_MEMORY:
                print(f"→ Agent task detected, routing to Claude CLI")

            # Call Claude agent
            assistant_text = call_claude_agent(task, repo_path)

            # Store the interaction to memory
            duration_ms = int((time.time() - started) * 1000)
            store_turn(
                user_text=user_text,
                assistant_text=assistant_text,
                duration_ms=duration_ms
            )

            # Auto-store significant findings to Veris for dev team
            store_agent_finding(task, assistant_text, repo_path)

            # Generate TTS response
            tts = client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=assistant_text,
                response_format="mp3",
            )

            return Response(
                content=tts.content,
                media_type="audio/mpeg",
                headers={"Content-Disposition": "inline; filename=response.mp3"}
            )

        # 3) Retrieve memory with intelligent expansion for personal questions
        memory_results = []
        direct_facts = []  # Facts from get_user_facts endpoint (complete recall)

        # Check if user is asking about personal information
        lower_text = user_text.lower()
        is_personal_query = any(phrase in lower_text for phrase in [
            # Identity questions
            "what is my", "who am i", "what's my", "what do you know about me",
            "do you know my", "remember my", "tell me about me",
            # Preference questions
            "my favorite", "my favourite",
            # Location questions
            "where do i live", "where am i", "my location"
        ])

        # For broad "about me" queries, use get_user_facts for complete recall
        is_broad_about_me = any(phrase in lower_text for phrase in [
            "what do you know about me", "tell me about me", "what do you remember",
            "everything you know", "all my facts"
        ])

        if is_broad_about_me:
            # Use new endpoint for complete fact recall (no semantic similarity)
            direct_facts = get_user_facts()
            if DEBUG_MEMORY:
                print(f"→ Got {len(direct_facts)} facts via get_user_facts")

        if is_personal_query:
            # Also do semantic search for context/conversations
            memory_results = retrieve_context(user_text, limit=5)
            if DEBUG_MEMORY:
                print(f"Retrieved {len(memory_results)} memories from Veris")
        else:
            # Normal retrieval
            memory_results = retrieve_context(user_text, limit=5)
            if DEBUG_MEMORY:
                print(f"Retrieved {len(memory_results)} memories from Veris")

        # Filter out test/system noise before compression
        memory_results = filter_memory_results(memory_results, user_text)

        # Compress memory into LLM-friendly context (now handles facts better)
        memory_block = compress_to_memory_block(memory_results, user_text, max_items=5)

        # Build complete facts block from direct_facts (if we used get_user_facts)
        if direct_facts:
            facts_lines = ["Known facts about the user:"]
            for f in direct_facts:
                key = f.get("fact_key", "").replace("_", " ").capitalize()
                value = f.get("fact_value", "")
                if key and value:
                    facts_lines.append(f"  • {key}: {value}")
            direct_facts_block = "\n".join(facts_lines)
            # Prepend to memory block or use as-is
            if memory_block:
                memory_block = direct_facts_block + "\n\n" + memory_block
            else:
                memory_block = direct_facts_block
            if DEBUG_MEMORY:
                print(f"→ Added {len(direct_facts)} direct facts to context")

        if DEBUG_MEMORY:
            if memory_block:
                print(f"Memory context:\n{memory_block}")
            else:
                print("No relevant memory found for this query")

        # 4) LLM with memory injected + chat history for conversation flow
        messages = [
            {"role": "system", "content": "You are my personal voice assistant. Be concise, practical, and grounded. Use the memory context to recall information about the user when asked. Pay attention to recent conversation history for context on follow-up questions."},
        ]
        if memory_block:
            messages.append({"role": "system", "content": f"Memory context:\n{memory_block}\n\nUse this information to answer the user's questions, especially about their identity or preferences."})

        # Add recent chat history for conversation flow (enables "yes please", "tell me more", etc.)
        if CHAT_HISTORY:
            # Include last few exchanges for context
            recent_history = CHAT_HISTORY[-(MAX_CHAT_HISTORY * 2):]  # Each exchange = 2 messages
            messages.extend(recent_history)
            if DEBUG_MEMORY:
                print(f"→ Including {len(recent_history)} messages from chat history")

        messages.append({"role": "user", "content": user_text})

        chat = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )
        assistant_text = chat.choices[0].message.content.strip()
        if DEBUG_MEMORY:
            print(f"Assistant says: {assistant_text}")

        # Update chat history for next turn
        CHAT_HISTORY.append({"role": "user", "content": user_text})
        CHAT_HISTORY.append({"role": "assistant", "content": assistant_text})
        # Trim to max size
        while len(CHAT_HISTORY) > MAX_CHAT_HISTORY * 2:
            CHAT_HISTORY.pop(0)
        if DEBUG_MEMORY:
            print(f"→ Chat history now has {len(CHAT_HISTORY)} messages")

        # 5) Store turn to memory (with smart filtering)
        duration_ms = int((time.time() - started) * 1000)
        should_store, store_reason = should_store_turn(user_text, assistant_text)
        if DEBUG_MEMORY:
            print(f"→ Smart storage decision: store={should_store}, reason={store_reason}")
        if should_store:
            store_turn(
                user_text=user_text,
                assistant_text=assistant_text,
                duration_ms=duration_ms
            )
        else:
            print(f"⊘ Skipped storing turn (reason: {store_reason})")

        # 5b) Extract and store facts from user input (semantic LLM extractor)
        # Uses GPT-4o-mini with JSON schema to cleanly extract facts like "favorite_color: green"
        extracted_facts = extract_facts_semantic(user_text)
        if DEBUG_MEMORY and extracted_facts:
            print(f"Semantic facts extracted: {extracted_facts}")
        for fact in extracted_facts:
            store_fact(fact["fact_key"], fact["fact_value"])

        # 6) TTS - Generate speech
        tts = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=assistant_text,
            response_format="mp3",
        )

        # Get audio bytes
        audio_bytes = tts.content

        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline; filename=response.mp3"
            }
        )

    finally:
        # Clean up temp file
        if tmp_path.exists():
            tmp_path.unlink()


# ---- Static Files & Frontend ----

# Determine frontend path (works in Docker and local dev)
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if not FRONTEND_DIR.exists():
    # Fallback for Docker layout
    FRONTEND_DIR = Path("/app/frontend")


@app.get("/")
async def root():
    """Serve the frontend index.html"""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {
        "status": "VoiceBot backend with memory is running",
        "session_id": SESSION_ID,
        "memory_enabled": bool(VERIS_API_KEY)
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "session_id": SESSION_ID,
        "memory_enabled": bool(VERIS_API_KEY)
    }


# Serve static files (JS, CSS) - must be after other routes
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
