import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from youtube_loader import (
    extract_video_id,
    get_transcript_with_timestamps,
    save_transcript,
)

from chunker import create_documents
from vector_store import create_vector_store
from rag import answer_question
from summarizer import summarize_video


# ============================================================
# 1. HELPER FUNCTIONS
# ============================================================

def format_timestamp(seconds):
    """
    Convert seconds into MM:SS or HH:MM:SS.
    """

    seconds = int(max(0, float(seconds)))

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
    Convert a character position in the transcript
    to an approximate video timestamp.
    """

    current_position = 0

    for segment in transcript_segments:

        segment_text = segment["text"]

        segment_start = current_position
        segment_end = (
            current_position
            + len(segment_text)
        )

        if position <= segment_end:
            return segment["start"]

        current_position = (
            segment_end + 1
        )

    if transcript_segments:
        return transcript_segments[-1]["end"]

    return 0


def add_timestamp_metadata(
    documents,
    transcript_segments,
    video_id,
):
    """
    Add approximate start/end timestamps to
    LangChain documents.
    """

    if not documents:
        return

    if not transcript_segments:
        return

    full_text = " ".join(
        segment["text"]
        for segment in transcript_segments
    )

    if not full_text:
        return

    current_position = 0

    for document in documents:

        chunk_text = (
            document.page_content
        )

        if not chunk_text:
            continue

        # Find the chunk inside the complete transcript
        chunk_position = full_text.find(
            chunk_text,
            current_position,
        )

        # If exact text is not found,
        # use the current position as fallback.
        if chunk_position == -1:
            chunk_position = current_position

        chunk_end = (
            chunk_position
            + len(chunk_text)
        )

        # Convert character positions to timestamps
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

        # Store timestamp metadata
        document.metadata["video_id"] = video_id
        document.metadata["start"] = start_time
        document.metadata["end"] = end_time

        current_position = max(
            current_position,
            chunk_end,
        )


# ============================================================
# 2. PROJECT CONFIGURATION
# ============================================================

BASE_DIR = Path(
    __file__
).resolve().parent


# ============================================================
# 3. STREAMLIT PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="YouTube RAG Assistant",
    page_icon="🎥",
    layout="wide",
)


# ============================================================
# 4. LOAD ENVIRONMENT VARIABLES
# ============================================================

# Local .env support
load_dotenv(
    BASE_DIR / ".env"
)


# ============================================================
# 5. GET GROQ API KEY
# ============================================================

GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY"
)

# Streamlit Cloud Secrets support
if not GROQ_API_KEY:

    try:

        GROQ_API_KEY = st.secrets.get(
            "GROQ_API_KEY"
        )

    except Exception:

        GROQ_API_KEY = None


if not GROQ_API_KEY:

    st.error(
        "GROQ_API_KEY is not configured."
    )

    st.info(
        "For local development, add GROQ_API_KEY "
        "to your .env file. For Streamlit Cloud, "
        "add GROQ_API_KEY under App Settings → Secrets."
    )

    st.stop()


# ============================================================
# 6. TITLE
# ============================================================

st.title(
    "🎥 YouTube RAG Assistant"
)

st.write(
    "Paste a YouTube video URL to summarize the video "
    "and ask questions about its content."
)


# ============================================================
# 7. SESSION STATE
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
# 8. YOUTUBE URL INPUT
# ============================================================

youtube_url = st.text_input(
    "🔗 YouTube Video URL",
    placeholder=(
        "https://www.youtube.com/watch?v=..."
    ),
)


# ============================================================
# 9. PROCESS VIDEO BUTTON
# ============================================================

process_button = st.button(
    "🚀 Process Video",
    type="primary",
)


# ============================================================
# 10. PROCESS VIDEO
# ============================================================

if process_button:

    if not youtube_url.strip():

        st.warning(
            "Please enter a YouTube URL."
        )

    else:

        try:

            # =================================================
            # STEP 1: EXTRACT VIDEO ID
            # =================================================

            with st.spinner(
                "Extracting YouTube video ID..."
            ):

                video_id = extract_video_id(
                    youtube_url
                )

            st.session_state.video_id = (
                video_id
            )

            st.session_state.youtube_url = (
                youtube_url
            )

            st.info(
                f"🎬 Video ID: `{video_id}`"
            )


            # =================================================
            # STEP 2: GET TRANSCRIPT + TIMESTAMPS
            # =================================================

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
                    "No transcript segments were found."
                )

                st.stop()


            # =================================================
            # CONVERT SEGMENTS TO PLAIN TEXT
            # =================================================

            transcript = " ".join(
                segment["text"]
                for segment in transcript_segments
            )


            if not transcript.strip():

                st.error(
                    "The transcript is empty."
                )

                st.stop()


            # Store timestamped transcript
            st.session_state.transcript_segments = (
                transcript_segments
            )


            st.success(
                "✅ Transcript retrieved successfully!"
            )


            # =================================================
            # TRANSCRIPT INFORMATION
            # =================================================

            total_segments = len(
                transcript_segments
            )

            video_duration = (
                transcript_segments[-1]["end"]
            )


            st.info(
                f"📝 Transcript segments: "
                f"{total_segments}"
            )

            st.info(
                f"⏱️ Approximate video duration: "
                f"{format_timestamp(video_duration)}"
            )


            # =================================================
            # STEP 3: SAVE TRANSCRIPT
            # =================================================

            with st.spinner(
                "Saving transcript..."
            ):

                transcript_dir = (
                    BASE_DIR
                    / "data"
                    / "transcripts"
                )

                transcript_path = (
                    save_transcript(
                        transcript,
                        video_id,
                        transcript_dir,
                    )
                )


            st.success(
                "✅ Transcript saved successfully!"
            )


            # =================================================
            # STEP 4: CREATE DOCUMENT CHUNKS
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
                    "No document chunks were created."
                )

                st.stop()


            # =================================================
            # ADD TIMESTAMP METADATA
            # =================================================

            add_timestamp_metadata(
                documents,
                transcript_segments,
                video_id,
            )


            st.info(
                f"📚 Created {len(documents)} chunks."
            )


            # =================================================
            # STEP 5: CREATE VECTOR STORE
            # =================================================

            with st.spinner(
                "Creating embeddings and FAISS index..."
            ):

                vector_store = create_vector_store(
                    documents
                )


            if vector_store is None:

                st.error(
                    "Failed to create FAISS vector store."
                )

                st.stop()


            # =================================================
            # STEP 6: SAVE VECTOR STORE
            # =================================================

            index_dir = (
                BASE_DIR
                / "data"
                / "indexes"
                / video_id
            )


            index_dir.mkdir(
                parents=True,
                exist_ok=True,
            )


            vector_store.save_local(
                str(index_dir)
            )


            st.success(
                "✅ FAISS vector store created successfully!"
            )


            # =================================================
            # STEP 7: STORE IN SESSION STATE
            # =================================================

            st.session_state.vector_store = (
                vector_store
            )

            st.session_state.documents = (
                documents
            )


            # =================================================
            # STEP 8: GENERATE SUMMARY
            # =================================================

            with st.spinner(
                "Generating video summary..."
            ):

                summary = summarize_video(
                    documents
                )


            st.session_state.summary = (
                summary
            )


            # =================================================
            # FINAL SUCCESS
            # =================================================

            st.success(
                "🎉 Video processed successfully!"
            )


        except Exception as e:

            st.error(
                "❌ Error while processing video:"
            )

            st.exception(e)


# ============================================================
# 11. DISPLAY SUMMARY
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
# 12. QUESTION ANSWERING
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

    # --------------------------------------------------------
    # Check vector store
    # --------------------------------------------------------

    if st.session_state.vector_store is None:

        st.warning(
            "Please process a YouTube video first."
        )


    # --------------------------------------------------------
    # Check question
    # --------------------------------------------------------

    elif not question.strip():

        st.warning(
            "Please enter a question."
        )


    else:

        try:

            # =================================================
            # GENERATE ANSWER
            # =================================================

            with st.spinner(
                "Searching the video and generating answer..."
            ):

                answer = answer_question(
                    st.session_state.vector_store,
                    question,
                )


            # =================================================
            # DISPLAY ANSWER
            # =================================================

            st.subheader(
                "🤖 Answer"
            )

            st.write(
                answer
            )


            # =================================================
            # RETRIEVE RELEVANT DOCUMENTS
            # =================================================

            source_documents = (
                st.session_state.vector_store
                .similarity_search(
                    question,
                    k=4,
                )
            )


            # =================================================
            # DISPLAY SOURCES
            # =================================================

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


                    # Prevent duplicate sources
                    timestamp_key = (
                        start_seconds
                    )


                    if timestamp_key in displayed_times:

                        continue


                    displayed_times.add(
                        timestamp_key
                    )


                    # -----------------------------------------
                    # Format timestamp
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
                    # Create YouTube timestamp URL
                    # -----------------------------------------

                    source_url = (
                        "https://www.youtube.com/watch?v="
                        f"{st.session_state.video_id}"
                        f"&t={start_seconds}s"
                    )


                    # -----------------------------------------
                    # Display source
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
# 13. VIDEO INFORMATION
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
            st.session_state
            .transcript_segments[-1]["end"]
        )

        st.write(
            f"**Approximate duration:** "
            f"{format_timestamp(duration)}"
        )
