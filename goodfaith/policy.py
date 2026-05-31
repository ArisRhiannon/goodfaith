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
    volume_min_active_days: int = config.VOLUME_MIN_ACTIVE_DAYS
    regular_min_server_days: float = config.REGULAR_MIN_SERVER_DAYS
    regular_min_msgs: int = config.REGULAR_MIN_MSGS
    new_account_days: float = config.NEW_ACCOUNT_DAYS

    # Understaffed servers: convert a lone-key HOLD into a reversible QUARANTINE
    # so flagged content does not sit unattended in a queue nobody works. Off by
    # default (it widens the action surface; the trade is yours to make).
    quarantine_unattended_holds: bool = False

    # Near-duplicate coordination
    simhash_bits: int = config.SIMHASH_BITS
    simhash_max_hamming: int = config.SIMHASH_MAX_HAMMING
    neardup_window_seconds: int = config.NEARDUP_WINDOW_SECONDS
    neardup_min_distinct_users: int = config.NEARDUP_MIN_DISTINCT_USERS
    neardup_min_tokens: int = config.NEARDUP_MIN_TOKENS
    neardup_index_max: int = config.NEARDUP_INDEX_MAX

    # Cross-user burst (single-vector mass raids)
    burst_window_seconds: int = config.BURST_WINDOW_SECONDS
    burst_min_distinct_users: int = config.BURST_MIN_DISTINCT_USERS
    burst_index_max: int = config.BURST_INDEX_MAX

    # Frequency (observe-only)
    rapid_window_seconds: int = config.RAPID_WINDOW_SECONDS
    rapid_count: int = config.RAPID_COUNT

    # Known-bad bank decay
    known_bad_ttl_seconds: int = config.KNOWN_BAD_TTL_SECONDS
    known_bad_max: int = config.KNOWN_BAD_MAX
    known_good_max: int = config.KNOWN_GOOD_MAX

    # Behavior allowlist
    emphasis_max_token_len: int = config.EMPHASIS_MAX_TOKEN_LEN
    short_message_tokens: int = config.SHORT_MESSAGE_TOKENS
    mass_mention_min: int = config.MASS_MENTION_MIN
    # English-internet default; REPLACE wholesale per locale (e.g. frozenset() to
    # rely purely on the language-agnostic structural gates), or extend below.
    agreement_words: frozenset[str] = config.AGREEMENT_WORDS
    extra_agreement_words: frozenset[str] = frozenset()

    # Channels never moderated (announcements, memes, bot-spam, etc.)
    channel_allowlist: frozenset[int] = frozenset()

    def __post_init__(self) -> None:
        # Fail loud on misconfiguration (e.g. a bad GF_* env) instead of silently
        # disabling detection. blake2b's digest_size caps usable width at 512 bits.
        if not 8 <= self.simhash_bits <= 512:
            raise ValueError("simhash_bits must be in [8, 512]")
        if not 0 <= self.simhash_max_hamming <= self.simhash_bits:
            raise ValueError("simhash_max_hamming must be in [0, simhash_bits]")
        if self.keys_for_punitive < 1:
            raise ValueError("keys_for_punitive must be >= 1")
        if self.known_bad_max < 1 or self.known_good_max < 1:
            raise ValueError("known_bad_max/known_good_max must be >= 1")
        if self.mass_mention_min < 1:
            raise ValueError("mass_mention_min must be >= 1")

    def all_agreement_words(self) -> frozenset[str]:
        return self.agreement_words | self.extra_agreement_words
