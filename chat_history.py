from pathlib import Path
import sqlite3
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parent

DEFAULT_DB_PATH = BASE_DIR / "data" / "chat_history.db"


def get_connection(db_path=None):
    """
    Create SQLite database connection.
    """
    db_path = Path(db_path or DEFAULT_DB_PATH)
    db_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    return sqlite3.connect(db_path)


def init_db(db_path=None):
    """
    Create chat history table if it does not exist.
    """

    conn = get_connection(db_path)

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            video_id TEXT NOT NULL,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def save_message(
    session_id,
    video_id,
    role,
    message,
    db_path=None,
):
    """
    Save one chat message.
    """

    conn = get_connection(db_path)

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO chat_history
        (
            session_id,
            video_id,
            role,
            message,
            timestamp
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            session_id,
            video_id,
            role,
            message,
            datetime.now().isoformat()
        )
    )

    conn.commit()
    conn.close()


def get_messages(
    session_id,
    video_id,
    db_path=None,
):
    """
    Get chat messages for a session and video.
    """

    conn = get_connection(db_path)

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT role, message
        FROM chat_history
        WHERE session_id = ?
        AND video_id = ?
        ORDER BY id ASC
        """,
        (
            session_id,
            video_id
        )
    )

    messages = cursor.fetchall()

    conn.close()

    return messages


def clear_messages(
    session_id,
    video_id,
    db_path=None,
):
    """
    Delete chat history for a session and video.
    """

    conn = get_connection(db_path)

    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM chat_history
        WHERE session_id = ?
        AND video_id = ?
        """,
        (
            session_id,
            video_id
        )
    )

    conn.commit()
    conn.close()
