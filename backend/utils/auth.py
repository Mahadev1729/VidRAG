"""
backend/utils/auth.py
=====================
JWT-based authentication and secure password hashing for FastAPI backend using TiDB Cloud.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import os
import re
import secrets
from typing import Any, Dict, Optional, Tuple

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES
from database import (
    create_user,
    get_user_by_username_or_email,
)

security = HTTPBearer(auto_error=False)
EMAIL_REGEX = re.compile(r"^[\w\.\+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\.\-]+$")


def hash_password(password: str) -> str:
    """Hash password using PBKDF2 HMAC-SHA256 with random salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
    )
    return f"{salt}${key.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored salt$hash."""
    try:
        salt, key = stored_hash.split("$", 1)
        expected_key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100000,
        )
        return secrets.compare_digest(expected_key.hex(), key)
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create signed JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def register_user(username: str, email: str, password: str) -> Tuple[bool, str]:
    """Register a new user in TiDB."""
    username = username.strip()
    email = email.strip().lower()

    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if not EMAIL_REGEX.match(email):
        return False, "Invalid email address format."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."

    existing_user = get_user_by_username_or_email(username)
    if existing_user:
        return False, "Username or Email is already registered."

    existing_email = get_user_by_username_or_email(email)
    if existing_email:
        return False, "Username or Email is already registered."

    pwd_hash = hash_password(password)
    try:
        create_user(username, email, pwd_hash)
        return True, "User registered successfully."
    except Exception as e:
        return False, f"Failed to register user: {str(e)}"


def authenticate_user(identifier: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate user with username or email."""
    user = get_user_by_username_or_email(identifier)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Dict[str, Any]:
    """FastAPI Dependency to get authenticated user from Bearer JWT."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    user = get_user_by_username_or_email(username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
    }
