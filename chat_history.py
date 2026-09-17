from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Tuple


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "chat_history.db"


def get_connection() -> sqlite3.Connection:
    """Create SQLite database connection, ensuring directory existence."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    """Create chat history table and handle migration for username support."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            video_id TEXT NOT NULL,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
        """
    )

    # Check for legacy session_id schema & migrate if necessary
    cursor.execute("PRAGMA table_info(chat_history)")
    columns = [col[1] for col in cursor.fetchall()]

    if "username" not in columns:
        cursor.execute("ALTER TABLE chat_history ADD COLUMN username TEXT")
        if "session_id" in columns:
            cursor.execute("UPDATE chat_history SET username = session_id WHERE username IS NULL")

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_user_video ON chat_history(username, video_id)"
    )

    conn.commit()
    conn.close()


def save_message(
    username: str,
    video_id: str,
    role: str,
    message: str,
) -> None:
    """Save one chat message for a specific user and video."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(chat_history)")
    columns = [col[1] for col in cursor.fetchall()]

    if "session_id" in columns:
        cursor.execute(
            """
            INSERT INTO chat_history (
                session_id,
                username,
                video_id,
                role,
                message,
                timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                username,
                video_id,
                role,
                message,
                datetime.now().isoformat(),
            ),
        )
    else:
        cursor.execute(
            """
            INSERT INTO chat_history (
                username,
                video_id,
                role,
                message,
                timestamp
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                username,
                video_id,
                role,
                message,
                datetime.now().isoformat(),
            ),
        )

    conn.commit()
    conn.close()


def get_messages(
    username: str,
    video_id: str,
) -> List[Tuple[str, str]]:
    """Get all chat messages (role, message) for a specific user and video."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT role, message
        FROM chat_history
        WHERE (username = ? OR (username IS NULL AND ? = 'default'))
        AND video_id = ?
        ORDER BY id ASC
        """,
        (username, username, video_id),
    )

    messages = cursor.fetchall()
    conn.close()
    return messages


def clear_messages(
    username: str,
    video_id: str,
) -> None:
    """Delete all chat history for a specific user and video."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM chat_history
        WHERE (username = ? OR (username IS NULL AND ? = 'default'))
        AND video_id = ?
        """,
        (username, username, video_id),
    )

    conn.commit()
    conn.close()


def get_user_recent_activity(
    username: str,
    limit: int = 15,
) -> List[Dict[str, Any]]:
    """
    Fetch distinct videos the user has interacted with, sorted by most recent timestamp.
    """
    if not username:
        return []

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT 
            video_id,
            MAX(timestamp) AS last_active,
            COUNT(*) AS message_count,
            (
                SELECT message FROM chat_history h2 
                WHERE (h2.username = h1.username OR (h2.username IS NULL AND h1.username = 'default'))
                  AND h2.video_id = h1.video_id 
                  AND h2.role = 'user'
                ORDER BY h2.id DESC LIMIT 1
            ) AS last_question
        FROM chat_history h1
        WHERE username = ? OR (username IS NULL AND ? = 'default')
        GROUP BY video_id
        ORDER BY last_active DESC
        LIMIT ?
        """,
        (username, username, limit),
    )

    rows = cursor.fetchall()
    conn.close()

    activity = []
    for row in rows:
        activity.append(
            {
                "video_id": row[0],
                "last_active": row[1],
                "message_count": row[2],
                "last_question": row[3] or "Video exploration",
            }
        )

    return activity


def delete_user_video_activity(
    username: str,
    video_id: str,
) -> None:
    """Delete all records for a user's specific video session."""
    clear_messages(username, video_id)
