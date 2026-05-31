"""Per-guild policy — the tunable surface of the engine.

The original engine was configured by global environment variables only. A
single bot serves many guilds with very different cultures, so goodfaith makes
configuration a per-guild :class:`Policy`. Defaults come from
:mod:`goodfaith.config` (which reads the environment), so an operator can set a
sane global baseline and override only what a specific guild needs.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import config
from .types import Mode


@dataclass(frozen=True)
class Policy:
    """Immutable configuration for one guild (or the global default)."""

    mode: Mode = Mode.SHADOW  # safe default: observe, never act, until trusted

    # Corroboration
    keys_for_punitive: int = config.KEYS_FOR_PUNITIVE

    # Reputation tiers
    trusted_min_server_days: float = config.TRUSTED_MIN_SERVER_DAYS
    trusted_min_msgs: int = config.TRUSTED_MIN_MSGS
    established_min_server_days: float = config.ESTABLISHED_MIN_SERVER_DAYS
    established_min_msgs: int = config.ESTABLISHED_MIN_MSGS
    established_volume_msgs: int = config.ESTABLISHED_VOLUME_MSGS
    regular_min_server_days: float = config.REGULAR_MIN_SERVER_DAYS
    regular_min_msgs: int = config.REGULAR_MIN_MSGS
    new_account_days: float = config.NEW_ACCOUNT_DAYS

    # Near-duplicate coordination
    simhash_max_hamming: int = config.SIMHASH_MAX_HAMMING
    neardup_window_seconds: int = config.NEARDUP_WINDOW_SECONDS
    neardup_min_distinct_users: int = config.NEARDUP_MIN_DISTINCT_USERS
    neardup_min_tokens: int = config.NEARDUP_MIN_TOKENS
    neardup_index_max: int = config.NEARDUP_INDEX_MAX

    # Frequency (observe-only)
    rapid_window_seconds: int = config.RAPID_WINDOW_SECONDS
    rapid_count: int = config.RAPID_COUNT

    # Known-bad bank decay
    known_bad_ttl_seconds: int = config.KNOWN_BAD_TTL_SECONDS

    # Behavior allowlist
    emphasis_max_token_len: int = config.EMPHASIS_MAX_TOKEN_LEN
    short_message_tokens: int = config.SHORT_MESSAGE_TOKENS
    agreement_words: frozenset[str] = config.AGREEMENT_WORDS
    extra_agreement_words: frozenset[str] = frozenset()

    # Channels never moderated (announcements, memes, bot-spam, etc.)
    channel_allowlist: frozenset[int] = frozenset()

    def all_agreement_words(self) -> frozenset[str]:
        return self.agreement_words | self.extra_agreement_words
