"""
llm/summarizer.py
=================
Multi-chunk transcript summarisation using Groq.

MOVED FROM: summarizer.py (root)
CHANGES   : Removed own load_dotenv + Groq() init.
            Now imports get_groq_client() from llm.groq_client.
            Imports GROQ_MODEL, SUMMARY_MAX_CHARS, SUMMARY_REQUEST_DELAY
            from config.

WHY MULTI-CHUNK?
----------------
Groq has token-per-minute (TPM) limits.  A long transcript can
exceed the single-request limit.  We split the transcript into
chunks of ~6000 characters, summarise each independently, then
combine the section summaries into one final structured summary.

This "map-reduce" pattern is common in LLM-based summarisation:
  map    → summarise each section independently
  reduce → combine section summaries into one final summary

FLOW
----
documents (LangChain Docs)
    ↓ join page_content
full transcript text
    ↓ split_text()
[chunk1, chunk2, ..., chunkN]
    ↓ summarize_chunk() × N   (with delay between calls)
[summary1, summary2, ..., summaryN]
    ↓ create_final_summary()
final structured summary (markdown)
"""

import time

from config import GROQ_MODEL, SUMMARY_MAX_CHARS, SUMMARY_REQUEST_DELAY
from llm.groq_client import get_groq_client


# ── Split Text into Pieces ────────────────────────────────────────────────────

def split_text(text: str, max_chars: int = SUMMARY_MAX_CHARS) -> list:
    """
    Split a long text string into word-aligned chunks of at most
    max_chars characters.

    Word-aligned means we never cut in the middle of a word —
    we accumulate words until adding the next would exceed max_chars,
    then start a new chunk.

    Args:
        text:      text to split
        max_chars: maximum characters per chunk

    Returns:
        list of text chunk strings
    """
    words         = text.split()
    chunks        = []
    current_chunk = []
    current_len   = 0

    for word in words:
        word_len = len(word) + 1  # +1 for the space
        if current_len + word_len > max_chars:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
            current_len   = 0
        current_chunk.append(word)
        current_len += word_len

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


# ── Summarise One Chunk ───────────────────────────────────────────────────────

def summarize_chunk(text: str, chunk_number: int, total_chunks: int) -> str:
    """
    Send one transcript section to Groq and return a concise summary.

    Args:
        text:         transcript section text
        chunk_number: 1-based index (for logging)
        total_chunks: total number of chunks (for logging)

    Returns:
        str: summary of this section
    """
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

    client   = get_groq_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role":    "system",
                "content": "You summarise transcript sections accurately and concisely.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=500,
    )

    return response.choices[0].message.content


# ── Create Final Summary ──────────────────────────────────────────────────────

def create_final_summary(summaries: list) -> str:
    """
    Combine section summaries into one structured final summary.

    Args:
        summaries: list of per-section summary strings

    Returns:
        str: final markdown-formatted summary
    """
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

    client   = get_groq_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role":    "system",
                "content": "Create a concise final summary from section summaries.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=800,
    )

    return response.choices[0].message.content


# ── Public Entry Point ────────────────────────────────────────────────────────

def summarize_video(documents) -> str:
    """
    Summarise a video given its LangChain Documents.

    Called from app.py after chunking.  Only called once per video
    (the result is cached in st.session_state.summary and saved to
    data/summaries/<video_id>.txt so it survives page reruns).

    Args:
        documents: list of LangChain Document objects

    Returns:
        str: final structured summary (markdown)
    """
    # Join all chunk texts into one full transcript
    transcript = "\n\n".join(doc.page_content for doc in documents)

    print(f"\n[SUMMARIZER] Transcript length: {len(transcript)} chars")

    chunks = split_text(transcript)

    print(f"[SUMMARIZER] Splitting into {len(chunks)} chunks ...")

    summaries = []

    for i, chunk in enumerate(chunks):
        summary = summarize_chunk(chunk, i + 1, len(chunks))
        summaries.append(summary)

        # Delay between Groq calls to avoid hitting TPM limits
        if i < len(chunks) - 1:
            print(f"[SUMMARIZER] Waiting {SUMMARY_REQUEST_DELAY}s ...")
            time.sleep(SUMMARY_REQUEST_DELAY)

    print("\n[SUMMARIZER] Creating final summary ...")
    time.sleep(SUMMARY_REQUEST_DELAY)

    return create_final_summary(summaries)
