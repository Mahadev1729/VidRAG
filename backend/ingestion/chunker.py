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
    Convert a list of transcript segments (with start, duration, end, text) into
    chunked LangChain Documents with preserved timestamp metadata.
    """
    if not segments:
        return []

    # If segments are short lines, group them up to CHUNK_SIZE while tracking start and end timestamps
    documents = []
    current_text = []
    current_length = 0
    current_start = segments[0].get("start", 0.0)
    current_end = segments[0].get("end", 0.0)

    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue
        
        seg_start = seg.get("start", 0.0)
        seg_end = seg.get("end", seg_start + seg.get("duration", 0.0))

        if current_length + len(text) > CHUNK_SIZE and current_text:
            chunk_content = " ".join(current_text)
            documents.append(
                Document(
                    page_content=chunk_content,
                    metadata={
                        "video_id": video_id,
                        "source": "youtube",
                        "start": current_start,
                        "end": current_end,
                    }
                )
            )
            # Retain overlap
            overlap_words = current_text[-max(1, len(current_text) // 5):]
            current_text = overlap_words + [text]
            current_length = sum(len(w) for w in current_text)
            current_start = seg_start
            current_end = seg_end
        else:
            current_text.append(text)
            current_length += len(text) + 1
            current_end = seg_end

    if current_text:
        chunk_content = " ".join(current_text)
        documents.append(
            Document(
                page_content=chunk_content,
                metadata={
                    "video_id": video_id,
                    "source": "youtube",
                    "start": current_start,
                    "end": current_end,
                }
            )
        )

    print(f"[CHUNKER] Generated {len(documents)} timestamped chunks for video {video_id}.")
    return documents
