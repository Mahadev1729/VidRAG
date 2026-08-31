import os
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from youtube_loader import (
    extract_video_id,
    get_transcript_with_timestamps,
    save_transcript,
)

from chunker import create_documents

from vector_store import (
    create_vector_store,
    load_vector_store,
)

from rag import answer_question
from summarizer import summarize_video

from chat_history import (
    init_db,
    save_message,
    get_messages,
    clear_messages,
)


# ============================================================
# 1. PROJECT CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")


# ============================================================
# 2. GROQ API KEY
# ============================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Streamlit Cloud Secrets fallback
if not GROQ_API_KEY:
    try:
        GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")
    except Exception:
        GROQ_API_KEY = None


if not GROQ_API_KEY:
    st.error("❌ GROQ_API_KEY is not configured.")

    st.info(
        "For local use, add GROQ_API_KEY to .env. "
        "For Streamlit Cloud, add it under App Settings → Secrets."
    )

    st.stop()


# ============================================================
# 3. INITIALIZE CHAT DATABASE
# ============================================================

init_db()


# ============================================================
# 4. STREAMLIT PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="YouTube RAG Assistant",
    page_icon="🎥",
    layout="wide",
)


# ============================================================
# 5. SESSION ID
# ============================================================

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())


# ============================================================
# 6. SESSION STATE
# ============================================================

if "vector_store" not in st.session_state:
    st.session_state.vector_store = None

if "documents" not in st.session_state:
    st.session_state.documents = None

if "video_id" not in st.session_state:
    st.session_state.video_id = None

if "summary" not in st.session_state:
    st.session_state.summary = None

if "youtube_url" not in st.session_state:
    st.session_state.youtube_url = None

if "transcript_segments" not in st.session_state:
    st.session_state.transcript_segments = None


# ============================================================
# 7. HELPER FUNCTIONS
# ============================================================

def format_timestamp(seconds):
    """
    Convert seconds into MM:SS or HH:MM:SS.
    """

    seconds = int(float(seconds))

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remaining_seconds = seconds % 60

    if hours > 0:
        return (
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{remaining_seconds:02d}"
        )

    return (
        f"{minutes:02d}:"
        f"{remaining_seconds:02d}"
    )


def get_timestamp_for_position(
    full_text,
    transcript_segments,
    position,
):
    """
    Find approximate timestamp for a character
    position in the full transcript.
    """

    current_position = 0

    for segment in transcript_segments:

        segment_text = segment["text"]

        segment_end = (
            current_position
            + len(segment_text)
        )

        if position <= segment_end:
            return segment["start"]

        current_position = segment_end + 1

    if transcript_segments:
        return transcript_segments[-1]["end"]

    return 0


def add_timestamp_metadata(
    documents,
    transcript_segments,
    video_id,
):
    """
    Add approximate timestamp metadata to
    LangChain documents.
    """

    if not documents or not transcript_segments:
        return

    full_text = " ".join(
        segment["text"]
        for segment in transcript_segments
    )

    if not full_text:
        return

    current_position = 0

    for document in documents:

        chunk_text = document.page_content

        if not chunk_text:
            continue

        chunk_position = full_text.find(
            chunk_text,
            current_position,
        )

        if chunk_position == -1:
            chunk_position = current_position

        chunk_end = (
            chunk_position
            + len(chunk_text)
        )

        start_time = get_timestamp_for_position(
            full_text,
            transcript_segments,
            chunk_position,
        )

        end_time = get_timestamp_for_position(
            full_text,
            transcript_segments,
            chunk_end,
        )

        document.metadata["video_id"] = video_id
        document.metadata["start"] = start_time
        document.metadata["end"] = end_time

        current_position = max(
            current_position,
            chunk_end,
        )


# ============================================================
# 8. TITLE
# ============================================================

st.title("🎥 YouTube RAG Assistant")

st.write(
    "Paste a YouTube video URL to summarize the video "
    "and ask questions about its content."
)


# ============================================================
# 9. YOUTUBE URL
# ============================================================

youtube_url = st.text_input(
    "🔗 YouTube Video URL",
    placeholder=(
        "https://www.youtube.com/watch?v=... "
        "or https://youtu.be/..."
    ),
)


# ============================================================
# 10. PROCESS VIDEO
# ============================================================

process_button = st.button(
    "🚀 Process Video",
    type="primary",
)


