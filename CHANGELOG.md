# Changelog

All notable changes to this project are documented here, following
[Keep a Changelog](https://keepachangelog.com/) and [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.4.0] - 2026-05-31

Evidence + durability pass: stop arguing efficacy, start measuring it.

### Added
- **Evaluation harness (`goodfaith.eval`, `goodfaith eval`).** A labeled,
  multilingual, adversarial scenario corpus (benign / abuse / evasion) and a
  scorer reporting the metrics that matter for a precision-biased system:
  false-positive rate, wrongful punishments, recall, precision, and — honestly —
  the evasions it misses by design. Ingests real hand-labeled exports via
  `eval.load_jsonl()`, and `eval.sweep()` turns a threshold into a
  precision/recall curve instead of a guess.
- **State persistence (`Engine.export_state()` / `load_state()`).** Vouches and
  the known-bad/known-good banks are JSON-serializable and survive restarts;
  sliding windows remain ephemeral by design.
- **`goodfaith.extract.classify()`** — a tested, pure link/invite classifier so
  adapters stop hand-rolling the riskiest parsing. Correctly treats your own
  server's invite as non-external (the bug the example adapter previously had).

### Changed
- Documented the single-event-loop concurrency assumption explicitly.
- Trimmed the framing to match measured reality (see the Evaluation section); the
  example adapter now uses `extract.classify`.

[Unreleased]: https://github.com/ArisRhiannon/goodfaith/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/ArisRhiannon/goodfaith/compare/v0.3.0...v0.4.0

## [0.3.0] - 2026-05-31

Second hardening pass plus a relicense, from continued review.

### Changed
- **Relicensed under the MIT License** (was AGPL-3.0 + commercial) to fit the
  self-hosted, permissively-licensed Discord-bot ecosystem.
- **Established-by-volume now requires activity across distinct days**
  (`Account.active_days` ≥ `volume_min_active_days`, default 3). A burner account
  that dumps messages in one or two sittings to bank trust no longer earns the
  volume shortcut. Adapters that don't supply `active_days` simply forgo the
  shortcut (the safe default).
- Honest reframing of the "no dependencies" value proposition (it is about
  deterministic offline testing, log replay, and chat-library portability — not a
  purity badge).

### Added
- **`Policy(quarantine_unattended_holds=True)`** — for thin moderation, converts a
  lone-key `HOLD` into a reversible `QUARANTINE` so flagged content does not sit
  in a queue nobody works (an opt-in widening of the action surface).
- **Review-queue telemetry**: `ReadinessReport.would_review` / `review_rate`
  (also in the `goodfaith replay` report) warn when the HOLD/QUARANTINE queue
  would outgrow available moderators.
- `.github/FUNDING.yml` so the repository's Sponsor button works once GitHub
  Sponsors enrollment is complete.

[Unreleased]: https://github.com/ArisRhiannon/goodfaith/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/ArisRhiannon/goodfaith/compare/v0.2.0...v0.3.0

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
