import os
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
# 6. RAG Question Answering
# ==================================================

def answer_question(
    vector_store,
    question: str,
    k: int = 4
):

    # ------------------------------------------------
    # Retrieve relevant chunks
    # ------------------------------------------------

    documents = vector_store.similarity_search(
        question,
        k=k
    )


    # ------------------------------------------------
    # If no documents found
    # ------------------------------------------------

    if not documents:

        return (
            "I couldn't find the answer in the video."
        )


    # ------------------------------------------------
    # Build context
    # ------------------------------------------------

    context = "\n\n".join(
        document.page_content
        for document in documents
    )


    # ------------------------------------------------
    # Prompt
    # ------------------------------------------------

    prompt = f"""
You are an AI assistant answering questions
about a YouTube video.

Use ONLY the context provided below.

Rules:
1. Do not use outside knowledge.
2. Do not make up information.
3. If the answer is not present in the context,
   say exactly:
   "I couldn't find the answer in the video."

CONTEXT:
-------------------------
{context}
-------------------------

QUESTION:
{question}

ANSWER:
"""


    # ------------------------------------------------
    # Call Groq
    # ------------------------------------------------

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "Answer questions using only "
                    "the provided video context."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2
    )


    # ------------------------------------------------
    # Return answer
    # ------------------------------------------------

    return response.choices[0].message.content
