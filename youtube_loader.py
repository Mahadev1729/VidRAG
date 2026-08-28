import re
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi


# ============================================================
# 1. EXTRACT YOUTUBE VIDEO ID
# ============================================================

def extract_video_id(url):
    """
    Extract YouTube video ID.

    Supported formats:

    1. https://www.youtube.com/watch?v=VIDEO_ID
    2. https://youtube.com/watch?v=VIDEO_ID
    3. https://youtu.be/VIDEO_ID
    4. https://www.youtube.com/shorts/VIDEO_ID

    Also supports URLs containing additional parameters.
    """

    if not url:
        raise ValueError(
            "YouTube URL cannot be empty."
        )

    url = url.strip()

    # Remove accidental quotes
    url = url.strip('"').strip("'")

    patterns = [

        # ----------------------------------------------------
        # Standard YouTube URL
        # https://www.youtube.com/watch?v=VIDEO_ID
        # ----------------------------------------------------

        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?[^#\s]*v=([A-Za-z0-9_-]{11})",

        # ----------------------------------------------------
        # Short YouTube URL
        # https://youtu.be/VIDEO_ID
        # ----------------------------------------------------

        r"(?:https?://)?youtu\.be/([A-Za-z0-9_-]{11})",

        # ----------------------------------------------------
        # YouTube Shorts
        # https://www.youtube.com/shorts/VIDEO_ID
        # ----------------------------------------------------

        r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([A-Za-z0-9_-]{11})",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            url
        )

        if match:
            return match.group(1)

    raise ValueError(
        "Invalid YouTube URL.\n\n"
        "Supported formats:\n"
        "https://www.youtube.com/watch?v=VIDEO_ID\n"
        "https://youtube.com/watch?v=VIDEO_ID\n"
        "https://youtu.be/VIDEO_ID\n"
        "https://www.youtube.com/shorts/VIDEO_ID"
    )


# ============================================================
# 2. GET TRANSCRIPT WITH TIMESTAMPS
# ============================================================

def get_transcript_with_timestamps(url):
    """
    Retrieve YouTube transcript while preserving timestamps.

    Priority:
        1. English transcript
        2. Manually created transcript
        3. Auto-generated transcript

    Returns:
        list of dictionaries:

        [
            {
                "text": "...",
                "start": 10.5,
                "duration": 4.2,
                "end": 14.7
            }
        ]
    """

    video_id = extract_video_id(url)

    try:

        api = YouTubeTranscriptApi()

        # ----------------------------------------------------
        # Get available transcripts
        # ----------------------------------------------------

        transcripts = api.list(
            video_id
        )

        selected_transcript = None

        # ----------------------------------------------------
        # Priority 1: English
        # ----------------------------------------------------

        for transcript in transcripts:

            language_code = getattr(
                transcript,
                "language_code",
                ""
            )

            if language_code.lower().startswith("en"):

                selected_transcript = transcript
                break

        # ----------------------------------------------------
        # Priority 2: Manual transcript
        # ----------------------------------------------------

        if selected_transcript is None:

            for transcript in transcripts:

                is_generated = getattr(
                    transcript,
                    "is_generated",
                    False
                )

                if not is_generated:

                    selected_transcript = transcript
                    break

        # ----------------------------------------------------
        # Priority 3: Auto-generated transcript
        # ----------------------------------------------------

        if selected_transcript is None:

            for transcript in transcripts:

                is_generated = getattr(
                    transcript,
                    "is_generated",
                    False
                )

                if is_generated:

                    selected_transcript = transcript
                    break

        # ----------------------------------------------------
        # No transcript found
        # ----------------------------------------------------

        if selected_transcript is None:

            raise ValueError(
                "No usable transcript was found for this video."
            )

        # ----------------------------------------------------
        # Fetch transcript
        # ----------------------------------------------------

        fetched = selected_transcript.fetch()

        segments = []

        for item in fetched:

            text = getattr(
                item,
                "text",
                ""
            )

            start = float(
                getattr(
                    item,
                    "start",
                    0
                )
            )

            duration = float(
                getattr(
                    item,
                    "duration",
                    0
                )
            )

            end = start + duration

            if text and text.strip():

                segments.append(
                    {
                        "text": text.strip(),
                        "start": start,
                        "duration": duration,
                        "end": end
                    }
                )

        if not segments:

            raise ValueError(
                "Transcript was found but contains no usable text."
            )

        return segments

    except Exception as e:

        raise ValueError(
            f"Could not retrieve transcript for video "
            f"{url}: {str(e)}"
        )


# ============================================================
# 3. GET PLAIN TRANSCRIPT
# ============================================================

def get_transcript(url):
    """
    Return transcript as plain text.

    This function is kept for compatibility with
    the rest of the project.
    """

    segments = get_transcript_with_timestamps(
        url
    )

    text = " ".join(
        segment["text"]
        for segment in segments
    )

    return text


# ============================================================
# 4. SAVE TRANSCRIPT
# ============================================================

def save_transcript(
    text,
    video_id,
    output_dir="data/transcripts"
):
    """
    Save transcript to a text file.
    """

    output_path = Path(
        output_dir
    )

    output_path.mkdir(
        parents=True,
        exist_ok=True
    )

    file_path = (
        output_path
        / f"{video_id}.txt"
    )

    with open(
        file_path,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(text)

    return str(file_path)
