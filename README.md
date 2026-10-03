# 🎥 VidRAG — YouTube AI Intelligence Workspace (FastAPI + React + TiDB Cloud Vector)

VidRAG is a modern, production-grade AI application that transforms any YouTube video into an interactive, real-time knowledge base. Powered by **React (Vite)**, **FastAPI**, **TiDB Cloud Serverless Vector Search**, **Groq LPU Inference (LLaMA 3.3)**, **Groq Cloud Whisper**, and **FastEmbed (ONNX Runtime)**.

---

## 🌟 Key Features

- 🔐 **Dual-Method Authentication**: Full user registration & login system with PBKDF2-HMAC-SHA256 (100,000 rounds + 16-byte random salt) supporting both **Username or Email** sign-in.
- 🌐 **Google OAuth 2.0 Integration**: One-click Google Sign-In with automated user account provisioning and profile avatar sync.
- ⚡ **Real-Time Token Streaming (SSE)**: Sub-300ms Time-to-First-Token (TTFT) powered by Server-Sent Events and Groq LPUs.
- 🔗 **Dual Ingestion Pipeline**:
  - **Primary**: Instant caption extraction via YouTube Transcript API (~1–2s with zero download overhead).
  - **Secondary Fallback**: Automated `yt-dlp` audio extraction + **Groq Cloud Whisper API** (`whisper-large-v3-turbo`) providing 216x real-time transcription with 0% server CPU usage.
- 🍪 **YouTube Anti-Bot & SABR Bypass**: Built-in support for `cookies.txt` to bypass YouTube's *"Sign in to confirm you're not a bot"* and `HTTP 403: Forbidden` blocks.
- ✂️ **Standard Recursive Chunking**: Powered by LangChain's `RecursiveCharacterTextSplitter` with configurable chunk sizes and overlap to keep sentences and concepts intact.
- 🚀 **FastEmbed ONNX Embeddings**: High-performance ONNX runtime (`sentence-transformers/all-MiniLM-L6-v2`) with in-memory LRU query caching for 5–10x faster embeddings on CPU.
- 🗄️ **TiDB Cloud Serverless Vector Store**: Unified multi-modal database hosting relational entities (users, chats, library) and high-dimensional vector embeddings with native `VECTOR(384)` and `VEC_COSINE_DISTANCE`.
- 📑 **Hierarchical Map-Reduce Summaries**: One-click structured executive summaries (Main Topic, Key Points, Important Concepts, Conclusion) with multi-model failover.
- 📂 **Personal Video Library & History**: Persistent user library and multi-turn chat history stored in TiDB Cloud.
- 🎨 **Modern Glassmorphic UI**: Dark mode React interface with responsive embedded YouTube player, markdown rendering, and quick starter prompts.

---

## 🏗️ System Architecture

```
React Frontend (Vite SPA) 
  │
  ├──► JWT Auth & Google OAuth 2.0 ──► FastAPI Security Layer (utils/auth.py)
  ├──► Real-Time SSE Stream        ──► FastAPI EventSource (/api/chat/stream)
  │
  ▼
FastAPI Backend (backend/main.py)
  │
  ├──► Ingestion Layer
  │      ├── Primary: YouTube Transcript API (ingestion/youtube_loader.py)
  │      ├── Fallback: yt-dlp + Groq Cloud Whisper (ingestion/whisper_loader.py)
  │      └── Chunker: RecursiveCharacterTextSplitter (ingestion/chunker.py)
  │
  ├──► Retrieval Layer
  │      ├── Embeddings: FastEmbed ONNX all-MiniLM-L6-v2 (retrieval/embeddings.py)
  │      └── Vector Store: TiDB Cloud Vector Store (retrieval/vector_store.py)
  │
  ├──► LLM & Generation Layer
  │      ├── Client: Groq LPU API (llm/groq_client.py)
  │      ├── RAG Streamer: Streaming Prompt Engine & Fallback (llm/rag.py)
  │      └── Summarizer: Map-Reduce Summarization (llm/summarizer.py)
  │
  └──► Database Layer (backend/database.py)
         └── TiDB Cloud Serverless (Pooled SSL Connection, Tables: users, video_metadata, transcript_chunks, chat_history, user_videos)
```

---

## 📁 Project Structure

