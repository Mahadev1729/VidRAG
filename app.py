"""
app.py
======
Streamlit UI and pipeline orchestration.

RESPONSIBILITY
--------------
app.py is ONLY the UI layer.  It orchestrates the pipeline by
calling the right module at the right time, but contains zero
implementation of ingestion, embedding, FAISS, or LLM logic.

PIPELINE ORCHESTRATION
-----------------------
app.py
  ↓ ingestion.youtube_loader  → transcript segments
  ↓ chunker                   → LangChain Documents
  ↓ retrieval.vector_store    → FAISS index (in memory + on disk)
  ↓ llm.rag                   → answer + source documents
  ↓ llm.summarizer            → video summary

SESSION STATE vs CACHE_RESOURCE
--------------------------------
st.cache_resource  → for HEAVY resources shared across ALL users
                     (ML models: embedding model, Whisper model)
                     Loaded once per server process. Never re-loaded.

st.session_state   → for per-USER, per-SESSION data
                     (current video ID, vector store, transcript,
                      conversation history)
                     Specific to one browser tab. Cleared on page refresh.
"""

import os
import uuid
from pathlib import Path

import streamlit as st

# ── Config ────────────────────────────────────────────────────────────────────
from config import (
    GROQ_API_KEY,
    BASE_DIR,
    INDEXES_DIR,
    SUMMARIES_DIR,
    TRANSCRIPTS_DIR,
)

# ── Ingestion ─────────────────────────────────────────────────────────────────
from ingestion.youtube_loader import (
    TranscriptError,
    extract_video_id,
    get_transcript_with_timestamps,
    save_transcript,
)

# ── Chunker ───────────────────────────────────────────────────────────────────
from ingestion.chunker import create_documents

# ── Retrieval ─────────────────────────────────────────────────────────────────
from retrieval.vector_store import (
    create_vector_store,
    load_vector_store,
    save_vector_store,
)

# ── LLM ───────────────────────────────────────────────────────────────────────
from llm.rag import answer_question
from llm.summarizer import summarize_video

# ── Chat History (utility, kept at root) ─────────────────────────────────────
from chat_history import (
    init_db,
    save_message,
    get_messages,
    clear_messages,
)


# ============================================================
# 1. API KEY CHECK
# ============================================================
# config.py loads the key from .env.  We check it here before
# rendering any UI — if it is missing we stop immediately with
# a clear error message.

if not GROQ_API_KEY:
    # Streamlit Cloud Secrets fallback
    try:
        _secret = st.secrets.get("GROQ_API_KEY", "")
        if _secret:
            os.environ["GROQ_API_KEY"] = _secret
    except Exception:
        pass

if not GROQ_API_KEY and not os.environ.get("GROQ_API_KEY"):
    st.error("❌ GROQ_API_KEY is not configured.")
    st.info(
        "For local use, add GROQ_API_KEY to .env. "
        "For Streamlit Cloud, add it under App Settings → Secrets."
    )
    st.stop()


# ============================================================
# 2. DATABASE + PAGE CONFIG
# ============================================================

init_db()

st.set_page_config(
    page_title="YouTube RAG Assistant",
    page_icon="🎥",
    layout="wide",
)


# ============================================================
# 3. SESSION STATE
# ============================================================
# All per-user state lives here.
# Streamlit re-runs app.py from top to bottom on every interaction.
# Session state persists values across those re-runs for the same user.