if process_button:

    if not youtube_url.strip():

        st.warning(
            "Please enter a YouTube URL."
        )

    else:

        try:

            # =================================================
            # STEP 1 — EXTRACT VIDEO ID
            # =================================================

            with st.spinner(
                "Extracting YouTube video ID..."
            ):

                video_id = extract_video_id(
                    youtube_url
                )

            st.session_state.video_id = video_id
            st.session_state.youtube_url = youtube_url

            st.info(
                f"🎬 Video ID: `{video_id}`"
            )


            # =================================================
            # STEP 2 — INDEX PATH
            # =================================================

            index_dir = (
                BASE_DIR
                / "data"
                / "indexes"
                / video_id
            )

            index_file = (
                index_dir
                / "index.faiss"
            )

            pkl_file = (
                index_dir
                / "index.pkl"
            )

            existing_index = (
                index_file.exists()
                and pkl_file.exists()
            )


            # =================================================
            # STEP 3 — EXISTING VECTOR STORE
            # =================================================

            if existing_index:

                st.info(
                    "♻️ Existing FAISS index found. "
                    "Loading saved vector store..."
                )

                with st.spinner(
                    "Loading existing vector store..."
                ):

                    vector_store = load_vector_store(
                        index_dir
                    )

                st.session_state.vector_store = vector_store


                # ---------------------------------------------
                # Load transcript for timestamps
                # ---------------------------------------------

                with st.spinner(
                    "Loading transcript information..."
                ):

                    transcript_segments = (
                        get_transcript_with_timestamps(
                            youtube_url
                        )
                    )

                st.session_state.transcript_segments = (
                    transcript_segments
                )


                # ---------------------------------------------
                # Load saved summary
                # ---------------------------------------------

                summary_file = (
                    BASE_DIR
                    / "data"
                    / "summaries"
                    / f"{video_id}.txt"
                )

                if summary_file.exists():

                    with open(
                        summary_file,
                        "r",
                        encoding="utf-8",
                    ) as file:

                        st.session_state.summary = (
                            file.read()
                        )

                st.success(
                    "♻️ Existing video data loaded successfully!"
                )


            # =================================================
            # STEP 4 — NEW VIDEO
            # =================================================

            else:

                # ---------------------------------------------
                # Get transcript
                # ---------------------------------------------

                with st.spinner(
                    "Fetching YouTube transcript..."
                ):

                    transcript_segments = (
                        get_transcript_with_timestamps(
                            youtube_url
                        )
                    )

                if not transcript_segments:

                    st.error(
                        "No transcript was found."
                    )

                    st.stop()


                st.session_state.transcript_segments = (
                    transcript_segments
                )


                # ---------------------------------------------
                # Convert segments to text
                # ---------------------------------------------

                transcript = " ".join(
                    segment["text"]
                    for segment in transcript_segments
                )


                if not transcript.strip():

                    st.error(
                        "Transcript is empty."
                    )

                    st.stop()


                st.success(
                    "✅ Transcript retrieved successfully!"
                )


                # ---------------------------------------------
                # Duration
                # ---------------------------------------------

                duration = (
                    transcript_segments[-1]["end"]
                )

                st.info(
                    f"⏱️ Approximate duration: "
                    f"{format_timestamp(duration)}"
                )


                # =================================================
                # STEP 5 — SAVE TRANSCRIPT
                # =================================================

                transcript_dir = (
                    BASE_DIR
                    / "data"
                    / "transcripts"
                )

                transcript_dir.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                with st.spinner(
                    "Saving transcript..."
                ):

                    save_transcript(
                        transcript,
                        video_id,
                        transcript_dir,
                    )


                # =================================================
                # STEP 6 — CHUNKING
                # =================================================

                with st.spinner(
                    "Splitting transcript into chunks..."
                ):

                    documents = create_documents(
                        transcript,
                        video_id,
                    )


                if not documents:

                    st.error(
                        "No chunks were created."
                    )

                    st.stop()


                st.info(
                    f"📚 Created {len(documents)} chunks."
                )


                # =================================================
                # STEP 7 — TIMESTAMP METADATA
                # =================================================

                add_timestamp_metadata(
                    documents,
                    transcript_segments,
                    video_id,
                )


                # =================================================
                # STEP 8 — CREATE VECTOR STORE
                # =================================================

                with st.spinner(
                    "Creating embeddings and FAISS index..."
                ):

                    vector_store = create_vector_store(
                        documents
                    )


                if vector_store is None:

                    st.error(
                        "Failed to create vector store."
                    )

                    st.stop()


                # =================================================
                # STEP 9 — SAVE FAISS
                # =================================================

                index_dir.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                vector_store.save_local(
                    str(index_dir)
                )


                st.success(
                    "✅ FAISS index saved successfully!"
                )


                # =================================================
                # STEP 10 — SESSION STATE
                # =================================================

                st.session_state.vector_store = (
                    vector_store
                )

                st.session_state.documents = (
                    documents
                )


                # =================================================
                # STEP 11 — SUMMARY
                # =================================================

                with st.spinner(
                    "Generating video summary..."
                ):

                    summary = summarize_video(
                        documents
                    )


                st.session_state.summary = summary


                # =================================================
                # STEP 12 — SAVE SUMMARY
                # =================================================

                summary_dir = (
                    BASE_DIR
                    / "data"
                    / "summaries"
                )

                summary_dir.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                summary_file = (
                    summary_dir
                    / f"{video_id}.txt"
                )

                with open(
                    summary_file,
                    "w",
                    encoding="utf-8",
                ) as file:

                    file.write(summary)


                st.success(
                    "🎉 Video processed successfully!"
                )


        except Exception as e:

            st.error(
                "❌ Error while processing video:"
            )

            st.exception(e)


