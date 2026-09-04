"""
config.py
=========
Single source of truth for all application configuration.

WHY THIS FILE EXISTS
--------------------
Before refactoring:
  - rag.py loaded its own .env and hardcoded the model name
  - summarizer.py loaded its own .env and hardcoded the model name
  - embeddings.py hardcoded the model name
  - whisper_transcriber.py hardcoded "base" and computed the audio path inline

All of those scattered constants now live here.
Every other module imports what it needs from config.py.
If you ever need to change a model, chunk size, or path — you
change it in ONE place.

USAGE
-----
    from config import GROQ_API_KEY, GROQ_MODEL, CHUNK_SIZE, TOP_K

ENVIRONMENT VARIABLES
---------------------
Put your real values in .env (never commit .env to git):
    GROQ_API_KEY=gsk_...

See .env.example for all supported variables.
"""

import os
from pathlib import Path

from dotenv import load_dotenv


# ── Base directory (project root) ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent

# ── Load .env ─────────────────────────────────────────────────────────────────
load_dotenv(BASE_DIR / ".env")


# ── API Keys ──────────────────────────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

# ── Model Names ───────────────────────────────────────────────────────────────
# To switch to a different Groq model, change GROQ_MODEL here (or in .env).
# No other file needs to know the model name.
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

# Sentence Transformer for creating text embeddings.
EMBEDDING_MODEL: str = os.getenv(
    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)

# Whisper model size.
# Options: tiny, base, small, medium, large
# "base" is the recommended default for CPU machines.
WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base")


# ── Chunking ──────────────────────────────────────────────────────────────────
# CHUNK_SIZE:    max characters per chunk sent to the embedding model
# CHUNK_OVERLAP: characters of overlap between adjacent chunks
#                (prevents context being cut at chunk boundaries)
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE",    "1000"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))


# ── Retrieval ─────────────────────────────────────────────────────────────────
# Number of chunks returned by FAISS similarity search.
# k=4 is a sensible default — enough context for most questions.
TOP_K: int = int(os.getenv("TOP_K", "4"))


# ── Data Directories ──────────────────────────────────────────────────────────
DATA_DIR = BASE_DIR / "data"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
AUDIO_DIR = DATA_DIR / "audio"
INDEXES_DIR = DATA_DIR / "indexes"
SUMMARIES_DIR = DATA_DIR / "summaries"


# ── Summarisation ─────────────────────────────────────────────────────────────
# Groq has token-per-minute limits.  We split long transcripts
# before summarising to stay within those limits.
SUMMARY_MAX_CHARS: int = int(os.getenv("SUMMARY_MAX_CHARS",      "6000"))
SUMMARY_REQUEST_DELAY: int = int(os.getenv("SUMMARY_REQUEST_DELAY",  "5"))
