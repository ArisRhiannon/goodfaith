"""Real threats escalate; punitive action requires independent corroboration."""

from goodfaith import Action, Engine, Mode, Policy

_SPAM = "free nitro airdrop promo reward click the link now everyone join"


def _engine(**kw):
    return Engine(Policy(mode=Mode.ENFORCE, **kw))


def test_two_independent_families_punish_a_newcomer(mk):
    eng = _engine()
    # Family 1: external_invite. Family 2: coordinated_neardup (3 prior distinct users).
    d = None
    for i in range(4):
        d = eng.evaluate(mk(100 + i, _SPAM, external_invite=True, invite_urls=("discord.gg/x",)))
    assert d.action == Action.PUNITIVE
    assert d.enforced is True
    assert {k.family for k in d.keys} >= {"invite", "neardup"}


def test_single_family_is_reviewed_not_punished(mk):
    eng = _engine()
    # Only an external invite (one family) from a newcomer → quarantine for review.
    d = eng.evaluate(mk(200, "hey join us discord.gg/x", external_invite=True,
                        invite_urls=("discord.gg/x",)))
    assert d.action == Action.QUARANTINE
    assert d.action < Action.PUNITIVE


def test_coordinated_neardup_alone_is_not_punitive(mk):
    eng = _engine()
    worst = Action.ALLOW
    for i in range(5):
        worst = max(worst, eng.evaluate(mk(300 + i, _SPAM)).action)
    # One family (neardup) only → review, never an automatic timeout.
    assert Action.OBSERVE < worst < Action.PUNITIVE


def test_mass_mention_raid_is_a_key(mk):
    eng = _engine()
    d = eng.evaluate(mk(400, "@everyone free stuff http://x.example",
                        mentions_everyone=True, unsafe_links=("http://x.example",),
                        account_age_days=0.1))
    assert any(k.family == "raid" for k in d.keys)


def test_raising_corroboration_threshold_blocks_punishment(mk):
    eng = _engine(keys_for_punitive=3)  # demand 3 independent families
    d = None
    for i in range(4):
        d = eng.evaluate(mk(500 + i, _SPAM, external_invite=True, invite_urls=("discord.gg/x",)))
    # Only two families available → cannot reach punitive under a 3-family policy.
    assert d.action < Action.PUNITIVE
