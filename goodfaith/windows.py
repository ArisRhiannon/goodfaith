"""Bounded sliding-window state (amortized O(1) memory).

* Near-dup index per guild: ``(ts, simhash, user_id)`` of SUBSTANTIAL messages,
  to detect "≥N distinct users posting near-identical text within T seconds".
* Per-user frequency (informative only → OBSERVE, never punitive).

Everything is bounded by time AND by a hard size cap. (The predecessor used an
unbounded deque, which could be OOM'd during a raid — fixed here by ``*_INDEX_MAX``.)
"""

from __future__ import annotations

import collections

from .policy import Policy
from .text import near


class WindowState:
    def __init__(self) -> None:
        # guild_id -> deque[(ts, simhash, user_id)]
        self._neardup: dict[int, collections.deque[tuple[float, int, int]]] = {}
        # (guild_id, user_id) -> deque[ts]
        self._freq: dict[tuple[int, int], collections.deque[float]] = {}

    def record_and_count_neardup(
        self, guild_id: int, user_id: int, fingerprint: int, now: float, policy: Policy
    ) -> int:
        """Record ``fingerprint`` and return how many DISTINCT users (≠ author)
        posted near-identical content within the window. 0 if fingerprint empty."""
        if not fingerprint:
            return 0
        dq = self._neardup.setdefault(guild_id, collections.deque())
        cutoff = now - policy.neardup_window_seconds

        while dq and dq[0][0] < cutoff:
            dq.popleft()
        while len(dq) >= policy.neardup_index_max:
            dq.popleft()

        distinct: set[int] = set()
        for ts, fp, uid in dq:
            if ts < cutoff or uid == user_id:
                continue
            if near(fingerprint, fp, policy.simhash_max_hamming):
                distinct.add(uid)

        dq.append((now, fingerprint, user_id))
        return len(distinct)

    def record_and_count_rapid(
        self, guild_id: int, user_id: int, now: float, policy: Policy
    ) -> int:
        dq = self._freq.setdefault((guild_id, user_id), collections.deque(maxlen=128))
        dq.append(now)
        cutoff = now - policy.rapid_window_seconds
        while dq and dq[0] < cutoff:
            dq.popleft()
        return len(dq)

    def prune(self, now: float, policy: Policy) -> None:
        cutoff = now - policy.neardup_window_seconds
        for gid in list(self._neardup):
            dq = self._neardup[gid]
            while dq and dq[0][0] < cutoff:
                dq.popleft()
            if not dq:
                del self._neardup[gid]
        fcut = now - policy.rapid_window_seconds
        for key in list(self._freq):
            dq = self._freq[key]
            while dq and dq[0] < fcut:
                dq.popleft()
            if not dq:
                del self._freq[key]
