"""
ingestion/whisper_loader.py
============================
Whisper fallback pipeline: YouTube URL → yt-dlp → MP3 → Whisper → segments.

MOVED FROM: whisper_transcriber.py (root)
CHANGES   : Uses AUDIO_DIR and WHISPER_MODEL from config.py
            get_whisper_model() is decorated with @st.cache_resource

WHY THIS FILE EXISTS
--------------------
When the YouTube Transcript API has no captions for a video,
we fall back to downloading the raw audio and running a local
speech-to-text model (Whisper) to generate a transcript.

This file owns the entire fallback chain:
  1. ensure_ffmpeg_available()  — checks FFmpeg is on PATH
  2. download_audio()           — yt-dlp grabs the audio stream
  3. get_whisper_model()        — loads/caches the Whisper model
  4. transcribe_audio()         — Whisper → timestamped segments
  5. whisper_transcribe_from_url() — public entry point

OUTPUT FORMAT (identical to youtube_loader.py)
----------------------------------------------
[
    {"text": "...", "start": 120.5, "duration": 4.2, "end": 124.7}
]

The downstream pipeline never needs to know WHICH loader produced
the segments — both loaders return the same structure.

MODEL CACHING
-------------
@st.cache_resource makes Streamlit load the model once per server
process.  Unlike st.session_state (which is per-browser session),
cache_resource is shared across ALL users and sessions.
Use it for heavy stateless resources: ML models, DB connections.
Use st.session_state for lightweight per-user state: video ID,
current vector store, conversation history.

fp16=False
----------
fp16 (half-precision) is a GPU optimisation.  On CPU it raises errors.
Always False for broad compatibility.
"""

import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import shutil
import subprocess
from pathlib import Path

import streamlit as st
import yt_dlp

from config import (
    AUDIO_DIR,
    COOKIES_FROM_BROWSER,
    GROQ_API_KEY,
    GROQ_WHISPER_MODEL,
    WHISPER_MODEL,
)
from llm.groq_client import get_groq_client


# ── Custom Errors ─────────────────────────────────────────────────────────────

class WhisperTranscriptionError(Exception):
    """Raised when the Whisper fallback pipeline fails."""


# ── FFmpeg Check ──────────────────────────────────────────────────────────────

def ensure_ffmpeg_available() -> None:
    """
    Verify FFmpeg is installed and available on PATH.

    WHY: yt-dlp needs FFmpeg to convert downloaded audio to MP3.
    Whisper also requires FFmpeg to decode audio formats.
    Without it the entire fallback fails — check early and raise clearly.
    """
    if shutil.which("ffmpeg") is None:
        raise WhisperTranscriptionError(
            "FFmpeg is not installed or not found on PATH. "
            "It is required for Whisper fallback transcription. "
            "Install from https://ffmpeg.org/download.html"
        )


# ── Whisper Model — cached across all Streamlit sessions ──────────────────────

@st.cache_resource
def get_whisper_model():
    """
    Load the Whisper model once and cache it for the process lifetime.

    st.cache_resource vs st.session_state
    --------------------------------------
    st.cache_resource  → shared across ALL users/sessions.
                         Perfect for ML models: load once, reuse forever.
    st.session_state   → per-browser-session only.
                         Perfect for user-specific data: current video,
                         chat history, vector store.

    The first call to this function takes 10-30 seconds (model download
    + load).  Every subsequent call returns the cached model instantly.
    """
    import whisper
    print(f"[WHISPER] Loading Whisper model '{WHISPER_MODEL}' ...")
    model = whisper.load_model(WHISPER_MODEL)
    print("[WHISPER] Model loaded and cached.")
    return model


# ── Audio Download (yt-dlp) ───────────────────────────────────────────────────

