"""
retrieval/vector_store.py
==========================
FAISS vector store: create, save, and load.

MOVED FROM: vector_store.py (root)
CHANGES   : Import get_embedding_model from retrieval.embeddings

WHY FAISS?
----------
FAISS (Facebook AI Similarity Search) is a library for efficient
similarity search over large collections of vectors.

Given a question embedding (384 floats), FAISS scans all stored
chunk embeddings and returns the k most similar ones in milliseconds
— even over millions of vectors.

VECTOR STORE vs RETRIEVER
--------------------------
Vector store  → storage and search engine (FAISS index on disk)
Retriever     → the act of asking a question and getting top-k chunks

The similarity search that powers retrieval lives in llm/rag.py
(answer_question) because it is tightly coupled to how the LLM
uses the retrieved context.  This file only handles the index itself.

SAVING/LOADING
--------------
FAISS indexes are saved under data/indexes/<video_id>/.
When a user re-processes the same video, we load the existing index
instead of recomputing all embeddings — saving significant time.
"""

from pathlib import Path

from langchain_community.vectorstores import FAISS

from retrieval.embeddings import get_embedding_model


# ── Create ────────────────────────────────────────────────────────────────────

def create_vector_store(documents):
    """
    Build a new FAISS index from a list of LangChain Documents.

    HOW IT WORKS
    ------------
    1. get_embedding_model() returns the cached Sentence Transformer
    2. FAISS.from_documents() calls the model on every document's
       page_content and builds an index from the resulting vectors
    3. The index lives in memory until save_vector_store() persists it

    Args:
        documents: list of LangChain Document objects

    Returns:
        FAISS vector store instance
    """
    print(f"[VECTORSTORE] Building FAISS index for {len(documents)} chunks ...")
    embeddings   = get_embedding_model()
    vector_store = FAISS.from_documents(documents, embeddings)
    print("[VECTORSTORE] FAISS index built.")
    return vector_store


# ── Save ──────────────────────────────────────────────────────────────────────

def save_vector_store(vector_store, path: Path) -> None:
    """
    Persist a FAISS index to disk.

    Saves two files:
        <path>/index.faiss  — the binary vector index
        <path>/index.pkl    — document metadata (text, metadata dicts)

    Args:
        vector_store: FAISS instance to save
        path:         directory to save into
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    vector_store.save_local(str(path))
    print(f"[VECTORSTORE] FAISS index saved to {path}")


# ── Load ──────────────────────────────────────────────────────────────────────

def load_vector_store(path: Path):
    """
    Load a previously saved FAISS index from disk.

    WHY allow_dangerous_deserialization=True?
    -----------------------------------------
    FAISS uses pickle to serialise document metadata.  LangChain
    requires this flag to be explicit — it is safe here because we
    control what we saved (our own chunked Documents).

    Args:
        path: directory containing index.faiss and index.pkl

    Returns:
        FAISS vector store instance
    """
    embeddings   = get_embedding_model()
    vector_store = FAISS.load_local(
        str(path),
        embeddings,
        allow_dangerous_deserialization=True,
    )
    print(f"[VECTORSTORE] FAISS index loaded from {path}")
    return vector_store
