"""Reputation / trust tiers. Regulars and veterans are almost never punished.

Trust is first-class here: it can be granted instantly by a moderator
(:func:`goodfaith.engine.Engine.vouch`) via ``Account.reputation_override``.

Deliberate invariant: **earned trust does not decay from inactivity.** A member
who goes quiet for months and returns is still a regular — penalizing dormancy
would manufacture exactly the false positives this project exists to prevent.

This is not a blanket bypass, though. Trust here governs *reputation tier* only;
the engine separately suspends a trusted account's immunity when it shows
strongly corroborated danger (a likely compromised account or abused vouch),
routing it to human review instead of waving it through. The only thing that
expires automatically is the curated known-bad bank (config ``KNOWN_BAD_TTL_SECONDS``).
"""

from __future__ import annotations

from .policy import Policy
from .types import Account

# Highest → lowest confidence.
TRUSTED = "trusted"
ESTABLISHED = "established"
REGULAR = "regular"
NEWCOMER = "newcomer"


def tier(acc: Account, policy: Policy) -> str:
    if acc.reputation_override:
        return acc.reputation_override
    if (acc.server_age_days >= policy.trusted_min_server_days
            and acc.msg_count >= policy.trusted_min_msgs):
        return TRUSTED
    if (acc.server_age_days >= policy.established_min_server_days
            and acc.msg_count >= policy.established_min_msgs):
        return ESTABLISHED
    # Established-by-volume: lots of history + a non-new account ⇒ a real member,
    # even if their join date isn't recorded. Requiring a non-new account blocks
    # the patient spammer who opens an account and floods immediately.
    if (acc.msg_count >= policy.established_volume_msgs
            and acc.account_age_days >= policy.new_account_days):
        return ESTABLISHED
    if (acc.server_age_days >= policy.regular_min_server_days
            and acc.msg_count >= policy.regular_min_msgs):
        return REGULAR
    return NEWCOMER


def is_trusted(acc: Account, policy: Policy) -> bool:
    """Trusted/established members never receive punitive action (soft at most)."""
    return tier(acc, policy) in (TRUSTED, ESTABLISHED)


def is_new_account(acc: Account, policy: Policy) -> bool:
    """A new account RAISES scrutiny; it is never a punishment on its own."""
    return acc.account_age_days < policy.new_account_days
