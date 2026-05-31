# Integration

goodfaith is the *decision* layer. Your bot is the *adapter*: it translates
Discord objects into a `Message`, calls `engine.evaluate`, and — when
`decision.enforced` is true — carries out the (reversible) action.

A complete, runnable cog is in
[`examples/discord_adapter.py`](../examples/discord_adapter.py). This page
explains the moving parts.

## 1. Build a `Message` from a Discord message

The engine never parses Discord. The adapter is responsible for:

- **Reputation inputs** — `account_age_days` (derivable from the user snowflake),
  `server_age_days` (from `member.joined_at`), and `msg_count` (from your own
  database; it is the hardest-to-forge in-guild trust signal).
- **Staff detection** — set `is_staff=True` for anyone with `manage_messages`,
  `kick_members`, `ban_members`, or `administrator`. Staff are fully immune.
- **Link classification** — extract invite URLs, mark `external_invite` when the
  invite points at another guild, and put non-allowlisted links in
  `unsafe_links`. Keep your own domain allowlist; the engine treats any provided
  `unsafe_links` as already-classified.

## 2. Evaluate and act

```python
decision = engine.evaluate(message)
if not decision.enforced:
    log.info("goodfaith shadow: %s", decision.explain())
    return
if decision.touches_message:
    await discord_message.delete()           # reversible: it stays in your logs
if decision.action == Action.PUNITIVE:
    await member.timeout(timedelta(hours=1), reason=decision.explain()[:400])
```

Because `enforced` already accounts for the guild's `Mode`, the same adapter
code works in shadow, canary, and enforce — only behavior changes.

## 3. Wire up the operator controls

- `engine.set_policy(guild_id, Policy(mode=Mode.ENFORCE, ...))` per guild.
- `engine.vouch(guild_id, user_id)` from a `/vouch` command for instant trust.
- `engine.add_known_bad(guild_id, text)` from a `/reportspam` reply.
- `engine.mark_false_positive(guild_id, text)` from your appeal flow, so a
  corrected mistake can never recur.

## 4. Persisting state (optional)

The engine keeps trust banks and counters in memory. For a long-running bot you
will usually:

- rebuild `msg_count` from your database on each evaluation (the example does
  this), and
- persist vouches and the known-bad/known-good banks yourself, replaying them
  into a fresh `Engine` on startup.

The sliding windows are intentionally ephemeral — they only matter within a
30-second coordination window.

## Environment

Defaults can be set globally with `GF_*` variables (see
[`config.py`](../goodfaith/config.py)), then overridden per guild via `Policy`.
Start every guild in `Mode.SHADOW` and graduate using `engine.readiness(...)`.
