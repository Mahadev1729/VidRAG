"""
backend/config.py
=================
Single source of truth for all backend application configuration.
Exclusively uses TiDB Cloud connection string (TIDB_DATABASE_URL).
"""

import os
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

# ── Base directory ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

# ── Load .env from backend/ or project root ─────────────────────────────────
if (BASE_DIR / ".env").exists():
    load_dotenv(BASE_DIR / ".env")
if (PROJECT_ROOT / ".env").exists():
    load_dotenv(PROJECT_ROOT / ".env")


def _get_config(key: str, default: str = "") -> str:
    return os.getenv(key, default)


# ── TiDB Cloud Connection String ─────────────────────────────────────────────
TIDB_DATABASE_URL: str = (
    _get_config("TIDB_DATABASE_URL")
    or _get_config("DATABASE_URL")
    or _get_config("TIDB_STRING")
    or _get_config("TIDB_URI")
)

if TIDB_DATABASE_URL:
    normalized_url = TIDB_DATABASE_URL
    if normalized_url.startswith("mysql+pymysql://"):
        normalized_url = "mysql://" + normalized_url[len("mysql+pymysql://"):]
    elif normalized_url.startswith("tidb://"):
        normalized_url = "mysql://" + normalized_url[len("tidb://"):]

    parsed = urlparse(normalized_url)
    TIDB_HOST: str = parsed.hostname or ""
    TIDB_PORT: int = parsed.port or 4000
    TIDB_USER: str = parsed.username or ""
    TIDB_PASSWORD: str = parsed.password or ""
    TIDB_DATABASE: str = (parsed.path or "").lstrip("/") or "youtube_rag"
    TIDB_SSL_CA: str = _get_config("TIDB_SSL_CA", "")
else:
    TIDB_HOST = ""
    TIDB_PORT = 4000
    TIDB_USER = ""
    TIDB_PASSWORD = ""
    TIDB_DATABASE = "youtube_rag"
    TIDB_SSL_CA = ""


# ── JWT Authentication & Google OAuth ─────────────────────────────────────────
JWT_SECRET: str = _get_config("JWT_SECRET", "youtube_rag_super_secret_jwt_key_2026")
JWT_ALGORITHM: str = _get_config("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES: int = int(_get_config("JWT_EXPIRE_MINUTES", str(60 * 24 * 7)))
GOOGLE_CLIENT_ID: str = _get_config("GOOGLE_CLIENT_ID", "")

# ── Groq API & LLM ──────────────────────────────────────────────────────────
GROQ_API_KEY: str = _get_config("GROQ_API_KEY", "")
GROQ_MODEL: str = _get_config("GROQ_MODEL", "llama-3.3-70b-versatile")

# Sentence Transformer embeddings
EMBEDDING_MODEL: str = _get_config(
    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)

# Whisper Model
WHISPER_MODEL: str = _get_config("WHISPER_MODEL", "base")
GROQ_WHISPER_MODEL: str = _get_config("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")

# ── Data Directories ────────────────────────────────────────────────────────
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
AUDIO_DIR = DATA_DIR / "audio"
INDEXES_DIR = DATA_DIR / "indexes"
SUMMARIES_DIR = DATA_DIR / "summaries"

# ── Cookie Configuration for yt-dlp ─────────────────────────────────────────
COOKIES_FROM_BROWSER: str = _get_config("COOKIES_FROM_BROWSER", "").strip().lower()
_custom_cookies_file = _get_config("COOKIES_FILE", "").strip()

if _custom_cookies_file and Path(_custom_cookies_file).exists():
    COOKIES_FILE: Path | None = Path(_custom_cookies_file)
elif (BASE_DIR / "cookies.txt").exists():
    COOKIES_FILE: Path | None = BASE_DIR / "cookies.txt"
elif (PROJECT_ROOT / "cookies.txt").exists():
    COOKIES_FILE: Path | None = PROJECT_ROOT / "cookies.txt"
else:
    COOKIES_FILE: Path | None = None

# ── Chunking & Retrieval ────────────────────────────────────────────────────
CHUNK_SIZE: int = int(_get_config("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP: int = int(_get_config("CHUNK_OVERLAP", "200"))
TOP_K: int = int(_get_config("TOP_K", "4"))
SUMMARY_MAX_CHARS: int = int(_get_config("SUMMARY_MAX_CHARS", "6000"))
SUMMARY_REQUEST_DELAY: int = int(_get_config("SUMMARY_REQUEST_DELAY", "5"))
