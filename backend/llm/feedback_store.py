"""
backend/llm/feedback_store.py
=============================
TiDB Cloud-based user feedback and verified Q&A memory store.
"""

from typing import Any, Dict, List, Optional
from database import save_feedback, get_feedback_examples, get_db_connection


def record_feedback(
    video_id: str,
    question: str,
    answer: str,
    rating: int | str,
    username: Optional[str] = None,
    comment: Optional[str] = None,
) -> bool:
    """
    Record user feedback for a Q&A interaction in TiDB Cloud.
    """
    if not video_id or not question or not answer:
        return False

    if isinstance(rating, str):
        numeric_rating = 1 if "up" in rating.lower() or rating == "1" else -1
        feedback_type = "positive" if numeric_rating == 1 else "negative"
    else:
        numeric_rating = 1 if rating > 0 else -1
        feedback_type = "positive" if numeric_rating == 1 else "negative"

    try:
        save_feedback(
            username=username or "anonymous",
            video_id=video_id.strip(),
            question=question.strip(),
            answer=answer.strip(),
            feedback_type=feedback_type,
            rating=numeric_rating,
            comment=comment.strip() if comment else None,
        )
        return True
    except Exception as e:
        print(f"[FEEDBACK] Error saving feedback to TiDB: {e}")
        return False


def get_verified_examples(
    video_id: str,
    question: Optional[str] = None,
    limit: int = 2,
) -> List[Dict[str, Any]]:
    """
    Retrieve positive past Q&A examples from TiDB Cloud for few-shot prompt injection.
    """
    try:
        return get_feedback_examples(video_id=video_id, limit=limit)
    except Exception as e:
        print(f"[FEEDBACK] Error retrieving verified examples: {e}")
        return []


def get_feedback_stats(video_id: Optional[str] = None) -> Dict[str, int]:
    """Get aggregated positive / negative feedback count from TiDB Cloud."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if video_id:
                cursor.execute(
                    """
                    SELECT
                        SUM(CASE WHEN feedback_type = 'positive' THEN 1 ELSE 0 END) AS upvotes,
                        SUM(CASE WHEN feedback_type = 'negative' THEN 1 ELSE 0 END) AS downvotes
                    FROM feedback
                    WHERE video_id = %s
                    """,
                    (video_id.strip(),),
                )
            else:
                cursor.execute(
                    """
                    SELECT
                        SUM(CASE WHEN feedback_type = 'positive' THEN 1 ELSE 0 END) AS upvotes,
                        SUM(CASE WHEN feedback_type = 'negative' THEN 1 ELSE 0 END) AS downvotes
                    FROM feedback
                    """
                )
            row = cursor.fetchone()
            return {
                "upvotes": int(row["upvotes"] or 0) if row else 0,
                "downvotes": int(row["downvotes"] or 0) if row else 0,
            }
    except Exception:
        return {"upvotes": 0, "downvotes": 0}
    finally:
        conn.close()
