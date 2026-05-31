"""The goodfaith decision engine: ``Message`` → ``Decision``.

Design objective: **strongly favor precision over recall.** A wrongful action
against a regular is treated as far more costly than letting a spam message
linger. This is an explicit, tunable bias — not a guarantee of zero false
positives, and it deliberately accepts a higher false-negative rate.

Rules:
  * Staff are immune. Trusted/established/vouched members are never *punished*,
    but they are NOT a blanket bypass: a trusted account showing strongly
    corroborated danger (e.g. a compromised account or an abused vouch) is sent
    to human review (HOLD), not waved through.
  * Legitimate behavior (agreement, emote-only, media, emphasis, formatting,
    high frequency) never triggers anything on its own. Short content never
    enters the near-dup index, which shields pile-ons in any language.
  * A punitive (reversible, appealable timeout) action requires ``keys_for_punitive``
    HIGH keys from *independent detector families* AND a non-trusted author.
    Crucially, a single-vector mass raid self-corroborates: when many distinct
    low-trust accounts trip the same signal in a short window, that burst is an
    independent family of its own. One isolated key → HOLD/QUARANTINE for review.

The engine holds no discord.py dependency and stores no personal data: only
integer IDs, SimHash fingerprints, and per-guild counters.

Concurrency: the engine mutates in-memory state without locking. It assumes a
single event loop (the discord.py model — ``on_message`` handlers do not run in
parallel). Do not share one Engine across OS threads; give each thread/process
its own, or add your own lock. Curated state survives restarts via
``export_state``/``load_state``; the sliding windows are intentionally ephemeral.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field

from . import behavior, reputation, signals
from .policy import Policy
from .text import near, simhash
from .types import Account, Action, Decision, Message, Mode, Signal
from .windows import WindowState

# Signal families whose cross-user repetition indicates a raid (not benign
# coordination). Near-duplication is excluded: identical text across users is
# often legitimate copypasta, and is already its own (review-only) signal.
_BURST_FAMILIES = frozenset({"invite", "known_bad", "raid"})

# A false-positive correction only un-flags the SIMILARITY-derived families a
# benign message can trip by collision. It must NOT whitelist an attacker's live
# invite/raid/link (those are facts, not detection mistakes — and the SimHash
# fingerprint ignores URLs, so a text match would otherwise smuggle them through).
_KNOWN_GOOD_SUPPRESSES = frozenset({"neardup", "known_bad"})

# GC the sliding-window key space periodically (deques self-bound by time/size,
# but their dict keys are only reclaimed by prune()).
_PRUNE_INTERVAL = 1024

# created_at beyond this far into the future is not trusted (clock skew / spoof).
_CLOCK_SKEW_SECONDS = 60.0


@dataclass
class ReadinessReport:
    """Shadow-mode rollout telemetry for one guild.

    Encodes the recommended methodology: run in SHADOW, accumulate real traffic,
    and only flip to ENFORCE once the engine has seen enough messages with zero
    (or an acceptable rate of) would-be punishments.
    """

    guild_id: int
    seen: int
    would_touch: int
    would_punish: int
    would_review: int = 0

    @property
    def punish_rate(self) -> float:
        return self.would_punish / self.seen if self.seen else 0.0

    @property
    def touch_rate(self) -> float:
        return self.would_touch / self.seen if self.seen else 0.0

    @property
    def review_rate(self) -> float:
        """Share of messages that would land in the human-review queue.

        On a large, understaffed server a high review_rate is the warning that
        the HOLD/QUARANTINE queue will grow faster than mods can clear it —
        consider ``Policy(quarantine_unattended_holds=True)`` or tighter scoping."""
        return self.would_review / self.seen if self.seen else 0.0

    def ready(self, min_seen: int = 1000, max_punish_rate: float = 0.0) -> bool:
        return self.seen >= min_seen and self.punish_rate <= max_punish_rate


@dataclass
class _Stats:
    seen: int = 0
    would_touch: int = 0
    would_review: int = 0
    would_punish: int = 0
    by_action: Counter = field(default_factory=Counter)


class Engine:
    def __init__(self, policy: Policy | None = None) -> None:
        self.default_policy = policy or Policy()
        self._policies: dict[int, Policy] = {}
        self.windows = WindowState()
        self._bad: dict[int, list[tuple[float, int]]] = {}   # guild -> [(ts, simhash)]
        self._good: dict[int, list[int]] = {}                # guild -> [simhash] (FP feedback)
        # guild -> {user_id -> {"actor_id", "reason", "ts"}}  (auditable)
        self._vouched: dict[int, dict[int, dict]] = {}
        self._stats: dict[int, _Stats] = {}
        self._calls = 0

    # ── Configuration ────────────────────────────────────────────────────
    def set_policy(self, guild_id: int, policy: Policy) -> None:
        self._policies[guild_id] = policy

    def policy_for(self, guild_id: int) -> Policy:
        return self._policies.get(guild_id, self.default_policy)

    # ── Trust controls ───────────────────────────────────────────────────
    def vouch(
        self, guild_id: int, user_id: int,
        actor_id: int | None = None, reason: str = "", now: float | None = None,
    ) -> None:
        """Grant a member trust (a mod action). Recorded with who/why/when.

        A vouch is NOT a blanket bypass: a vouched account that later shows
        corroborated danger is still sent to review (see ``_decide``), which
        contains the damage from a careless or compromised moderator vouch.
        """
        self._vouched.setdefault(guild_id, {})[user_id] = {
            "actor_id": actor_id,
            "reason": reason,
            "ts": now if now is not None else time.time(),
        }

    def unvouch(self, guild_id: int, user_id: int) -> None:
        self._vouched.get(guild_id, {}).pop(user_id, None)

    def is_vouched(self, guild_id: int, user_id: int) -> bool:
        return user_id in self._vouched.get(guild_id, {})

    def list_vouches(self, guild_id: int) -> dict[int, dict]:
        """Return the auditable vouch ledger for a guild (user_id → metadata)."""
        return dict(self._vouched.get(guild_id, {}))

    # ── Curated banks ────────────────────────────────────────────────────
    def add_known_bad(self, guild_id: int, text: str, now: float | None = None) -> bool:
        """Add a curated bad fingerprint (mod-reviewed). Entries decay (TTL).

        Rejects non-substantial text: a low-entropy fingerprint would collide
        broadly and cause false positives — the opposite of this project's goal.
        """
        policy = self.policy_for(guild_id)
        if not behavior.is_substantial(text, policy):
            return False
        fp = simhash(text, policy.simhash_bits)
        if not fp:
            return False
        bank = self._bad.setdefault(guild_id, [])
        bank.append((now if now is not None else time.time(), fp))
        del bank[: max(0, len(bank) - policy.known_bad_max)]  # FIFO cap
        return True

    def mark_false_positive(self, guild_id: int, text: str) -> bool:
        """Record content the engine wrongly flagged so it can NEVER reoccur.

        The fingerprint is added to a per-guild known-good bank that suppresses
        the similarity-derived signals (near-dup / known-bad) on matching content
        — closing the loop so a corrected false positive never repeats. It does
        NOT whitelist a live invite/raid/link. Requires substantial content (a
        short, low-entropy entry would over-suppress real detections).
        """
        policy = self.policy_for(guild_id)
        if not behavior.is_substantial(text, policy):
            return False
        fp = simhash(text, policy.simhash_bits)
        if not fp:
            return False
        bank = self._good.setdefault(guild_id, [])
        bank.append(fp)
        del bank[: max(0, len(bank) - policy.known_good_max)]  # FIFO cap
        return True

    def _matches_known_bad(self, guild_id: int, fp: int, policy: Policy, now: float) -> bool:
        if not fp:
            return False
        entries = self._bad.get(guild_id)
        if not entries:
            return False
        ttl = policy.known_bad_ttl_seconds
        if ttl > 0:  # decay: drop stale entries in place
            entries[:] = [(ts, f) for ts, f in entries if now - ts <= ttl]
        return any(near(fp, f, policy.simhash_max_hamming) for _, f in entries)

    def _matches_known_good(self, guild_id: int, fp: int, policy: Policy) -> bool:
        if not fp:
            return False
        return any(near(fp, f, policy.simhash_max_hamming) for f in self._good.get(guild_id, ()))

    # ── Persistence ──────────────────────────────────────────────────────
    def export_state(self) -> dict:
        """JSON-serializable snapshot of CURATED state (survives restarts).

        Includes vouches and the known-bad/known-good banks — the operator's
        investment. Excludes the sliding windows and counters, which are
        intentionally ephemeral. Persist this and replay it with load_state()."""
        return {
            "vouched": {str(g): {str(u): v for u, v in users.items()}
                        for g, users in self._vouched.items()},
            "known_bad": {str(g): [[ts, fp] for ts, fp in e] for g, e in self._bad.items()},
            "known_good": {str(g): list(fps) for g, fps in self._good.items()},
        }

    def load_state(self, state: dict) -> None:
        """Restore a snapshot from export_state(), defensively.

        State may be read from disk/DB where it can be corrupted or tampered, so
        malformed entries are skipped (never raised on) and banks are size-capped.
        """
        if not isinstance(state, dict):
            return
        p = self.default_policy

        def _as_int(x):
            try:
                return int(x)
            except (TypeError, ValueError):
                return None

        vouched = state.get("vouched")
        if isinstance(vouched, dict):
            for g, users in vouched.items():
                gid = _as_int(g)
                if gid is None or not isinstance(users, dict):
                    continue
                clean = {uid: meta for u, meta in users.items()
                         if (uid := _as_int(u)) is not None and isinstance(meta, dict)}
                if clean:
                    self._vouched[gid] = clean

        known_bad = state.get("known_bad")
        if isinstance(known_bad, dict):
            for g, entries in known_bad.items():
                gid = _as_int(g)
                if gid is None or not isinstance(entries, list):
                    continue
                clean_b: list[tuple[float, int]] = []
                for e in entries:
                    if isinstance(e, (list, tuple)) and len(e) == 2 and _as_int(e[1]) is not None:
                        try:
                            clean_b.append((float(e[0]), int(e[1])))
                        except (TypeError, ValueError):
                            pass
                if clean_b:
                    self._bad[gid] = clean_b[-p.known_bad_max:]

        known_good = state.get("known_good")
        if isinstance(known_good, dict):
            for g, fps in known_good.items():
                gid = _as_int(g)
                if gid is None or not isinstance(fps, list):
                    continue
                clean_g = [v for f in fps if (v := _as_int(f)) is not None]
                if clean_g:
                    self._good[gid] = clean_g[-p.known_good_max:]

    # ── Telemetry ────────────────────────────────────────────────────────
    def readiness(self, guild_id: int) -> ReadinessReport:
        s = self._stats.get(guild_id, _Stats())
        return ReadinessReport(guild_id, s.seen, s.would_touch, s.would_punish, s.would_review)

    def _record(self, guild_id: int, decision: Decision) -> None:
        s = self._stats.setdefault(guild_id, _Stats())
        s.seen += 1
        s.by_action[decision.action.name] += 1
        if decision.touches_message:
            s.would_touch += 1
        if decision.action in (Action.QUARANTINE, Action.HOLD):
            s.would_review += 1
        if decision.punished:
            s.would_punish += 1

    # ── Evaluation ───────────────────────────────────────────────────────
    def evaluate(self, msg: Message) -> Decision:
        policy = self.policy_for(msg.guild_id)
        acc = msg.author
        now = msg.created_at or time.time()
        if now > time.time() + _CLOCK_SKEW_SECONDS:  # don't trust future timestamps
            now = time.time()
        self._calls += 1
        if self._calls % _PRUNE_INTERVAL == 0:  # reclaim idle window keys
            self.windows.prune(now, policy)

        if msg.channel_id in policy.channel_allowlist:
            return self._allow(msg, policy, "channel_allowlisted")

        if acc.is_staff:
            return self._allow(msg, policy, "staff_immune")

        fp = simhash(msg.content, policy.simhash_bits)
        known_good = self._matches_known_good(msg.guild_id, fp, policy)

        allow_patterns = behavior.legitimate_patterns(msg, policy)
        substantial = behavior.is_substantial(msg.content, policy)

        rapid = self.windows.record_and_count_rapid(msg.guild_id, acc.user_id, now, policy)
        distinct_users = 0
        if substantial:
            distinct_users = self.windows.record_and_count_neardup(
                msg.guild_id, acc.user_id, fp, now, policy)

        raw: list[Signal] = []
        for s in (
            signals.detect_external_invite(msg),
            signals.detect_unsafe_link(msg),
            signals.detect_mass_mention_raid(msg, acc, policy),
            signals.detect_known_bad(self._matches_known_bad(msg.guild_id, fp, policy, now)),
            signals.detect_coordinated_neardup(distinct_users, policy),
            signals.detect_rapid(rapid, policy),
        ):
            if s is not None:
                raw.append(s)

        if known_good:  # FP correction: drop only similarity-derived signals
            raw = [s for s in raw if s.family not in _KNOWN_GOOD_SUPPRESSES]
            allow_patterns = [*allow_patterns, "false_positive_feedback"]

        keys = signals.keys(raw)
        trusted = reputation.is_trusted(acc, policy) or self.is_vouched(msg.guild_id, acc.user_id)

        # Cross-user burst: if other low-trust accounts are tripping the same
        # high-precision CONTENT signal right now, that coordination corroborates
        # a single-vector mass raid (e.g. an invite flood). Restricted to
        # dangerous-content families on purpose — near-duplication is excluded so
        # a legitimate copypasta/quote-chain among regulars is never escalated
        # here. Only untrusted authors feed/trigger the burst, so a lone regular
        # sharing one invite is never escalated this way either.
        if keys and not trusted:
            burst = max(
                (self.windows.record_and_count_family_burst(
                    msg.guild_id, acc.user_id, k.family, now, policy)
                 for k in keys if k.family in _BURST_FAMILIES),
                default=0,
            )
            bsig = signals.detect_coordinated_burst(burst, policy)
            if bsig is not None:
                raw.append(bsig)
                keys = signals.keys(raw)

        reasons = [f"{s.name}:{s.detail}" for s in raw]
        decision = self._decide(acc, policy, keys, raw, reasons, allow_patterns, trusted)
        return self._finish(msg, policy, decision)

    def _decide(
        self, acc: Account, policy: Policy, keys, raw, reasons, allow_patterns, trusted
    ) -> Decision:
        families = {k.family for k in keys}
        known_bad = any(k.family == "known_bad" for k in keys)

        # No HIGH keys → allow (frequency/repetition/legitimate never punish).
        if not families:
            action = Action.OBSERVE if raw else Action.ALLOW
            return Decision(action, 0.1 if raw else 0.0, keys=[], reasons=reasons,
                            allowlisted=allow_patterns)

        # Trusted/established/vouched: never auto-*punished*, but not a blanket
        # bypass. Strongly corroborated danger from a trusted account most likely
        # means a compromised account or an abused vouch → hold for human review
        # (reversible, no penalty) rather than waving it through.
        if trusted:
            if len(families) >= policy.keys_for_punitive:
                return Decision(Action.HOLD, 0.7, keys=keys, reasons=reasons,
                                allowlisted=allow_patterns, reversible=True)
            action = Action.SOFT if known_bad else Action.OBSERVE
            return Decision(action, 0.4, keys=keys, reasons=reasons, allowlisted=allow_patterns)

        # Non-trusted + corroboration from independent families → punitive (reversible).
        if len(families) >= policy.keys_for_punitive:
            return Decision(Action.PUNITIVE, 0.9, keys=keys, reasons=reasons,
                            allowlisted=allow_patterns, reversible=True)

        # Non-trusted, exactly one family → human review, NEVER an automatic
        # punishment. New accounts are quarantined (reversible); older accounts
        # are held for review — unless the guild opts to quarantine unattended
        # holds so flagged content does not sit in a queue nobody is working.
        new = reputation.is_new_account(acc, policy)
        action = (Action.QUARANTINE if new or policy.quarantine_unattended_holds
                  else Action.HOLD)
        return Decision(action, 0.6, keys=keys, reasons=reasons,
                        allowlisted=allow_patterns, reversible=True)

    def _finish(self, msg: Message, policy: Policy, decision: Decision) -> Decision:
        decision.mode = policy.mode
        decision.enforced = self._enforced(decision.action, policy.mode)
        self._record(msg.guild_id, decision)
        return decision

    def _allow(self, msg: Message, policy: Policy, reason: str) -> Decision:
        return self._finish(msg, policy, Decision(Action.ALLOW, 0.0, reasons=[reason]))

    @staticmethod
    def _enforced(action: Action, mode: Mode) -> bool:
        if action <= Action.OBSERVE:
            return False
        if mode == Mode.ENFORCE:
            return True
        if mode == Mode.CANARY:  # act on reversible non-punitive; hold punitive back
            return action < Action.PUNITIVE
        return False  # SHADOW
