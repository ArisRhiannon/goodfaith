"""Core data model for goodfaith — pure, discord-free, and free of personal data.

The engine only ever sees opaque integer IDs and a message's text. It never
needs usernames, emails, or any other PII, and it never persists raw message
content (only fixed-width SimHash fingerprints). See ``docs/ARCHITECTURE.md``.

Design philosophy: **strongly favor precision over recall.** A wrongful action
against a regular is treated as far more costly than missing a spammer — an
explicit, tunable bias, not a guarantee of zero false positives. Detection
*confidence* is deliberately decoupled from action *severity* (a "defer band"),
and no punitive action is taken without corroboration from independent signals.
"""

from __future__ import annotations

import enum
from collections.abc import Sequence
from dataclasses import dataclass, field


class Action(enum.IntEnum):
    """Response ladder, from least to most disruptive. Only PUNITIVE is a punishment."""

    ALLOW = 0       # do nothing
    OBSERVE = 1     # count/log only, never touch the message
    SOFT = 2        # delete the triggering message (reversible: content stays in logs)
    QUARANTINE = 3  # reversible quarantine role (revokes send) + send to modqueue
    HOLD = 4        # hold for human review (modqueue) — does NOT punish the user
    PUNITIVE = 5    # temporary, reversible, appealable timeout


class Tier(enum.IntEnum):
    """Precision of a signal. HIGH ≈ almost never legitimate (precision ≈ 1)."""

    LOW = 1   # never justifies action on its own
    MED = 2   # at most soft/observe on its own; never punitive
    HIGH = 3  # a valid "key" for the corroboration rule


class Mode(str, enum.Enum):
    """Per-guild enforcement mode. SHADOW is the safe default (log-only)."""

    SHADOW = "shadow"    # decide + record, never act (build trust first)
    CANARY = "canary"    # enforce reversible non-punitive actions, hold punitive in shadow
    ENFORCE = "enforce"  # enforce the full ladder


@dataclass(frozen=True)
class Signal:
    """A danger signal detected in a message/context.

    ``family`` groups signals that share a detection source so the engine can
    require corroboration from *independent* families before punishing.
    """

    name: str
    tier: Tier
    family: str
    detail: str = ""

    def is_key(self) -> bool:
        return self.tier == Tier.HIGH


@dataclass
class Account:
    """Author state, independent of discord.py. Integer IDs only — no PII."""

    user_id: int
    account_age_days: float = 999.0   # age of the Discord account
    server_age_days: float = 999.0    # tenure in this guild
    msg_count: int = 0                # historical messages in this guild
    active_days: int = 0              # distinct days the member has posted (anti-farm)
    has_avatar: bool = True
    is_staff: bool = False            # mod/admin/owner → fully immune
    reputation_override: str | None = None  # force a tier (tests/config/vouch)


@dataclass
class Message:
    """A normalized message for the engine. No discord.py objects."""

    guild_id: int
    channel_id: int
    message_id: int
    author: Account
    content: str = ""
    created_at: float = 0.0           # epoch seconds (time.time)
    mention_count: int = 0
    mentions_everyone: bool = False
    has_attachments: bool = False
    sticker_count: int = 0
    # URLs are extracted/classified by the adapter; the core never parses Discord:
    invite_urls: Sequence[str] = field(default_factory=tuple)   # invites to ANY server
    external_invite: bool = False     # an invite to a DIFFERENT server (not this one)
    unsafe_links: Sequence[str] = field(default_factory=tuple)  # links not on the allowlist
    is_reply: bool = False


@dataclass
class Decision:
    """The engine's verdict for one message."""

    action: Action
    confidence: float                                      # 0..1, informative only
    keys: list[Signal] = field(default_factory=list)       # HIGH signals that counted
    reasons: list[str] = field(default_factory=list)
    allowlisted: list[str] = field(default_factory=list)   # legitimate patterns that applied
    reversible: bool = True                                # punitive is always a temp timeout
    mode: Mode = Mode.SHADOW
    enforced: bool = False                                 # did this mode actually act?

    @property
    def punished(self) -> bool:
        return self.action >= Action.PUNITIVE

    @property
    def touches_message(self) -> bool:
        return self.action >= Action.SOFT

    def explain(self) -> str:
        """One-line, human-readable rationale for audit logs and appeals."""
        keys = ",".join(k.name for k in self.keys) or "none"
        allow = ",".join(self.allowlisted) or "none"
        if self.action <= Action.OBSERVE:
            state = "no-op"
        elif self.enforced:
            state = "ENFORCED"
        else:
            state = f"shadow({self.mode.value})"
        why = "; ".join(self.reasons) or "no signals"
        return (
            f"{self.action.name} [{state}] conf={self.confidence:.2f} "
            f"keys=[{keys}] allow=[{allow}] :: {why}"
        )
