---
title: YouTube RAG Chatbot
emoji: 🎥
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
---

# 🎥 YouTube RAG Chatbot

An AI-powered YouTube Video Summarization and Question Answering system built using **Python, LangChain, FAISS, Hugging Face Embeddings, Groq, and Streamlit**.

The user pastes a YouTube video URL, and the application retrieves the transcript, splits it into chunks, creates local embeddings, stores them in FAISS, generates a summary, and allows the user to ask questions about the video.

---

## 🚀 Features

- 🔗 Accept YouTube video URLs
- 📝 Retrieve YouTube transcripts
- ✂️ Split transcripts using LangChain
- 🧠 Use free local Hugging Face embeddings
- 🔎 Semantic search using FAISS
- 🤖 Use Groq for LLM inference
- 📄 Generate video summaries
- 💬 Ask questions about the video
- 🎯 Retrieve relevant transcript chunks using RAG
- 🌐 Streamlit web interface
- 💰 No paid embedding API required
- 📚 Support long-video summarization using chunk-based processing

---

## 🏗️ Architecture

```text
                         YouTube URLs
                              │
                              ▼
                     Extract Video ID
                              │
                              ▼
                    YouTube Transcript
                              │
                              ▼
                    LangChain Chunking
                              │
                              ▼
                         Text Chunks
                              │
                              ▼
                   Hugging Face Embeddings
                sentence-transformers/all-MiniLM-L6-v2
                              │
                              ▼
                            FAISS
                         Vector Store
                         /          \
                        /            \
                       ▼              ▼
                Summarization         Q&A
                       │              │
                       ▼              ▼
                Chunk Summaries   Similarity Search
                       │              │
                       ▼              ▼
                  Final Summary      Context
                                      │
                                      ▼
                                     Groq
                                      │
                                      ▼
                                    Answer
```

---

# 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| Python | Core programming language |
| Streamlit | Web application interface |
| LangChain | Text splitting and RAG pipeline |
| Groq | Large Language Model inference |
| FAISS | Vector similarity search |
| Hugging Face | Local embedding model |
| Sentence Transformers | Text embeddings |
| YouTube Transcript API | YouTube transcript extraction |

---

# 🧠 Embedding Model

This project uses:

```text
sentence-transformers/all-MiniLM-L6-v2
```

The model runs locally.

Embedding dimension:

```text
384
```

Therefore, no paid embedding API is required.

---

# 🤖 LLM

The application uses Groq for fast LLM inference.

Current model:

```text
openai/gpt-oss-20b
```

A Groq API key is required.

---

# 📁 Project Structure

```text
YoutubeChatBot_RAG/
│
├── app.py
├── youtube_loader.py
├── chunker.py
├── embeddings.py
├── vector_store.py
├── rag.py
├── summarizer.py
│
├── requirements.txt
├── README.md
├── .gitignore
│
├── .streamlit/
│   └── config.toml
│
└── data/
    ├── transcripts/
    └── indexes/
```

---

# 📄 File Responsibilities

### `app.py`
Main Streamlit application and user interface.

### `youtube_loader.py`
Extracts the YouTube video ID, retrieves the transcript, and saves transcripts.

### `chunker.py`
Splits transcript text into LangChain `Document` objects with metadata.

### `embeddings.py`
Loads the local Hugging Face embedding model.

### `vector_store.py`
Creates, saves, and loads the FAISS vector store.

### `rag.py`
Performs similarity search and generates answers using retrieved context and Groq.

### `summarizer.py`
Summarizes transcript sections and creates the final video summary.

---

# ⚙️ Installation

## 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YoutubeChatBot_RAG
```

## 2. Create Virtual Environment

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

# 🔐 Environment Variables

For local development, create a `.env` file in the project root:

```text
GROQ_API_KEY=your_groq_api_key
```

Never commit `.env` to GitHub.

Your `.gitignore` should contain:

```text
.env
venv/
.venv/
__pycache__/
*.pyc
```

---

# ▶️ Run the Application

Start Streamlit:

```bash
streamlit run app.py
```

The application will open in your browser.

---

# 💬 How to Use

## Step 1 — Enter YouTube URL

Paste a YouTube video URL:

```text
https://www.youtube.com/watch?v=VIDEO_ID
```

## Step 2 — Process Video

Click:

```text
🚀 Process Video
```

The application performs:

```text
YouTube URL
      ↓
Extract Video ID
      ↓
Get Transcript
      ↓
Split Transcript
      ↓
Create Embeddings
      ↓
Create FAISS Index
      ↓
Generate Summary
```

## Step 3 — Read Summary

The application generates:

- Main Topic
- Key Points
- Important Concepts
- Conclusion

## Step 4 — Ask Questions

Example:

```text
What is the main topic of this video?
```

Other examples:

```text
What are the key points discussed?

Explain the main concept in simple words.

