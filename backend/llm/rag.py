"""
backend/llm/rag.py
==================
RAG (Retrieval-Augmented Generation) question answering with automatic model fallback.
"""

from typing import Tuple, List, Any
from config import GROQ_MODEL, TOP_K
from llm.groq_client import get_groq_client


def answer_question(
    vector_store,
    question: str,
    k: int = TOP_K,
) -> Tuple[str, List[Any]]:
    """
    Answer a question using RAG over the TiDB vector store.
    """
    # ── Step 1: Retrieve relevant chunks ─────────────────────────────────────
    print(f"[RETRIEVAL] Searching top-{k} chunks for: '{question[:60]}'")
    source_docs = vector_store.similarity_search(question, k=k)

    if not source_docs:
        return "I couldn't find the answer in the video.", []

    # ── Step 2: Build context string ─────────────────────────────────────────
    context = "\n\n".join(doc.page_content for doc in source_docs)

    # ── Step 3: Build structured prompt ──────────────────────────────────────
    prompt = f"""You are an intelligent, articulate AI assistant answering questions about a YouTube video based strictly on its transcript.

### Context from Video:
-------------------------
{context}
-------------------------

### User Question:
{question}

### Formatting & Answer Guidelines:
1. **Direct & Understandable**: Start with a clear, direct answer in 1-2 concise sentences.
2. **Structured Layout**: When providing explanations, multiple steps, or lists, use bullet points (`-`) or numbered lists (`1.`, `2.`).
3. **Emphasis**: Use **bold** on key concepts, metrics, and important terms for effortless reading.
4. **Accuracy**: Use ONLY the context provided above. Do not hallucinate or use outside knowledge.
5. **Missing Information**: If the answer cannot be found in the provided context, state clearly and politely:
   "I couldn't find information about that in the video transcript."

### Formatted Response:
"""

    # ── Step 4: Call Groq with active model fallbacks ─────────────────────────
    client = get_groq_client()
    candidate_models = [
        GROQ_MODEL,
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "openai/gpt-oss-120b",
        "qwen/qwen3.8-27b",
    ]
    # De-duplicate while preserving order
    models_to_try = []
    for m in candidate_models:
        if m and m not in models_to_try:
            models_to_try.append(m)

    last_error = None
    for model_name in models_to_try:
        try:
            print(f"[LLM] Sending context to Groq ({model_name}) ...")
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert video analyst. You provide crystal-clear, "
                            "beautifully formatted Markdown answers using only the given transcript context. "
                            "You always format answers with clean bullet points, bold key terms, and easy-to-read sections."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.2,
            )
            answer = response.choices[0].message.content or "I couldn't find the answer in the video."
            return answer, source_docs
        except Exception as err:
            last_error = err
            print(f"[LLM WARNING] Model '{model_name}' failed ({err}). Trying next model...")

    raise last_error


def answer_question_stream(
    vector_store,
    question: str,
    k: int = TOP_K,
):
    """
    Yields (token_text, source_docs) in real-time as Groq streams tokens.
    First chunk yields (empty_text, source_docs) so frontend renders citations immediately.
    """
    print(f"[RETRIEVAL STREAM] Searching top-{k} chunks for: '{question[:60]}'")
    source_docs = vector_store.similarity_search(question, k=k)

    if not source_docs:
        yield "I couldn't find the answer in the video.", []
        return

    context = "\n\n".join(doc.page_content for doc in source_docs)
    prompt = f"""You are an intelligent, articulate AI assistant answering questions about a YouTube video based strictly on its transcript.

### Context from Video:
-------------------------
{context}
-------------------------

### User Question:
{question}

### Formatting & Answer Guidelines:
1. **Direct & Understandable**: Start with a clear, direct answer in 1-2 concise sentences.
2. **Structured Layout**: When providing explanations, multiple steps, or lists, use bullet points (`-`) or numbered lists (`1.`, `2.`).
3. **Emphasis**: Use **bold** on key concepts, metrics, and important terms for effortless reading.
4. **Accuracy**: Use ONLY the context provided above. Do not hallucinate or use outside knowledge.
5. **Missing Information**: If the answer cannot be found in the provided context, state clearly and politely:
   "I couldn't find information about that in the video transcript."

### Formatted Response:
"""

    client = get_groq_client()
    candidate_models = [
        GROQ_MODEL,
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "openai/gpt-oss-120b",
        "qwen/qwen3.8-27b",
    ]
    models_to_try = []
    for m in candidate_models:
        if m and m not in models_to_try:
            models_to_try.append(m)

    for model_name in models_to_try:
        try:
            print(f"[LLM STREAM] Streaming response from Groq ({model_name}) ...")
            stream_resp = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert video analyst. You provide crystal-clear, "
                            "beautifully formatted Markdown answers using only the given transcript context. "
                            "You always format answers with clean bullet points, bold key terms, and easy-to-read sections."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.2,
                stream=True,
            )
            for chunk in stream_resp:
                content = chunk.choices[0].delta.content if chunk.choices else ""
                if content:
                    yield content, []
            return
        except Exception as err:
            print(f"[LLM STREAM WARNING] Model '{model_name}' failed ({err}). Trying next model...")

    yield "Error generating response from AI model.", []

