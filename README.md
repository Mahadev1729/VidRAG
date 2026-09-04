# 🎥 YouTube RAG Assistant

A local AI assistant that lets you **summarise any YouTube video and ask questions about its content** — grounded entirely in what the video actually says.

Built with Python, Streamlit, LangChain, Sentence Transformers, FAISS, Groq, and Whisper.

---

## Features

- 🔗 Paste any YouTube URL and process it instantly
- 📝 Automatic transcript retrieval via YouTube captions
- 🎙️ Whisper fallback when captions are unavailable
- 🧠 RAG (Retrieval-Augmented Generation) for accurate, grounded answers
- 📍 Clickable timestamp links for every answer source
- 📄 Automatic video summary generation
- 💬 Persistent conversation history per video
- ⚡ FAISS index cached on disk — no re-embedding on reload

---

## Architecture

```
app.py
  │
  ▼
ingestion/
  ├── youtube_loader.py   → YouTube Transcript API
  └── whisper_loader.py   → yt-dlp + Whisper fallback
  └── chunker.py          → split transcript into chunks
  │
  ▼
retrieval/
  ├── embeddings.py       → Sentence Transformers (MiniLM)
  └── vector_store.py     → FAISS index (create / save / load)
  │
  ▼
llm/
  ├── groq_client.py      → Groq API client (shared)
  ├── rag.py              → retrieval + prompt + answer
  └── summarizer.py       → multi-chunk summarisation
```

### Data Flow

```
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
     ↓
User Question → similarity search → top-4 chunks
     ↓
 llm/rag.py  →  context + prompt → Groq
     ↓
Grounded Answer + Timestamp Sources
```

---

## Project Structure

```
YoutubeChatBot_RAG/
│
├── app.py                  ← Streamlit UI + pipeline orchestration
├── chat_history.py         ← SQLite conversation history
├── config.py               ← All configuration and environment variables
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
│   └── indexes/            ← FAISS indexes per video
│
├── .env                    ← Your secrets (not committed)
├── .env.example            ← Template for new developers
├── .gitignore
└── requirements.txt
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

FFmpeg is required for Whisper fallback (audio processing).

- **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg`

### 5. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env` and add your Groq API key:

```
GROQ_API_KEY=gsk_your_key_here
```

Get a free key at [console.groq.com](https://console.groq.com).

### 6. Run the app

```bash
streamlit run app.py
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | — | **Required.** Your Groq API key |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | Groq model name |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model |
| `WHISPER_MODEL` | `base` | Whisper model size (`tiny`, `base`, `small`, `medium`, `large`) |
| `CHUNK_SIZE` | `1000` | Characters per transcript chunk |
| `CHUNK_OVERLAP` | `200` | Overlap between adjacent chunks |
| `TOP_K` | `4` | Number of chunks retrieved per question |
| `FORCE_WHISPER_FALLBACK` | `0` | Set to `1` to skip YouTube captions and test Whisper |

## Optional User Authentication

Authentication uses Streamlit's OIDC support. To enable it:

1. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`.
2. Create an OIDC application with Google or another compatible identity provider.
3. Replace the client values in `secrets.toml` and set the correct production redirect URI.
4. Set `AUTH_ENABLED=true` in `.env` or your deployment environment.

Authentication is disabled by default for local development. Never commit
`.streamlit/secrets.toml` or place credentials in source code.

---

## How It Works

### 1. Transcript Retrieval

When you submit a YouTube URL, the app tries **YouTube captions first**:

- Checks for English captions → manual captions → auto-generated captions
- If any caption is found → used directly (fastest path)

If captions fail for any reason (disabled, unavailable, parse error):

- **Whisper fallback** activates automatically
- `yt-dlp` downloads the audio stream as MP3
- Local `openai-whisper` transcribes it with word-level timestamps
- Audio file is deleted immediately after transcription

Both paths return the same structure:
```python
[{"text": "...", "start": 120.5, "duration": 4.2, "end": 124.7}]
```

### 2. Chunking

The transcript is split into overlapping 1000-character chunks.

- **Why chunk?** Embedding models have a token limit — a full transcript can be 50,000+ characters
- **Why overlap?** 200-character overlap prevents context from being cut at boundaries

### 3. Embeddings

Each chunk is converted to a 384-dimensional vector using `all-MiniLM-L6-v2`:

```
"What is machine learning?"  →  [0.12, -0.34, 0.87, ...]
```

Semantically similar sentences produce similar vectors. This is how FAISS finds relevant chunks for any question.

### 4. FAISS Vector Store

Vectors are stored in a FAISS index saved to `data/indexes/<video_id>/`.

- First time: embeddings computed, index built and saved to disk
- Subsequent loads: index loaded from disk — no re-embedding needed

### 5. RAG Question Answering

```
Question → embed → FAISS similarity search → top-4 chunks
         → build prompt with context
         → send to Groq
         → grounded answer + source documents
```

The LLM is instructed to answer **only from the retrieved context**. If the answer is not in the video, it says so.

### 6. Timestamps

Every retrieved chunk carries `start` and `end` metadata (in seconds). The app converts these to clickable YouTube links:

```
https://www.youtube.com/watch?v=VIDEO_ID&t=120s
```

Timestamps are stored in **metadata only** — never embedded into the vector — so they don't affect similarity search accuracy.

---

## Technology Stack

| Component | Technology |
|---|---|
| UI | Streamlit |
| Transcript API | youtube-transcript-api |
| Audio download | yt-dlp |
| Speech-to-text | openai-whisper (local) |
| Text splitting | LangChain RecursiveCharacterTextSplitter |
| Embeddings | sentence-transformers / all-MiniLM-L6-v2 |
| Vector store | FAISS (faiss-cpu) |
| LLM | Groq |
| Chat history | SQLite |
| Config | python-dotenv |

---

## Limitations

- Whisper fallback requires FFmpeg and can take several minutes for long videos
- Groq has token-per-minute rate limits — summarisation of very long videos may be slow
- Private or age-restricted videos cannot be accessed
- Answers are grounded in the transcript — if the transcript is inaccurate, answers may be too

---

## Future Improvements

- Multi-video cross-search
- Chapter-aware chunking
- Support for uploaded video files
- Multi-language transcript support
- Streaming LLM responses
