from pathlib import Path
from urllib.parse import urlparse, parse_qs

from youtube_transcript_api import YouTubeTranscriptApi


# ============================================================
# Extract Video ID
# ============================================================

def extract_video_id(url: str) -> str:

    parsed_url = urlparse(url)
    hostname = parsed_url.hostname

    # --------------------------------------------------------
    # Standard YouTube URL
    # https://www.youtube.com/watch?v=VIDEO_ID
    # --------------------------------------------------------

    if hostname in ["www.youtube.com", "youtube.com"]:

        video_id = parse_qs(
            parsed_url.query
        ).get("v", [None])[0]

        if video_id:
            return video_id

    # --------------------------------------------------------
    # Short YouTube URL
    # https://youtu.be/VIDEO_ID
    # --------------------------------------------------------

    if hostname == "youtu.be":

        video_id = (
            parsed_url.path
            .lstrip("/")
            .split("/")[0]
        )

        if video_id:
            return video_id

    raise ValueError(
        "Invalid YouTube URL. "
        "Please provide a valid YouTube video URL."
    )


# ============================================================
# Get Transcript
# ============================================================

def get_transcript(video_id: str) -> str:

    api = YouTubeTranscriptApi()

    transcript = api.fetch(video_id)

    text = "\n".join(
        item.text
        for item in transcript
    )

    return text


# ============================================================
# Save Transcript
# ============================================================

def save_transcript(
    video_id: str,
    text: str,
    base_dir: Path
):

    output_dir = (
        base_dir
        / "data"
        / "transcripts"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    output_file = (
        output_dir
        / f"{video_id}.txt"
    )

    output_file.write_text(
        text,
        encoding="utf-8"
    )

    return output_file
