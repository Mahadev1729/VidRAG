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
# 1. PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="YouTube RAG Assistant",
    page_icon="🎥",
    layout="wide",
)


# ============================================================
# 2. API KEY CHECK
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
# 3. DATABASE
# ============================================================

init_db()

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');

    :root {
        --ink: #17212b;
        --muted: #687783;
        --line: #dce5e8;
        --paper: #f7faf9;
        --mint: #d9f4e8;
        --teal: #087f78;
        --coral: #e8664f;
    }

    .stApp {
        background: linear-gradient(135deg, #f7faf9 0%, #eef7f4 52%, #fff8f1 100%);
        color: var(--ink);
    }

    .block-container {
        max-width: 1180px;
        padding: 3.5rem 2rem 4rem;
    }

    h1, h2, h3, [data-testid="stMarkdownContainer"] strong {
        font-family: 'Space Grotesk', sans-serif;
        letter-spacing: 0;
        color: var(--ink);
    }

    p, label, input, button, textarea, [data-testid="stMarkdownContainer"] {
        font-family: 'DM Sans', sans-serif;
        letter-spacing: 0;
    }

    .hero {
        position: relative;
        overflow: hidden;
        padding: 2.25rem 2.5rem 2.35rem;
        border: 1px solid rgba(8, 127, 120, .16);
        border-radius: 18px;
        background: linear-gradient(120deg, rgba(217, 244, 232, .88), rgba(255, 248, 241, .92));
        box-shadow: 0 18px 45px rgba(32, 74, 69, .08);
    }

    .hero:after {
        content: '';
        position: absolute;
        width: 220px;
        height: 220px;
        right: -70px;
        top: -95px;
        border: 22px solid rgba(232, 102, 79, .16);
        border-radius: 50%;
    }

    .hero-kicker {
        position: relative;
        z-index: 1;
        margin: 0 0 .5rem;
        color: var(--teal);
        font-size: .76rem;
        font-weight: 700;
        letter-spacing: .12em;
        text-transform: uppercase;
    }

    .hero-title {
        position: relative;
        z-index: 1;
        margin: 0;
        font-family: 'Space Grotesk', sans-serif;
        font-size: clamp(2rem, 4vw, 3.3rem);
        line-height: 1.04;
    }

    .hero-copy {
        position: relative;
        z-index: 1;
        max-width: 650px;
        margin: .85rem 0 0;
        color: #49615f;
        font-size: 1.05rem;
    }

    .workflow {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: .75rem;
        margin: 1.1rem 0 2rem;
    }

    .workflow-step {
        display: flex;
        align-items: center;
        gap: .7rem;
        min-height: 3.2rem;
        padding: .7rem .85rem;
        border: 1px solid rgba(8, 127, 120, .12);
        border-radius: 12px;
        background: rgba(255, 255, 255, .58);
        color: #49615f;
        font-size: .86rem;
        font-weight: 600;
    }

    .workflow-number {
        display: grid;
        flex: 0 0 1.8rem;
        width: 1.8rem;
        height: 1.8rem;
        place-items: center;
        border-radius: 50%;
        background: var(--teal);
        color: white;
        font-size: .76rem;
        font-weight: 700;
    }

    .active-video {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        margin: .25rem 0 1.8rem;
        padding: .8rem 1rem;
        border-left: 3px solid var(--coral);
        border-radius: 0 10px 10px 0;
        background: rgba(255, 255, 255, .7);
        color: var(--muted);
        font-size: .86rem;
    }

    .active-video strong { color: var(--ink); }

    .source-row {
        margin: .45rem 0;
        padding: .7rem .85rem;
        border: 1px solid var(--line);
        border-radius: 10px;
        background: rgba(255, 255, 255, .58);
    }

    .info-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: .7rem;
        margin-top: 1rem;
    }

    .info-item {
        padding: .8rem;
        border: 1px solid var(--line);
        border-radius: 10px;
        background: rgba(255, 255, 255, .58);
    }

    .info-item-label {
        color: var(--muted);
        font-size: .72rem;
        font-weight: 700;
        letter-spacing: .08em;
        text-transform: uppercase;
    }

    .info-item-value {
        margin-top: .35rem;
        color: var(--ink);
        font-weight: 700;
    }

    [data-testid="stTextInput"] input {
        min-height: 3rem;
        border: 1px solid var(--line);
        border-radius: 10px;
        background: rgba(255, 255, 255, .86);
    }

    [data-testid="stTextInput"] input:focus {
        border-color: var(--teal);
        box-shadow: 0 0 0 3px rgba(8, 127, 120, .12);
    }

    [data-testid="stButton"] button {
        min-height: 3rem;
        border-radius: 10px;
        font-weight: 700;
    }

    [data-testid="stVerticalBlockBorderWrapper"] {
        border-color: var(--line);
        border-radius: 14px;
        background: rgba(255, 255, 255, .68);
    }

    .section-label {
        margin: .25rem 0 .65rem;
        color: var(--teal);
        font-size: .75rem;
        font-weight: 700;
        letter-spacing: .1em;
        text-transform: uppercase;
    }

    .meta-pill {
        display: inline-block;
        margin: .2rem .35rem .2rem 0;
        padding: .38rem .7rem;
        border: 1px solid rgba(8, 127, 120, .15);
        border-radius: 999px;
        background: rgba(217, 244, 232, .55);
        color: #27615b;
        font-size: .82rem;
    }

    @media (max-width: 640px) {
        .block-container { padding: 1.25rem 1rem 2.5rem; }
        .hero { padding: 1.5rem 1.25rem 1.65rem; border-radius: 14px; }
        .hero-copy { font-size: .95rem; }
        .workflow, .info-grid { grid-template-columns: 1fr; }
        .active-video { align-items: flex-start; flex-direction: column; gap: .25rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
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
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
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
        doc.metadata["start"] = get_timestamp_for_position(
            full_text, transcript_segments, chunk_pos
        )
        doc.metadata["end"] = get_timestamp_for_position(
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

st.markdown(
    """
    <section class="hero">
        <p class="hero-kicker">Watch less. Understand more.</p>
        <h1 class="hero-title">YouTube RAG Assistant</h1>
        <p class="hero-copy">Turn a long video into a searchable summary and ask grounded questions with timestamped sources.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="workflow" aria-label="How the assistant works">
        <div class="workflow-step"><span class="workflow-number">1</span>Bring a video</div>
        <div class="workflow-step"><span class="workflow-number">2</span>Build your knowledge base</div>
        <div class="workflow-step"><span class="workflow-number">3</span>Ask with evidence</div>
    </div>
    """,
    unsafe_allow_html=True,
)

if st.session_state.video_id:
    st.markdown(
        f"""
        <div class="active-video">
            <span>Active video</span>
            <strong>{st.session_state.video_id}</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# 6. URL INPUT
# ============================================================

st.markdown('<p class="section-label">Start with a video</p>',
            unsafe_allow_html=True)
url_column, action_column = st.columns([5, 1], vertical_alignment="bottom")
with url_column:
    youtube_url = st.text_input(
        "YouTube Video URL",
        placeholder="https://www.youtube.com/watch?v=... or https://youtu.be/...",
        label_visibility="collapsed",
    )
with action_column:
    process_button = st.button(
        "Process video", type="primary", use_container_width=True)


# ============================================================
# 7. PROCESS VIDEO
# ============================================================

if process_button:

    if not youtube_url.strip():
        st.warning("Please enter a YouTube URL.")

    else:
        try:

            # ── Step 1: Extract video ID ──────────────────────────────────────
            with st.spinner("Extracting video ID..."):
                video_id = extract_video_id(youtube_url)

            st.session_state.video_id = video_id
            st.session_state.youtube_url = youtube_url
            st.info(f"🎬 Video ID: `{video_id}`")

            # ── Step 2: Check for existing FAISS index ────────────────────────
            index_dir = INDEXES_DIR / video_id
            index_file = index_dir / "index.faiss"
            pkl_file = index_dir / "index.pkl"
            existing = index_file.exists() and pkl_file.exists()

            # ── Step 3a: Load existing index ──────────────────────────────────
            if existing:
                st.info(
                    "♻️ Existing FAISS index found. Loading saved vector store...")

                with st.spinner("Loading vector store..."):
                    vector_store = load_vector_store(index_dir)
                st.session_state.vector_store = vector_store

                # Load transcript (needed for timestamp metadata)
                with st.spinner("Loading transcript..."):
                    segments, source = fetch_transcript_with_progress(
                        youtube_url)
                st.session_state.transcript_segments = segments
                st.session_state.transcript_source = source
                show_transcript_source_message(source)

                # Load saved summary if available
                summary_file = SUMMARIES_DIR / f"{video_id}.txt"
                if summary_file.exists():
                    st.session_state.summary = summary_file.read_text(
                        encoding="utf-8")

                st.success("♻️ Existing video data loaded successfully!")

            # ── Step 3b: Process new video ────────────────────────────────────
            else:

                # Get transcript (YouTube captions or Whisper)
                segments, source = fetch_transcript_with_progress(youtube_url)

                if not segments:
                    st.error("No transcript was found.")
                    st.stop()

                st.session_state.transcript_segments = segments
                st.session_state.transcript_source = source
                show_transcript_source_message(source)

                # Build plain text
                transcript = " ".join(s["text"] for s in segments)
                if not transcript.strip():
                    st.error("Transcript is empty.")
                    st.stop()

                duration = segments[-1]["end"]
                st.info(
                    f"⏱️ Approximate duration: {format_timestamp(duration)}")

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
    with st.container(border=True):
        st.markdown(
            '<p class="section-label">The essential takeaways</p>', unsafe_allow_html=True)
        st.header("Video Summary")
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
        st.subheader("Conversation History")

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
st.markdown('<p class="section-label">Explore the transcript</p>',
            unsafe_allow_html=True)
st.header("Ask questions about the video")

question_column, ask_column = st.columns([5, 1], vertical_alignment="bottom")
with question_column:
    question = st.text_input(
        "Your question",
        placeholder="What is the main idea of this video?",
        label_visibility="collapsed",
    )
with ask_column:
    ask_button = st.button("Ask question", use_container_width=True)

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
            with st.container(border=True):
                st.markdown(
                    '<p class="section-label">Grounded response</p>', unsafe_allow_html=True)
                st.subheader("Answer")
                st.write(answer)

            # ── Timestamp Sources ─────────────────────────────────────────────
            # answer_question() already returns source_docs — no second
            # similarity_search() needed here.
            if source_docs:
                st.subheader("Relevant video sources")
                displayed_times = set()
                source_number = 1

                for doc in source_docs:
                    start = doc.metadata.get("start")
                    end = doc.metadata.get("end")

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
                        f"""
                        <div class="source-row">
                            <strong>Source {source_number}</strong>&nbsp;&nbsp;
                            <code>{time_text}</code>&nbsp;&nbsp;→&nbsp;&nbsp;
                            <a href="{source_url}" target="_blank">Watch at {format_timestamp(start_seconds)}</a>
                        </div>
                        """,
                        unsafe_allow_html=True,
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
    st.markdown('<p class="section-label">At a glance</p>',
                unsafe_allow_html=True)
    st.subheader("Video information")

    duration_text = "Pending"
    if st.session_state.transcript_segments:
        duration_text = format_timestamp(
            st.session_state.transcript_segments[-1]["end"])

    source_text = "Pending"
    if st.session_state.transcript_source:
        source_text = (
            "Whisper transcription"
            if st.session_state.transcript_source == "whisper"
            else "YouTube captions"
        )

    chunk_text = str(len(st.session_state.documents)
                     ) if st.session_state.documents else "Pending"
    st.markdown(
        f"""
        <div class="info-grid">
            <div class="info-item"><div class="info-item-label">Video ID</div><div class="info-item-value">{st.session_state.video_id}</div></div>
            <div class="info-item"><div class="info-item-label">Duration</div><div class="info-item-value">{duration_text}</div></div>
            <div class="info-item"><div class="info-item-label">Knowledge chunks</div><div class="info-item-value">{chunk_text}</div></div>
        </div>
        <div class="meta-pill">Transcript: {source_text}</div>
        """,
        unsafe_allow_html=True,
    )
