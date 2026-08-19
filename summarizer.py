import os
import time
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq


# ==================================================
# 1. Project directory
# ==================================================

BASE_DIR = Path(__file__).resolve().parent


# ==================================================
# 2. Load environment variables
# ==================================================

ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


# ==================================================
# 3. Get Groq API key
# ==================================================

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError(
        "GROQ_API_KEY not found in .env"
    )


# ==================================================
# 4. Groq Client
# ==================================================

client = Groq(
    api_key=api_key
)


# ==================================================
# 5. Model
# ==================================================

MODEL_NAME = "openai/gpt-oss-20b"


# ==================================================
# 6. Configuration
# ==================================================

# Keep input comfortably below 8K tokens.
# 1 token is roughly 4 characters for English text.

MAX_CHARS_PER_REQUEST = 6000

# Delay between requests to avoid TPM spikes.
REQUEST_DELAY = 5


# ==================================================
# 7. Split text into small pieces
# ==================================================

def split_text(text, max_chars=MAX_CHARS_PER_REQUEST):

    words = text.split()

    chunks = []

    current_chunk = []
    current_length = 0

    for word in words:

        word_length = len(word) + 1

        if (
            current_length + word_length
            > max_chars
        ):

            chunks.append(
                " ".join(current_chunk)
            )

            current_chunk = []
            current_length = 0

        current_chunk.append(word)

        current_length += word_length

    if current_chunk:

        chunks.append(
            " ".join(current_chunk)
        )

    return chunks


# ==================================================
# 8. Summarize one small chunk
# ==================================================

def summarize_chunk(text, chunk_number, total_chunks):

    print(
        f"Summarizing chunk "
        f"{chunk_number}/{total_chunks}..."
    )

    prompt = f"""
Summarize the following section of a YouTube
video transcript.

Keep the important information.

Do not add outside information.

Write a concise summary.

TRANSCRIPT SECTION:

{text}

SUMMARY:
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,

        messages=[
            {
                "role": "system",
                "content": (
                    "You summarize transcript sections "
                    "accurately and concisely."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],

        temperature=0.2,

        max_tokens=500
    )

    return response.choices[0].message.content


# ==================================================
# 9. Create final summary
# ==================================================

def create_final_summary(summaries):

    combined = "\n\n".join(
        f"Section {i + 1}:\n{summary}"
        for i, summary in enumerate(summaries)
    )

    # The combined summaries should be very small
    # compared with the original transcript.

    prompt = f"""
Create a final summary of this YouTube video
using the section summaries below.

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

Do not add information that is not contained
in the section summaries.

SECTION SUMMARIES:

{combined}

FINAL SUMMARY:
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,

        messages=[
            {
                "role": "system",
                "content": (
                    "Create a concise final summary "
                    "from section summaries."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],

        temperature=0.2,

        max_tokens=800
    )

    return response.choices[0].message.content


# ==================================================
# 10. Main function used by app.py
# ==================================================

def summarize_video(documents):

    # ------------------------------------------------
    # Combine transcript
    # ------------------------------------------------

    transcript = "\n\n".join(
        document.page_content
        for document in documents
    )

    print(
        "\nTranscript characters:",
        len(transcript)
    )

    # ------------------------------------------------
    # Split into SMALL groups
    # ------------------------------------------------

    chunks = split_text(transcript)

    print(
        "Summary chunks:",
        len(chunks)
    )

    # ------------------------------------------------
    # Summarize chunks
    # ------------------------------------------------

    summaries = []

    for i, chunk in enumerate(chunks):

        summary = summarize_chunk(
            chunk,
            i + 1,
            len(chunks)
        )

        summaries.append(summary)

        # --------------------------------------------
        # Wait before next Groq request
        # --------------------------------------------

        if i < len(chunks) - 1:

            print(
                f"Waiting {REQUEST_DELAY} seconds..."
            )

            time.sleep(
                REQUEST_DELAY
            )

    # ------------------------------------------------
    # Final summary
    # ------------------------------------------------

    print(
        "\nCreating final summary..."
    )

    # Wait before final request
    time.sleep(REQUEST_DELAY)

    final_summary = create_final_summary(
        summaries
    )

    return final_summary
