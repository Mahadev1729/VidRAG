"""
chunker.py
==========
Converts a plain-text transcript into a list of LangChain Documents.

KEPT AT ROOT — WHY?
-------------------
Chunking sits in the middle of the pipeline:
    ingestion → chunker → retrieval → llm

It is not purely "ingestion" (it does not fetch data),
not purely "retrieval" (it does not embed or search),
and not purely "llm" (it does not call the model).

Placing it at the root makes its central, bridge role explicit
and avoids forcing it into a folder where it does not naturally belong.

WHY CHUNK AT ALL?
-----------------
Embedding models have a token limit (usually 256–512 tokens).
A 30-minute video transcript can be 50,000+ characters — far too
long to embed as one piece.

We split it into overlapping chunks of ~1000 chars each:
  - Small enough for the embedding model to handle
  - Overlapping (200 chars) so relevant context is not cut off
    at a chunk boundary

WHY TIMESTAMPS STAY IN METADATA, NOT THE TEXT?
------------------------------------------------
If we embedded "At 2:05 the speaker says ..."
the embedding vector would encode the timestamp tokens.
Two chunks on the same topic but different timestamps would get
different vectors → worse similarity search.

Timestamps belong in metadata.  Metadata travels alongside the
vector but is NOT part of the embedding calculation.
It is only used AFTER retrieval, to generate the clickable
YouTube timestamp URL shown to the user.
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import CHUNK_SIZE, CHUNK_OVERLAP


def create_documents(text: str, video_id: str) -> list:
    """
    Split a transcript string into overlapping LangChain Documents.

    Each Document has:
        page_content: a chunk of the transcript text
        metadata:     {"video_id": ..., "source": "youtube"}
                      (start/end timestamps are added by app.py
                       via add_timestamp_metadata() after chunking)

    Args:
        text:     full transcript as a plain string
        video_id: YouTube video ID (stored in metadata)

    Returns:
        list of LangChain Document objects
    """
    print(f"[CHUNKING] Creating documents — chunk_size={CHUNK_SIZE}, "
          f"overlap={CHUNK_OVERLAP}")

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
    )

    documents = text_splitter.create_documents(
        [text],
        metadatas=[
            {
                "video_id": video_id,
                "source":   "youtube",
            }
        ],
    )

    print(f"[CHUNKING] Created {len(documents)} chunks.")

    return documents
