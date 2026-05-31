# Architecture

goodfaith is a small, pure-Python decision engine. It takes a normalized
`Message` and returns a `Decision`. It has no runtime dependencies, no
discord.py dependency, and no I/O — which is what makes it cheap to unit-test
and safe to trust.

## Modules

| Module | Responsibility |
|--------|----------------|
| `types.py` | The data model: `Action`, `Tier`, `Mode`, `Signal`, `Account`, `Message`, `Decision`. No logic beyond `Decision.explain()`. |
| `config.py` | Conservative defaults, overridable via `GF_*` environment variables. Houses the agreement-word lexicon. |
| `policy.py` | `Policy` — the per-guild tunable surface (mode, thresholds, allowlists). Immutable. |
| `text.py` | Normalization + configurable-width SimHash (**128-bit default**) and Hamming distance for near-duplicate detection. |
| `behavior.py` | The legitimate-behavior allowlist. Decides which frequency/repetition signals to **suppress**. The agreement lexicon is a replaceable, locale-specific default; short-message gating is the language-agnostic shield. |
| `reputation.py` | Trust tiers (`trusted`/`established`/`regular`/`newcomer`) and the trust invariants. Tier resists dormancy; the *engine* suspends immunity on anomaly. Established-by-volume also requires activity across distinct days (`active_days`) so trust can't be farmed in a burst. |
| `signals.py` | The danger detectors, including the cross-user **burst** detector. Tags each signal with a `Tier` and a detector `family`. |
| `windows.py` | Bounded sliding-window state for cross-user near-dup, per-user frequency, and per-family burst. |
| `engine.py` | Orchestration: trust gating (with anomaly-based suspension), corroboration across independent families, the action ladder, rollout telemetry, the auditable vouch ledger, the curated banks, and `export_state`/`load_state` persistence. |
| `extract.py` | Pure, tested link/invite classification for adapters (keeps the riskiest parsing out of untested per-bot code). |
| `eval.py` | Labeled-corpus evaluation harness: scorecard (FP rate, wrongful punishments, recall, precision, evasions), threshold sweep, and JSONL ingestion of real labeled data. |
| `cli.py` | `goodfaith replay` (shadow-replay a log) and `goodfaith eval` (score the corpus / a JSONL corpus / a sweep). |

## Data flow

```
Message ─▶ Engine.evaluate
   1. channel allowlist?         → ALLOW
   2. staff?                     → ALLOW (immune)
   3. known-good (FP feedback)?  → ALLOW
   4. behavior.legitimate_patterns + is_substantial   (suppress noise signals)
   5. windows: rapid count; cross-user near-dup (substantial content only)
   6. signals.*  → raw signals (each with a family)
   7. keys = HIGH signals
   8. _decide(trust, keys, families)  → Decision
   9. apply Mode → set `enforced`; record telemetry
```

## The decision rule

Let `families` = the set of distinct detector families among the HIGH keys. The
cross-user **burst** is one such family: it is added when many distinct low-trust
accounts trip the same dangerous-content signal in a short window.

| Condition | Verdict |
|-----------|---------|
| no keys, no signals | `ALLOW` |
| no keys, some LOW signals | `OBSERVE` |
| trusted/established/vouched, `len(families) >= keys_for_punitive` | `HOLD` — likely compromise / abused vouch → review (never auto-punished) |
| trusted/established/vouched, one family | `SOFT` if known-bad, else `OBSERVE` |
| `len(families) >= keys_for_punitive`, untrusted | `PUNITIVE` (reversible timeout) |
| exactly one family, untrusted, new account | `QUARANTINE` (reversible, for review) |
| exactly one family, untrusted, older account | `HOLD` (modqueue, no user penalty) |

The crucial property: **punitive action requires both a non-trusted author and
corroboration from independent families.** Trust removes the punitive option but
not scrutiny — corroborated danger from a trusted account is still held for review.

On large, understaffed servers the lone-key `HOLD` can pile up unworked.
`ReadinessReport.review_rate` surfaces how fast that queue would grow, and
`Policy(quarantine_unattended_holds=True)` converts those holds into reversible
quarantines so flagged content does not simply sit. This widens the action
surface deliberately — it is an opt-in trade for thin moderation.

## Why these signals are "high precision"

A signal is a `HIGH` key only if it is almost never produced by a legitimate
message:

- **external invite** — an invite to a *different* server.
- **known-bad match** — near-duplicate of mod-curated bad content (precision ≈ 1).
- **coordinated near-dup** — ≥N *distinct* accounts posting near-identical
  *substantial* text within a short window. Short and agreement messages are not
  "substantial", so pile-ons never qualify. URLs and custom emotes are stripped
  before hashing, so sharing the same GIF/link is not "coordination".
- **mass-mention raid** — `@everyone`/`@here` + a link from a new account.
- **cross-user burst** — ≥N distinct low-trust accounts tripping the *same*
  dangerous-content family (invite/known-bad/raid) within a short window. This is
  what makes a single-vector flood self-corroborating. Near-duplication is
  deliberately excluded from burst, so a legitimate copypasta chain is not escalated.

Generic links (`unsafe_link`) and high posting frequency (`rapid_frequency`) are
`LOW`: informational, capped at `OBSERVE`, never a key. Real humans post links
and info-dump constantly.

## Memory & safety

All window state is bounded by both time and a hard size cap (`neardup_index_max`,
`burst_index_max`), so a raid cannot grow memory without limit — the failure mode
of many naive automods. The curated known-bad bank decays by TTL so stale entries
cannot resurface as a surprise months later.

## Privacy

The engine only ever sees integer IDs and message text, and it persists only
SimHash integers (in the known-good/known-bad banks) plus vouch metadata
(actor/reason/timestamp you supply). It never stores usernames, raw content, or
message history. Reputation inputs (account age, tenure, message count) are
supplied by the adapter as plain numbers.
