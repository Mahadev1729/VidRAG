"""
backend/ingestion/youtube_loader.py
==================================
YouTube URL validation, transcript retrieval, and Whisper fallback.
"""

import os
import re
from typing import List, Dict, Any, Tuple, Optional

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from ingestion.whisper_loader import (
    WhisperTranscriptionError,
    whisper_transcribe_from_url,
)


class TranscriptError(Exception):
    """Raised when both YouTube captions and Whisper fallback fail."""
    pass


def extract_video_id(url: str) -> str:
    """
    Extract the 11-character video ID from a YouTube URL.
    """
    if not url:
        raise ValueError("YouTube URL cannot be empty.")

    url = url.strip().strip('"').strip("'")

    patterns = [
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?[^#\s]*v=([A-Za-z0-9_-]{11})",
        r"(?:https?://)?youtu\.be/([A-Za-z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([A-Za-z0-9_-]{11})",
        r"^([A-Za-z0-9_-]{11})$",  # Plain 11-char ID
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    raise ValueError(
        "Invalid YouTube URL or Video ID.\n"
        "Supported formats:\n"
        "  https://www.youtube.com/watch?v=VIDEO_ID\n"
        "  https://youtu.be/VIDEO_ID\n"
        "  https://www.youtube.com/shorts/VIDEO_ID"
    )


def _fetch_youtube_transcript_segments(video_id: str, languages: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Fetch transcript segments from the YouTube Transcript API."""
    api = YouTubeTranscriptApi()
    transcripts = api.list(video_id)

    selected = None
    pref_langs = languages or ["en", "hi", "es", "fr", "de"]

    # Priority: user preferred languages
    for lang in pref_langs:
        for t in transcripts:
            if getattr(t, "language_code", "").lower().startswith(lang.lower()):
                selected = t
                break
        if selected:
            break

    # Priority 2: Any manually created transcript
    if selected is None:
        for t in transcripts:
            if not getattr(t, "is_generated", False):
                selected = t
                break

    # Priority 3: Any auto-generated transcript
    if selected is None:
        for t in transcripts:
            if getattr(t, "is_generated", False):
                selected = t
                break

    if selected is None:
        raise ValueError("No usable transcript found for this video.")

    fetched = selected.fetch()
    segments = []

    for item in fetched:
        text = getattr(item, "text", "")
        start = float(getattr(item, "start", 0))
        duration = float(getattr(item, "duration", 0))
        end = start + duration

        if text and text.strip():
            segments.append({
                "text": text.strip(),
                "start": start,
                "duration": duration,
                "end": end,
            })

    if not segments:
        raise ValueError("Transcript exists but contains no usable text.")

    return segments


def _try_youtube_transcript(video_id: str, languages: Optional[List[str]] = None) -> Optional[List[Dict[str, Any]]]:
    """Safe wrapper for YouTube transcript API."""
    import time
    for attempt in range(2):
        try:
            return _fetch_youtube_transcript_segments(video_id, languages=languages)
        except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable):
            return None
        except Exception as error:
            print(f"[INGESTION] YouTube caption attempt {attempt + 1} failed: {error}")
            if attempt == 0:
                time.sleep(1)
    return None


def get_transcript_with_timestamps(
    url: str,
    status_callback=None,
    force_whisper: bool = False,
    languages: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Main transcript retrieval entrypoint.
    Tries YouTube Transcript API first, falls back to Whisper on failure.
    """
    video_id = extract_video_id(url)
    force_env = os.getenv("FORCE_WHISPER_FALLBACK", "").strip().lower() in {"1", "true", "yes"}
    use_whisper = force_whisper or force_env

    segments = None

    if not use_whisper:
        print(f"[INGESTION] Fetching YouTube transcript for {video_id}")
        segments = _try_youtube_transcript(video_id, languages=languages)

    if segments:
        print(f"[INGESTION] YouTube captions retrieved — {len(segments)} segments.")
        return segments, "youtube_api"

    # Whisper fallback
    print(f"[INGESTION] Whisper fallback activated for {video_id}")
    if status_callback:
        status_callback("YouTube captions unavailable. Falling back to Whisper AI...")

    try:
        segments = whisper_transcribe_from_url(url, video_id, status_callback=status_callback)
    except WhisperTranscriptionError as error:
        raise TranscriptError(str(error)) from error
    except Exception as error:
        raise TranscriptError(
            "Both YouTube captions and Whisper transcription failed. "
            "The video may be unavailable, private, or age-restricted."
        ) from error

    if not segments:
        raise TranscriptError("No usable transcript could be generated.")

    print(f"[INGESTION] Whisper transcript — {len(segments)} segments.")
    return segments, "whisper_ai"
