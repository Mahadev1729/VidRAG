"""
retrieval/embeddings.py
=======================
Sentence Transformer embedding model loader.

MOVED FROM: embeddings.py (root)
CHANGES   : Uses EMBEDDING_MODEL from config.py
            @st.cache_resource on get_embedding_model()

WHY EMBEDDINGS BELONG IN retrieval/
-------------------------------------
Embeddings and FAISS are two halves of the same system:
  - embeddings.py converts text → vector
  - vector_store.py stores and searches those vectors

Grouping them in retrieval/ makes that relationship explicit.

HOW EMBEDDINGS WORK
--------------------
"Sentence Transformers" is a library that wraps the
all-MiniLM-L6-v2 model.  This model was trained to map
semantically similar sentences close together in 384-dimensional
vector space.

  "What is machine learning?"
        ↓  embedding model
  [0.12, -0.34, 0.87, ...]   ← 384 floats

  "Explain ML to me"
        ↓  embedding model
  [0.11, -0.32, 0.85, ...]   ← similar vector → nearby in FAISS

So when you ask a question, its embedding vector is compared to
every chunk's vector.  The chunks with the closest vectors are
the most relevant — retrieved as context for the LLM.

CACHING
-------
The embedding model is ~90 MB.  Loading it takes a few seconds.
@st.cache_resource loads it once and reuses it for the lifetime
of the Streamlit server process.
"""

import streamlit as st
from langchain_huggingface import HuggingFaceEmbeddings

from config import EMBEDDING_MODEL


@st.cache_resource
def get_embedding_model():
    """
    Load and cache the Sentence Transformer embedding model.

    Returns:
        HuggingFaceEmbeddings: the cached embedding model instance

    @st.cache_resource
    - Runs only ONCE per Streamlit server process
    - The same model instance is shared across all user sessions
    - Perfect for stateless, expensive resources like ML models
    """
    print(f"[EMBEDDING] Loading embedding model '{EMBEDDING_MODEL}' ...")
    model = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    print("[EMBEDDING] Embedding model loaded and cached.")
    return model
