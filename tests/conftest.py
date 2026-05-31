"""Shared test fixtures."""

from __future__ import annotations

import pytest

from goodfaith import Account, Message

_ACCOUNT_FIELDS = {
    "account_age_days", "server_age_days", "msg_count",
    "has_avatar", "is_staff", "reputation_override",
}

NOW = 1_000_000.0


@pytest.fixture
def now() -> float:
    return NOW


@pytest.fixture
def mk(now):
    """Factory: mk(user_id, content, **account_or_message_fields) -> Message.

    Newcomer defaults (new account, no tenure, no history) so tests must opt
    *into* trust explicitly — the strict case for a moderation engine.
    """

    def _mk(user_id: int, content: str = "", guild_id: int = 1,
            channel_id: int = 9, created_at: float | None = None, **fields) -> Message:
        acc_kw = {
            "account_age_days": 0.5,
            "server_age_days": 0.0,
            "msg_count": 0,
        }
        for key in list(fields):
            if key in _ACCOUNT_FIELDS:
                acc_kw[key] = fields.pop(key)
        message_id = fields.pop("message_id", user_id)
        return Message(
            guild_id=guild_id,
            channel_id=channel_id,
            message_id=message_id,
            author=Account(user_id=user_id, **acc_kw),
            content=content,
            created_at=now if created_at is None else created_at,
            **fields,
        )

    return _mk
