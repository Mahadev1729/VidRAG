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
from pathlib import Path
import uuid

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
from llm.self_rag import self_corrective_rag_answer
from llm.summarizer import summarize_video
from llm.feedback_store import (
    init_feedback_db,
    record_feedback,
    get_feedback_stats,
)

# ── Chat History (utility, kept at root) ─────────────────────────────────────
from chat_history import (
    init_db as init_chat_db,
    save_message,
    get_messages,
    clear_messages,
    get_user_recent_activity,
    delete_user_video_activity,
)

# ── Authentication & Styles ───────────────────────────────────────────────────
from utils.auth import (
    init_db as init_auth_db,
    render_auth_page,
)
from utils.styles import load_css


# ============================================================
# 1. PAGE CONFIG & STYLES
# ============================================================

st.set_page_config(
    page_title="YouTube RAG Assistant",
    page_icon="🎥",
    layout="wide",
)

# Load external CSS styling from static/style.css
load_css()



# ============================================================
# 2. DATABASE & SIDEBAR UTILITIES
# ============================================================

def init_db() -> None:
    """Initialize authentication, chat history, and feedback databases."""
    init_auth_db()
    init_chat_db()
    init_feedback_db()


def load_saved_video_context(video_id: str) -> bool:
    """Load a previously indexed video's vector store, summary, and segments from disk."""
    index_dir = INDEXES_DIR / video_id
    index_file = index_dir / "index.faiss"
    pkl_file = index_dir / "index.pkl"
    if not (index_file.exists() and pkl_file.exists()):
        return False

    st.session_state.video_id = video_id
    st.session_state.youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    st.session_state.vector_store = load_vector_store(index_dir)

    summary_file = SUMMARIES_DIR / f"{video_id}.txt"
    if summary_file.exists():
        st.session_state.summary = summary_file.read_text(encoding="utf-8")
    else:
        st.session_state.summary = None

    try:
        segments, source = get_transcript_with_timestamps(f"https://www.youtube.com/watch?v={video_id}")
        st.session_state.transcript_segments = segments
        st.session_state.transcript_source = source
    except Exception:
        pass

    st.session_state.last_qa = None
    st.session_state.feedback_submitted = False
    return True


