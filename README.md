# 🎥 YouTube RAG Assistant

A local AI assistant that lets you **summarise any YouTube video and ask questions about its content** — grounded entirely in what the video actually says.

Built with Python, Streamlit, LangChain, Sentence Transformers, FAISS, Groq, Whisper, and SQLite.

---

## Features

- 🔐 **Secure User Authentication**: Complete SQLite3 user registration & login system (PBKDF2-HMAC-SHA256, 100,000 rounds, 16-byte random salt).
- 📧 **Dual Sign-In**: Sign in seamlessly using either your **Username or Gmail / Email Address**.
- 👤 **Session Guard & User Status**: Authenticated route protection with sidebar user status (`👤 [username] ● Active`) and one-click logout.
- 🔗 **Instant Video Ingestion**: Paste any YouTube URL and process it into a vector knowledge base.
- 📝 **Automatic Captions**: Transcript retrieval via YouTube captions with language fallback.
- 🎙️ **Whisper Fallback**: Local Whisper transcription via `yt-dlp` when captions are disabled or unavailable.
- 🧠 **RAG (Retrieval-Augmented Generation)**: Grounded question answering strictly based on video transcripts.
- 📍 **Clickable Timestamps**: Every answer source links directly to the exact second in the YouTube video.
- 📄 **Automatic Video Summary**: High-level key takeaways generated for quick understanding.
- 💬 **Persistent Conversation History**: Video-specific chat history stored locally in SQLite.
- ⚡ **Cached FAISS Index**: Vector stores cached to disk to eliminate re-embedding on reload.
- 🎨 **Clean Design System**: Externalized stylesheet (`static/style.css`) with Space Grotesk & DM Sans typography and high-contrast styling.

---

## Architecture

```
app.py (UI Layer & Route Guard)
  │
  ├──► utils/auth.py          → SQLite User DB + PBKDF2 Hashing + Dual Sign-In
  ├──► utils/styles.py        → Injects static/style.css design tokens
  │
  ▼
ingestion/
  ├── youtube_loader.py       → YouTube Transcript API
  ├── whisper_loader.py       → yt-dlp + Whisper fallback
  └── chunker.py              → Split transcript into overlapping chunks
  │
  ▼
retrieval/
  ├── embeddings.py           → Sentence Transformers (MiniLM)
  └── vector_store.py         → FAISS index (create / save / load)
  │
  ▼
llm/
  ├── groq_client.py          → Groq API client (shared)
  ├── rag.py                  → Retrieval + prompt + answer with sources
  └── summarizer.py           → Multi-chunk video summarisation
```

### Data Flow

```
1. User Authentication
   Username/Email + Password ──► PBKDF2 Constant-Time Check ──► Authenticated Session

2. Video Ingestion
   YouTube URL
        ↓
    ingestion/
        ├── YouTube Transcript API  ──► success → segments
        └── FAIL → yt-dlp → MP3 → Whisper → segments
        ↓
   Timestamped Transcript Segments
        ↓
    ingestion/chunker.py
        ↓
   LangChain Documents (with start/end metadata)
        ↓
    retrieval/embeddings.py  →  384-dim vectors
        ↓
    retrieval/vector_store.py  →  FAISS index

3. Question Answering
   User Question → FAISS similarity search → top-4 chunks
        ↓
    llm/rag.py  →  context + prompt → Groq
        ↓
   Grounded Answer + Clickable Timestamp Sources
```

---

## Project Structure

```
YoutubeChatBot_RAG/
│
├── app.py                  ← Streamlit UI, entry point, & page guard
├── chat_history.py         ← SQLite conversation history
├── config.py               ← Configuration and environment variables
│
├── .streamlit/
│   └── config.toml         ← Streamlit theme configuration (light palette)
│
├── static/
│   └── style.css           ← Design system (fonts, forms, cards, responsive rules)
│
├── utils/
│   ├── __init__.py
│   ├── auth.py             ← SQLite auth, PBKDF2 hashing, dual login, auth card
│   └── styles.py           ← Style injection utility (load_css)
│
├── ingestion/
│   ├── __init__.py
│   ├── youtube_loader.py   ← URL parsing, YouTube Transcript API, Whisper fallback
│   ├── whisper_loader.py   ← yt-dlp audio download + local Whisper transcription
│   └── chunker.py          ← Transcript → overlapping LangChain Documents
│
├── retrieval/
│   ├── __init__.py
│   ├── embeddings.py       ← Sentence Transformer (all-MiniLM-L6-v2)
│   └── vector_store.py     ← FAISS create / save / load
│
├── llm/
│   ├── __init__.py
│   ├── groq_client.py      ← Shared Groq API client
│   ├── rag.py              ← RAG question answering
│   └── summarizer.py       ← Multi-chunk video summarisation
│
├── data/
│   ├── transcripts/        ← Saved transcript text files
│   ├── audio/              ← Temporary audio (deleted after transcription)
│   ├── indexes/            ← FAISS indexes per video
│   ├── summaries/          ← Cached summary text files
│   └── chat_history.db     ← SQLite chat messages
│
├── users.db                ← Local user credentials database (gitignored)
├── .env                    ← Secrets & API keys (gitignored)
├── .env.example            ← Template for environment variables
├── .gitignore              ← Excludes users.db*, .env, audio/, etc.
└── requirements.txt        ← Python dependencies
```

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/YoutubeChatBot_RAG.git
cd YoutubeChatBot_RAG
```

### 2. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install FFmpeg

FFmpeg is required for Whisper fallback (audio extraction).

- **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to `PATH`
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg`

