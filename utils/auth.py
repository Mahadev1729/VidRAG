"""
utils/auth.py
=============
SQLite3-based user authentication and registration service.

Supports:
- User registration with username, gmail/email, and password
- Dual sign-in via either username or gmail/email
- PBKDF2 HMAC-SHA256 password hashing (100,000 iterations, 16-byte random salt)
- Constant-time password verification via secrets.compare_digest
- Automatic SQLite migration to ensure email column exists
"""

import hashlib
from pathlib import Path
import re
import secrets
import sqlite3
from typing import Any, Dict, Optional, Tuple

import streamlit as st


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "users.db"

# Basic RFC 5322 compatible email pattern
EMAIL_REGEX = re.compile(r"^[\w\.\+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\.\-]+$")


class AuthResult(tuple):
    """Result tuple supporting unpacking, bool coercion, and named properties."""

    def __new__(cls, success: bool, message: str):
        return super().__new__(cls, (success, message))

    @property
    def success(self) -> bool:
        return self[0]

    @property
    def message(self) -> str:
        return self[1]

    def __bool__(self) -> bool:
        return self[0]


def get_connection(db_path: Optional[Path | str] = None) -> sqlite3.Connection:
    """Create a SQLite database connection, ensuring directory existence."""
    target_path = Path(db_path) if db_path else DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(target_path))


