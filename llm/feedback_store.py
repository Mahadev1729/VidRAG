"""
llm/feedback_store.py
=====================
SQLite-based user feedback and verified Q&A memory store.

Features:
- Stores user ratings (thumbs up / thumbs down) and feedback notes.
- Indexes verified high-quality answers to serve as dynamic few-shot context.
- Provides statistics on answer quality and user satisfaction.
"""

from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from config import FEEDBACK_DB_PATH


def get_connection(db_path: Optional[Path | str] = None) -> sqlite3.Connection:
    """Create a SQLite database connection, ensuring directory existence."""
    target_path = Path(db_path) if db_path else FEEDBACK_DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(target_path))


def init_feedback_db(db_path: Optional[Path | str] = None) -> None:
    """Initialize the feedback database table."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS qa_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT NOT NULL,
            username TEXT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            rating INTEGER NOT NULL,  -- +1 for positive, -1 for negative
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_qa_feedback_video ON qa_feedback(video_id, rating);"
    )
    conn.commit()
    conn.close()


def record_feedback(
    video_id: str,
    question: str,
    answer: str,
    rating: int | str,
    username: Optional[str] = None,
    comment: Optional[str] = None,
    db_path: Optional[Path | str] = None,
) -> bool:
    """
    Record user feedback for a Q&A interaction.

    Args:
        video_id: YouTube video ID
        question: User query
        answer: Model generated answer
        rating: +1 (thumbs up) or -1 (thumbs down), or 'thumbs_up'/'thumbs_down'
        username: Active username (optional)
        comment: User correction / notes (optional)
        db_path: Path to feedback database (optional)

    Returns:
        bool: True if recorded successfully
    """
    if not video_id or not question or not answer:
        return False

    init_feedback_db(db_path)

    # Normalize numeric rating
    if isinstance(rating, str):
        numeric_rating = 1 if "up" in rating.lower() or rating == "1" else -1
    else:
        numeric_rating = 1 if rating > 0 else -1

    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO qa_feedback (video_id, username, question, answer, rating, comment)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                video_id.strip(),
                (username or "").strip(),
                question.strip(),
                answer.strip(),
                numeric_rating,
                (comment or "").strip(),
            ),
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"[FEEDBACK] Error saving feedback: {e}")
        return False
    finally:
        conn.close()


def get_verified_examples(
    video_id: str,
    question: Optional[str] = None,
    limit: int = 2,
    db_path: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve highly rated (thumbs up) past Q&A examples for dynamic few-shot prompting.

    Args:
        video_id: YouTube video ID
        question: Current question (for future semantic matching)
        limit: Max number of examples to retrieve
        db_path: Custom database path

    Returns:
        List of dicts with 'question' and 'answer'
    """
    init_feedback_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT question, answer, comment
            FROM qa_feedback
            WHERE video_id = ? AND rating > 0
            ORDER BY id DESC
            LIMIT ?
            """,
            (video_id.strip(), limit),
        )
        rows = cursor.fetchall()
        return [
            {
                "question": row[0],
                "answer": row[1],
                "comment": row[2],
            }
            for row in rows
        ]
    except Exception as e:
        print(f"[FEEDBACK] Error reading verified examples: {e}")
        return []
    finally:
        conn.close()


def get_feedback_stats(
    video_id: Optional[str] = None,
    db_path: Optional[Path | str] = None,
) -> Dict[str, int]:
    """Get aggregated thumbs up / thumbs down statistics."""
    init_feedback_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        if video_id:
            cursor.execute(
                """
                SELECT
                    SUM(CASE WHEN rating > 0 THEN 1 ELSE 0 END) AS upvotes,
                    SUM(CASE WHEN rating < 0 THEN 1 ELSE 0 END) AS downvotes
                FROM qa_feedback
                WHERE video_id = ?
                """,
                (video_id.strip(),),
            )
        else:
            cursor.execute(
                """
                SELECT
                    SUM(CASE WHEN rating > 0 THEN 1 ELSE 0 END) AS upvotes,
                    SUM(CASE WHEN rating < 0 THEN 1 ELSE 0 END) AS downvotes
                FROM qa_feedback
                """
            )
        row = cursor.fetchone()
        return {
            "upvotes": (row[0] or 0) if row else 0,
            "downvotes": (row[1] or 0) if row else 0,
        }
    except Exception:
        return {"upvotes": 0, "downvotes": 0}
    finally:
        conn.close()
