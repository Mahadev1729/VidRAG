# ==============================================================================
# Multi-Stage Dockerfile for VidRAG (Railway & Docker Production)
# ==============================================================================

# --- Stage 1: Build React Frontend ---
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# --- Stage 2: Production Python Backend + Static SPA ---
FROM python:3.11-slim

# Install system dependencies (ffmpeg is required for yt-dlp & Whisper audio processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy Backend Source Code
COPY backend/ ./backend/

# Copy built frontend assets into backend static folder
COPY --from=frontend-builder /app/frontend/dist ./backend/static/

# Environment configurations
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app/backend

# Expose container port (Railway overrides this via $PORT)
EXPOSE 8000

# Start FastAPI server using uvicorn binding to 0.0.0.0 and $PORT
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