### 5. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env` and configure your Groq API key:

```env
GROQ_API_KEY=gsk_your_key_here
```

Get a free key at [console.groq.com](https://console.groq.com).

### 6. Run the application

```bash
streamlit run app.py
```

---

## Authentication & Security

The application includes a built-in user authentication layer implemented strictly using the Python Standard Library (`sqlite3`, `hashlib`, `secrets`):

- **Database Table**: Automatically initializes `users.db` with auto-migration:
  ```sql
  CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL COLLATE NOCASE,
      email TEXT UNIQUE COLLATE NOCASE,
      password_hash TEXT NOT NULL,
      salt TEXT NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
  ```
- **Password Security**:
  - **Salt**: 16 cryptographically secure random bytes generated via `secrets.token_bytes(16)`.
  - **Hashing**: PBKDF2 HMAC-SHA256 with 100,000 iterations (`hashlib.pbkdf2_hmac`).
  - **Verification**: Constant-time comparison using `secrets.compare_digest`.
- **Registration**:
  - Requires a unique Username (≥ 3 characters) and valid Gmail / Email address.
  - Requires Password (≥ 6 characters) with confirmation check.
- **Dual Sign-In**:
  - Users can sign in using either their **Username** or **Gmail / Email Address**.
- **Session Control**:
  - Unauthorized visitors are restricted to the authentication card.
  - Logging out clears `st.session_state` and returns to the login screen.
  - Credential database (`users.db*`) is excluded from Git tracking via `.gitignore`.

---

## Environment Variables

| Variable                 | Default                                  | Description                                                     |
| ------------------------ | ---------------------------------------- | --------------------------------------------------------------- |
| `GROQ_API_KEY`           | —                                        | **Required.** Your Groq API key                                 |
| `GROQ_MODEL`             | `openai/gpt-oss-20b`                     | Groq model name                                                 |
| `EMBEDDING_MODEL`        | `sentence-transformers/all-MiniLM-L6-v2` | Sentence Transformer embedding model                            |
| `WHISPER_MODEL`          | `base`                                   | Whisper model size (`tiny`, `base`, `small`, `medium`, `large`) |
| `CHUNK_SIZE`             | `1000`                                   | Characters per transcript chunk                                 |
| `CHUNK_OVERLAP`          | `200`                                    | Overlap characters between adjacent chunks                      |
| `TOP_K`                  | `4`                                      | Number of chunks retrieved per question                         |
| `FORCE_WHISPER_FALLBACK` | `0`                                      | Set to `1` to bypass YouTube captions and force Whisper         |

---

## Technology Stack

| Component          | Technology                               | Description                                         |
| ------------------ | ---------------------------------------- | --------------------------------------------------- |
| **UI**             | Streamlit                                | Interactive web interface                           |
| **Styling**        | Vanilla CSS                              | Custom tokens & stylesheet (`static/style.css`)     |
| **Authentication** | SQLite3 + Python StdLib                  | PBKDF2-HMAC-SHA256 & dual sign-in (`utils/auth.py`) |
| **Transcript API** | `youtube-transcript-api`                 | Official and auto-generated YouTube captions        |
| **Audio Download** | `yt-dlp`                                 | High-performance audio stream extractor            |
| **Speech-to-Text** | `openai-whisper`                         | Local audio transcription fallback                  |
| **Chunking**       | LangChain `RecursiveCharacterTextSplitter` | Overlapping semantic text chunking                |
| **Embeddings**     | Sentence Transformers (`all-MiniLM-L6-v2`)| 384-dimensional dense text embeddings              |
| **Vector Store**   | FAISS (`faiss-cpu`)                      | Fast local similarity search                        |
| **LLM**            | Groq (`openai/gpt-oss-20b`)              | Ultra-fast inference for summaries & answers        |
| **Chat History**   | SQLite                                   | Per-video conversation persistence                  |

---

## Limitations

- Whisper fallback requires local FFmpeg and processing time scales with video length.
- Groq free tier has token-per-minute rate limits; very long video summarisation may take a few seconds.
- Private, unlisted, or age-restricted videos cannot be downloaded or transcribed.
- Grounded answers depend directly on transcript quality.

---

## Future Improvements

- Multi-video cross-search & playlist ingestion
- Chapter-aware transcript chunking
- Support for local audio/video file uploads
- Real-time streaming LLM responses
- Export conversation and summary to PDF / Markdown
