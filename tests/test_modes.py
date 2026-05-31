"""Enforcement modes gate whether a decision is actually acted upon."""

from goodfaith import Action, Engine, Mode, Policy

_SPAM = "free nitro airdrop promo reward click the link now everyone join"


def _punitive(eng, mk):
    d = None
    for i in range(4):
        d = eng.evaluate(mk(10 + i, _SPAM, external_invite=True, invite_urls=("discord.gg/x",)))
    assert d.action == Action.PUNITIVE
    return d


def test_shadow_never_enforces(mk):
    eng = Engine(Policy(mode=Mode.SHADOW))
    d = _punitive(eng, mk)
    assert d.enforced is False


def test_enforce_acts_on_punitive(mk):
    eng = Engine(Policy(mode=Mode.ENFORCE))
    assert _punitive(eng, mk).enforced is True


def test_canary_holds_punitive_but_acts_on_reversible(mk):
    eng = Engine(Policy(mode=Mode.CANARY))
    # Punitive is held back in canary.
    assert _punitive(eng, mk).enforced is False
    # A reversible non-punitive action (quarantine of a lone-key newcomer) is enforced.
    d = eng.evaluate(mk(900, "join us discord.gg/x", external_invite=True,
                        invite_urls=("discord.gg/x",)))
    assert d.action == Action.QUARANTINE and d.enforced is True
