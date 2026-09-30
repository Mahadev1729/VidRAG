"""
backend/database.py
===================
TiDB Cloud database manager supporting:
- Relational schema (Users, Sessions, Chat History, Feedback, Video Metadata)
- TiDB Vector Search with 384-dimensional embeddings (SentenceTransformers)
- SSL connection handling using TiDB connection string (TIDB_DATABASE_URL)
"""

import json
import queue
import ssl
import threading
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


class PooledConnection:
    """Thread-safe connection wrapper that returns raw connection to pool on close()."""

    def __init__(self, raw_conn: pymysql.connections.Connection, pool: "TiDBConnectionPool"):
        self._raw_conn = raw_conn
        self._pool = pool
        self._closed = False

    def cursor(self, *args, **kwargs):
        return self._raw_conn.cursor(*args, **kwargs)

    def commit(self):
        return self._raw_conn.commit()

    def rollback(self):
        return self._raw_conn.rollback()

    def close(self):
        if not self._closed and self._pool is not None:
            self._closed = True
            self._pool.release(self._raw_conn)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __getattr__(self, name: str):
        return getattr(self._raw_conn, name)


class TiDBConnectionPool:
    """Reusable connection pool for TiDB Cloud Serverless (eliminates 500ms SSL handshakes)."""

    def __init__(self, max_connections: int = 15):
        self.max_connections = max_connections
        self._pool: queue.Queue = queue.Queue(maxsize=max_connections)
        self._created_count = 0
        self._lock = threading.Lock()

    def _create_raw_connection(self) -> pymysql.connections.Connection:
        if not TIDB_DATABASE_URL or not TIDB_HOST or not TIDB_USER:
            raise ValueError(
                "TiDB connection string is missing! Please set TIDB_DATABASE_URL in your .env file:\n"
                'TIDB_DATABASE_URL="mysql://<user>:<password>@<host>:4000/<database>"'
            )

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
            connect_timeout=10,
            read_timeout=30,
            write_timeout=30,
        )

    def get_connection(self) -> PooledConnection:
        conn = None
        try:
            conn = self._pool.get_nowait()
            try:
                conn.ping(reconnect=True)
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
                conn = self._create_raw_connection()
        except queue.Empty:
            with self._lock:
                if self._created_count < self.max_connections:
                    self._created_count += 1
                    conn = self._create_raw_connection()
            if conn is None:
                conn = self._pool.get(timeout=10)
                try:
                    conn.ping(reconnect=True)
                except Exception:
                    conn = self._create_raw_connection()

        return PooledConnection(conn, self)

    def release(self, raw_conn: pymysql.connections.Connection):
        try:
            self._pool.put_nowait(raw_conn)
        except queue.Full:
            try:
                raw_conn.close()
            except Exception:
                pass
            with self._lock:
                self._created_count = max(0, self._created_count - 1)


_DB_POOL = TiDBConnectionPool(max_connections=15)


def get_db_connection() -> PooledConnection:
    """Acquire a pooled, validated SSL connection to TiDB Cloud instantly (<5ms)."""
    return _DB_POOL.get_connection()


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

            # 5. User Videos Association Table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_videos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(100) NOT NULL,
                    video_id VARCHAR(64) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_user_video (username, video_id),
                    INDEX idx_user (username)
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


def link_user_video(username: str, video_id: str) -> None:
    """Link a video to a user's private library cleanly in the user_videos table."""
    if not username or username == "anonymous" or not video_id:
        return
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO user_videos (username, video_id)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE created_at = CURRENT_TIMESTAMP
                    """,
                    (username.strip(), video_id.strip()),
                )
        finally:
            conn.close()
    except Exception as e:
        print(f"[DB WARNING] link_user_video failed: {e}")


def get_user_videos(username: str) -> List[Dict[str, Any]]:
    """
    Mode B: Strictly Private Library.
    Returns only the videos that this specific user has personally added or chatted about.
    """
    if not username or username == "anonymous":
        return []

    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Query user_videos first, left join with chat_history count
                cursor.execute(
                    """
                    SELECT 
                        u.video_id, 
                        u.created_at AS last_activity,
                        (SELECT COUNT(*) FROM chat_history c WHERE c.username = u.username AND c.video_id = u.video_id) AS message_count
                    FROM user_videos u
                    WHERE u.username = %s
                    ORDER BY u.created_at DESC
                    """,
                    (username.strip(),),
                )
                rows = cursor.fetchall()

                # If no user_videos rows exist yet, fallback to distinct chat_history
                if not rows:
                    cursor.execute(
                        """
                        SELECT 
                            c.video_id, 
                            MAX(c.created_at) AS last_activity,
                            COUNT(c.id) AS message_count
                        FROM chat_history c
                        WHERE c.username = %s
                        GROUP BY c.video_id
                        ORDER BY last_activity DESC
                        """,
                        (username.strip(),),
                    )
                    rows = cursor.fetchall()

                return [
                    {
                        "video_id": r["video_id"],
                        "thumbnail": f"https://img.youtube.com/vi/{r['video_id']}/mqdefault.jpg",
                        "message_count": r.get("message_count", 0),
                        "last_active": str(r.get("last_activity", "")),
                    }
                    for r in rows
                    if r.get("video_id")
                ]
        finally:
            conn.close()
    except Exception as e:
        print(f"[DB WARNING] get_user_videos failed: {e}")
        return []



