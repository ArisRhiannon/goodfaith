"""Rollout telemetry, vouching, false-positive feedback, and known-bad decay."""

from goodfaith import Action, Engine, Mode, Policy

_SPAM = "free nitro airdrop promo reward click the link now everyone join"


def test_readiness_tracks_would_be_actions(mk):
    eng = Engine(Policy(mode=Mode.SHADOW))
    for i in range(50):
        eng.evaluate(mk(1000 + i, "just chatting about the show", message_id=1000 + i))
    r = eng.readiness(1)
    assert r.seen == 50
    assert r.would_punish == 0
    assert r.ready(min_seen=50, max_punish_rate=0.0) is True


def test_readiness_flags_when_punishments_would_occur(mk):
    eng = Engine(Policy(mode=Mode.SHADOW))
    for i in range(4):
        eng.evaluate(mk(10 + i, _SPAM, external_invite=True, invite_urls=("discord.gg/x",)))
    r = eng.readiness(1)
    assert r.would_punish >= 1
    assert r.ready(min_seen=1, max_punish_rate=0.0) is False


def test_vouch_protects_a_newcomer(mk):
    eng = Engine(Policy(mode=Mode.ENFORCE))
    eng.vouch(1, 42)
    d = None
    for i in range(4):
        d = eng.evaluate(mk(42, _SPAM, external_invite=True, invite_urls=("discord.gg/x",),
                            message_id=700 + i))
    assert d.action < Action.PUNITIVE
    eng.unvouch(1, 42)
    assert not eng.is_vouched(1, 42)


def test_mark_false_positive_forces_allow(mk):
    eng = Engine(Policy(mode=Mode.ENFORCE))
    text = "buy cheap followers onlyfans promo link spam"
    eng.add_known_bad(1, text)
    flagged = eng.evaluate(mk(800, text))
    assert flagged.action > Action.OBSERVE          # would be acted on
    eng.mark_false_positive(1, text)
    cleared = eng.evaluate(mk(801, text))
    assert cleared.action == Action.ALLOW           # never again


def test_known_bad_decays_after_ttl(mk, now):
    eng = Engine(Policy(mode=Mode.ENFORCE, known_bad_ttl_seconds=10))
    text = "limited time scam offer act now wire money"
    eng.add_known_bad(1, text, now=now)
    fresh = eng.evaluate(mk(810, text, created_at=now + 1))
    assert fresh.action > Action.OBSERVE
    stale = eng.evaluate(mk(811, text, created_at=now + 100))  # past TTL
    assert stale.action == Action.ALLOW


def test_channel_allowlist_is_never_moderated(mk):
    eng = Engine(Policy(mode=Mode.ENFORCE, channel_allowlist=frozenset({77})))
    d = eng.evaluate(mk(900, _SPAM, channel_id=77, external_invite=True,
                        invite_urls=("discord.gg/x",)))
    assert d.action == Action.ALLOW
