"""Regressions for the v0.5 red-team findings — each reproduces a verified PoC."""

import pytest

from goodfaith import Action, Engine, Mode, Policy
from goodfaith.extract import classify
from goodfaith.text import MAX_CONTENT, hamming, normalize, simhash

_GOOD = "hey friends here is the cool community resource i mentioned earlier today"
_BAD = "free discord nitro giveaway click the link right now everyone join"


# ── H1: known_good must not whitelist a live invite/raid, only similarity FPs ──

def test_known_good_does_not_whitelist_an_invite(mk):
    eng = Engine(Policy(mode=Mode.ENFORCE))
    eng.mark_false_positive(1, _GOOD)
    d = eng.evaluate(mk(50, _GOOD, external_invite=True,
                        invite_urls=("https://discord.gg/evil",), account_age_days=0.1))
    assert d.action != Action.ALLOW  # invite survives the FP-correction


def test_known_good_still_corrects_a_known_bad_false_positive(mk):
    eng = Engine(Policy(mode=Mode.ENFORCE))
    eng.add_known_bad(1, _BAD)
    assert eng.evaluate(mk(60, _BAD)).action > Action.OBSERVE
    eng.mark_false_positive(1, _BAD)
    assert eng.evaluate(mk(61, _BAD)).action == Action.ALLOW


def test_banks_reject_low_entropy_content():
    eng = Engine()
    assert eng.add_known_bad(1, "scam") is False
    assert eng.mark_false_positive(1, "ok") is False


# ── H2: misconfiguration fails loud ───────────────────────────────────────────

@pytest.mark.parametrize("kw", [{"simhash_bits": 0}, {"simhash_bits": 9999},
                                {"simhash_max_hamming": 200}, {"keys_for_punitive": 0}])
def test_invalid_policy_raises(kw):
    with pytest.raises(ValueError):
        Policy(**kw)


# ── H3: window key space is bounded (prune runs), not proportional to all users ─

def test_window_keys_are_bounded(mk):
    eng = Engine(Policy(mode=Mode.ENFORCE))
    n = 2500
    for u in range(n):
        eng.evaluate(mk(u, "just a normal message here", created_at=1000.0 + u))
    assert len(eng.windows._freq) < n


# ── H4: curated banks are FIFO-capped ─────────────────────────────────────────

def test_known_bad_bank_is_capped():
    eng = Engine(Policy(mode=Mode.ENFORCE, known_bad_max=5))
    for i in range(20):
        eng.add_known_bad(1, f"distinct bad phrase number {i} buy now click here", now=1000.0)
    assert len(eng._bad[1]) == 5


# ── M1: scheme-less / obfuscated links are detected; benign tokens are not ─────

@pytest.mark.parametrize("text,hit", [
    ("scam at evil.com", True),
    ("go to evil [dot] com", True),
    ("join evil(dot)com now", True),
    ("evil dot com", True),
    ("node.js is fine", False),
    ("check main.py too", False),
    ("mail me a@evil.com", False),
])
def test_bare_and_obfuscated_links(text, hit):
    assert bool(classify(text).unsafe_links) is hit


def test_safe_host_still_exempt():
    assert classify("clip youtube.com/x", safe_hosts=("youtube.com",)).unsafe_links == ()


# ── M2: @everyone + external invite from a new account is a raid ───────────────

def test_everyone_plus_invite_is_a_raid(mk):
    eng = Engine(Policy(mode=Mode.ENFORCE))
    d = eng.evaluate(mk(70, "@everyone join discord.gg/x", mentions_everyone=True,
                        external_invite=True, invite_urls=("discord.gg/x",), account_age_days=0.1))
    assert any(k.family == "raid" for k in d.keys)


# ── M3: homoglyph obfuscation no longer defeats near-dup, legit text untouched ─

def test_homoglyph_is_folded_for_matching():
    homoglyph = _BAD.replace("free", "fr\u0435\u0435")  # Cyrillic e
    assert hamming(simhash(_BAD), simhash(homoglyph)) <= 12


def test_pure_non_latin_is_not_mangled():
    ru = "привет как дела сегодня хорошо"
    assert simhash(ru) == simhash(ru) and simhash(ru) != 0