def render_sidebar() -> None:
    """Render authenticated user badge, recent activity drawer, and logout button in sidebar."""
    username = st.session_state.get("username", "User")
    st.sidebar.markdown(
        f"""
        <div style="padding: 0.75rem 0.9rem; border-radius: 10px; background: rgba(8, 127, 120, 0.08); border: 1px solid rgba(8, 127, 120, 0.2); margin-bottom: 1rem;">
            <span style="font-size: 1rem; font-weight: 600; color: #17212b;">👤 {username}</span>
            <span style="display: inline-block; margin-left: 0.5rem; color: #10b981; font-weight: bold; font-size: 0.85rem;">● Active</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.sidebar.button("🚪 Log Out", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.subheader("📜 Your Recent Activity")

    activities = get_user_recent_activity(username, limit=10)
    if activities:
        for item in activities:
            vid = item["video_id"]
            q_preview = item["last_question"]
            if len(q_preview) > 32:
                q_preview = q_preview[:30] + "..."
            msg_cnt = item["message_count"]
            is_active = (st.session_state.get("video_id") == vid)

            btn_prefix = "▶ " if is_active else ""
            btn_label = f"{btn_prefix}🎬 {vid} ({msg_cnt} msgs)\n{q_preview}"
            if st.sidebar.button(btn_label, key=f"act_btn_{vid}", use_container_width=True):
                if load_saved_video_context(vid):
                    st.rerun()
                else:
                    st.sidebar.warning(f"Cached index missing for `{vid}`. Please paste its URL to re-index.")
    else:
        st.sidebar.caption("No past activity yet. Ask questions about a video to save history!")


# ============================================================
# 3. HELPER FUNCTIONS (UI utilities)
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
# 4. MAIN ENTRY POINT
# ============================================================

def main():
    """Main application entrypoint with page guard and UI rendering."""
    init_db()
    if not st.session_state.get("authenticated", False):
        render_auth_page()
        return  # Stop execution until user logs in

    render_sidebar()

    # ── API Key Check ─────────────────────────────────────────────────────────
    # config.py loads the key from .env. We check it here before
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

    # ── Session State Defaults ────────────────────────────────────────────────
    defaults = {
        "session_id": str(uuid.uuid4()),
        "vector_store": None,
        "documents": None,
        "video_id": None,
        "summary": None,
        "youtube_url": None,
        "transcript_segments": None,
        "transcript_source": None,
        "last_qa": None,
        "feedback_submitted": False,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # ── Title & Workflow ──────────────────────────────────────────────────────
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

    # ── URL Input ─────────────────────────────────────────────────────────────
    st.markdown('<p class="section-label">Start with a video</p>', unsafe_allow_html=True)
    url_column, action_column = st.columns([5, 1], vertical_alignment="bottom")
    with url_column:
        youtube_url = st.text_input(
            "YouTube Video URL",
            placeholder="https://www.youtube.com/watch?v=... or https://youtu.be/...",
        )
    with action_column:
        process_button = st.button("Process video", type="primary", use_container_width=True)

    # ── Process Video ─────────────────────────────────────────────────────────
    if process_button:
        if not youtube_url.strip():
            st.warning("Please enter a YouTube URL.")
        else:
            try:
                # Step 1: Extract video ID
                with st.spinner("Extracting video ID..."):
                    video_id = extract_video_id(youtube_url)

                st.session_state.video_id = video_id
                st.session_state.youtube_url = youtube_url
                st.info(f"🎬 Video ID: `{video_id}`")

                # Step 2: Check for existing FAISS index
                index_dir = INDEXES_DIR / video_id
                index_file = index_dir / "index.faiss"
                pkl_file = index_dir / "index.pkl"
                existing = index_file.exists() and pkl_file.exists()

                # Step 3a: Load existing index
                if existing:
                    st.info("♻️ Existing FAISS index found. Loading saved vector store...")

                    with st.spinner("Loading vector store..."):
                        vector_store = load_vector_store(index_dir)
                    st.session_state.vector_store = vector_store

                    # Load transcript (needed for timestamp metadata)
                    with st.spinner("Loading transcript..."):
                        segments, source = fetch_transcript_with_progress(youtube_url)
                    st.session_state.transcript_segments = segments
                    st.session_state.transcript_source = source
                    show_transcript_source_message(source)

                    # Load saved summary if available
                    summary_file = SUMMARIES_DIR / f"{video_id}.txt"
                    if summary_file.exists():
                        st.session_state.summary = summary_file.read_text(encoding="utf-8")

                    st.success("♻️ Existing video data loaded successfully!")

                # Step 3b: Process new video
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

    # ── Summary ───────────────────────────────────────────────────────────────
    if st.session_state.summary:
        st.divider()
        with st.container(border=True):
            st.markdown(
                '<p class="section-label">The essential takeaways</p>',
                unsafe_allow_html=True,
            )
            st.header("Video Summary")
            st.markdown(st.session_state.summary)

    # ── Chat History ──────────────────────────────────────────────────────────
    username = st.session_state.get("username", "User")
    if st.session_state.video_id:
        messages = get_messages(
            username,
            st.session_state.video_id,
        )

        if messages:
            st.divider()
            st.subheader("Conversation History")

            for role, message in messages:
                with st.chat_message(role):
                    st.write(message)

            if st.button("🗑️ Clear Chat History for This Video"):
                clear_messages(
                    username,
                    st.session_state.video_id,
                )
                st.session_state.last_qa = None
                st.rerun()

    # ── Ask Questions ─────────────────────────────────────────────────────────
    st.divider()
    st.markdown('<p class="section-label">Explore the transcript</p>', unsafe_allow_html=True)
    st.header("Ask questions about the video")

    question_column, ask_column = st.columns([5, 1], vertical_alignment="bottom")
    with question_column:
        question = st.text_input(
            "Your question",
            placeholder="What is the main idea of this video?",
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
                    username,
                    st.session_state.video_id,
                    "user",
                    question,
                )

                # Corrective Self-RAG: evaluate, rewrite if needed, and answer
                with st.spinner("Analyzing transcript with Adaptive Self-RAG..."):
                    answer, source_docs, trace = self_corrective_rag_answer(
                        st.session_state.vector_store,
                        question,
                        video_id=st.session_state.video_id,
                    )

                # Save assistant answer
                save_message(
                    username,
                    st.session_state.video_id,
                    "assistant",
                    answer,
                )

                st.session_state.last_qa = {
                    "id": str(uuid.uuid4()),
                    "question": question,
                    "answer": answer,
                    "source_docs": source_docs,
                    "trace": trace,
                }
                st.session_state.feedback_submitted = False

            except Exception as e:
                st.error("❌ Error while answering:")
                st.exception(e)

    # ── Render Latest Answer & Self-Correction Trace ──────────────────────────
    if st.session_state.last_qa:
        last_qa = st.session_state.last_qa
        answer = last_qa["answer"]
        source_docs = last_qa["source_docs"]
        trace = last_qa.get("trace", {})

        # Display answer
        with st.container(border=True):
            st.markdown(
                '<p class="section-label">Grounded response</p>',
                unsafe_allow_html=True,
            )
            st.subheader("Answer")
            st.write(answer)

        # ── 🧠 Self-Correction & Reasoning Trace ─────────────────────────────
        with st.expander("🧠 Self-Correction & Reasoning Trace", expanded=False):
            st.markdown("#### Adaptive Pipeline Telemetry")

            if not trace.get("self_rag_enabled", True):
                st.info("ℹ️ **Baseline RAG Mode Active**: Self-RAG evaluation is disabled in configuration (`ENABLE_SELF_RAG=false`).")
            else:
                # 1. Active Correction & Guardrail Notifications
                if trace.get("fallback_triggered"):
                    st.error("⚠️ **Conservative Fallback Activated**: The generated claims could not be verified against the transcript. Reverted safely to prevent hallucination.")
                elif trace.get("grounding_corrected"):
                    st.warning(
                        f"🛡️ **Hallucination Intercepted & Self-Corrected**:\n"
                        f"Initial response contained ungrounded claims (*\"{trace.get('correction_reason', 'Unverified facts')}\"*). "
                        f"A strict correction pass was automatically executed."
                    )

                # 2. Retrieval Grading
                grade_info = trace.get("initial_grade", {})
                is_relevant = grade_info.get("is_relevant", True)
                grade_score = grade_info.get("score", 1.0)
                grade_reason = grade_info.get("reason", "Direct transcript match.")

                col_g1, col_g2 = st.columns([1, 2])
                with col_g1:
                    if is_relevant and grade_score >= 0.7:
                        st.success(f"🎯 Relevance Score: **{int(grade_score * 100)}%**")
                    else:
                        st.warning(f"⚠️ Initial Match: **{int(grade_score * 100)}%**")
                with col_g2:
                    st.caption(f"**Evaluation**: {grade_reason}")

                # 3. Query Rewriting Status
                if trace.get("query_rewritten"):
                    st.info(
                        "🔄 **Adaptive Query Expansion Triggered**:\n"
                        "Initial transcript keywords were insufficient. Query was automatically reformulated into:\n"
                        + "\n".join(f"- *\"{q}\"*" for q in trace.get("rewritten_queries", []))
                    )
                    st.caption(f"📚 Discovered **{trace.get('final_chunks_count', 0)}** total context chunks.")
                else:
                    st.caption("⚡ **Direct Match**: Search query matched video audio directly without rewriting.")

                # 4. Grounding & Hallucination Guardrail
                grounding_info = trace.get("grounding_check", {})
                g_confidence = grounding_info.get("confidence", 1.0)
                g_notes = grounding_info.get("notes", "All claims verified against transcript.")
                st.caption(f"🛡️ **Factual Grounding**: {int(g_confidence * 100)}% confidence — *{g_notes}*")

                # 5. Few-shot Memory
                if trace.get("few_shot_count", 0) > 0:
                    st.caption(f"💡 **Feedback Memory**: Injected {trace['few_shot_count']} verified high-rated past answers.")

        # ── Timestamp Sources ────────────────────────────────────────────────
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

        # ── User Feedback & Continuous Learning Loop ────────────────────────
        st.divider()
        st.markdown('<p class="section-label">Help the assistant learn</p>', unsafe_allow_html=True)
        st.caption("Rate this response to reinforce high-quality answers in the self-learning memory.")

        if not st.session_state.feedback_submitted:
            fb_col1, fb_col2, _ = st.columns([1, 1, 4])
            with fb_col1:
                if st.button("👍 Helpful", key=f"thumb_up_{last_qa['id']}", use_container_width=True):
                    record_feedback(
                        video_id=st.session_state.video_id,
                        question=last_qa["question"],
                        answer=last_qa["answer"],
                        rating=1,
                        username=st.session_state.get("username", "User"),
                    )
                    st.session_state.feedback_submitted = True
                    st.rerun()

            with fb_col2:
                if st.button("👎 Inaccurate", key=f"thumb_down_{last_qa['id']}", use_container_width=True):
                    record_feedback(
                        video_id=st.session_state.video_id,
                        question=last_qa["question"],
                        answer=last_qa["answer"],
                        rating=-1,
                        username=st.session_state.get("username", "User"),
                    )
                    st.session_state.feedback_submitted = True
                    st.rerun()
        else:
            st.success("✨ **Thank you!** Your feedback has been saved to the self-learning memory.")

    # ── Video Information ─────────────────────────────────────────────────────
    if st.session_state.video_id:
        st.divider()
        st.markdown('<p class="section-label">At a glance</p>', unsafe_allow_html=True)
        st.subheader("Video information")

        duration_text = "Pending"
        if st.session_state.transcript_segments:
            duration_text = format_timestamp(
                st.session_state.transcript_segments[-1]["end"]
            )

        source_text = "Pending"
        if st.session_state.transcript_source:
            source_text = (
                "Whisper transcription"
                if st.session_state.transcript_source == "whisper"
                else "YouTube captions"
            )

        chunk_text = (
            str(len(st.session_state.documents))
            if st.session_state.documents
            else "Pending"
        )

        fb_stats = get_feedback_stats(st.session_state.video_id)
        rating_text = f"👍 {fb_stats['upvotes']} | 👎 {fb_stats['downvotes']}"

        st.markdown(
            f"""
            <div class="info-grid">
                <div class="info-item"><div class="info-item-label">Video ID</div><div class="info-item-value">{st.session_state.video_id}</div></div>
                <div class="info-item"><div class="info-item-label">Duration</div><div class="info-item-value">{duration_text}</div></div>
                <div class="info-item"><div class="info-item-label">Knowledge chunks</div><div class="info-item-value">{chunk_text}</div></div>
                <div class="info-item"><div class="info-item-label">Community Rating</div><div class="info-item-value">{rating_text}</div></div>
            </div>
            <div class="meta-pill">Transcript: {source_text}</div>
            """,
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()

