"""
backend/llm/summarizer.py
=========================
Multi-chunk transcript summarisation using Groq map-reduce pattern with candidate model fallbacks.
"""

import time
from typing import List
from config import GROQ_MODEL, SUMMARY_MAX_CHARS, SUMMARY_REQUEST_DELAY
from llm.groq_client import get_groq_client


def _call_groq_with_fallback(system_prompt: str, user_prompt: str, max_tokens: int = 600) -> str:
    """Helper to execute chat completion with fallback models."""
    client = get_groq_client()
    candidate_models = [
        GROQ_MODEL,
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.8-27b",
        "allam-2-7b",
    ]
    models_to_try = []
    for m in candidate_models:
        if m and m not in models_to_try:
            models_to_try.append(m)

    last_error = None
    for model_name in models_to_try:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as err:
            last_error = err
            print(f"[SUMMARIZER WARNING] Model '{model_name}' failed ({err}). Trying fallback...")

    raise last_error


def split_text(text: str, max_chars: int = SUMMARY_MAX_CHARS) -> List[str]:
    """Split a long text string into word-aligned chunks of at most max_chars characters."""
    words = text.split()
    chunks = []
    current_chunk = []
    current_len = 0

    for word in words:
        word_len = len(word) + 1
        if current_len + word_len > max_chars:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
            current_len = 0
        current_chunk.append(word)
        current_len += word_len

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def summarize_chunk(text: str, chunk_number: int, total_chunks: int) -> str:
    """Send one transcript section to Groq and return a concise summary."""
    print(f"[SUMMARIZER] Summarising chunk {chunk_number}/{total_chunks} ...")

    prompt = f"""
Summarize the following section of a YouTube video transcript.
Keep the important information.
Do not add outside information.
Write a concise summary.

TRANSCRIPT SECTION:
{text}

SUMMARY:
"""
    return _call_groq_with_fallback(
        system_prompt="You summarise transcript sections accurately and concisely.",
        user_prompt=prompt,
        max_tokens=500,
    )


def create_final_summary(summaries: List[str]) -> str:
    """Combine section summaries into one structured final markdown summary."""
    combined = "\n\n".join(
        f"Section {i + 1}:\n{s}" for i, s in enumerate(summaries)
    )

    prompt = f"""
Create a final summary of this YouTube video using the section summaries below.

Use this structure:

## Main Topic

## Key Points
- Point 1
- Point 2
- Point 3
- Point 4
- Point 5

## Important Concepts

## Conclusion

Do not add information that is not in the section summaries.

SECTION SUMMARIES:
{combined}

FINAL SUMMARY:
"""
    return _call_groq_with_fallback(
        system_prompt="Create a concise final summary from section summaries.",
        user_prompt=prompt,
        max_tokens=800,
    )


def summarize_transcript(transcript: str) -> str:
    """
    Summarize raw transcript text.
    """
    if not transcript or not transcript.strip():
        return "No transcript content to summarize."

    chunks = split_text(transcript)
    if len(chunks) == 1:
        return summarize_chunk(chunks[0], 1, 1)

    summaries = []
    for i, chunk in enumerate(chunks):
        summary = summarize_chunk(chunk, i + 1, len(chunks))
        summaries.append(summary)
        if i < len(chunks) - 1 and SUMMARY_REQUEST_DELAY > 0:
            time.sleep(SUMMARY_REQUEST_DELAY)

    return create_final_summary(summaries)


def summarize_video(documents) -> str:
    """
    Summarise a video given its LangChain Documents.
    """
    transcript = "\n\n".join(doc.page_content for doc in documents)
    return summarize_transcript(transcript)
