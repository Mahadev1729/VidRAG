"""
backend/database.py
===================
TiDB Cloud database manager supporting:
- Relational schema (Users, Sessions, Chat History, Feedback, Video Metadata)
- TiDB Vector Search with 384-dimensional embeddings (SentenceTransformers)
- SSL connection handling using TiDB connection string (TIDB_DATABASE_URL)
"""

import json
import ssl
from typing import Any, Dict, List, Optional, Tuple
import pymysql
import pymysql.cursors

from config import (
    TIDB_HOST,
    TIDB_PORT,
    TIDB_USER,
    TIDB_PASSWORD,
    TIDB_DATABASE,
    TIDB_SSL_CA,
    TIDB_DATABASE_URL,
)


def get_db_connection() -> pymysql.connections.Connection:
    """
    Establish a secure SSL connection to TiDB Cloud using TIDB_DATABASE_URL.
    """
    if not TIDB_DATABASE_URL or not TIDB_HOST or not TIDB_USER:
        raise ValueError(
            "TiDB connection string is missing! Please set TIDB_DATABASE_URL in your .env file:\n"
            'TIDB_DATABASE_URL="mysql://<user>:<password>@<host>:4000/<database>"'
        )

    # SSL context required for TiDB Cloud Serverless
    ssl_context = ssl.create_default_context()
    if TIDB_SSL_CA:
        ssl_context.load_verify_locations(cafile=TIDB_SSL_CA)
    else:
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED

    return pymysql.connect(
        host=TIDB_HOST,
        port=TIDB_PORT,
        user=TIDB_USER,
        password=TIDB_PASSWORD,
        database=TIDB_DATABASE,
        ssl=ssl_context,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def init_tidb_schema() -> None:
    """
    Initialize all necessary tables in TiDB Cloud:
    - users
    - video_metadata
    - transcript_chunks (with Vector column for embeddings)
    - chat_history
    - feedback
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Users Table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(100) NOT NULL UNIQUE,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_username (username),
                    INDEX idx_email (email)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )

            # 2. Video Metadata Table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS video_metadata (
                    video_id VARCHAR(64) PRIMARY KEY,
                    title VARCHAR(500),
                    channel VARCHAR(255),
                    duration INT DEFAULT 0,
                    source VARCHAR(50) DEFAULT 'youtube',
                    summary LONGTEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )

            # 3. Transcript Chunks Table with Vector Support
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS transcript_chunks (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    video_id VARCHAR(64) NOT NULL,
                    chunk_index INT NOT NULL,
                    page_content LONGTEXT NOT NULL,
                    start_time FLOAT DEFAULT 0.0,
                    end_time FLOAT DEFAULT 0.0,
                    source VARCHAR(100) DEFAULT 'youtube',
                    embedding VECTOR(384) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_chunk_video (video_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )

            # 4. Chat History Table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(100) NOT NULL,
                    video_id VARCHAR(64) NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    message LONGTEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_video (username, video_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )
        print("[DATABASE] TiDB Cloud schema initialized successfully.")
    finally:
        conn.close()


# ── User Management ──────────────────────────────────────────────────────────

def get_user_by_username_or_email(identifier: str) -> Optional[Dict[str, Any]]:
    """Fetch user by username or email."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM users WHERE username = %s OR email = %s LIMIT 1",
                (identifier.strip(), identifier.strip()),
            )
            return cursor.fetchone()
    finally:
        conn.close()


def create_user(username: str, email: str, password_hash: str) -> bool:
    """Create a new user in TiDB."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
                (username.strip(), email.strip().lower(), password_hash),
            )
            return True
    finally:
        conn.close()


# ── Chat History in TiDB ─────────────────────────────────────────────────────

def save_chat_message(username: str, video_id: str, role: str, message: str) -> None:
    """Save a single chat message for user and video in TiDB."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO chat_history (username, video_id, role, message)
                VALUES (%s, %s, %s, %s)
                """,
                (username, video_id, role, message),
            )
    finally:
        conn.close()


def get_chat_history(username: str, video_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Retrieve chat history for a user and video from TiDB."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT role, message, created_at
                FROM chat_history
                WHERE username = %s AND video_id = %s
                ORDER BY id ASC
                LIMIT %s
                """,
                (username, video_id, limit),
            )
            return cursor.fetchall()
    finally:
        conn.close()


def clear_chat_history(username: str, video_id: str) -> None:
    """Clear chat history for a user and video in TiDB."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM chat_history WHERE username = %s AND video_id = %s",
                (username, video_id),
            )
    finally:
        conn.close()


def get_user_videos(username: str) -> List[str]:
    """Get list of distinct video IDs the user has chatted about."""
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT video_id
                    FROM chat_history
                    WHERE username = %s
                    GROUP BY video_id
                    ORDER BY MAX(id) DESC
                    """,
                    (username,),
                )
                rows = cursor.fetchall()
                return [row["video_id"] for row in rows]
        finally:
            conn.close()
    except Exception as e:
        print(f"[DB WARNING] get_user_videos failed: {e}")
        return []
