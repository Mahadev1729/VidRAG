import re
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi


def extract_video_id(url):
    """
    Extract YouTube video ID.

    Supported:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/shorts/VIDEO_ID
    """

    url = url.strip()

    patterns = [
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([A-Za-z0-9_-]{11})",
        r"(?:https?://)?youtu\.be/([A-Za-z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([A-Za-z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)

        if match:
            return match.group(1)

    raise ValueError(
        "Invalid YouTube URL. Supported formats: "
        "youtube.com/watch?v=..., "
        "youtu.be/..., "
        "youtube.com/shorts/..."
    )


def get_transcript(url):
    """
    Get the available YouTube transcript.

    Priority:
    1. English
    2. Manually created transcript
    3. Auto-generated transcript

    No Whisper fallback.
    """

    video_id = extract_video_id(url)

    try:
        api = YouTubeTranscriptApi()

        transcripts = api.list(video_id)

        # 1. English
        for transcript in transcripts:

            if transcript.language_code.startswith("en"):

                fetched = transcript.fetch()

                text = " ".join(
                    item.text for item in fetched
                )

                if text.strip():
                    return text

        # 2. Manually created transcript
        for transcript in transcripts:

            if not transcript.is_generated:

                fetched = transcript.fetch()

                text = " ".join(
                    item.text for item in fetched
                )

                if text.strip():
                    return text

        # 3. Auto-generated transcript
        for transcript in transcripts:

            if transcript.is_generated:

                fetched = transcript.fetch()

                text = " ".join(
                    item.text for item in fetched
                )

                if text.strip():
                    return text

        raise ValueError(
            "No usable transcript was found for this video."
        )

    except Exception as e:

        raise ValueError(
            f"Could not retrieve transcript for video "
            f"{url}: {str(e)}"
        )


def save_transcript(text, video_id, output_dir="data/transcripts"):
    """Save transcript to a text file."""

    output_path = Path(output_dir)

    output_path.mkdir(
        parents=True,
        exist_ok=True
    )

    file_path = output_path / f"{video_id}.txt"

    with open(
        file_path,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(text)

    return str(file_path)
