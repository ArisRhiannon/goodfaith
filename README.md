# goodfaith

> A trust-first Discord automod for tight-knit communities. It treats muting a regular as far worse than missing a spammer — and makes that trade-off **explicit, tunable, and auditable**.

[![CI](https://github.com/ArisRhiannon/goodfaith/actions/workflows/ci.yml/badge.svg)](https://github.com/ArisRhiannon/goodfaith/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Most automods optimize for catching spam. In a tight-knit community that is the
wrong objective: a single wrongful mute of a long-time regular does more damage
to trust than ten spam messages that linger for a few extra seconds. **goodfaith
inverts the priority** — it is built to favor precision over recall, treating a
false positive as far costlier than a false negative.

To be clear about what that is and is not: this is a deliberate, configurable
**bias**, not a guarantee. "Zero false positives" is not a property any real
classifier can promise, and the flip side of this design is that it will
knowingly let some spam through (a higher false-negative rate) to protect your
regulars. See the [threat model & non-goals](#threat-model--non-goals).

The engine is **pure Python, has no runtime dependencies, holds no discord.py
dependency, and stores no personal data** — only opaque integer IDs and SimHash
fingerprints. Drop it into any bot through a thin adapter (see
[`examples/discord_adapter.py`](examples/discord_adapter.py)).

> It is a clean-room, standalone rework of the private automod that runs on a
> real ~1,200-member community. See **[field validation](docs/METHODOLOGY.md)**
> — including, honestly, what that validation does *not* cover.

## Why it (almost) never false-positives

Five independent guardrails, any one of which is usually enough to spare a regular:

1. **Trust is first-class — but not a blanket bypass.** Staff are immune;
   established members and anyone a moderator has `vouch()`ed are never
   *auto-punished*. Earned trust does not decay from inactivity (a returning
   regular is still a regular). The exception is deliberate: a trusted account
   showing strongly corroborated danger — the signature of a compromised account
   or an abused vouch — is routed to human review (`HOLD`), not waved through.
   Vouches are recorded with who/why/when so the trust graph is auditable.
2. **Detection confidence is decoupled from action severity.** A signal firing
   does not imply a punishment. Verdicts climb a ladder
   (`ALLOW → OBSERVE → SOFT → QUARANTINE → HOLD → PUNITIVE`) and most stop early.
3. **Corroboration from independent sources.** A timeout requires multiple HIGH
   signals from *different detector families* (e.g. an external invite **and**
   coordinated cross-user duplication). One signal is only ever held for human
   review — never an automatic punishment.
3. **Corroboration from independent sources.** A timeout requires multiple HIGH
   signals from *different detector families* (e.g. an external invite **and**
   coordinated cross-user duplication). One isolated signal is only ever held
   for human review — never an automatic punishment. A single-vector mass raid
   still escalates, because *many distinct fresh accounts tripping the same
   signal at once* is itself an independent corroborating family (the cross-user
   **burst** detector) — so an invite flood is caught even with mods offline,
   while a lone user sharing one invite is not.
4. **A replaceable legitimate-behavior allowlist** grounded in how real
   communities talk: agreement pile-ons (`same`, `this`, `W`, `fr`), emote/GIF
   walls, emphasis (`WWWW`), one-thought-per-message texting, and markdown. The
   word list is an English-internet default you can replace per locale; the
   primary shield is *structural and language-agnostic* — short messages never
   enter the duplicate index, so pile-ons in any language are safe.
5. **Reversible actions only.** The single punitive action is a temporary,
   appealable timeout; everything else is a delete that stays in your logs.
   (Reversibility limits damage; it does not erase the experience of a wrongful
   action — which is exactly why the bias and the shadow-first rollout exist.)

Everything punitive demands a *non-trusted* author **and** corroboration, so the
people most likely to be wrongly hit — your regulars — are structurally protected.

## How a message is judged

```
            ┌─ staff / vouched / channel-allowlisted ─→ ALLOW
            │
 message ──▶┤─ legitimate pattern? ─→ suppress frequency/repetition signals
            │
            └─ assemble HIGH "keys" from independent families
                   0 keys              → ALLOW / OBSERVE
                   trusted member      → OBSERVE (SOFT only if known-bad)
                   1 key               → HOLD / QUARANTINE  (human review)
                   ≥2 keys, untrusted  → PUNITIVE (reversible timeout)
```

HIGH-precision keys: external invite, curated known-bad match, coordinated
cross-user near-duplicate, `@everyone` + link from a new account, and a
cross-user **burst** (many low-trust accounts tripping the same signal at once).
Generic links and high posting frequency are **informational only** and never punish.

## Install

```sh
pip install goodfaith            # core engine, zero dependencies
pip install "goodfaith[discord]" # + discord.py for the example adapter
```

## Quickstart

```python
from goodfaith import Engine, Policy, Mode, Account, Message

engine = Engine(Policy(mode=Mode.SHADOW))  # SHADOW is the safe default

msg = Message(
    guild_id=1, channel_id=2, message_id=3,
    author=Account(user_id=42, account_age_days=0.5, server_age_days=0.0, msg_count=0),
    content="free nitro, join my server discord.gg/x",
    external_invite=True, invite_urls=("discord.gg/x",),
    created_at=0.0,
)

decision = engine.evaluate(msg)
print(decision.action)      # Action.QUARANTINE  (one key → review, not a punishment)
print(decision.enforced)    # False              (SHADOW never acts)
print(decision.explain())   # human-readable rationale for your audit log
```

## Roll it out the safe way

goodfaith is designed to **earn** enforcement, not assume it:

1. **SHADOW** (default): the engine decides and records but never acts.
2. Let it observe real traffic, then check it would not have hurt anyone:

   ```python
   r = engine.readiness(guild_id)
   print(r.seen, r.would_touch, r.would_punish, r.punish_rate)
   if r.ready(min_seen=1000, max_punish_rate=0.0):
       ...  # safe to advance
   ```
3. **CANARY**: enforce only reversible, non-punitive actions; punitive verdicts
   stay in shadow.
4. **ENFORCE**: the full ladder, once you trust it.

You can replay an exported message log through this exact workflow:

```sh
goodfaith replay messages.jsonl          # human report
goodfaith replay messages.jsonl --json   # machine-readable
```

## Tuning (per guild)

Every threshold lives on an immutable [`Policy`](goodfaith/policy.py) (defaults
are conservative and also overridable via `GF_*` environment variables):

```python
engine.set_policy(guild_id, Policy(
    mode=Mode.ENFORCE,
    keys_for_punitive=2,                  # raise to demand more corroboration
    simhash_bits=128,                     # widen further if you wish
    channel_allowlist=frozenset({123}),   # never moderate #memes
    agreement_words=frozenset(),          # drop the English lexicon for a non-EN server
    extra_agreement_words=frozenset({"de acuerdo", "cierto"}),
))
```

Operational hooks: `engine.vouch(guild, user, actor_id=..., reason=...)` for an
auditable trust grant (`engine.list_vouches(guild)` returns the ledger),
`engine.add_known_bad(guild, text)` for a curated bad-content bank (entries
decay), and `engine.mark_false_positive(guild, text)` to guarantee a corrected
mistake can never repeat.

## Threat model & non-goals

Being honest about scope is part of the design.

**Built for:** small-to-mid, tight-knit communities (roughly hundreds to a few
thousand members) where trust is the scarce resource and moderators are not
watching 24/7. There, wrongly muting a regular is the expensive failure, and
goodfaith is tuned to avoid it.

**Explicitly *not* claimed:**

- **Not "zero false positives."** No data-driven classifier can guarantee that.
  This is a precision-biased system that *accepts more false negatives* (spam it
  lets through) to protect regulars. If your priority is maximal spam capture,
  this is the wrong tool.
- **Not validated against sophisticated, large-scale adversaries.** The field
  evidence comes from a ~1,200-member community. Botnets, 100k–1M-member servers,
  and burner accounts farmed for weeks to bank trust before turning malicious are
  a *different* threat class this has not been tested against. The trust model is
  in fact a liability there, partially mitigated — not solved — by the
  anomaly-based suspension and cross-user burst detection.
- **Not a replacement for human moderation.** `HOLD`/`QUARANTINE` exist precisely
  because the engine defers ambiguous cases to people. If nobody works the
  modqueue, those cases sit.
- **Not a silver bullet for raids.** The burst detector catches simple high-volume
  raids; a slow, low-and-distributed campaign can still stay under thresholds.

If you run a large or high-threat server, treat goodfaith as one precision-first
layer in a defense-in-depth setup, run it in shadow first, and tune aggressively.

## Privacy

The engine never receives usernames, emails, or message history, and never
stores raw content — only integer IDs and SimHash fingerprints. See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — modules, data flow, decision rules.
- [Methodology](docs/METHODOLOGY.md) — how the defaults were field-validated, honestly.
- [Integration](docs/INTEGRATION.md) — wiring it into a discord.py bot.

## Development

```sh
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest -q
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Please run `ruff check .` and `pytest`
before submitting, and add an entry to `CHANGELOG.md` under **Unreleased**.

## Support

No pressure — a star or a thoughtful issue means a lot. If goodfaith saved your
moderators from an awkward apology, an optional tip is welcome at
`0x4705fA2de020E2D7F7FE08f5dD4585710897f3E1` (ETH / any EVM chain).

## License

[MIT](LICENSE) © 2026 Aris Rhiannon — use it, fork it, self-host it, ship it.
