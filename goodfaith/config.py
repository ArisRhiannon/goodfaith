"""Default thresholds for goodfaith, overridable by environment (``GF_*``).

Every default is deliberately conservative — biased toward zero false positives:
short windows, high counts, generous allowlists. A deployment tunes these per
guild through :class:`goodfaith.policy.Policy` rather than editing code.
"""

from __future__ import annotations

import os


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# ── Reputation tiers ──────────────────────────────────────────────────────────
TRUSTED_MIN_SERVER_DAYS = _float("GF_TRUSTED_DAYS", 30.0)
TRUSTED_MIN_MSGS = _int("GF_TRUSTED_MSGS", 100)
ESTABLISHED_MIN_SERVER_DAYS = _float("GF_ESTAB_DAYS", 7.0)
ESTABLISHED_MIN_MSGS = _int("GF_ESTAB_MSGS", 20)
REGULAR_MIN_SERVER_DAYS = _float("GF_REGULAR_DAYS", 1.0)
REGULAR_MIN_MSGS = _int("GF_REGULAR_MSGS", 5)

# Established-by-volume: many historical messages + a non-new account ⇒ clearly a
# real member, even when their join date isn't recorded. msg_count is the hardest
# in-guild reputation signal to forge; requiring a non-new account blocks the
# patient spammer who opens an account and posts 100 times immediately.
ESTABLISHED_VOLUME_MSGS = _int("GF_ESTAB_VOLUME_MSGS", 100)

# ...and require activity spread across several DISTINCT days, so a burner farmed
# by dumping messages in one or two sittings cannot buy the volume shortcut.
# Adapters that don't supply ``active_days`` simply forgo this shortcut (safer).
VOLUME_MIN_ACTIVE_DAYS = _int("GF_VOLUME_MIN_ACTIVE_DAYS", 3)

# A "new" account is a RISK signal (raises scrutiny), never a punishment by itself.
NEW_ACCOUNT_DAYS = _float("GF_NEW_ACCOUNT_DAYS", 7.0)

# ── Near-duplicate cross-user coordination ───────────────────────────────────
SIMHASH_BITS = _int("GF_SIMHASH_BITS", 128)               # 128-bit resists chat-scale collisions
SIMHASH_MAX_HAMMING = _int("GF_SIMHASH_HAMMING", 12)      # ≈ same ratio as 6/64, at 128 bits
NEARDUP_WINDOW_SECONDS = _int("GF_NEARDUP_WINDOW", 30)
NEARDUP_MIN_DISTINCT_USERS = _int("GF_NEARDUP_USERS", 3)   # ≥3 distinct accounts
NEARDUP_MIN_TOKENS = _int("GF_NEARDUP_MIN_TOKENS", 5)      # only SUBSTANTIAL content
NEARDUP_INDEX_MAX = _int("GF_NEARDUP_INDEX_MAX", 512)      # bounded memory (anti-OOM)

# ── Cross-user burst (single-vector mass raids) ──────────────────────────────
# When many distinct low-trust accounts trip the SAME high-precision signal in a
# short window, that coordination is itself an independent corroborating signal —
# so a mass invite-spam raid (one vector, no @everyone, not yet known-bad) can be
# acted on even with mods offline, while a lone user sharing one invite cannot.
BURST_WINDOW_SECONDS = _int("GF_BURST_WINDOW", 30)
BURST_MIN_DISTINCT_USERS = _int("GF_BURST_USERS", 3)
BURST_INDEX_MAX = _int("GF_BURST_INDEX_MAX", 512)

# ── Frequency (NEVER punitive — only OBSERVE; real humans spam) ───────────────
RAPID_WINDOW_SECONDS = _int("GF_RAPID_WINDOW", 7)
RAPID_COUNT = _int("GF_RAPID_COUNT", 10)                   # intentionally high

# ── Corroboration ─────────────────────────────────────────────────────────────
# Punitive action requires this many HIGH keys from DISTINCT detector families.
KEYS_FOR_PUNITIVE = _int("GF_KEYS_PUNITIVE", 2)

# ── Known-bad bank decay ──────────────────────────────────────────────────────
# Curated bad fingerprints expire after this TTL so stale entries can't cause a
# surprise hit months later. 0 disables expiry. This is the ONLY thing that decays;
# a member's earned trust never does (a returning regular is still a regular).
KNOWN_BAD_TTL_SECONDS = _int("GF_KNOWN_BAD_TTL", 90 * 86400)

# Hard FIFO caps on the curated banks — bound memory AND the per-message O(N)
# scan even if an operator keeps adding entries (or a buggy caller floods them).
KNOWN_BAD_MAX = _int("GF_KNOWN_BAD_MAX", 10_000)
KNOWN_GOOD_MAX = _int("GF_KNOWN_GOOD_MAX", 10_000)

# ── Behavior allowlist tuning ─────────────────────────────────────────────────
EMPHASIS_MAX_TOKEN_LEN = _int("GF_EMPHASIS_TOKEN_LEN", 6)
SHORT_MESSAGE_TOKENS = _int("GF_SHORT_TOKENS", 4)

# Cross-user agreement pile-ons ("same", "this", "W", "fr"…) — the #1 near-dup
# false-positive trap. Many distinct users posting the same short word of
# agreement is community behavior, not coordinated spam.
#
# IMPORTANT: this default list is English-internet-centric and therefore
# PAROCHIAL. It is meant to be replaced per community via
# ``Policy(agreement_words=...)`` (or extended via ``extra_agreement_words``).
# It is NOT the primary defense: pile-ons in *any* language are already shielded
# structurally because short messages are excluded from near-dup (see
# ``NEARDUP_MIN_TOKENS`` / ``SHORT_MESSAGE_TOKENS``). The lexicon only adds an
# explicit "agreement_pileon" label for transparency.
AGREEMENT_WORDS = frozenset({
    "same", "this", "real", "fr", "frfr", "w", "ww", "l", "ll", "based",
    "lol", "lmao", "lmaooo", "true", "facts", "fax", "+1", "yes", "no", "yep",
    "nah", "ok", "okay", "agreed", "exactly", "mood", "felt", "valid", "bet",
    "gg", "f", "rip", "oof", "sheesh", "deadass", "ong", "icl", "ya", "yeah",
    "yup", "nope", "si", "sí", "dale", "obvio", "verdad", "x", "xd", "jaja",
    "jajaja", "kek", "kekw", "pog", "pogchamp", "real shit", "this this",
})
