"""
backend/chat_history.py
=======================
Chat history manager redirecting to TiDB Cloud backend.
"""

from typing import Any, Dict, List, Optional
from database import (
    save_chat_message,
    get_chat_history,
    clear_chat_history,
    get_user_videos,
)


def save_message(
    username: str,
    video_id: str,
    role: str,
    message: str,
) -> None:
    """Save one chat message for a specific user and video in TiDB."""
    save_chat_message(username=username, video_id=video_id, role=role, message=message)


def load_history(
    username: str,
    video_id: str,
) -> List[Dict[str, Any]]:
    """Load all messages for a user and video from TiDB."""
    return get_chat_history(username=username, video_id=video_id)


def clear_history(
    username: str,
    video_id: str,
) -> None:
    """Delete all messages for a user and video in TiDB."""
    clear_chat_history(username=username, video_id=video_id)


def list_user_videos(username: str) -> List[str]:
    """List all video IDs that the user has chatted with."""
    return get_user_videos(username=username)
