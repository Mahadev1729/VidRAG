"""
backend/retrieval/embeddings.py
===============================
FastEmbed ONNX-powered high-performance embedding model loader.
Replaces heavy PyTorch/HuggingFace SentenceTransformers with lightning-fast ONNX Runtime.
"""

from functools import lru_cache
from typing import List
from fastembed import TextEmbedding
from config import EMBEDDING_MODEL


class FastEmbeddingWrapper:
    """
    Wrapper around fastembed.TextEmbedding conforming to standard LangChain embedding interface:
    - embed_documents(texts: List[str]) -> List[List[float]]
    - embed_query(text: str) -> List[float]
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        print(f"[EMBEDDING] Initializing FastEmbed ONNX model '{model_name}'...")
        self.model = TextEmbedding(model_name=model_name)
        print("[EMBEDDING] FastEmbed ONNX model loaded successfully (~0.5s).")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of document chunks."""
        embeddings_generator = self.model.embed(texts)
        return [emb.tolist() if hasattr(emb, "tolist") else list(emb) for emb in embeddings_generator]

    @lru_cache(maxsize=1024)
    def _cached_embed_query(self, text: str) -> tuple:
        embedding_generator = self.model.embed([text])
        emb = next(embedding_generator)
        return tuple(emb.tolist() if hasattr(emb, "tolist") else list(emb))

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query string (cached for 0ms repeat latency)."""
        return list(self._cached_embed_query(text.strip()))


@lru_cache(maxsize=1)
def get_embedding_model() -> FastEmbeddingWrapper:
    """
    Load and cache the FastEmbed embedding model instance in memory.
    """
    return FastEmbeddingWrapper(model_name=EMBEDDING_MODEL)
