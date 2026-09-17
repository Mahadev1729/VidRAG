# 🎥 YouTube RAG & Self-Reflective AI Assistant

A modern, production-ready AI assistant that lets you **summarise any YouTube video and ask questions about its content** — powered by **Self-RAG**, **Corrective RAG (CRAG)**, and **continuous feedback memory**.

Built with **Python**, **Streamlit**, **LangChain**, **Sentence Transformers**, **FAISS**, **Groq LLM**, **OpenAI Whisper**, and **SQLite**.

---

## 🌟 Key Features

- 🔐 **Secure User Authentication**: Complete SQLite3 user registration & login system with PBKDF2-HMAC-SHA256 (100,000 iterations + 16-byte random salt).
- 📧 **Dual Sign-In**: Sign in seamlessly using either your **Username or Email Address**.
- 👤 **Session Guard & User Status**: Authenticated route protection with persistent sidebar user status and one-click logout.
- 🔗 **Instant Video Ingestion**: Paste any YouTube URL (Standard, Short, or Shorts) to convert it into a vector knowledge base.
- 📝 **Automatic Captions**: Fetches transcripts instantly via the YouTube Transcript API (zero download overhead for 90%+ of videos).
- 🎙️ **Whisper Fallback Pipeline**: Automatically falls back to downloading audio and running Whisper speech-to-text when captions are disabled or unavailable.
- 🍪 **YouTube Bot & SABR Bypass**: Built-in authentication support for `cookies.txt` and Streamlit Cloud secrets to bypass YouTube's `Sign in to confirm you're not a bot` and `HTTP 403: Forbidden` errors.
- 🧠 **Self-RAG & Corrective RAG (CRAG)**:
  - **Document Relevance Grading**: Evaluates whether retrieved chunks contain sufficient context to answer the question.
  - **Adaptive Query Expansion**: Automatically reformulates queries into conversational video search phrases when initial retrieval is weak.
  - **Active Hallucination Guardrail**: Intercepts ungrounded claims and runs an automatic self-correction pass before returning answers.
  - **Conservative Fallback**: Reverts safely to ungrounded disclaimers if claims cannot be verified against the transcript.
- 💡 **Continuous Learning Memory**:
  - User feedback system (👍 / 👎) saved to SQLite.
  - Verified high-quality past Q&A pairs are dynamically injected as few-shot examples into future prompts.
  - Community satisfaction metrics displayed in the video overview.
- 🔬 **Reasoning Trace & Telemetry Expander**: Interactive UI inspector displaying real-time retrieval grades, query rewrites, and factual grounding confidence.
- 📍 **Clickable Timestamps**: Every answer citation links directly to the exact second in the YouTube video.
- 📄 **Automatic Video Summary**: High-level key takeaways and structured outlines generated instantly via Groq.
- 💬 **Persistent Conversation History**: Video-specific chat history stored locally in SQLite.
- ⚡ **Cached FAISS Index**: Vector stores cached to disk to eliminate redundant embeddings on reload.
- 🎨 **Modern Design System**: Styled with custom CSS (`static/style.css`), Space Grotesk & DM Sans typography, and responsive cards.

---

## 🏗️ Architecture

```
app.py (Streamlit UI Layer & Route Guard)
  │
  ├──► utils/auth.py          → SQLite User DB + PBKDF2 Hashing + Dual Sign-In
  ├──► utils/styles.py        → Injects static/style.css design tokens
  │
  ▼
ingestion/
  ├── youtube_loader.py       → YouTube Transcript API (Primary)
  ├── whisper_loader.py       → yt-dlp + Cookies + Whisper Fallback (Secondary)
  └── chunker.py              → Split transcript into overlapping chunks
  │
  ▼
retrieval/
  ├── embeddings.py           → Sentence Transformers (all-MiniLM-L6-v2)
  └── vector_store.py         → FAISS index (create / cache / load)
  │
  ▼
llm/
  ├── groq_client.py          → Groq API client (shared)
  ├── self_rag.py             → Self-RAG (grading, rewriting, grounding & self-correction)
  ├── feedback_store.py       → Feedback ratings & dynamic few-shot memory DB
  ├── rag.py                  → Baseline RAG fallback
  └── summarizer.py           → Multi-chunk video summarisation
```

### 🔄 Self-RAG & CRAG Data Flow

```
1. Ingestion & Indexing
   YouTube URL ──► Transcript API / Whisper ──► Chunks ──► FAISS Vector Store

2. Adaptive Retrieval & Grading
   User Question ──► FAISS Similarity Search (Top-k Chunks)
        ↓
   Document Relevance Grading (Groq Evaluator)
        ├─► [Score >= 0.5] ──► Proceed to Generation
        └─► [Score < 0.5]  ──► Adaptive Query Rewriting ──► Secondary Retrieval ──► Merge Chunks

