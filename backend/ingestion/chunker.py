"""
backend/ingestion/chunker.py
============================
Converts transcript segments or text into LangChain Documents using standard RecursiveCharacterTextSplitter.
"""

from typing import List, Dict, Any
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import CHUNK_SIZE, CHUNK_OVERLAP


def create_documents_from_segments(segments: List[Dict[str, Any]], video_id: str) -> List[Document]:
    """
    Standard Recursive Character Chunking for YouTube Transcripts.
    Recursively splits on paragraphs, sentences, and words to preserve semantic coherence.
    """
    if not segments:
        return []

    # 1. Reconstruct full transcript text from segments
    full_text = " ".join(seg.get("text", "").strip() for seg in segments if seg.get("text"))
    if not full_text.strip():
        return []

    # 2. Use industry-standard RecursiveCharacterTextSplitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    # 3. Create LangChain Documents with video metadata
    documents = text_splitter.create_documents(
        texts=[full_text],
        metadatas=[{"video_id": video_id, "source": "youtube"}],
    )

    print(f"[CHUNKER] Generated {len(documents)} chunks using RecursiveCharacterTextSplitter for video {video_id}.")
    return documents