def init_db(db_path: Optional[Path | str] = None) -> None:
    """
    Initialize the users table in SQLite if it does not exist.
    Also ensures migration if existing table lacks the email column.
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL COLLATE NOCASE,
            email TEXT UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()

    # Schema migration: check if email column exists in existing database
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1].lower() for row in cursor.fetchall()]
    if "email" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN email TEXT COLLATE NOCASE")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        conn.commit()

    conn.close()


def _hash_password(password: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
    """
    Generate PBKDF2 HMAC-SHA256 hash using a 16-byte random salt.
    Returns (password_hash_hex, salt_hex).
    """
    if salt is None:
        salt = secrets.token_bytes(16)

    hash_bytes = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        100000,
    )
    return hash_bytes.hex(), salt.hex()


def _verify_password(password: str, stored_hash: str, stored_salt: str) -> bool:
    """Constant-time verification of password against stored hash and salt."""
    try:
        salt_bytes = bytes.fromhex(stored_salt)
        computed_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt_bytes,
            100000,
        ).hex()
        return secrets.compare_digest(computed_hash, stored_hash)
    except Exception:
        return False


def is_valid_email(email: str) -> bool:
    """Check if an email string is well-formed."""
    return bool(email and EMAIL_REGEX.match(email.strip()))


def register_user(
    username: str,
    email: str,
    password: Optional[str] = None,
    db_path: Optional[Path | str] = None,
) -> AuthResult:
    """
    Validate inputs, check for duplicate usernames/emails, and register a new user.
    Validation rules:
    - Username: non-empty, minimum 3 characters
    - Email: valid email / gmail address
    - Password: non-empty, minimum 6 characters
    """
    # Allow register_user(username, password) backwards compatibility
    if password is None:
        password = email
        email = ""

    if not username or not username.strip():
        return AuthResult(False, "Username cannot be empty.")

    username = username.strip()
    if len(username) < 3:
        return AuthResult(False, "Username must be at least 3 characters long.")

    if not email or not email.strip():
        return AuthResult(False, "Gmail / Email address cannot be empty.")

    email = email.strip()
    if not is_valid_email(email):
        return AuthResult(False, "Please enter a valid Gmail / Email address (e.g. name@gmail.com).")

    if not password:
        return AuthResult(False, "Password cannot be empty.")

    if len(password) < 6:
        return AuthResult(False, "Password must be at least 6 characters long.")

    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    try:
        # Check for duplicate username
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone() is not None:
            conn.close()
            return AuthResult(
                False,
                f"Username '{username}' is already taken. Please choose another.",
            )

        # Check for duplicate email
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone() is not None:
            conn.close()
            return AuthResult(
                False,
                f"Email '{email}' is already registered. Please sign in or use another email.",
            )

        password_hash, salt = _hash_password(password)
        cursor.execute(
            """
            INSERT INTO users (username, email, password_hash, salt)
            VALUES (?, ?, ?, ?)
            """,
            (username, email, password_hash, salt),
        )
        conn.commit()
        conn.close()
        return AuthResult(
            True,
            f"Account for '{username}' created successfully! You can now sign in.",
        )
    except sqlite3.IntegrityError as e:
        conn.close()
        err_msg = str(e).lower()
        if "email" in err_msg:
            return AuthResult(False, f"Email '{email}' is already registered. Please sign in.")
        return AuthResult(False, f"Username '{username}' is already taken. Please choose another.")
    except Exception as e:
        conn.close()
        return AuthResult(False, f"Database error: {str(e)}")


def get_user_by_identifier(
    identifier: str,
    db_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Retrieve user record by username or email.
    Returns dictionary with user fields if found, otherwise None.
    """
    if not identifier or not identifier.strip():
        return None

    cleaned_id = identifier.strip()
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT id, username, email, password_hash, salt
            FROM users
            WHERE username = ? OR email = ?
            LIMIT 1
            """,
            (cleaned_id, cleaned_id),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "password_hash": row[3],
            "salt": row[4],
        }
    except Exception:
        conn.close()
        return None


def authenticate_user(
    identifier: str,
    password: str,
    db_path: Optional[Path | str] = None,
) -> bool:
    """
    Validate credentials using either username or gmail/email.
    Returns True on successful authentication, False otherwise.
    """
    if not identifier or not identifier.strip() or not password:
        return False

    user = get_user_by_identifier(identifier, db_path)
    if not user:
        return False

    return _verify_password(password, user["password_hash"], user["salt"])


def render_auth_page() -> None:
    """
    Render a centered, elegant authentication card with Sign In and Create Account tabs.
    Supports signing in via username or gmail/email.
    """
    _, center_col, _ = st.columns([1, 2.2, 1])

    with center_col:
        with st.container(border=True):
            st.markdown(
                """
                <div class="auth-header">
                    <div class="auth-icon">🎥</div>
                    <h2 class="auth-title">YouTube RAG Assistant</h2>
                    <p class="auth-subtitle">Sign in to summarize videos and chat with timestamps</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            tab_signin, tab_register = st.tabs(["🔑 Sign In", "📝 Create Account"])

            with tab_signin:
                with st.form("signin_form", clear_on_submit=False):
                    signin_identifier = st.text_input(
                        "Username or Gmail / Email",
                        placeholder="Enter your username or email address",
                        key="signin_identifier",
                    )
                    signin_password = st.text_input(
                        "Password",
                        type="password",
                        placeholder="••••••••",
                        key="signin_password",
                    )
                    signin_submitted = st.form_submit_button(
                        "Sign In",
                        use_container_width=True,
                        type="primary",
                    )

                    if signin_submitted:
                        if not signin_identifier.strip() or not signin_password:
                            st.error("Please enter your username/email and password.")
                        else:
                            is_authenticated = authenticate_user(
                                signin_identifier,
                                signin_password,
                            )
                            if is_authenticated:
                                user = get_user_by_identifier(signin_identifier)
                                st.session_state.authenticated = True
                                st.session_state.username = (
                                    user["username"] if user else signin_identifier.strip()
                                )
                                st.success("Signed in successfully! Redirecting...")
                                st.rerun()
                            else:
                                st.error("Invalid username/email or password. Please try again.")

            with tab_register:
                with st.form("register_form", clear_on_submit=False):
                    reg_username = st.text_input(
                        "Choose Username",
                        placeholder="Minimum 3 characters",
                        key="register_username",
                        help="Usernames are case-insensitive and must be at least 3 characters.",
                    )
                    reg_email = st.text_input(
                        "Gmail / Email Address",
                        placeholder="e.g. yourname@gmail.com",
                        key="register_email",
                        help="Used for sign in and account identification.",
                    )
                    reg_password = st.text_input(
                        "Password",
                        type="password",
                        placeholder="Minimum 6 characters",
                        key="register_password",
                        help="Password must be at least 6 characters.",
                    )
                    reg_confirm = st.text_input(
                        "Confirm Password",
                        type="password",
                        placeholder="Re-enter your password",
                        key="register_confirm",
                    )
                    register_submitted = st.form_submit_button(
                        "Create Account",
                        use_container_width=True,
                        type="primary",
                    )

                    if register_submitted:
                        if not reg_username.strip() or not reg_email.strip() or not reg_password:
                            st.error("Please fill in all required fields.")
                        elif not is_valid_email(reg_email):
                            st.error("Please enter a valid Gmail / Email address (e.g. name@gmail.com).")
                        elif reg_password != reg_confirm:
                            st.error("Passwords do not match. Please verify and try again.")
                        else:
                            result = register_user(reg_username, reg_email, reg_password)
                            if result.success:
                                st.success(result.message)
                                st.info("👉 Switch to the **🔑 Sign In** tab above to log in.")
                            else:
                                st.error(result.message)

