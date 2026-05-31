# Methodology — how the defaults were validated

> **Short version:** goodfaith's defaults were tuned and validated by running the
> engine in **shadow mode for about one month on a real ~1,200-member Discord
> community (~200 active members)**. Over that period it logged what it *would*
> have done on live traffic and produced **zero automatic punishments of
> established members**. This is *field validation*, not a benchmark score, and
> it is not a guarantee for your server — which is exactly why shadow mode is the
> default and the rollout tooling exists.

## What "shadow mode" means here

In `Mode.SHADOW` the engine evaluates every message and records a full
`Decision` — action, keys, reasons, the legitimate patterns that applied — but
**never acts**. `decision.enforced` is always `False`. This lets you measure the
engine against your actual community before giving it any power.

## What was actually done

- The predecessor of this engine ran in shadow mode on a live community of
  roughly **1,200 members, of whom about 200 were active** in a typical week.
- It observed normal traffic for **~1 month**: agreement pile-ons, emote/GIF
  walls, copypasta, neurodivergent info-dumping, rapid back-and-forth, links,
  and the occasional real spam/raid attempt.
- Across that window, the engine recorded **zero would-be automatic punishments
  of established/regular members.** The cases it escalated to *review* were
  genuine: external-invite advertising and coordinated cross-user duplication
  from fresh accounts.
- Those observations are what set the conservative defaults you see in
  [`config.py`](../goodfaith/config.py): high frequency thresholds, a generous
  agreement lexicon, substantial-content gating for near-dup, and the
  requirement of corroboration from independent families before any timeout.

## What this is — and is not

**It is** evidence that, on a real community of this size and culture, the design
did not manufacture false positives against the people it most wants to protect.

**It is not:**

- a labelled benchmark with published precision/recall numbers;
- a model trained on a dataset (there is no model and no training — the engine is
  deterministic rules over explicit signals);
- a promise that your community's norms match the one it was observed on.

We deliberately describe this as *field validation*, not "trained on N messages".
No message contents or personal data from that community are included in this
repository; only the resulting, generic thresholds are.

## Reproduce it on your own server

This is the recommended adoption path, and it is the same workflow used above:

1. Export a sample of your channels to JSONL — one message per line, e.g.:

   ```json
   {"guild_id": 1, "channel_id": 2, "user_id": 42, "msg_count": 3, "account_age_days": 0.5, "content": "same"}
   ```

   (Any field of [`Account`](../goodfaith/types.py) / [`Message`](../goodfaith/types.py)
   may be supplied; missing ones default to safe values.)

2. Replay it through the engine in shadow mode:

   ```sh
   goodfaith replay your_export.jsonl
   ```

3. Read the per-guild report. You want `would_punish` at or near `0` and every
   `would_touch` case to be one you agree with. Inspect individual verdicts in
   code with `decision.explain()`.

4. Only once the numbers look right, advance `Mode.SHADOW → CANARY → ENFORCE`,
   and keep `mark_false_positive()` wired up so any mistake is corrected once and
   never repeats.

The goal is not to trust these defaults blindly — it is to let you prove, on your
own traffic, that the engine is safe before it can touch anyone.
