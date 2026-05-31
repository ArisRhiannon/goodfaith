"""A fast, dependency-free evaluation harness for the engine.

Unit tests prove the code matches the rules; they do not show whether the rules
*moderate well*. This harness measures behavior over a **labeled** corpus and
reports the metrics that matter for a precision-biased system — above all, how
often it would wrongly act on benign traffic from real members.

Honesty notes:
  * The bundled corpus is SYNTHETIC, multilingual, and adversarial, and it
    deliberately includes evasions the design is known to miss. Synthetic numbers
    are only as good as the corpus.
  * The same scorer ingests real, hand-labeled exports via :func:`load_jsonl`,
    which is the intended bridge from "argued" to "measured" on your own server.
  * :func:`sweep` turns threshold choices (e.g. ``simhash_max_hamming``) into a
    precision/recall curve instead of a guess.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace

from .engine import Engine
from .policy import Policy
from .types import Account, Action, Message, Mode

# Reusable spammy payloads (substantial enough for near-dup).
_SPAM = "free nitro airdrop click this promo link now everyone join fast today"
_BAD = "buy cheap followers onlyfans promo link spam service best price"
_VET = {"age": 400.0, "sage": 120.0, "msgs": 3000, "active": 90}


@dataclass
class Scenario:
    """An ordered message stream with a ground-truth label.

    ``benign``  → no message should be acted on (any SOFT+ is a false positive).
    ``abuse``   → at least one message should be acted on (no action = a miss).
    ``evasion`` → abuse the design knowingly may miss; reported separately so the
                  holes are quantified, not hidden.
    """

    name: str
    kind: str
    messages: list[Message]
    known_bad: tuple[str, ...] = ()
    note: str = ""


@dataclass
class Scorecard:
    benign_scenarios: int = 0
    abuse_scenarios: int = 0
    evasion_scenarios: int = 0
    benign_messages: int = 0
    false_positives: int = 0       # benign messages acted on (SOFT+)
    wrongful_punishments: int = 0  # benign messages timed out — the cardinal sin
    benign_scenarios_acted: int = 0
    abuse_caught: int = 0
    evasion_caught: int = 0
    misses: list[str] = field(default_factory=list)

    @property
    def fp_rate(self) -> float:
        return self.false_positives / self.benign_messages if self.benign_messages else 0.0

    @property
    def recall(self) -> float:
        return self.abuse_caught / self.abuse_scenarios if self.abuse_scenarios else 0.0

    @property
    def precision(self) -> float:
        acted = self.abuse_caught + self.benign_scenarios_acted
        return self.abuse_caught / acted if acted else 1.0

    @property
    def evasion_recall(self) -> float:
        return self.evasion_caught / self.evasion_scenarios if self.evasion_scenarios else 0.0

    def as_dict(self) -> dict:
        return {
            "benign_scenarios": self.benign_scenarios,
            "abuse_scenarios": self.abuse_scenarios,
            "evasion_scenarios": self.evasion_scenarios,
            "benign_messages": self.benign_messages,
            "false_positives": self.false_positives,
            "fp_rate": round(self.fp_rate, 4),
            "wrongful_punishments": self.wrongful_punishments,
            "recall": round(self.recall, 4),
            "precision": round(self.precision, 4),
            "evasion_recall": round(self.evasion_recall, 4),
            "misses": self.misses,
        }

    def format_text(self) -> str:
        return "\n".join([
            "goodfaith evaluation scorecard",
            f"  benign scenarios   : {self.benign_scenarios} ({self.benign_messages} messages)",
            f"  FALSE POSITIVES    : {self.false_positives}  (rate {self.fp_rate:.4f})",
            f"  WRONGFUL PUNISH.   : {self.wrongful_punishments}   <- cardinal metric, target 0",
            f"  abuse recall       : {self.abuse_caught}/{self.abuse_scenarios} "
            f"({self.recall:.2f})",
            f"  precision          : {self.precision:.2f}",
            f"  known evasions hit : {self.evasion_caught}/{self.evasion_scenarios} "
            f"(by design, these are accepted misses)",
        ])


def _msg(uid: int, content: str = "", *, mid: int | None = None, age: float = 0.5,
         sage: float = 0.0, msgs: int = 0, active: int = 0, staff: bool = False,
         ev: bool = False, inv: tuple = (), unsafe: tuple = (), everyone: bool = False,
         at: float = 1000.0) -> Message:
    return Message(
        guild_id=1, channel_id=1, message_id=mid if mid is not None else uid,
        author=Account(uid, account_age_days=age, server_age_days=sage,
                       msg_count=msgs, active_days=active, is_staff=staff),
        content=content, created_at=at, external_invite=ev, invite_urls=inv,
        unsafe_links=unsafe, mentions_everyone=everyone,
    )


def corpus() -> list[Scenario]:
    """The bundled labeled corpus. Extend it, or replace it via load_jsonl()."""
    return [
        # ── benign: must never be acted on ──────────────────────────────
        Scenario("agreement_pileon_multilingual", "benign",
                 [_msg(1 + i, w) for i, w in enumerate(
                     ["same", "this", "W", "real", "真的", "同意", "echt", "oui"])],
                 note="8 newcomers, short agreement in several languages"),
        Scenario("emote_walls", "benign",
                 [_msg(10 + i, "<:pog:1><a:hype:2>🎉🎉") for i in range(5)]),
        Scenario("copypasta_by_veterans", "benign",
                 [_msg(20 + i, _SPAM, **_VET) for i in range(6)],
                 note="identical meme text, but from established members"),
        Scenario("rapid_infodump", "benign",
                 [_msg(30, f"lore thought number {i} about the finale", mid=300 + i)
                  for i in range(15)]),
        Scenario("multilingual_distinct", "benign", [
            _msg(40, "creo que el ritmo del último episodio estuvo excelente la verdad"),
            _msg(41, "die musik im finale hat mir wirklich eine gänsehaut gegeben wow"),
            _msg(42, "あのキャラクターの成長が今シーズンの一番の見どころだと思う"),
            _msg(43, "honestly the foreshadowing in the second episode was incredible"),
        ]),
        Scenario("veteran_shares_one_invite", "benign",
                 [_msg(50, "come hang out here discord.gg/x", ev=True, inv=("discord.gg/x",),
                       **_VET)]),
        Scenario("normal_safe_link", "benign",
                 [_msg(60, "great clip https://youtube.com/watch?v=abc")]),
        Scenario("short_hype_chant", "benign",
                 [_msg(70 + i, "lets go team") for i in range(4)],
                 note="4 newcomers, identical short chant; safe ONLY because short "
                      "content is excluded from near-dup — the sweep proves this"),

        # ── abuse: at least one message should be acted on ──────────────
        Scenario("invite_flood", "abuse",
                 [_msg(100 + i, "join discord.gg/raid", ev=True, inv=("discord.gg/raid",))
                  for i in range(7)],
                 note="single vector, no @everyone — relies on cross-user burst"),
        Scenario("coordinated_neardup_raid", "abuse",
                 [_msg(110 + i, _SPAM) for i in range(6)]),
        Scenario("mass_mention_raid", "abuse",
                 [_msg(120, "@everyone free stuff http://x.example", everyone=True,
                       unsafe=("http://x.example",))]),
        Scenario("known_bad_match", "abuse",
                 [_msg(130, _BAD)], known_bad=(_BAD,)),
        Scenario("aged_burner_takeover", "abuse",
                 [_msg(140, _BAD, age=14, sage=0.0, msgs=500, active=1,
                       ev=True, inv=("discord.gg/x",))],
                 known_bad=(_BAD,),
                 note="2-week burner, lots of msgs but active 1 day -> denied trust shortcut"),
        Scenario("split_signal_same_user", "abuse",
                 [_msg(145, "come hang out discord.gg/x", mid=145, ev=True, inv=("discord.gg/x",)),
                  _msg(145, _BAD, mid=146)],
                 known_bad=(_BAD,),
                 note="one user splits an invite and a known-bad hit across two messages "
                      "in the window -> self-corroborated, escalates beyond a lone QUARANTINE"),

        # ── evasion: accepted misses, reported so the holes are visible ──
        Scenario("fully_trusted_first_invite", "evasion",
                 [_msg(150, "hey everyone join discord.gg/x", ev=True, inv=("discord.gg/x",),
                       age=400, sage=200, msgs=5000, active=120)],
                 note="a genuinely trusted account's FIRST malicious invite slips (by design)"),
        Scenario("lone_unknown_link", "evasion",
                 [_msg(160, "check this out http://sketchy.tld/x", unsafe=("http://sketchy.tld/x",))],
                 note="a single non-allowlisted link is never a key — real users post links"),
    ]


def evaluate(scenarios: list[Scenario] | None = None, policy: Policy | None = None) -> Scorecard:
    """Replay each scenario through a fresh ENFORCE-mode engine and score it."""
    scenarios = scenarios if scenarios is not None else corpus()
    policy = replace(policy or Policy(), mode=Mode.ENFORCE)
    card = Scorecard()
    for sc in scenarios:
        eng = Engine(policy)
        for kb in sc.known_bad:
            eng.add_known_bad(1, kb)
        acted_any = False
        for m in sc.messages:
            d = eng.evaluate(m)
            if sc.kind == "benign":
                card.benign_messages += 1
                if d.touches_message:
                    card.false_positives += 1
                if d.action == Action.PUNITIVE:
                    card.wrongful_punishments += 1
            if d.touches_message:
                acted_any = True
        if sc.kind == "benign":
            card.benign_scenarios += 1
            if acted_any:
                card.benign_scenarios_acted += 1
                card.misses.append(f"false-positive: {sc.name}")
        elif sc.kind == "abuse":
            card.abuse_scenarios += 1
            if acted_any:
                card.abuse_caught += 1
            else:
                card.misses.append(f"missed-abuse: {sc.name}")
        else:
            card.evasion_scenarios += 1
            if acted_any:
                card.evasion_caught += 1
    return card


def sweep(param: str, values: list, scenarios: list[Scenario] | None = None) -> list[dict]:
    """Re-score the corpus while varying one Policy field — a tradeoff curve."""
    rows = []
    for v in values:
        card = evaluate(scenarios, replace(Policy(), **{param: v}))
        rows.append({param: v, "recall": round(card.recall, 3),
                     "fp_rate": round(card.fp_rate, 3),
                     "wrongful_punishments": card.wrongful_punishments})
    return rows


def load_jsonl(path: str) -> list[Scenario]:
    """Load a real, hand-labeled corpus. Each line is a scenario:

        {"name": "...", "kind": "benign|abuse|evasion", "known_bad": [...],
         "messages": [{"user_id": 1, "content": "...", "account_age_days": ...,
                       "external_invite": true, ...}, ...]}

    Any field of Account/Message may be supplied; missing ones default safely.
    """
    out: list[Scenario] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            msgs = [_scenario_message(m, i) for i, m in enumerate(obj["messages"])]
            out.append(Scenario(obj.get("name", "unnamed"), obj["kind"], msgs,
                                 tuple(obj.get("known_bad", ()))))
    return out


def _scenario_message(m: dict, i: int) -> Message:
    return _msg(
        int(m["user_id"]), m.get("content", ""), mid=int(m.get("message_id", 10000 + i)),
        age=float(m.get("account_age_days", 999.0)), sage=float(m.get("server_age_days", 999.0)),
        msgs=int(m.get("msg_count", 0)), active=int(m.get("active_days", 0)),
        staff=bool(m.get("is_staff", False)), ev=bool(m.get("external_invite", False)),
        inv=tuple(m.get("invite_urls", ())), unsafe=tuple(m.get("unsafe_links", ())),
        everyone=bool(m.get("mentions_everyone", False)), at=float(m.get("created_at", 1000.0)),
    )