```
YoutubeChatBot_RAG/
│
├── backend/
│   ├── main.py                 ← FastAPI application routes & SPA static server
│   ├── config.py               ← Centralized configuration & environment loader
│   ├── database.py             ← TiDB connection pool, table schemas & SQL queries
│   ├── requirements.txt        ← Python backend dependencies
│   ├── cookies.txt             ← (Optional) Exported YouTube cookies for bot bypass
│   │
│   ├── ingestion/
│   │   ├── youtube_loader.py   ← Primary caption fetcher & URL parser
│   │   ├── whisper_loader.py   ← yt-dlp audio extraction & Groq Cloud Whisper API
│   │   └── chunker.py          ← LangChain RecursiveCharacterTextSplitter
│   │
│   ├── retrieval/
│   │   ├── embeddings.py       ← FastEmbed ONNX runtime with LRU query cache
│   │   └── vector_store.py     ← TiDB Vector Store & VEC_COSINE_DISTANCE queries
│   │
│   ├── llm/
│   │   ├── groq_client.py      ← Authenticated singleton Groq API client
│   │   ├── rag.py              ← Context grounding, prompt engine & SSE streaming
│   │   └── summarizer.py       ← Hierarchical Map-Reduce video summarizer
│   │
│   └── utils/
│       └── auth.py             ← PBKDF2-HMAC-SHA256 hashing & JWT authentication
│
├── frontend/
│   ├── index.html              ← HTML root
│   ├── package.json            ← React, Lucide-react, React-Markdown dependencies
│   ├── vite.config.js          ← Vite development server configuration
│   └── src/
│       ├── App.jsx             ← Main orchestrator, route guard & dashboard
│       ├── index.css           ← Dark mode glassmorphic design system
│       ├── components/
│       │   ├── AuthPage.jsx        ← Dual login, registration & Google SSO modal
│       │   ├── Navbar.jsx          ← Navigation bar, user status & logout
│       │   ├── VideoProcessor.jsx  ← URL ingestion bar with live progress
│       │   ├── YouTubePlayer.jsx   ← Synchronized 16:9 embedded player
│       │   ├── ChatInterface.jsx   ← Streaming markdown AI chat interface
│       │   ├── VideoLibrary.jsx    ← User's private video carousel/library
│       │   ├── SummaryModal.jsx    ← Modal for generated structured summaries
│       │   └── AddVideoModal.jsx   ← Quick video ingestion modal
│       └── services/
│           └── api.js              ← REST client & SSE stream decoder
│
├── Dockerfile                  ← Multi-stage production container build
├── railway.json                ← 1-click cloud deployment configuration
├── .env.example                ← Template for environment variables
└── README.md                   ← Project documentation
```

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.10+**
- **Node.js 18+** & `npm`
- **FFmpeg** (required for audio extraction on videos without subtitles)
  - **Windows**: `winget install Gyan.FFmpeg` or download from [ffmpeg.org](https://ffmpeg.org/download.html)
  - **macOS**: `brew install ffmpeg`
  - **Linux**: `sudo apt install ffmpeg`
- **Free Groq API Key** (get one at [console.groq.com](https://console.groq.com))
- **Free TiDB Cloud Serverless Cluster** (get one at [tidbcloud.com](https://tidbcloud.com))

---

### 2. Backend Setup

```bash
# 1. Navigate to backend directory
cd backend

# 2. Create and activate virtual environment
# Windows:
python -m venv venv
venv\Scripts\activate

# macOS / Linux:
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp ../.env.example .env
```

Edit your `.env` file:
```env
# Groq Cloud API
GROQ_API_KEY="gsk_your_groq_api_key_here"
GROQ_MODEL="llama-3.3-70b-versatile"
GROQ_WHISPER_MODEL="whisper-large-v3-turbo"

# TiDB Cloud Serverless Database
TIDB_DATABASE_URL="mysql://<user>:<password>@<host>:4000/<database>"

# Authentication & Security
JWT_SECRET="your_custom_jwt_secret_key"
JWT_ALGORITHM="HS256"
JWT_EXPIRE_MINUTES="10080"
GOOGLE_CLIENT_ID="your_google_oauth_client_id.apps.googleusercontent.com"
```

Start the FastAPI backend:
```bash
python main.py
# Backend runs at http://127.0.0.1:8000
```

---

### 3. Frontend Setup

```bash
# 1. Open a new terminal and navigate to frontend
cd frontend

# 2. Install dependencies
npm install

# 3. Start development server
npm run dev
# Frontend runs at http://localhost:5173
```

---

## 🍪 Bypassing YouTube Bot Checks (`cookies.txt`)

If YouTube blocks automated audio downloads on cloud servers with `Sign in to confirm you're not a bot` or `HTTP 403 Forbidden`:

1. Install the browser extension **"Get cookies.txt LOCALLY"** ([Chrome](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbngbenbfghflnefglmimmnj) / [Firefox](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)).
2. Log into [youtube.com](https://www.youtube.com).
3. Export your cookies and save the file as `cookies.txt` in the project root or `backend/` directory.
4. VidRAG will automatically detect and authenticate with your session cookies.

---

## 📦 Single-Server Production Deployment (Docker / Railway)

The repository includes a multi-stage [Dockerfile](file:///f:/My%20projects/YoutubeChatBot_RAG/Dockerfile) that builds the React frontend and bundles it directly with FastAPI:

```bash
# Build and run container locally
docker build -t vidrag .
docker run -p 8000:8000 --env-file .env vidrag
```

FastAPI automatically mounts and serves the static React assets from `frontend/dist`, hosting the entire application on a single port (`8000`).

---

## 🛡️ Database Schema (TiDB Cloud Serverless)

| Table | Description |
| :--- | :--- |
| **`users`** | Salted PBKDF2 password hashes, unique usernames, and emails |
| **`video_metadata`** | Video titles, channel names, duration, and cached full summaries |
| **`transcript_chunks`** | Semantic transcript text blocks and native **`VECTOR(384)`** embeddings |
| **`chat_history`** | Video-specific user & assistant message history |
| **`user_videos`** | Many-to-many user library association (`UNIQUE(username, video_id)`) |

---

## 📄 License

Distributed under the [MIT License](LICENSE).