3. Few-Shot Memory & Generation
   Fetch Verified Past Q&A (Feedback DB) ──► Assemble Grounded Prompt ──► Groq Generation

4. Grounding & Active Self-Correction Guardrail
   Factual Grounding Check
        ├─► [Grounded]   ──► Return Answer + Source Timestamps + Reasoning Trace
        └─► [Ungrounded] ──► Active Correction Pass ──► (If still ungrounded) Conservative Fallback
```

---

## 📁 Project Structure

```
YoutubeChatBot_RAG/
│
├── app.py                  ← Streamlit UI, main orchestrator & page guard
├── chat_history.py         ← SQLite conversation history manager
├── config.py               ← Centralized configuration & environment loader
├── packages.txt            ← Linux system dependencies (ffmpeg, nodejs for cloud)
├── requirements.txt        ← Python dependencies
├── cookies.txt             ← (Optional) YouTube cookies for bot bypass (gitignored)
├── users.db                ← SQLite user database (gitignored)
├── .env                    ← Local environment secrets (gitignored)
├── .env.example            ← Template for environment variables
│
├── .streamlit/
│   └── config.toml         ← Streamlit theme configuration
│
├── static/
│   └── style.css           ← Modern design system & styling
│
├── utils/
│   ├── __init__.py
│   ├── auth.py             ← SQLite authentication & PBKDF2 password hashing
│   └── styles.py           ← Style injection helper
│
├── ingestion/
│   ├── __init__.py
│   ├── youtube_loader.py   ← Primary transcript fetcher & fallback orchestrator
│   ├── whisper_loader.py   ← yt-dlp audio downloader & Whisper transcriber
│   └── chunker.py          ← Semantic transcript text splitter
│
├── retrieval/
│   ├── __init__.py
│   ├── embeddings.py       ← Sentence Transformers embedding generator
│   └── vector_store.py     ← FAISS vector store creation, saving & loading
│
├── llm/
│   ├── __init__.py
│   ├── groq_client.py      ← Shared Groq API client
│   ├── self_rag.py         ← Self-RAG & Corrective RAG pipeline
│   ├── feedback_store.py   ← User feedback DB & dynamic few-shot retrieval
│   ├── rag.py              ← Baseline RAG implementation
│   └── summarizer.py       ← Multi-chunk video summarizer
│
└── data/                   ← Local persistent storage (gitignored)
    ├── transcripts/        ← Cached raw transcript files
    ├── audio/              ← Temporary audio files (auto-cleaned)
    ├── indexes/            ← Cached FAISS vector stores per video
    ├── summaries/          ← Cached summary files
    ├── feedback.db         ← Feedback ratings & verified Q&A memory
    └── chat_history.db     ← SQLite chat messages
```

---

## 🚀 Local Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/YoutubeChatBot_RAG.git
cd YoutubeChatBot_RAG
```

### 2. Create and Activate Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 4. Install FFmpeg
FFmpeg is required for Whisper fallback audio extraction:
- **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add the `bin` folder to your System `PATH` (or install via `winget install Gyan.FFmpeg` or `choco install ffmpeg`).
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt update && sudo apt install ffmpeg`

### 5. Configure Environment Variables
Copy the example environment file:
```bash
cp .env.example .env
```
Edit `.env` and add your **Groq API Key** (get one free at [console.groq.com](https://console.groq.com)):
```env
GROQ_API_KEY=gsk_your_groq_api_key_here
```

### 6. Run the Application
```bash
streamlit run app.py
```

---

## 🍪 Bypassing YouTube Bot Verification (`cookies.txt`)

YouTube enforces bot detection and SABR streaming protection, which can trigger errors like:
```text
ERROR: [youtube] Sign in to confirm you’re not a bot.
ERROR: unable to download video data: HTTP Error 403: Forbidden
```

### How to Fix in 30 Seconds:
1. Install the **Get cookies.txt LOCALLY** browser extension:
   - [Chrome / Edge / Brave Extension](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbngbenbfghflnefglmimmnj)
   - [Firefox Add-on](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)
2. Go to **[youtube.com](https://www.youtube.com)** in your browser and ensure you are logged in.
3. Click the extension icon and click **Export**.
4. Rename the downloaded file to **`cookies.txt`** and place it in your project's root folder:
   ```text
   YoutubeChatBot_RAG/
   ├── cookies.txt     <-- Place file here
   ├── app.py
   ...
   ```
5. The application will automatically detect and use `cookies.txt` to authenticate downloads.

---

## ☁️ Streamlit Community Cloud Deployment

Deploying this app to Streamlit Cloud allows public users to access it without needing to install anything.

### 1. Push to GitHub
```bash
git add .
git commit -m "Deploy YouTube Self-RAG Assistant"
git push origin main
```

### 2. Deploy on Streamlit Cloud
1. Go to [share.streamlit.io](https://share.streamlit.io) and click **New app**.
2. Select your repository, branch (`main`), and set Main file path to `app.py`.
3. Click **Deploy**.

### 3. Configure Cloud Secrets
In your Streamlit Cloud app dashboard:
1. Click **⋮ (three dots)** next to your app → **Settings** → **Secrets**.
2. Add your secrets in TOML format:

```toml
GROQ_API_KEY = "your_groq_api_key_here"

