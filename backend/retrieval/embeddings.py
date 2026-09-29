"""
backend/retrieval/embeddings.py
===============================
Sentence Transformer embedding model loader using LRU caching.
"""

from functools import lru_cache
from langchain_huggingface import HuggingFaceEmbeddings

from config import EMBEDDING_MODEL


@lru_cache(maxsize=1)
def get_embedding_model():
    """
    Load and cache the Sentence Transformer embedding model in memory.
    """
    print(f"[EMBEDDING] Loading embedding model '{EMBEDDING_MODEL}' ...")
    model = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    print("[EMBEDDING] Embedding model loaded and cached.")
    return model
