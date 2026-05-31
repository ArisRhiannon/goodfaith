# goodfaith

> A trust-first Discord automoderation engine that would rather miss a spammer than mute a regular. **Zero false positives by design.**

[![CI](https://github.com/ArisRhiannon/goodfaith/actions/workflows/ci.yml/badge.svg)](https://github.com/ArisRhiannon/goodfaith/actions/workflows/ci.yml)
[![License: AGPL-3.0 + Commercial](https://img.shields.io/badge/license-AGPL--3.0%20%2B%20Commercial-blue.svg)](LICENSE)

Most automods optimize for catching spam. In a tight-knit community that is the
wrong objective: a single wrongful mute of a long-time regular does more damage
to trust than ten spam messages that linger for a few extra seconds. **goodfaith
inverts the priority.** It is built so that the cost of a false positive is
treated as far higher than the cost of a false negative, and it makes that
trade-off explicit, tunable, and auditable.

The engine is **pure Python, has no runtime dependencies, holds no discord.py
dependency, and stores no personal data** — only opaque integer IDs and 64-bit
fingerprints. Drop it into any bot through a thin adapter (see
[`examples/discord_adapter.py`](examples/discord_adapter.py)).

> It is a clean-room, standalone rework of the private automod that runs on a
> real ~1,200-member community. See **[field validation](docs/METHODOLOGY.md)**.

## Why it (almost) never false-positives

Five independent guardrails, any one of which is usually enough to spare a regular:

1. **Trust is first-class.** Staff are immune; established members and anyone a
   moderator has `vouch()`ed are never punished — at most their message is
   soft-deleted, and only on a near-certain known-bad hit. Earned trust never
   decays: a member who goes quiet for months and returns is still a regular.
2. **Detection confidence is decoupled from action severity.** A signal firing
   does not imply a punishment. Verdicts climb a ladder
   (`ALLOW → OBSERVE → SOFT → QUARANTINE → HOLD → PUNITIVE`) and most stop early.
3. **Corroboration from independent sources.** A timeout requires multiple HIGH
   signals from *different detector families* (e.g. an external invite **and**
   coordinated cross-user duplication). One signal is only ever held for human
   review — never an automatic punishment.
4. **A legitimate-behavior allowlist** grounded in how real communities talk:
   agreement pile-ons (`same`, `this`, `W`, `fr`), emote/GIF walls, emphasis
   (`WWWW`), one-thought-per-message texting, and markdown. These suppress
   frequency/repetition signals so normal chatter never escalates.
5. **Reversible actions only.** The single punitive action is a temporary,
   appealable timeout; everything else is a delete that stays in your logs.

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
cross-user near-duplicate, and `@everyone` + link from a new account. Generic
links and high posting frequency are **informational only** and never punish.

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
    keys_for_punitive=2,                 # raise to demand more corroboration
    channel_allowlist=frozenset({123}),  # never moderate #memes
    extra_agreement_words=frozenset({"basé", "kekw"}),
))
```

Operational hooks: `engine.vouch(guild, user)` to grant instant trust,
`engine.add_known_bad(guild, text)` for a curated bad-content bank (entries
decay), and `engine.mark_false_positive(guild, text)` to guarantee a corrected
mistake can never repeat.

## Privacy

The engine never receives usernames, emails, or message history, and never
stores raw content — only integer IDs and 64-bit SimHash fingerprints. See
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

Source-available — **not** OSI open source. Free under the GNU **AGPL-3.0** for
individuals, non-profits, and organizations below **US$1M annual revenue and 50
employees**; larger organizations require a commercial license. See [LICENSE](LICENSE).

© 2026 Aris Rhiannon