# ── M4: load_state tolerates corrupt/tampered input ───────────────────────────

@pytest.mark.parametrize("bad", ["not a dict", {"vouched": {"x": {}}},
                                 {"known_bad": {"1": [["x", 5]]}},
                                 {"known_good": {"1": ["nope", 7]}}])
def test_load_state_is_defensive(bad):
    Engine().load_state(bad)  # must not raise


def test_load_state_skips_malformed_keeps_valid():
    eng = Engine()
    eng.load_state({"known_good": {"1": ["nope", 7]}})
    assert eng._good == {1: [7]}


# ── M6: a future timestamp cannot dodge the burst window ──────────────────────

def test_future_timestamps_do_not_escape_burst(mk):
    eng = Engine(Policy(mode=Mode.ENFORCE))
    future = 10**12  # far beyond wall clock
    actions = [
        eng.evaluate(mk(80 + i, "join discord.gg/raid", external_invite=True,
                        invite_urls=("discord.gg/raid",), account_age_days=0.1,
                        created_at=future, message_id=80 + i)).action
        for i in range(6)
    ]
    assert Action.PUNITIVE in actions


# ── FN reduction: same user splitting independent families self-corroborates ───

def test_split_signal_same_user_escalates(mk):
    eng = Engine(Policy(mode=Mode.ENFORCE))
    eng.add_known_bad(1, _BAD)
    q = eng.evaluate(mk(5, "come hang out discord.gg/x", external_invite=True,
                        invite_urls=("discord.gg/x",), message_id=1))
    assert q.action == Action.QUARANTINE          # lone signal: contained, not punished
    p = eng.evaluate(mk(5, _BAD, message_id=2))    # second, independent family
    assert p.action == Action.PUNITIVE


def test_benign_followup_after_a_flag_is_not_punished(mk):
    eng = Engine(Policy(mode=Mode.ENFORCE))
    eng.evaluate(mk(6, "come hang out discord.gg/x", external_invite=True,
                    invite_urls=("discord.gg/x",), message_id=1))
    d = eng.evaluate(mk(6, "anyway how is everyone doing today", message_id=2))
    assert d.action == Action.ALLOW               # no second family -> no escalation


def test_repeating_one_family_does_not_self_escalate(mk):
    eng = Engine(Policy(mode=Mode.ENFORCE))
    worst = Action.ALLOW
    for i in range(4):  # same user, same family (invite) repeated
        worst = max(worst, eng.evaluate(mk(7, "join discord.gg/x", external_invite=True,
                                            invite_urls=("discord.gg/x",), message_id=i)).action)
    assert worst == Action.QUARANTINE             # one family, however many times


# ── rainbow-teaming v0.5.2: obfuscation, diacritics, ping-raid, DoS cap ───────

def test_obfuscated_invite_is_treated_as_an_invite():
    assert classify("join discord dot gg/abc").external_invite is True
    assert classify("join discord.gg/abc").external_invite is True


def test_diacritic_obfuscation_is_folded():
    bad = "free discord nitro giveaway click the link right now everyone join"
    obf = bad.replace("free", "fr\u0301e\u0301e\u0301")  # combining acute accents
    assert hamming(simhash(bad), simhash(obf)) <= 12


def test_ping_raid_without_everyone_is_caught(mk):
    eng = Engine(Policy(mode=Mode.ENFORCE))
    d = eng.evaluate(mk(9, "hi", mention_count=12, unsafe_links=("http://x.tld",),
                        account_age_days=0.1))
    assert any(k.family == "raid" for k in d.keys)


def test_a_few_pings_is_not_a_raid(mk):
    eng = Engine(Policy(mode=Mode.ENFORCE))
    d = eng.evaluate(mk(9, "hey friends", mention_count=3, unsafe_links=("http://x.tld",),
                        account_age_days=0.1))
    assert all(k.family != "raid" for k in d.keys)  # below threshold -> no false raid


def test_oversized_content_is_capped():
    assert len(normalize("a" * (MAX_CONTENT * 3))) <= MAX_CONTENT