YOUTUBE_COOKIES = """
# Paste the ENTIRE content of your cookies.txt file here
"""
```

3. Click **Save** and **Reboot App**.

> [!NOTE]
> The included `packages.txt` ensures that `ffmpeg` is automatically installed on Streamlit Cloud's Linux servers.

---

## ⚙️ Environment Variables Reference

| Variable                 | Default                                  | Description                                                                 |
| ------------------------ | ---------------------------------------- | --------------------------------------------------------------------------- |
| `GROQ_API_KEY`           | —                                        | **Required.** Your Groq Cloud API key                                       |
| `GROQ_MODEL`             | `openai/gpt-oss-20b`                     | Primary Groq LLM for summaries and RAG generation                           |
| `GROQ_EVALUATOR_MODEL`   | `openai/gpt-oss-20b`                     | Groq model for grading retrieval, query rewriting, and grounding checks     |
| `ENABLE_SELF_RAG`        | `true`                                   | Set to `true` to enable Self-RAG / CRAG adaptive pipeline                   |
| `EMBEDDING_MODEL`        | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model for semantic search                                         |
| `WHISPER_MODEL`          | `base`                                   | Local Whisper model size (`tiny`, `base`, `small`, `medium`, `large`)       |
| `GROQ_WHISPER_MODEL`     | `whisper-large-v3-turbo`                 | Groq Cloud Whisper model for accelerated transcription                      |
| `COOKIES_FILE`           | `cookies.txt`                            | Path to custom Netscape formatted cookies file                              |
| `COOKIES_FROM_BROWSER`   | —                                        | Browser name for direct cookie extraction (`edge`, `firefox`, `chrome`)     |
| `YOUTUBE_COOKIES`        | —                                        | Direct cookie string (for Streamlit Cloud secrets)                          |
| `CHUNK_SIZE`             | `1000`                                   | Character limit per transcript chunk                                        |
| `CHUNK_OVERLAP`          | `200`                                    | Character overlap between adjacent chunks                                   |
| `TOP_K`                  | `4`                                      | Number of retrieved chunks sent to the LLM prompt                           |
| `FORCE_WHISPER_FALLBACK` | `0`                                      | Set to `1` to bypass YouTube caption API and force Whisper audio extraction |

---

## 🔒 Security & Privacy

- **Password Storage**: Passwords are never stored in plaintext. They are salted with 16 random bytes and hashed using PBKDF2-HMAC-SHA256 across 100,000 iterations.
- **Timing Attacks**: Authentication uses constant-time string comparisons (`secrets.compare_digest`).
- **Data Isolation**: Each video's transcript, vector store, chat history, and feedback memory are indexed by the YouTube video ID.
- **Git Protection**: Sensitive files (`.env`, `users.db*`, `cookies.txt`, `data/`, and temporary audio) are strictly ignored in `.gitignore`.

---

## 🛠️ Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Frontend UI** | Streamlit (Python) |
| **Styling & Theme** | Vanilla CSS (`static/style.css`), Inter / Space Grotesk / DM Sans |
| **Authentication** | SQLite3 + `hashlib` + `secrets` (Python Standard Library) |
| **Adaptive RAG** | Self-RAG & Corrective RAG (CRAG) Pipeline |
| **Feedback Memory** | SQLite3 Verified Few-Shot Store |
| **Transcript API** | `youtube-transcript-api` |
| **Audio Downloader**| `yt-dlp` with cookie & player-client fallback |
| **Speech-to-Text**  | `openai-whisper` & Groq Whisper Cloud |
| **Chunking**        | LangChain `RecursiveCharacterTextSplitter` |
| **Embeddings**      | Sentence Transformers (`all-MiniLM-L6-v2`) |
| **Vector Index**    | FAISS (`faiss-cpu`) |
| **LLM Inference**   | Groq Cloud (`openai/gpt-oss-20b`) |
| **Chat Storage**    | SQLite Database |

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