def download_audio(
    youtube_url: str,
    video_id: str,
    status_callback=None,
) -> Path:
    """
    Download the best available audio stream from YouTube and save as MP3.

    HOW yt-dlp WORKS
    ----------------
    yt-dlp selects the highest-quality audio-only stream (no video data),
    then uses FFmpeg to transcode it to 192-kbps MP3.
    The file is saved to AUDIO_DIR/<video_id>.mp3.

    Args:
        youtube_url:     full YouTube URL
        video_id:        YouTube video ID (used as filename)
        status_callback: optional callable(str) for Streamlit progress

    Returns:
        Path to the downloaded .mp3 file

    Raises:
        WhisperTranscriptionError on any download failure
    """
    ensure_ffmpeg_available()

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    output_template = str(AUDIO_DIR / f"{video_id}.%(ext)s")

    # Disable external plugins that may hang on Windows
    os.environ["YTDLP_NO_PLUGINS"] = "1"

    base_ydl_opts = {
        "format":    "bestaudio/best",
        "outtmpl":   output_template,
        "retries":    3,
        "fragment_retries": 3,
        "extractor_retries": 3,
        "socket_timeout": 30,
        "postprocessors": [
            {
                "key":              "FFmpegExtractAudio",
                "preferredcodec":   "mp3",
                "preferredquality": "192",
            }
        ],
        "quiet":       True,
        "no_warnings": True,
    }

    # Player client priority:
    # 1. android      - Highly reliable; avoids YouTube's web 403 Forbidden & SABR anti-bot
    # 2. ios          - Excellent mobile client fallback
    # 3. mweb         - Mobile web client
    # 4. web_embedded - Embedded web client
    # 5. default      - Standard yt-dlp extractor fallback
    client_configs = [
        {"extractor_args": {"youtube": {"player_client": ["android"]}}},
        {"extractor_args": {"youtube": {"player_client": ["ios"]}}},
        {"extractor_args": {"youtube": {"player_client": ["mweb"]}}},
        {"extractor_args": {"youtube": {"player_client": ["web_embedded", "web"]}}},
        {},
    ]

    ydl_options = []

    # Safely probe browser cookies (avoids repetitive failed attempts if browser SQLite DB is locked on Windows)
    if COOKIES_FROM_BROWSER:
        try:
            yt_dlp.cookies.extract_cookies_from_browser(COOKIES_FROM_BROWSER)
            for cfg in client_configs:
                ydl_options.append({
                    **base_ydl_opts,
                    "cookiesfrombrowser": (COOKIES_FROM_BROWSER,),
                    **cfg,
                })
        except Exception as cookie_err:
            print(
                f"[WHISPER] Browser cookie extraction from '{COOKIES_FROM_BROWSER}' "
                f"unavailable ({cookie_err}). Using resilient player clients."
            )

    # Robust fallback without browser cookies using modern clients
    for cfg in client_configs:
        ydl_options.append({
            **base_ydl_opts,
            **cfg,
        })

    if status_callback:
        status_callback("⬇️ Downloading audio...")

    print(f"[WHISPER] Downloading audio for {video_id}")

    last_error = None
    for ydl_opts in ydl_options:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([youtube_url])
            break
        except yt_dlp.utils.DownloadError as error:
            last_error = error
            cleanup_audio_files(video_id)
        except Exception as error:
            raise WhisperTranscriptionError(
                "Unexpected error while downloading audio."
            ) from error
    else:
        error = last_error
        msg = str(error).lower()
        if "private" in msg:
            raise WhisperTranscriptionError(
                "This video is private. Whisper fallback cannot access it."
            ) from error
        if "unavailable" in msg:
            raise WhisperTranscriptionError(
                "This video is unavailable. Cannot download audio."
            ) from error
        raise WhisperTranscriptionError(
            "Failed to download audio from YouTube. "
            "The video may be restricted or blocked in your region. "
            f"Downloader details: {error}"
        ) from error

    audio_path = AUDIO_DIR / f"{video_id}.mp3"

    if not audio_path.exists():
        raise WhisperTranscriptionError(
            "Audio download completed but no .mp3 file was created."
        )

    print(f"[WHISPER] Audio saved to {audio_path}")
    return audio_path


# ── Audio Cleanup ─────────────────────────────────────────────────────────────

