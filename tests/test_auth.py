from datetime import datetime, timedelta, timezone

import jwt

from src.api import auth


def test_access_token_round_trip(monkeypatch):
    monkeypatch.setattr(auth, "SECRET_KEY", "test-secret-key-with-at-least-32-bytes")

    token = auth.create_access_token(7, "alice", "admin")
    decoded = auth.decode_token(token)

    assert decoded is not None
    assert decoded["sub"] == "7"
    assert decoded["username"] == "alice"
    assert decoded["role"] == "admin"
    assert isinstance(decoded["exp"], int)


def test_decode_token_rejects_expired_token(monkeypatch):
    monkeypatch.setattr(auth, "SECRET_KEY", "test-secret-key-with-at-least-32-bytes")
    token = jwt.encode(
        {
            "sub": "7",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
        auth.SECRET_KEY,
        algorithm=auth.ALGORITHM,
    )

    assert auth.decode_token(token) is None


def test_decode_token_rejects_malformed_token():
    assert auth.decode_token("not-a-jwt") is None
