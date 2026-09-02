"""
ingestion/youtube_loader.py
============================
YouTube URL validation, transcript retrieval, and Whisper fallback.

MOVED FROM: youtube_loader.py (root)
CHANGES   : Import whisper_loader from ingestion package.

RESPONSIBILITY
--------------
This is the single public entry point for transcript retrieval.
It tries the YouTube Transcript API first; if that fails for any
reason, it automatically falls back to Whisper.

FALLBACK TRIGGERS
-----------------
The Whisper fallback activates when ANY of these occur:
  - TranscriptsDisabled   (captions turned off)
  - NoTranscriptFound     (no captions exist)
  - VideoUnavailable      (video gone/private)
  - YouTubeRequestFailed  (network/API error)
  - ParseError            (malformed XML in caption data)
  - Empty transcript      (captions exist but have no text)
  - Any other exception   (defensive catch-all)

Setting FORCE_WHISPER_FALLBACK=1 in .env skips YouTube captions
entirely — useful for testing the fallback pipeline.

SUPPORTED URL FORMATS
---------------------
  https://www.youtube.com/watch?v=VIDEO_ID
  https://youtube.com/watch?v=VIDEO_ID
  https://youtu.be/VIDEO_ID
  https://www.youtube.com/shorts/VIDEO_ID
"""

import os
import re
from xml.etree.ElementTree import ParseError

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeRequestFailed,
)

from ingestion.whisper_loader import (
    WhisperTranscriptionError,
    whisper_transcribe_from_url,
)


# ── Custom Error ──────────────────────────────────────────────────────────────

class TranscriptError(Exception):
    """
    Raised when both YouTube captions and Whisper fallback fail.
    The message is shown directly to the user in the Streamlit UI.
    """


# ── Video ID Extraction ───────────────────────────────────────────────────────

def extract_video_id(url: str) -> str:
    """
    Extract the 11-character video ID from a YouTube URL.

    Args:
        url: YouTube URL string (any supported format)

    Returns:
        str: 11-character video ID

    Raises:
        ValueError: if the URL is empty or does not match any pattern
    """
    if not url:
        raise ValueError("YouTube URL cannot be empty.")

    url = url.strip().strip('"').strip("'")

    patterns = [
        # Standard: https://www.youtube.com/watch?v=VIDEO_ID
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?[^#\s]*v=([A-Za-z0-9_-]{11})",
        # Short:    https://youtu.be/VIDEO_ID
        r"(?:https?://)?youtu\.be/([A-Za-z0-9_-]{11})",
        # Shorts:   https://www.youtube.com/shorts/VIDEO_ID
        r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([A-Za-z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    raise ValueError(
        "Invalid YouTube URL.\n\n"
        "Supported formats:\n"
        "  https://www.youtube.com/watch?v=VIDEO_ID\n"
        "  https://youtube.com/watch?v=VIDEO_ID\n"
        "  https://youtu.be/VIDEO_ID\n"
        "  https://www.youtube.com/shorts/VIDEO_ID"
    )


# ── YouTube Transcript API (internal) ────────────────────────────────────────

def _fetch_youtube_transcript_segments(video_id: str) -> list:
    """
    Fetch transcript segments from the YouTube Transcript API.

    TRANSCRIPT SELECTION PRIORITY
    -----------------------------
    1. English transcript (manual or auto-generated)
    2. Any manually created transcript (non-English)
    3. Any auto-generated transcript

    Returns:
        list of {"text", "start", "duration", "end"} dicts

    Raises:
        Various youtube_transcript_api errors on failure
        ValueError if transcript is empty
    """
    api = YouTubeTranscriptApi()
    transcripts = api.list(video_id)

    selected = None

    # Priority 1: English
    for t in transcripts:
        if getattr(t, "language_code", "").lower().startswith("en"):
            selected = t
            break

    # Priority 2: Manual (any language)
    if selected is None:
        for t in transcripts:
            if not getattr(t, "is_generated", False):
                selected = t
                break

    # Priority 3: Auto-generated (any language)
    if selected is None:
        for t in transcripts:
            if getattr(t, "is_generated", False):
                selected = t
                break

    if selected is None:
        raise ValueError("No usable transcript found for this video.")

    fetched  = selected.fetch()
    segments = []

    for item in fetched:
        text     = getattr(item, "text", "")
        start    = float(getattr(item, "start", 0))
        duration = float(getattr(item, "duration", 0))
        end      = start + duration

        if text and text.strip():
            segments.append({
                "text":     text.strip(),
                "start":    start,
                "duration": duration,
                "end":      end,
            })

    if not segments:
        raise ValueError("Transcript exists but contains no usable text.")

    return segments


def _try_youtube_transcript(video_id: str) -> list | None:
    """
    Safe wrapper: returns segments on success, None on any failure.
    This lets the caller silently fall back to Whisper.
    """
    try:
        return _fetch_youtube_transcript_segments(video_id)
    except (
        NoTranscriptFound, TranscriptsDisabled, VideoUnavailable,
        YouTubeRequestFailed, ParseError, ValueError,
        AttributeError, TypeError, KeyError,
    ):
        return None
    except Exception:
        return None


# ── Public Entry Point ────────────────────────────────────────────────────────

def get_transcript_with_timestamps(
    url: str,
    status_callback=None,
    force_whisper: bool = False,
) -> tuple[list, str]:
    """
    Main transcript retrieval function.

    Tries YouTube Transcript API first.  Falls back to Whisper
    automatically on any failure.

    Args:
        url:             YouTube video URL
        status_callback: optional callable(str) for Streamlit progress
        force_whisper:   skip YouTube API and go straight to Whisper

    Returns:
        (segments, source)
        segments: list of {"text", "start", "duration", "end"}
        source:   "youtube_transcript" or "whisper"

    Raises:
        TranscriptError: if both methods fail
    """
    video_id = extract_video_id(url)

    force_env = os.getenv("FORCE_WHISPER_FALLBACK", "").strip().lower() in {
        "1", "true", "yes"
    }
    use_whisper = force_whisper or force_env

    segments = None

    if not use_whisper:
        print(f"[INGESTION] Fetching YouTube transcript for {video_id}")
        segments = _try_youtube_transcript(video_id)

    if segments:
        print(f"[INGESTION] YouTube captions retrieved — {len(segments)} segments.")
        return segments, "youtube_transcript"

    # ── Whisper fallback ──────────────────────────────────────────────────────
    print(f"[INGESTION] Whisper fallback activated for {video_id}")

    if status_callback:
        status_callback(
            "YouTube captions unavailable. Falling back to Whisper..."
        )

    try:
        segments = whisper_transcribe_from_url(
            url, video_id, status_callback=status_callback
        )
    except WhisperTranscriptionError as error:
        raise TranscriptError(str(error)) from error
    except Exception as error:
        raise TranscriptError(
            "Both YouTube captions and Whisper transcription failed. "
            "The video may be unavailable, private, or restricted."
        ) from error

    if not segments:
        raise TranscriptError(
            "Both YouTube captions and Whisper transcription failed. "
            "No usable transcript could be generated."
        )

    print(f"[INGESTION] Whisper transcript — {len(segments)} segments.")
    return segments, "whisper"


# ── Save Transcript ───────────────────────────────────────────────────────────

def save_transcript(text: str, video_id: str, output_dir) -> str:
    """
    Save a plain-text transcript to disk.

    Args:
        text:       transcript as plain text
        video_id:   YouTube video ID (used as filename)
        output_dir: directory path (str or Path)

    Returns:
        str: path to the saved file
    """
    from pathlib import Path
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    file_path = output_path / f"{video_id}.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(text)
    return str(file_path)