def cleanup_audio_files(video_id: str) -> None:
    """
    Delete temporary audio files and chunk folders after transcription.

    WHY: Audio files can be hundreds of MB.  Always delete them
    after transcription — even on failure (called in a finally block).
    """
    if not AUDIO_DIR.exists():
        return

    # Delete primary audio file(s)
    for file_path in AUDIO_DIR.glob(f"{video_id}.*"):
        try:
            file_path.unlink()
        except OSError:
            pass

    # Delete any temporary chunk directories
    chunk_dir = AUDIO_DIR / f"{video_id}_chunks"
    if chunk_dir.exists():
        try:
            shutil.rmtree(chunk_dir, ignore_errors=True)
        except OSError:
            pass


# ── Audio Splitting (for long videos e.g. 1-2 hours) ──────────────────────────

def split_audio_into_chunks(
    audio_path: Path,
    segment_seconds: int = 600,
) -> list[tuple[Path, float]]:
    """
    Split audio into ~10-minute segments using FFmpeg if the file is large.
    
    Re-encodes to 64-kbps mono MP3 during segmentation for very small
    file sizes (< 5 MB per 10 min) and rapid uploading to Groq.

    Returns:
        list of (chunk_file_path, start_offset_seconds)
    """
    chunk_dir = audio_path.parent / f"{audio_path.stem}_chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    output_pattern = str(chunk_dir / "chunk_%03d.mp3")

    cmd = [
        "ffmpeg", "-y", "-i", str(audio_path),
        "-f", "segment", "-segment_time", str(segment_seconds),
        "-c:a", "libmp3lame", "-b:a", "64k", "-ac", "1",
        output_pattern,
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except Exception as e:
        raise WhisperTranscriptionError(f"Failed to segment audio with FFmpeg: {e}") from e

    chunk_files = sorted(chunk_dir.glob("chunk_*.mp3"))
    if not chunk_files:
        raise WhisperTranscriptionError("FFmpeg audio splitting produced no chunk files.")

    chunks = []
    for idx, chunk_file in enumerate(chunk_files):
        offset = float(idx * segment_seconds)
        chunks.append((chunk_file, offset))

    return chunks


# ── Groq Cloud Whisper API ───────────────────────────────────────────────────

def _transcribe_single_groq_file(
    client,
    file_path: Path,
    time_offset: float = 0.0,
) -> list[dict]:
    """
    Send a single audio file to Groq Whisper and normalize segments.
    Applies time_offset so timestamps map correctly to the full video duration.
    """
    with open(file_path, "rb") as f:
        transcription = client.audio.transcriptions.create(
            file=(file_path.name, f.read()),
            model=GROQ_WHISPER_MODEL,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )

    raw_segments = getattr(transcription, "segments", []) or []
    segments = []

    for item in raw_segments:
        if isinstance(item, dict):
            text = (item.get("text") or "").strip()
            start = float(item.get("start", 0)) + time_offset
            end = float(item.get("end", start)) + time_offset
        else:
            text = (getattr(item, "text", "") or "").strip()
            start = float(getattr(item, "start", 0)) + time_offset
            end = float(getattr(item, "end", start)) + time_offset

        if not text:
            continue

        duration = max(end - start, 0.0)
        segments.append({
            "text": text,
            "start": start,
            "duration": duration,
            "end": end,
        })

    return segments


def transcribe_with_groq(
    audio_path: Path,
    status_callback=None,
) -> list[dict]:
    """
    Transcribe audio via Groq Cloud Whisper API.

    Features:
      - Takes ~2 to 5 seconds per chunk
      - Automatically chunks files > 24 MB (handling 1 to 2+ hour videos)
      - Returns normalized segment timestamps matching the downstream pipeline
    """
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not configured.")

    client = get_groq_client()
    file_size = audio_path.stat().st_size
    max_single_size = 24 * 1024 * 1024  # 24 MB safe threshold

    # Under 24 MB: Send directly
    if file_size <= max_single_size:
        if status_callback:
            status_callback(
                f"⚡ Transcribing audio via Groq Cloud Whisper ({GROQ_WHISPER_MODEL})..."
            )
        print(f"[GROQ_WHISPER] Sending {audio_path.name} ({file_size / (1024*1024):.1f} MB) to Groq...")
        return _transcribe_single_groq_file(client, audio_path, time_offset=0.0)

    # Over 24 MB (long video): Split into 10-minute chunks
    if status_callback:
        status_callback(
            f"⚡ Audio exceeds 24MB ({file_size / (1024*1024):.1f} MB). "
            "Splitting into 10-min chunks for Groq Cloud..."
        )
    print(f"[GROQ_WHISPER] Audio exceeds 24MB. Slicing into chunks...")

    chunks = split_audio_into_chunks(audio_path, segment_seconds=600)
    all_segments = []

    for idx, (chunk_file, offset) in enumerate(chunks):
        if status_callback:
            status_callback(
                f"⚡ Transcribing chunk {idx + 1} of {len(chunks)} via Groq Cloud..."
            )
        print(f"[GROQ_WHISPER] Transcribing chunk {idx + 1}/{len(chunks)} (start offset: {offset}s)...")
        chunk_segments = _transcribe_single_groq_file(client, chunk_file, time_offset=offset)
        all_segments.extend(chunk_segments)

    return all_segments


# ── Whisper Transcription (Groq Cloud + Local Fallback) ───────────────────────

def transcribe_audio(
    audio_path: Path,
    status_callback=None,
) -> list:
    """
    Transcribe an MP3 file.
    
    PRIMARY: Groq Cloud Whisper API (ultra-fast, zero CPU load).
    FALLBACK: Local Whisper CPU model if Groq is unavailable or rate-limited.
    """
    # ── 1. Try Groq Cloud Whisper First ────────────────────────────────────────
    if GROQ_API_KEY:
        try:
            segments = transcribe_with_groq(audio_path, status_callback=status_callback)
            if segments:
                print(f"[GROQ_WHISPER] Success — {len(segments)} segments.")
                return segments
        except Exception as groq_err:
            print(f"[GROQ_WHISPER] Cloud Whisper failed: {groq_err}. Falling back to local CPU model...")
            if status_callback:
                status_callback("Groq Whisper unavailable. Falling back to local CPU Whisper...")

    # ── 2. Local Whisper Fallback ──────────────────────────────────────────────
    if status_callback:
        status_callback("🎙️ Transcribing audio with local Whisper (CPU)...")

    print(f"[WHISPER] Transcribing {audio_path} locally...")
    model = get_whisper_model()

    try:
        result = model.transcribe(str(audio_path), fp16=False)
    except Exception as error:
        raise WhisperTranscriptionError(
            "Whisper transcription failed. "
            "The audio file may be corrupted or unsupported."
        ) from error

    raw_segments = result.get("segments") or []

    segments = []
    for item in raw_segments:
        text = (item.get("text") or "").strip()
        if not text:
            continue
        start = float(item.get("start", 0))
        end = float(item.get("end", start))
        duration = max(end - start, 0.0)
        segments.append({"text": text, "start": start,
                        "duration": duration, "end": end})

    if not segments:
        raise WhisperTranscriptionError(
            "Whisper completed but produced no usable transcript text."
        )

    print(f"[WHISPER] Transcription complete — {len(segments)} segments.")
    return segments


# ── Public Entry Point ────────────────────────────────────────────────────────

def whisper_transcribe_from_url(
    youtube_url: str,
    video_id: str,
    status_callback=None,
) -> list:
    """
    Full Whisper fallback pipeline:
        YouTube URL → yt-dlp → MP3 → Whisper → segments

    Audio is always cleaned up in the finally block.

    Returns:
        list of {"text", "start", "duration", "end"} dicts
    """
    audio_path = None
    try:
        audio_path = download_audio(youtube_url, video_id, status_callback)
        return transcribe_audio(audio_path, status_callback)
    finally:
        cleanup_audio_files(video_id)