defaults = {
    "session_id":         str(uuid.uuid4()),
    "vector_store":       None,
    "documents":          None,
    "video_id":           None,
    "summary":            None,
    "youtube_url":        None,
    "transcript_segments": None,
    "transcript_source":  None,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# 4. HELPER FUNCTIONS (UI utilities — belong in app.py)
# ============================================================

def format_timestamp(seconds) -> str:
    """Convert seconds to MM:SS or HH:MM:SS display string."""
    seconds = int(float(seconds))
    hours   = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs    = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def make_youtube_url(video_id: str, start_seconds: int) -> str:
    """Build a YouTube URL that jumps to a specific timestamp."""
    return f"https://www.youtube.com/watch?v={video_id}&t={int(start_seconds)}s"


def get_timestamp_for_position(full_text, segments, position):
    """Find the segment start time for a character position in the transcript."""
    current = 0
    for segment in segments:
        seg_end = current + len(segment["text"])
        if position <= seg_end:
            return segment["start"]
        current = seg_end + 1
    return segments[-1]["end"] if segments else 0


def add_timestamp_metadata(documents, transcript_segments, video_id):
    """
    Attach start/end timestamps to each Document's metadata.

    WHY AFTER CHUNKING?
    The chunker splits flat text.  It has no knowledge of where
    each chunk falls in the original timeline.  We compute that
    here by searching for the chunk text inside the full transcript
    and mapping its character position to the corresponding segment
    timestamp.
    """
    if not documents or not transcript_segments:
        return

    full_text = " ".join(s["text"] for s in transcript_segments)
    if not full_text:
        return

    current_pos = 0

    for doc in documents:
        chunk_text = doc.page_content
        if not chunk_text:
            continue

        chunk_pos = full_text.find(chunk_text, current_pos)
        if chunk_pos == -1:
            chunk_pos = current_pos

        chunk_end = chunk_pos + len(chunk_text)

        doc.metadata["video_id"] = video_id
        doc.metadata["start"]    = get_timestamp_for_position(
            full_text, transcript_segments, chunk_pos
        )
        doc.metadata["end"]      = get_timestamp_for_position(
            full_text, transcript_segments, chunk_end
        )

        current_pos = max(current_pos, chunk_end)


def show_transcript_source_message(source):
    """Display how the transcript was obtained."""
    if source == "whisper":
        st.info(
            "YouTube captions unavailable. "
            "Transcript generated using Whisper."
        )
    else:
        st.success("Transcript retrieved from YouTube captions.")


def fetch_transcript_with_progress(youtube_url):
    """
    Fetch transcript and show Whisper progress in the UI.

    The status_callback passes Whisper progress messages
    (e.g. "Downloading audio...") directly into a Streamlit
    placeholder so the user sees live updates.
    """
    status_container = st.empty()
    messages = []

    def status_callback(message):
        messages.append(message)
        status_container.info(message)

    segments, source = get_transcript_with_timestamps(
        youtube_url,
        status_callback=status_callback,
    )

    status_container.empty()
    return segments, source


# ============================================================
# 5. TITLE
# ============================================================

st.title("🎥 YouTube RAG Assistant")
st.write(
    "Paste a YouTube video URL to summarise the video "
    "and ask questions about its content."
)


# ============================================================
# 6. URL INPUT
# ============================================================

youtube_url = st.text_input(
    "🔗 YouTube Video URL",
    placeholder="https://www.youtube.com/watch?v=... or https://youtu.be/...",
)


# ============================================================
# 7. PROCESS VIDEO
# ============================================================

process_button = st.button("🚀 Process Video", type="primary")

if process_button:

    if not youtube_url.strip():
        st.warning("Please enter a YouTube URL.")

    else:
        try:

            # ── Step 1: Extract video ID ──────────────────────────────────────
            with st.spinner("Extracting video ID..."):
                video_id = extract_video_id(youtube_url)

            st.session_state.video_id    = video_id
            st.session_state.youtube_url = youtube_url
            st.info(f"🎬 Video ID: `{video_id}`")

            # ── Step 2: Check for existing FAISS index ────────────────────────
            index_dir  = INDEXES_DIR / video_id
            index_file = index_dir / "index.faiss"
            pkl_file   = index_dir / "index.pkl"
            existing   = index_file.exists() and pkl_file.exists()

            # ── Step 3a: Load existing index ──────────────────────────────────
            if existing:
                st.info("♻️ Existing FAISS index found. Loading saved vector store...")

                with st.spinner("Loading vector store..."):
                    vector_store = load_vector_store(index_dir)
                st.session_state.vector_store = vector_store

                # Load transcript (needed for timestamp metadata)
                with st.spinner("Loading transcript..."):
                    segments, source = fetch_transcript_with_progress(youtube_url)
                st.session_state.transcript_segments = segments
                st.session_state.transcript_source   = source
                show_transcript_source_message(source)

                # Load saved summary if available
                summary_file = SUMMARIES_DIR / f"{video_id}.txt"
                if summary_file.exists():
                    st.session_state.summary = summary_file.read_text(encoding="utf-8")

                st.success("♻️ Existing video data loaded successfully!")

            # ── Step 3b: Process new video ────────────────────────────────────
            else:

                # Get transcript (YouTube captions or Whisper)
                segments, source = fetch_transcript_with_progress(youtube_url)

                if not segments:
                    st.error("No transcript was found.")
                    st.stop()

                st.session_state.transcript_segments = segments
                st.session_state.transcript_source   = source
                show_transcript_source_message(source)

                # Build plain text
                transcript = " ".join(s["text"] for s in segments)
                if not transcript.strip():
                    st.error("Transcript is empty.")
                    st.stop()

                duration = segments[-1]["end"]
                st.info(f"⏱️ Approximate duration: {format_timestamp(duration)}")

                # Save transcript to disk
                TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
                with st.spinner("Saving transcript..."):
                    save_transcript(transcript, video_id, TRANSCRIPTS_DIR)

                # Chunk
                with st.spinner("Splitting transcript into chunks..."):
                    documents = create_documents(transcript, video_id)

                if not documents:
                    st.error("No chunks were created.")
                    st.stop()

                st.info(f"📚 Created {len(documents)} chunks.")

                # Attach timestamps to chunk metadata
                add_timestamp_metadata(documents, segments, video_id)

                st.session_state.documents = documents

                # Embed + build FAISS
                st.info("🔧 Building knowledge base...")
                with st.spinner("Creating embeddings and FAISS index..."):
                    vector_store = create_vector_store(documents)

                if vector_store is None:
                    st.error("Failed to create vector store.")
                    st.stop()

                # Save FAISS to disk
                with st.spinner("Saving index..."):
                    save_vector_store(vector_store, index_dir)

                st.success("✅ FAISS index saved!")
                st.session_state.vector_store = vector_store

                # Generate summary
                with st.spinner("Generating video summary..."):
                    summary = summarize_video(documents)

                st.session_state.summary = summary

                # Save summary
                SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
                (SUMMARIES_DIR / f"{video_id}.txt").write_text(
                    summary, encoding="utf-8"
                )

                st.success("🎉 Video processed successfully!")

        except ValueError as error:
            st.error(str(error))

        except TranscriptError as error:
            st.error(str(error))

        except Exception as error:
            st.error(
                "An unexpected error occurred while processing the video. "
                "Please check the URL and try again."
            )
            st.exception(error)


# ============================================================
# 8. SUMMARY
# ============================================================

if st.session_state.summary:
    st.divider()
    st.header("📄 Video Summary")
    st.markdown(st.session_state.summary)


# ============================================================
# 9. CHAT HISTORY
# ============================================================

if st.session_state.video_id:
    messages = get_messages(
        st.session_state.session_id,
        st.session_state.video_id,
    )

    if messages:
        st.divider()
        st.subheader("💬 Conversation History")

        for role, message in messages:
            with st.chat_message(role):
                st.write(message)

        if st.button("🗑️ Clear Chat"):
            clear_messages(
                st.session_state.session_id,
                st.session_state.video_id,
            )
            st.rerun()


# ============================================================
# 10. ASK QUESTIONS
# ============================================================

st.divider()
st.header("💬 Ask Questions About the Video")

question = st.text_input(
    "Your question",
    placeholder="Example: What is the main topic of this video?",
)

ask_button = st.button("🔍 Ask Question")

if ask_button:

    if st.session_state.vector_store is None:
        st.warning("Please process a YouTube video first.")

    elif not question.strip():
        st.warning("Please enter a question.")

    else:
        try:
            # Save user question
            save_message(
                st.session_state.session_id,
                st.session_state.video_id,
                "user",
                question,
            )

            # RAG: retrieve + answer (returns answer AND source docs in one call)
            with st.spinner("Searching the video and generating answer..."):
                answer, source_docs = answer_question(
                    st.session_state.vector_store,
                    question,
                )

            # Save assistant answer
            save_message(
                st.session_state.session_id,
                st.session_state.video_id,
                "assistant",
                answer,
            )

            # Display answer
            st.subheader("🤖 Answer")
            st.write(answer)

            # ── Timestamp Sources ─────────────────────────────────────────────
            # answer_question() already returns source_docs — no second
            # similarity_search() needed here.
            if source_docs:
                st.subheader("📍 Relevant Video Sources")
                displayed_times = set()
                source_number   = 1

                for doc in source_docs:
                    start = doc.metadata.get("start")
                    end   = doc.metadata.get("end")

                    if start is None:
                        continue

                    start_seconds = int(float(start))
                    if start_seconds in displayed_times:
                        continue
                    displayed_times.add(start_seconds)

                    time_text = format_timestamp(start_seconds)
                    if end is not None:
                        time_text += f" – {format_timestamp(int(float(end)))}"

                    source_url = make_youtube_url(
                        st.session_state.video_id, start_seconds
                    )

                    st.markdown(
                        f"**Source {source_number}:** "
                        f"`{time_text}` → "
                        f"[▶ Watch at {format_timestamp(start_seconds)}]({source_url})"
                    )
                    source_number += 1

        except Exception as e:
            st.error("❌ Error while answering:")
            st.exception(e)


# ============================================================
# 11. VIDEO INFORMATION
# ============================================================

if st.session_state.video_id:
    st.divider()
    st.subheader("ℹ️ Video Information")

    st.write(f"**Video ID:** `{st.session_state.video_id}`")

    if st.session_state.documents:
        st.write(f"**Number of chunks:** {len(st.session_state.documents)}")

    if st.session_state.transcript_segments:
        duration = st.session_state.transcript_segments[-1]["end"]
        st.write(f"**Approximate duration:** {format_timestamp(duration)}")

    if st.session_state.transcript_source:
        label = (
            "Whisper (audio transcription)"
            if st.session_state.transcript_source == "whisper"
            else "YouTube captions"
        )
        st.write(f"**Transcript source:** {label}")
