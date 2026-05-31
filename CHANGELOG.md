# Changelog

All notable changes to this project are documented here, following
[Keep a Changelog](https://keepachangelog.com/) and [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-05-31

Hardening release in response to a technical critique. Sharpens both the honesty
of the claims and the robustness of the engine.

### Changed
- **Honest framing.** Dropped the "zero false positives" claim throughout. The
  design is now described accurately as precision-biased — an explicit, tunable
  trade-off that accepts more false negatives — not a guarantee. README gains an
  explicit **Threat model & non-goals** section; METHODOLOGY scopes the field
  validation and states what it does not cover.
- **128-bit SimHash by default** (was 64-bit; configurable via `simhash_bits` /
  `GF_SIMHASH_BITS`), reducing accidental near-collisions at chat scale.
- **Trust is no longer a blanket bypass.** A trusted/established/vouched account
  showing corroborated danger from independent families is routed to `HOLD`
  (human review) instead of being waved through — an account-takeover and
  abused-vouch guard. Earned trust still does not decay from inactivity.

### Added
- **Cross-user burst corroboration.** When many distinct low-trust accounts trip
  the same dangerous-content signal (invite/known-bad/raid) within a short
  window, that burst is an independent corroborating family — so a single-vector
  mass raid (e.g. an invite flood with no `@everyone`) escalates even with mods
  offline. Near-duplication is excluded from burst so copypasta is not escalated.
- **Auditable vouches.** `vouch(guild, user, actor_id=, reason=, now=)` records
  who/why/when; `list_vouches(guild)` returns the ledger.
- **Replaceable agreement lexicon.** `Policy(agreement_words=...)` replaces the
  English-internet default wholesale (or `frozenset()` to rely purely on the
  language-agnostic structural gates); documented as locale-specific.

[Unreleased]: https://github.com/ArisRhiannon/goodfaith/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/ArisRhiannon/goodfaith/compare/v0.1.0...v0.2.0

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

[0.1.0]: https://github.com/ArisRhiannon/goodfaith/releases/tag/v0.1.0
