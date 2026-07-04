"""
用户认证 — JWT 注册/登录/获取当前用户。
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
import bcrypt
from jose import jwt, JWTError

from src.engine.db_core import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ── 配置 ──

SECRET_KEY = os.environ.get("JWT_SECRET", "ai-news-dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


# ── 请求/响应模型 ──

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)
    email: str = Field(default="")


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ── 工具函数 ──

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: int, username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def get_user_by_id(user_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_username(username: str) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── API 端点 ──

@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest):
    existing = get_user_by_username(payload.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")

    conn = get_db()
    cur = conn.execute(
        "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
        (payload.username, payload.email, _hash_password(payload.password)),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()

    token = create_access_token(user_id, payload.username, "user")
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user_id, username=payload.username,
            email=payload.email, role="user",
            created_at=datetime.now(timezone.utc).isoformat(),
        ),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    user = get_user_by_username(payload.username)
    if not user or not _verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(user["id"], user["username"], user["role"])
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user["id"], username=user["username"],
            email=user.get("email", ""), role=user["role"],
            created_at=user.get("created_at", ""),
        ),
    )
