"""
llm/rag.py
==========
RAG (Retrieval-Augmented Generation) question answering.

MOVED FROM: rag.py (root)
CHANGES   : Removed own load_dotenv + Groq() init.
            Now imports get_groq_client() from llm.groq_client.
            Imports GROQ_MODEL and TOP_K from config.

WHAT IS RAG?
------------
RAG = Retrieval-Augmented Generation.

Without RAG:
  Question → LLM → answer based on training data
  Problem:  LLM has no knowledge of THIS specific video.

With RAG:
  Question → FAISS similarity search → top-k relevant chunks
           → inject chunks into prompt → LLM → grounded answer

The LLM is told to ONLY use the provided context.  This prevents
hallucination and grounds every answer in the actual video content.

HOW answer_question() WORKS
----------------------------
1. Embed the question using the same model used to embed chunks
2. FAISS finds the top-k most similar chunks
3. Join those chunks into a single "context" string
4. Build a prompt: [system rules] + [context] + [question]
5. Send to Groq → get answer
6. Return both the answer text AND the retrieved source documents
   (so the caller can show timestamp links)

WHY TOP_K = 4?
--------------
k is configurable because the optimal value depends on the use case:
  - Short factual Q&A → k=2 or 3 (less noise)
  - Broad thematic questions → k=5 or 6 (more context)
  - Summarisation-like queries → k=8+
Set TOP_K in .env to override without code changes.
"""

from config import GROQ_MODEL, TOP_K
from llm.groq_client import get_groq_client


def answer_question(
    vector_store,
    question: str,
    k: int = TOP_K,
) -> tuple[str, list]:
    """
    Answer a question using RAG over the FAISS vector store.

    Args:
        vector_store: FAISS vector store (from retrieval/vector_store.py)
        question:     user's question string
        k:            number of chunks to retrieve (default: TOP_K from config)

    Returns:
        tuple:
            answer (str):          LLM-generated grounded answer
            source_docs (list):    list of retrieved LangChain Documents
                                   (each has metadata with "start", "end",
                                    "video_id" for timestamp links)
    """

    # ── Step 1: Retrieve relevant chunks ─────────────────────────────────────
    print(f"[RETRIEVAL] Searching top-{k} chunks for: '{question[:60]}'")

    source_docs = vector_store.similarity_search(question, k=k)

    if not source_docs:
        return "I couldn't find the answer in the video.", []

    # ── Step 2: Build context string ─────────────────────────────────────────
    context = "\n\n".join(doc.page_content for doc in source_docs)

    # ── Step 3: Build prompt ──────────────────────────────────────────────────
    prompt = f"""
You are an AI assistant answering questions about a YouTube video.

Use ONLY the context provided below.

Rules:
1. Do not use outside knowledge.
2. Do not make up information.
3. If the answer is not present in the context, say exactly:
   "I couldn't find the answer in the video."

CONTEXT:
-------------------------
{context}
-------------------------

QUESTION:
{question}

ANSWER:
"""

    # ── Step 4: Call Groq ─────────────────────────────────────────────────────
    print(f"[LLM] Sending context to Groq ({GROQ_MODEL}) ...")

    client   = get_groq_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role":    "system",
                "content": "Answer questions using only the provided video context.",
            },
            {
                "role":    "user",
                "content": prompt,
            },
        ],
        temperature=0.2,
    )

    answer = response.choices[0].message.content

    # ── Step 5: Return answer + source docs (for timestamp links) ─────────────
    return answer, source_docs
