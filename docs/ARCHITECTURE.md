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
| `text.py` | Normalization + 64-bit SimHash and Hamming distance for near-duplicate detection. |
| `behavior.py` | The legitimate-behavior allowlist. Decides which frequency/repetition signals to **suppress**. |
| `reputation.py` | Trust tiers (`trusted`/`established`/`regular`/`newcomer`) and the trust invariants. |
| `signals.py` | The danger detectors. Tags each signal with a `Tier` and a detector `family`. |
| `windows.py` | Bounded sliding-window state for cross-user near-dup and per-user frequency. |
| `engine.py` | Orchestration: trust gating, corroboration, the action ladder, rollout telemetry, and the curated banks. |
| `cli.py` | `goodfaith replay` — shadow-replay a JSONL log and print a readiness report. |

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

Let `families` = the set of distinct detector families among the HIGH keys.

| Condition | Verdict |
|-----------|---------|
| no keys, no signals | `ALLOW` |
| no keys, some LOW signals | `OBSERVE` |
| author trusted/established/vouched | `OBSERVE` (or `SOFT` if known-bad) — never punitive |
| `len(families) >= keys_for_punitive`, untrusted | `PUNITIVE` (reversible timeout) |
| exactly one family, untrusted, new account | `QUARANTINE` (reversible, for review) |
| exactly one family, untrusted, older account | `HOLD` (modqueue, no user penalty) |

The crucial property: **punitive action requires both a non-trusted author and
corroboration from independent families.** Either condition failing downgrades
the verdict to review-only.

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

Generic links (`unsafe_link`) and high posting frequency (`rapid_frequency`) are
`LOW`: informational, capped at `OBSERVE`, never a key. Real humans post links
and info-dump constantly.

## Memory & safety

All window state is bounded by both time and a hard size cap
(`neardup_index_max`), so a raid cannot grow memory without limit — the failure
mode of many naive automods. The curated known-bad bank decays by TTL so stale
entries cannot resurface as a surprise months later.

## Privacy

The engine only ever sees integer IDs and message text, and it persists only
64-bit SimHash integers (in the known-good/known-bad banks). It never stores
usernames, raw content, or message history. Reputation inputs (account age,
tenure, message count) are supplied by the adapter as plain numbers.
