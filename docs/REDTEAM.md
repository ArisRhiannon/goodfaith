# Red-team report

This is the honest, full disclosure behind the phrase "an internal red-team pass"
in the README. It is **internal** (the author, not a third party) and **adversarial
but not exhaustive** — read it as a record of what was probed, what was found, what
was fixed, and what is *known to remain broken*.

## Scope and method

- **What:** the pure engine (`goodfaith/`), not a live Discord deployment.
- **Who / how long:** single author; iterative, over the v0.5.x line.
- **Method:** adversarial probing across multiple independent dimensions
  (evasion, false-positive triggers, resource exhaustion, i18n, persistence,
  honesty/dead code), in the spirit of "rainbow teaming" — diversify the *axes*
  of attack rather than hammer one. **Every finding below is backed by a runnable
  proof-of-concept and a measured number, and each fix shipped with a regression
  test** (see `tests/test_redteam_v05.py`).
- **What this is NOT:** it is not a third-party audit, not a fuzzing campaign at
  scale, and not validation against real botnets. The evaluation corpus is
  synthetic (see "Limitations").

## Findings — round 1 (hardening, shipped in v0.5.0)

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| H1 | High | `mark_false_positive` forced an unconditional ALLOW *before* detectors ran, and the SimHash fingerprint ignores URLs — so appending an invite to a known-good text smuggled it through. | Fixed: FP-feedback now suppresses only the similarity families (`neardup`/`known_bad`), never a live invite/raid/link. |
| H2 | High | A bad `GF_SIMHASH_BITS` (`0`/negative) made `simhash` return 0, silently disabling **all** content detection. | Fixed: `Policy` validates numeric ranges and fails loud. |
| H3 | High | The sliding-window key space was never pruned → memory grew with every distinct user seen. | Fixed: periodic `prune()`; key count is now bounded (measured 3000 users → ~960 keys). |
| H4 | High | The known-bad/known-good banks were unbounded lists scanned on every message. | Fixed: FIFO caps (`known_bad_max`/`known_good_max`). |
| M4 | Med  | `load_state` trusted its input and crashed on a corrupt/tampered snapshot. | Fixed: validates types, skips malformed entries, caps sizes. |
| M6 | Med  | `created_at` was caller-supplied and trusted; a future timestamp could dodge the burst window. | Fixed: future timestamps clamped to wall clock. |

## Findings — round 2 (rainbow teaming, shipped in v0.5.1 / v0.5.2)

Threshold for the text probes: SimHash Hamming `<= 12` means *matched* (caught);
a larger distance means *evaded*. Baseline is a known-bad string.

| ID | Dimension | Probe | Measured | Status |
|----|-----------|-------|----------|--------|
| SC | corroboration | one user splits an invite then a known-bad hit across two messages | only QUARANTINE, never PUNITIVE | **Fixed (v0.5.1):** same-user cross-message families self-corroborate. |
| E4 | evasion | obfuscated invite `discord dot gg/x` | `external_invite=False` (dodged the HIGH key) | **Fixed (v0.5.2):** invite detection sees through dot-obfuscation. |
| E5 | i18n evasion | combining marks `fŕéé` | token `fŕéé` ≠ `free` | **Fixed (v0.5.2):** NFKD + drop combining marks (Hamming → 0). |
| E6 | evasion / dead code | 20 `@user` pings + link, no `@everyone` | OBSERVE (nothing); `mention_count` was a dead field | **Fixed (v0.5.2):** ping-raid detected; `mention_count` is now live. |
| D2 | resource | `simhash` on an 80k-token message | **1.66 s** (blocks the event loop) | **Fixed (v0.5.2):** content length cap → **0.05 s**. |
| — | honesty | a stray "Zero-FP design" claim in a docstring | n/a | **Fixed (v0.5.2):** removed. |
| D1 | resource | ReDoS on the scheme-less-domain regex | 0.003 s @ 8000 chars (linear) | **No issue** (verified, not vulnerable). |

## Open limitations (measured, deliberately not "fixed")

These are real and reproducible. They are not fixed because a fix would either
raise false positives — which this project treats as the cardinal sin — or require
a redesign out of scope for a point release.

| ID | Probe | Measured Hamming (≤12 = caught) | Why not fixed |
|----|-------|----------------------------------|---------------|
| E1 | letter-spacing `f r e e n i t r o` | 49–58 (evaded) | Collapsing single-char runs would flag legit initialisms ("I D K", "U S A"). |
| E2 | leetspeak `fr33 n1tr0` | 56 (evaded) | Digit→letter folding mangles legit tokens (`2024`, `v2`). |
| E3 | padding with 40 junk words | 39 (evaded) | SimHash is a whole-document fingerprint; robust matching needs shingling/n-grams — a redesign. |

Mitigating context: E1–E3 evade only the **text-similarity** families
(`neardup` / `known_bad`). The independent invite, link, raid, and burst
detectors still fire on the dangerous payload regardless of how the surrounding
text is obfuscated.

Two larger, structural limitations remain by design:

- **Trust vs a patient adversary.** An account farmed for weeks to bank trust, or
  a genuinely trusted account's *first* malicious invite, is not caught — the trust
  model is a liability here, only partially mitigated by anomaly-based suspension
  and cross-user burst detection. See the README threat model.
- **Synthetic evaluation.** The bundled corpus (`goodfaith eval --generated`,
  ~8,164 benign messages across varied scripts, lengths, and edge cases) is
  synthetic. 0 false positives on it is a strong *regression contract*, not proof
  of real-world efficacy. Run `goodfaith eval your_export.jsonl` on your own
  hand-labeled data for numbers that mean something on your server.

## Reproducing

```sh
pytest tests/test_redteam_v05.py   # every fix above, as a regression test
goodfaith eval --generated         # the scaled synthetic scorecard
```
