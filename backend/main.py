"""
backend/main.py
===============
FastAPI Backend API for YouTube RAG Chatbot.
Integrates TiDB Cloud Serverless (Vector + Relational), Groq LLM, Whisper, and JWT Auth.
"""

import json
import os
import sys
import threading
from pathlib import Path

# Ensure backend root is always in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
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
from retrieval.embeddings import get_embedding_model
from fastapi.responses import FileResponse, StreamingResponse
from retrieval.vector_store import (
    store_documents_in_tidb,
    get_vector_store_for_video,
    TiDBVectorStore,
)
from llm.rag import answer_question, answer_question_stream
from llm.summarizer import summarize_transcript
from utils.auth import (
    register_user,
    authenticate_user,
    authenticate_or_create_google_user,
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


def _warmup_resources():
    """Pre-warm database connection and embedding model in background thread."""
    try:
        print("[STARTUP] Pre-warming embedding model in memory...")
        get_embedding_model()
        print("[STARTUP] Embedding model pre-warmed successfully!")
    except Exception as e:
        print(f"[STARTUP WARNING] Embedding pre-warm notice: {e}")


@app.on_event("startup")
def startup_event():
    """Initialize TiDB schema and pre-warm models on startup."""
    try:
        init_tidb_schema()
        print("[STARTUP] Connected to TiDB Cloud & Initialized Schema.")
    except Exception as e:
        print(f"[STARTUP WARNING] TiDB Cloud status: {e}")

    # Launch model warmup in a daemon thread so server starts immediately without cold-start blocking
    threading.Thread(target=_warmup_resources, daemon=True).start()


# ── Pydantic Request/Response Models ─────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    identifier: str
    password: str


class GoogleAuthRequest(BaseModel):
    credential: str


class ProcessVideoRequest(BaseModel):
    url: str
    force_whisper: bool = False
    preferred_language: str = "en"


class ChatRequest(BaseModel):
    video_id: str
    question: str


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


@app.post("/api/auth/google")
def google_auth(req: GoogleAuthRequest):
    """Authenticate or automatically register user using verified Google ID token."""
    user = authenticate_or_create_google_user(req.credential)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google authentication failed or invalid token.",
        )
    token = create_access_token(data={"sub": user["username"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user.get("display_name") or user["username"],
            "email": user["email"],
            "avatar": user.get("avatar"),
        },
    }


@app.get("/api/auth/me")
def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    return {"user": current_user}


# ── Video Processing & Ingestion Endpoint ────────────────────────────────────

@app.post("/api/video/process")
def process_video(
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
def chat_endpoint(
    req: ChatRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """
    Answer question using RAG over TiDB Vector Store (Threadpooled).
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


@app.post("/api/chat/stream")
def chat_stream_endpoint(
    req: ChatRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """
    Stream answer tokens in real-time using Server-Sent Events (SSE).
    Sends citations immediately, followed by token deltas (<300ms time to first token).
    """
    video_id = req.video_id
    vector_store = get_vector_store_for_video(video_id)

    if not vector_store:
        raise HTTPException(
            status_code=404,
            detail="Video has not been processed yet. Please index it first.",
        )

    username = current_user["username"] if current_user else "anonymous"
    save_chat_message(username=username, video_id=video_id, role="user", message=req.question)

    def event_generator():
        accumulated_answer = []
        for token, source_docs in answer_question_stream(vector_store=vector_store, question=req.question):
            if source_docs:
                citations = [
                    {
                        "start": doc.metadata.get("start", 0.0),
                        "end": doc.metadata.get("end", 0.0),
                        "timestamp": format_timestamp(doc.metadata.get("start", 0.0)),
                        "text": doc.page_content,
                    }
                    for doc in source_docs
                ]
                yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"
            if token:
                accumulated_answer.append(token)
                yield f"data: {json.dumps({'type': 'token', 'token': token})}\n\n"

        full_answer = "".join(accumulated_answer)
        if full_answer:
            save_chat_message(username=username, video_id=video_id, role="assistant", message=full_answer)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")



# ── Summarization Endpoint ───────────────────────────────────────────────────

@app.post("/api/summary")
def get_video_summary(
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
    try:
        videos = get_user_videos(username=current_user["username"])
        return {"videos": videos}
    except Exception as e:
        print(f"[API ERROR] /api/user/videos failed: {e}")
        return {"videos": []}


# ── Production SPA Static Mounting (Railway / Docker Deployment) ──────────────
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

STATIC_DIRS = [
    Path(__file__).resolve().parent / "static",
    Path(__file__).resolve().parent.parent / "frontend" / "dist",
]

for s_dir in STATIC_DIRS:
    if s_dir.exists() and (s_dir / "index.html").exists():
        if (s_dir / "assets").exists():
            app.mount("/assets", StaticFiles(directory=str(s_dir / "assets")), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            if full_path.startswith("api"):
                raise HTTPException(status_code=404, detail="API route not found")
            target = s_dir / full_path
            if target.is_file():
                return FileResponse(target)
            return FileResponse(s_dir / "index.html")
        print(f"[DEPLOYMENT] Mounted SPA static assets from {s_dir}")
        break


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "127.0.0.1")
    reload = os.getenv("ENV", "development").lower() != "production"
    uvicorn.run("main:app", host=host, port=port, reload=reload)

