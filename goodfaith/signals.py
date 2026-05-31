"""Danger-signal detectors. Only high-precision ones are "keys".

Precision-first: a generic non-allowlisted link is NOT a key (real users post
links constantly). Only these are HIGH keys, each in its own detector *family*
so the engine can demand corroboration from independent sources:

  * ``invite``    — an invite to ANOTHER server (classic ad/raid spam)
  * ``known_bad`` — a hit against the curated known-bad bank (precision ≈ 1)
  * ``neardup``   — coordinated cross-user near-duplicate of substantial content
  * ``raid``      — @everyone/@here + link from a new account (raid pattern)
"""

from __future__ import annotations

from .policy import Policy
from .types import Account, Message, Signal, Tier


def detect_external_invite(msg: Message) -> Signal | None:
    if msg.external_invite:
        n = len(msg.invite_urls) or 1
        return Signal("external_invite", Tier.HIGH, "invite", f"{n} invite(s) to another server")
    return None


def detect_unsafe_link(msg: Message) -> Signal | None:
    # Generic non-allowlist link: informative only, NEVER a key on its own (0-FP).
    if msg.unsafe_links:
        return Signal(
            "unsafe_link", Tier.LOW, "link", f"{len(msg.unsafe_links)} non-allowlist link(s)"
        )
    return None


def detect_mass_mention_raid(msg: Message, acc: Account, policy: Policy) -> Signal | None:
    new = acc.account_age_days < policy.new_account_days
    mass = msg.mentions_everyone or msg.mention_count >= policy.mass_mention_min
    if mass and (msg.unsafe_links or msg.external_invite) and new:
        return Signal(
            "mass_mention_raid", Tier.HIGH, "raid",
            "mass mention + link/invite from a new account",
        )
    return None


def detect_known_bad(matched: bool) -> Signal | None:
    if matched:
        return Signal("known_bad_match", Tier.HIGH, "known_bad", "match in curated known-bad bank")
    return None


def detect_coordinated_neardup(distinct_users: int, policy: Policy) -> Signal | None:
    if distinct_users >= policy.neardup_min_distinct_users:
        return Signal(
            "coordinated_neardup", Tier.HIGH, "neardup",
            f"{distinct_users} distinct accounts posting near-identical content",
        )
    return None


def detect_coordinated_burst(distinct_users: int, policy: Policy) -> Signal | None:
    """Many distinct low-trust accounts tripping the SAME high-precision signal in
    a short window. Independent of *which* signal, so it corroborates single-vector
    mass raids (e.g. invite floods) that would otherwise be one lonely key."""
    if distinct_users >= policy.burst_min_distinct_users:
        return Signal(
            "coordinated_burst", Tier.HIGH, "burst",
            f"{distinct_users} other accounts tripped the same signal in a short window",
        )
    return None


def detect_rapid(count: int, policy: Policy) -> Signal | None:
    # High frequency: real humans (info-dumpers, the terminally online) do this.
    # Informative only (LOW) → at most OBSERVE, never a punishment.
    if count >= policy.rapid_count:
        return Signal("rapid_frequency", Tier.LOW, "frequency", f"{count} msgs in a short window")
    return None


def keys(signals: list[Signal]) -> list[Signal]:
    return [s for s in signals if s.is_key()]