What examples were given?

What is the conclusion?

What does the speaker say about AI?
```

---

# 🔎 RAG Pipeline

```text
User Question
      │
      ▼
Question Embedding
      │
      ▼
FAISS Similarity Search
      │
      ▼
Top-K Relevant Chunks
      │
      ▼
Retrieved Context
      │
      ▼
Question + Context
      │
      ▼
Groq LLM
      │
      ▼
Generated Answer
```

Instead of sending the complete transcript to the LLM for every question, the system retrieves only the most relevant transcript chunks.

---

# 📄 Long Video Summarization

Long YouTube videos can contain thousands of words and exceed LLM token limits.

The summarization process therefore works in sections:

```text
Large Transcript
       │
       ▼
Split into Sections
       │
       ├──────────┐
       ▼          ▼
    Section 1   Section 2
       │          │
       ▼          ▼
      Groq       Groq
       │          │
       ▼          ▼
   Summary 1   Summary 2
       │          │
       └────┬─────┘
            ▼
      Section Summaries
            │
            ▼
       Final Groq Request
            │
            ▼
       Final Summary
```

This keeps individual requests smaller and helps avoid oversized requests for long videos.

---

# 💰 Cost

The embedding model:

```text
sentence-transformers/all-MiniLM-L6-v2
```

runs locally, so no paid embedding API is required.

Groq is used for LLM inference. Actual usage limits depend on the selected model and account/service tier.

---

# ⚠️ Current Limitations

- The video must have an accessible transcript.
- Videos without an accessible transcript cannot currently be processed.
- Very long videos require multiple LLM requests.
- Groq rate limits can affect long-video summarization.
- FAISS indexes are currently local.
- Conversation memory is not implemented yet.
- The system is primarily designed for English transcripts.
- YouTube transcript availability depends on the video.

---

# 🔒 Security

Never expose your Groq API key directly in source code.

### ❌ Incorrect

```python
api_key = "gsk_xxxxxxxxxxxxxxxxx"
```

### ✅ Correct

```python
import os

api_key = os.getenv("GROQ_API_KEY")
```

For Streamlit Cloud, use Streamlit Secrets instead of committing `.env`.

---

# 🌐 Deployment

The application can be deployed using Streamlit Community Cloud.

Deployment flow:

```text
GitHub Repository
       │
       ▼
Streamlit Community Cloud
       │
       ▼
Configure GROQ_API_KEY
       │
       ▼
Deploy Application
       │
       ▼
Public YouTube RAG Chatbot
```

For Streamlit Cloud, configure:

```text
GROQ_API_KEY
```

inside the application's Secrets settings.

Do not upload `.env` to GitHub.

---

# 🔮 Future Improvements

- 💬 Conversation memory
- 🧠 Multi-turn chat
- 📚 Multiple YouTube videos
- 🔗 Source citations
- ⏱️ Timestamp-based answers
- ⚡ Caching
- 📊 RAG evaluation
- 📝 Improved long-video summarization
- 🗄️ Persistent vector database
- 📈 Retrieval quality evaluation
- 🎯 Answer quality evaluation
- 🌐 Production deployment
- 👥 User authentication
- 📜 Chat history

---

# 🧪 Example Workflow

```text
                     YouTube Video
                           │
                           ▼
                       Transcript
                           │
                           ▼
                    Text Processing
                           │
                           ▼
                         Chunks
                           │
                           ▼
                      Embeddings
                           │
                           ▼
                         FAISS
                       /       \
                      /         \
                     ▼           ▼
                 Summary         Q&A
                    │             │
                    ▼             ▼
                   Groq         FAISS
                                  │
                                  ▼
                                Groq
                                  │
                                  ▼
                                Answer
```

---

# 🎯 Project Goal

The goal of this project is to demonstrate how **Retrieval Augmented Generation (RAG)** can be applied to long-form YouTube content.

Instead of asking an LLM to process an entire video every time, the system:

1. Retrieves the YouTube transcript.
2. Splits the transcript into smaller chunks.
3. Generates embeddings locally.
4. Stores embeddings in FAISS.
5. Retrieves relevant chunks for each question.
6. Sends relevant context to the LLM.
7. Generates an answer based on the retrieved information.

This architecture makes the application more efficient and reduces the chance of hallucination.

---

# 📚 What I Learned

Through this project, the following concepts were implemented:

- Large Language Models
- Prompt Engineering
- Retrieval Augmented Generation
- Text Chunking
- Vector Embeddings
- Semantic Search
- FAISS Vector Database
- LangChain
- Groq API
- YouTube Transcript Processing
- Long-Document Summarization
- Streamlit
- Environment Variables
- Modular Python Architecture

---

# 👨‍💻 Author

**Mahadev Athani**



---

## ⭐ Support

If you found this project useful, consider giving the repository a ⭐ on GitHub.
