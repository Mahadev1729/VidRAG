from pathlib import Path

from langchain_community.vectorstores import FAISS

from embeddings import get_embedding_model


# ============================================================
# Create FAISS Vector Store
# ============================================================

def create_vector_store(documents):

    embeddings = get_embedding_model()

    vector_store = FAISS.from_documents(
        documents,
        embeddings
    )

    return vector_store


# ============================================================
# Save FAISS Vector Store
# ============================================================

def save_vector_store(
    vector_store,
    path: Path
):

    path.mkdir(
        parents=True,
        exist_ok=True
    )

    vector_store.save_local(
        str(path)
    )


# ============================================================
# Load FAISS Vector Store
# ============================================================

def load_vector_store(
    path: Path
):

    embeddings = get_embedding_model()

    vector_store = FAISS.load_local(
        str(path),
        embeddings,
        allow_dangerous_deserialization=True
    )

    return vector_store
