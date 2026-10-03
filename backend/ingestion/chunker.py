"""
backend/ingestion/chunker.py
============================
Converts transcript segments or text into LangChain Documents with timestamp metadata.
"""

from typing import List, Dict, Any
from langchain_core.documents import Document

from config import CHUNK_SIZE, CHUNK_OVERLAP


def create_documents_from_segments(segments: List[Dict[str, Any]], video_id: str) -> List[Document]:
    """
    Convert a list of transcript segments or text into chunked LangChain Documents.
    """
    if not segments:
        return []

    documents = []
    current_text = []
    current_length = 0

    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue

        if current_length + len(text) > CHUNK_SIZE and current_text:
            chunk_content = " ".join(current_text)
            documents.append(
                Document(
                    page_content=chunk_content,
                    metadata={
                        "video_id": video_id,
                        "source": "youtube",
                    }
                )
            )
            # Retain overlap
            overlap_words = current_text[-max(1, len(current_text) // 5):]
            current_text = overlap_words + [text]
            current_length = sum(len(w) for w in current_text)
        else:
            current_text.append(text)
            current_length += len(text) + 1

    if current_text:
        chunk_content = " ".join(current_text)
        documents.append(
            Document(
                page_content=chunk_content,
                metadata={
                    "video_id": video_id,
                    "source": "youtube",
                }
            )
        )

    print(f"[CHUNKER] Generated {len(documents)} text chunks for video {video_id}.")
    return documents
