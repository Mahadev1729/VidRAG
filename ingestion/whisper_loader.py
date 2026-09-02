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

import shutil
from pathlib import Path

import streamlit as st
import whisper
import yt_dlp

from config import AUDIO_DIR, WHISPER_MODEL


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

    ydl_opts = {
        "format":    "bestaudio/best",
        "outtmpl":   output_template,
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

    if status_callback:
        status_callback("⬇️ Downloading audio...")

    print(f"[WHISPER] Downloading audio for {video_id}")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])

    except yt_dlp.utils.DownloadError as error:
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
            "The video may be restricted or blocked in your region."
        ) from error

    except Exception as error:
        raise WhisperTranscriptionError(
            "Unexpected error while downloading audio."
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
    Delete temporary audio files after transcription.

    WHY: Audio files can be hundreds of MB.  Always delete them
    after transcription — even on failure (called in a finally block).
    """
    if not AUDIO_DIR.exists():
        return
    for file_path in AUDIO_DIR.glob(f"{video_id}.*"):
        try:
            file_path.unlink()
        except OSError:
            pass


# ── Whisper Transcription ─────────────────────────────────────────────────────

def transcribe_audio(
    audio_path: Path,
    status_callback=None,
) -> list:
    """
    Transcribe an MP3 file with local Whisper.

    HOW WHISPER WORKS
    -----------------
    Whisper is an encoder-decoder neural network.  It converts raw
    audio waveforms into text and produces per-segment timestamps.

    result["segments"] is a list of dicts:
        {"text": "...", "start": 1.5, "end": 4.2, ...}

    We normalise each segment into our standard format:
        {"text", "start", "duration", "end"}

    Args:
        audio_path:      Path to the .mp3 file
        status_callback: optional callable(str) for UI progress

    Returns:
        list of {"text", "start", "duration", "end"} dicts

    Raises:
        WhisperTranscriptionError on failure
    """
    if status_callback:
        status_callback("🎙️ Transcribing audio with Whisper...")

    print(f"[WHISPER] Transcribing {audio_path}")

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
        text     = (item.get("text") or "").strip()
        if not text:
            continue
        start    = float(item.get("start", 0))
        end      = float(item.get("end", start))
        duration = max(end - start, 0.0)
        segments.append({"text": text, "start": start, "duration": duration, "end": end})

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
