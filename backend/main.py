"""
backend/main.py
===============
FastAPI Backend API for YouTube RAG Chatbot.
Integrates TiDB Cloud Serverless (Vector + Relational), Groq LLM, Whisper, and JWT Auth.
"""

import json
import os
import sys
from pathlib import Path

# Ensure backend root is always in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import (
    GROQ_API_KEY,
    GROQ_MODEL,
)
from database import (
    init_tidb_schema,
    save_chat_message,
    get_chat_history,
    clear_chat_history,
    get_user_videos,
)
from ingestion.youtube_loader import (
    extract_video_id,
    get_transcript_with_timestamps,
    format_timestamp,
    TranscriptError,
)
from ingestion.chunker import create_documents_from_segments
from retrieval.vector_store import (
    store_documents_in_tidb,
    get_vector_store_for_video,
    TiDBVectorStore,
)
from llm.rag import answer_question
from llm.summarizer import summarize_transcript
from llm.feedback_store import record_feedback, get_feedback_stats
from utils.auth import (
    register_user,
    authenticate_user,
    create_access_token,
    get_current_user,
)


app = FastAPI(
    title="YouTube RAG API",
    description="FastAPI Backend for YouTube Transcript AI ChatBot powered by TiDB Cloud Vector Search & Groq.",
    version="2.0.0",
)

# ── CORS Middleware for React frontend ───────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    """Initialize TiDB schema on startup if configured."""
    try:
        init_tidb_schema()
        print("[STARTUP] Connected to TiDB Cloud & Initialized Schema.")
    except Exception as e:
        print(f"[STARTUP WARNING] TiDB Cloud status: {e}")


# ── Pydantic Request/Response Models ─────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    identifier: str
    password: str


class ProcessVideoRequest(BaseModel):
    url: str
    force_whisper: bool = False
    preferred_language: str = "en"


class ChatRequest(BaseModel):
    video_id: str
    question: str


class FeedbackRequest(BaseModel):
    video_id: str
    question: str
    answer: str
    rating: int  # 1 for positive, -1 for negative
    comment: Optional[str] = None


# ── Health Check ─────────────────────────────────────────────────────────────

@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "service": "YouTube RAG FastAPI",
        "model": GROQ_MODEL,
    }


# ── Authentication Endpoints ─────────────────────────────────────────────────

@app.post("/api/auth/register")
def register(req: RegisterRequest):
    success, message = register_user(
        username=req.username,
        email=req.email,
        password=req.password,
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@app.post("/api/auth/login")
def login(req: LoginRequest):
    user = authenticate_user(req.identifier, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password.",
        )
    token = create_access_token(data={"sub": user["username"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
        },
    }


@app.get("/api/auth/me")
def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    return {"user": current_user}


# ── Video Processing & Ingestion Endpoint ────────────────────────────────────

@app.post("/api/video/process")
async def process_video(
    req: ProcessVideoRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """
    1. Extract YouTube Video ID
    2. Check if already indexed in TiDB Vector Store
    3. If not, fetch transcript segments (via API or Whisper fallback)
    4. Chunk transcript into timestamped segments
    5. Embed & index into TiDB Cloud Serverless
    """
    try:
        video_id = extract_video_id(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Check if existing vector index exists in TiDB
    existing_store = get_vector_store_for_video(video_id)
    if existing_store and not req.force_whisper:
        return {
            "video_id": video_id,
            "status": "already_indexed",
            "message": "Video is already indexed in TiDB Cloud.",
            "source": "tidb_cache",
        }

    try:
        segments, source_used = get_transcript_with_timestamps(
            url=req.url,
            force_whisper=req.force_whisper,
            languages=[req.preferred_language, "en", "hi"],
        )
    except TranscriptError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

    if not segments:
        raise HTTPException(
            status_code=404,
            detail="No transcript available for this video.",
        )

    # Chunk transcript with timestamp metadata
    chunks = create_documents_from_segments(segments, video_id=video_id)
    if not chunks:
        raise HTTPException(status_code=500, detail="Failed to create transcript chunks.")

    # Store in TiDB Cloud Vector Table
    store_documents_in_tidb(chunks, video_id=video_id)

    return {
        "video_id": video_id,
        "status": "indexed_successfully",
        "chunks_count": len(chunks),
        "source": source_used,
        "message": f"Successfully indexed {len(chunks)} chunks into TiDB Cloud.",
    }


# ── Chat & RAG Endpoints ─────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat_endpoint(
    req: ChatRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """
    Answer question using RAG over TiDB Vector Store.
    """
    video_id = req.video_id
    vector_store = get_vector_store_for_video(video_id)

    if not vector_store:
        raise HTTPException(
            status_code=404,
            detail="Video has not been processed yet. Please index it first.",
        )

    username = current_user["username"] if current_user else "anonymous"

    # Save user message to TiDB
    save_chat_message(username=username, video_id=video_id, role="user", message=req.question)

    answer, source_docs = answer_question(
        vector_store=vector_store,
        question=req.question,
    )

    # Format citations
    citations = []
    for doc in source_docs:
        start_sec = doc.metadata.get("start", 0.0)
        end_sec = doc.metadata.get("end", 0.0)
        citations.append({
            "start": start_sec,
            "end": end_sec,
            "timestamp": format_timestamp(start_sec),
            "text": doc.page_content,
        })

    # Save assistant message to TiDB
    save_chat_message(username=username, video_id=video_id, role="assistant", message=answer)

    return {
        "answer": answer,
        "citations": citations,
    }


# ── Summarization Endpoint ───────────────────────────────────────────────────

@app.post("/api/summary")
async def get_video_summary(
    req: ProcessVideoRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """Generate a structured summary for the video."""
    video_id = extract_video_id(req.url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL.")

    # Retrieve chunks
    conn = get_vector_store_for_video(video_id)
    if not conn:
        raise HTTPException(
            status_code=404,
            detail="Please process and index the video first before generating summary.",
        )

    # Get raw transcript text
    from database import get_db_connection
    c = get_db_connection()
    try:
        with c.cursor() as cursor:
            cursor.execute(
                "SELECT page_content FROM transcript_chunks WHERE video_id = %s ORDER BY chunk_index ASC",
                (video_id,),
            )
            rows = cursor.fetchall()
            full_text = " ".join([r["page_content"] for r in rows])
    finally:
        c.close()

    if not full_text:
        raise HTTPException(status_code=404, detail="No transcript content found.")

    summary = summarize_transcript(full_text)
    return {"video_id": video_id, "summary": summary}


# ── Chat History Endpoints ───────────────────────────────────────────────────

@app.get("/api/history/{video_id}")
def get_history(
    video_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    history = get_chat_history(username=current_user["username"], video_id=video_id)
    return {"history": history}


@app.delete("/api/history/{video_id}")
def clear_history(
    video_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    clear_chat_history(username=current_user["username"], video_id=video_id)
    return {"success": True, "message": "Chat history cleared."}


@app.get("/api/user/videos")
def get_my_videos(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    videos = get_user_videos(username=current_user["username"])
    return {"videos": videos}


# ── Feedback Endpoints ───────────────────────────────────────────────────────

@app.post("/api/feedback")
def submit_feedback(
    req: FeedbackRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    username = current_user["username"] if current_user else "anonymous"
    success = record_feedback(
        video_id=req.video_id,
        question=req.question,
        answer=req.answer,
        rating=req.rating,
        username=username,
        comment=req.comment,
    )
    return {"success": success}


@app.get("/api/feedback/stats/{video_id}")
def feedback_stats(video_id: str):
    stats = get_feedback_stats(video_id=video_id)
    return {"stats": stats}
