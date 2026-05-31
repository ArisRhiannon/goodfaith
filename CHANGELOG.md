# Changelog

All notable changes to this project are documented here, following
[Keep a Changelog](https://keepachangelog.com/) and [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-05-31

First public release: a standalone, dependency-free rework of a private
Discord automod, rebuilt around an explicit zero-false-positive objective.

### Added
- Pure-Python decision engine (`Engine.evaluate`) with no discord.py dependency
  and no personal-data storage (integer IDs and 64-bit SimHash fingerprints only).
- Action ladder `ALLOW → OBSERVE → SOFT → QUARANTINE → HOLD → PUNITIVE`, with
  detection confidence decoupled from action severity.
- Corroboration rule: punitive action requires HIGH keys from **independent
  detector families** and a non-trusted author; a single key is held for review.
- Reputation tiers with staff immunity, established-by-volume, instant
  moderator `vouch()`, and the invariant that earned trust never decays.
- Legitimate-behavior allowlist (agreement pile-ons, emote walls, media-only,
  emphasis, markdown) that shields normal chatter from frequency/repetition.
- 64-bit SimHash near-duplicate detection that ignores shared URLs/emotes.
- Bounded sliding-window state (memory-safe under raids).
- Per-guild `Policy` (defaults overridable via `GF_*` env vars) and three modes:
  `SHADOW` (default), `CANARY`, `ENFORCE`.
- Rollout telemetry: per-guild `ReadinessReport` (`seen` / `would_touch` /
  `would_punish` / `punish_rate` / `ready()`).
- False-positive feedback loop (`mark_false_positive`) and a TTL-decaying
  curated known-bad bank.
- `Decision.explain()` for auditable, appealable verdicts.
- `goodfaith replay` CLI for shadow-replaying a JSONL message log.
- Example discord.py adapter cog and documentation
  (architecture, methodology, integration).

[Unreleased]: https://github.com/ArisRhiannon/goodfaith/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ArisRhiannon/goodfaith/releases/tag/v0.1.0
