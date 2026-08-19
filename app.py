import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from youtube_loader import (
    extract_video_id,
    get_transcript,
    save_transcript
)

from chunker import create_documents
from vector_store import create_vector_store
from rag import answer_question
from summarizer import summarize_video


# ============================================================
# 1. PROJECT CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")


# Check Groq API key
if not os.getenv("GROQ_API_KEY"):
    st.error("GROQ_API_KEY not found in .env file.")
    st.stop()


# ============================================================
# 2. STREAMLIT PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="YouTube RAG Assistant",
    page_icon="🎥",
    layout="wide"
)


# ============================================================
# 3. TITLE
# ============================================================

st.title("🎥 YouTube RAG Assistant")

st.write(
    "Paste a YouTube video URL to summarize the video "
    "and ask questions about its content."
)


# ============================================================
# 4. SESSION STATE
# ============================================================

if "vector_store" not in st.session_state:
    st.session_state.vector_store = None

if "documents" not in st.session_state:
    st.session_state.documents = None

if "video_id" not in st.session_state:
    st.session_state.video_id = None

if "summary" not in st.session_state:
    st.session_state.summary = None


# ============================================================
# 5. YOUTUBE URL
# ============================================================

youtube_url = st.text_input(
    "🔗 YouTube Video URL",
    placeholder="https://www.youtube.com/watch?v=..."
)


# ============================================================
# 6. PROCESS VIDEO
# ============================================================

process_button = st.button(
    "🚀 Process Video",
    type="primary"
)


if process_button:

    if not youtube_url.strip():

        st.warning(
            "Please enter a YouTube URL."
        )

    else:

        try:

            # ------------------------------------------------
            # Step 1: Extract Video ID
            # ------------------------------------------------

            with st.spinner(
                "Extracting YouTube video ID..."
            ):

                video_id = extract_video_id(
                    youtube_url
                )

            st.info(
                f"Video ID: `{video_id}`"
            )

            # ------------------------------------------------
            # Step 2: Get Transcript
            # ------------------------------------------------

            with st.spinner(
                "Fetching YouTube transcript..."
            ):

                transcript = get_transcript(
                    video_id
                )

            if not transcript.strip():

                st.error(
                    "The transcript is empty."
                )

                st.stop()

            st.success(
                "✅ Transcript retrieved successfully!"
            )

            # ------------------------------------------------
            # Step 3: Save Transcript
            # ------------------------------------------------

            save_transcript(
                video_id,
                transcript,
                BASE_DIR
            )

            # ------------------------------------------------
            # Step 4: Create LangChain Documents
            # ------------------------------------------------

            with st.spinner(
                "Splitting transcript into chunks..."
            ):

                documents = create_documents(
                    transcript,
                    video_id
                )

            st.info(
                f"Created {len(documents)} chunks."
            )

            # ------------------------------------------------
            # Step 5: Create FAISS Vector Store
            # ------------------------------------------------

            with st.spinner(
                "Creating embeddings and FAISS index..."
            ):

                vector_store = create_vector_store(
                    documents
                )

            # ------------------------------------------------
            # Step 6: Save Vector Store
            # ------------------------------------------------

            index_dir = (
                BASE_DIR
                / "data"
                / "indexes"
                / video_id
            )

            index_dir.mkdir(
                parents=True,
                exist_ok=True
            )

            vector_store.save_local(
                str(index_dir)
            )

            # ------------------------------------------------
            # Step 7: Store in Session
            # ------------------------------------------------

            st.session_state.vector_store = (
                vector_store
            )

            st.session_state.documents = (
                documents
            )

            st.session_state.video_id = (
                video_id
            )

            # ------------------------------------------------
            # Step 8: Generate Summary
            # ------------------------------------------------

            with st.spinner(
                "Generating video summary..."
            ):

                summary = summarize_video(
                    documents
                )

            st.session_state.summary = (
                summary
            )

            st.success(
                "🎉 Video processed successfully!"
            )

        except Exception as e:

            st.error(
                f"❌ Error while processing video:\n\n{e}"
            )


# ============================================================
# 7. DISPLAY SUMMARY
# ============================================================

if st.session_state.summary:

    st.divider()

    st.header("📄 Video Summary")

    st.markdown(
        st.session_state.summary
    )


# ============================================================
# 8. QUESTION ANSWERING
# ============================================================

st.divider()

st.header("💬 Ask Questions About the Video")


question = st.text_input(
    "Your question",
    placeholder="Example: What is the main topic of this video?"
)


ask_button = st.button(
    "🔍 Ask Question"
)


if ask_button:

    if st.session_state.vector_store is None:

        st.warning(
            "Please process a YouTube video first."
        )

    elif not question.strip():

        st.warning(
            "Please enter a question."
        )

    else:

        try:

            with st.spinner(
                "Searching the video and generating answer..."
            ):

                answer = answer_question(
                    st.session_state.vector_store,
                    question
                )

            st.subheader("🤖 Answer")

            st.write(answer)

        except Exception as e:

            st.error(
                f"❌ Error while answering:\n\n{e}"
            )


# ============================================================
# 9. VIDEO INFORMATION
# ============================================================

if st.session_state.video_id:

    st.divider()

    st.subheader("ℹ️ Video Information")

    st.write(
        f"**Video ID:** `{st.session_state.video_id}`"
    )

    if st.session_state.documents:

        st.write(
            f"**Number of chunks:** "
            f"{len(st.session_state.documents)}"
        )