# ============================================================
# 11. SUMMARY
# ============================================================

if st.session_state.summary:

    st.divider()

    st.header(
        "📄 Video Summary"
    )

    st.markdown(
        st.session_state.summary
    )


# ============================================================
# 12. CHAT HISTORY
# ============================================================

if st.session_state.video_id:

    messages = get_messages(
        st.session_state.session_id,
        st.session_state.video_id,
    )

    if messages:

        st.divider()

        st.subheader(
            "💬 Conversation History"
        )

        for role, message in messages:

            if role == "user":

                with st.chat_message("user"):

                    st.write(message)

            elif role == "assistant":

                with st.chat_message("assistant"):

                    st.write(message)


        # ---------------------------------------------
        # Clear Chat
        # ---------------------------------------------

        if st.button("🗑️ Clear Chat"):

            clear_messages(
                st.session_state.session_id,
                st.session_state.video_id,
            )

            st.rerun()


# ============================================================
# 13. ASK QUESTIONS
# ============================================================

st.divider()

st.header(
    "💬 Ask Questions About the Video"
)


question = st.text_input(
    "Your question",
    placeholder=(
        "Example: What is the main topic of this video?"
    ),
)


ask_button = st.button(
    "🔍 Ask Question"
)


if ask_button:

    # ========================================================
    # CHECK VECTOR STORE
    # ========================================================

    if st.session_state.vector_store is None:

        st.warning(
            "Please process a YouTube video first."
        )


    # ========================================================
    # CHECK QUESTION
    # ========================================================

    elif not question.strip():

        st.warning(
            "Please enter a question."
        )


    else:

        try:

            # =================================================
            # SAVE USER QUESTION
            # =================================================

            save_message(
                st.session_state.session_id,
                st.session_state.video_id,
                "user",
                question,
            )


            # =================================================
            # RAG
            # =================================================

            with st.spinner(
                "Searching the video and generating answer..."
            ):

                answer = answer_question(
                    st.session_state.vector_store,
                    question,
                )


            # =================================================
            # SAVE AI ANSWER
            # =================================================

            save_message(
                st.session_state.session_id,
                st.session_state.video_id,
                "assistant",
                answer,
            )


            # =================================================
            # DISPLAY ANSWER
            # =================================================

            st.subheader(
                "🤖 Answer"
            )

            st.write(answer)


            # =================================================
            # TIMESTAMP SOURCES
            # =================================================

            source_documents = (
                st.session_state.vector_store
                .similarity_search(
                    question,
                    k=4,
                )
            )


            if source_documents:

                st.subheader(
                    "📍 Relevant Video Sources"
                )

                displayed_times = set()

                source_number = 1


                for doc in source_documents:

                    start = doc.metadata.get(
                        "start"
                    )

                    end = doc.metadata.get(
                        "end"
                    )


                    if start is None:

                        continue


                    start_seconds = int(
                        float(start)
                    )


                    if start_seconds in displayed_times:

                        continue


                    displayed_times.add(
                        start_seconds
                    )


                    # -----------------------------------------
                    # Time display
                    # -----------------------------------------

                    if end is not None:

                        end_seconds = int(
                            float(end)
                        )

                        time_text = (
                            f"{format_timestamp(start_seconds)}"
                            f" – "
                            f"{format_timestamp(end_seconds)}"
                        )

                    else:

                        time_text = (
                            format_timestamp(
                                start_seconds
                            )
                        )


                    # -----------------------------------------
                    # YouTube timestamp URL
                    # -----------------------------------------

                    source_url = (
                        "https://www.youtube.com/watch?v="
                        f"{st.session_state.video_id}"
                        f"&t={start_seconds}s"
                    )


                    # -----------------------------------------
                    # Display
                    # -----------------------------------------

                    st.markdown(
                        f"**Source {source_number}:** "
                        f"`{time_text}` → "
                        f"[▶ Watch at "
                        f"{format_timestamp(start_seconds)}]"
                        f"({source_url})"
                    )


                    source_number += 1


        except Exception as e:

            st.error(
                "❌ Error while answering:"
            )

            st.exception(e)


# ============================================================
# 14. VIDEO INFORMATION
# ============================================================

if st.session_state.video_id:

    st.divider()

    st.subheader(
        "ℹ️ Video Information"
    )

    st.write(
        f"**Video ID:** "
        f"`{st.session_state.video_id}`"
    )


    if st.session_state.documents:

        st.write(
            f"**Number of chunks:** "
            f"{len(st.session_state.documents)}"
        )


    if st.session_state.transcript_segments:

        duration = (
            st.session_state.transcript_segments[-1]["end"]
        )

        st.write(
            f"**Approximate duration:** "
            f"{format_timestamp(duration)}"
        )
