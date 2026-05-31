"""The core guarantee: legitimate community behavior is never punished.

Every scenario here runs in ENFORCE mode (the strictest) so any regression
toward a false positive fails loudly.
"""

from goodfaith import Action, Engine, Mode, Policy


def _engine():
    return Engine(Policy(mode=Mode.ENFORCE))


def test_agreement_pileon_across_many_newcomers_never_acts(mk):
    eng = _engine()
    worst = Action.ALLOW
    for i, word in enumerate(["same", "this", "W", "real", "fr", "based", "true", "mood"]):
        d = eng.evaluate(mk(100 + i, word))
        worst = max(worst, d.action)
    assert worst <= Action.OBSERVE


def test_emote_walls_never_act(mk):
    eng = _engine()
    for i in range(6):
        d = eng.evaluate(mk(200 + i, "<:pog:123><a:hype:456>🎉🎉"))
        assert d.action <= Action.OBSERVE


def test_rapid_infodump_single_user_never_punished(mk):
    eng = _engine()
    worst = Action.ALLOW
    for i in range(15):  # well past rapid_count
        d = eng.evaluate(mk(300, f"thought number {i} about the lore", message_id=300 + i))
        worst = max(worst, d.action)
    assert worst <= Action.OBSERVE  # frequency is informational only


def test_distinct_substantial_messages_are_not_coordination(mk):
    eng = _engine()
    texts = [
        "i really think the new episode pacing was excellent honestly",
        "my favorite character arc this season has to be the rival",
        "the soundtrack during the finale gave me actual chills wow",
        "anyone else notice the foreshadowing in the second episode",
    ]
    worst = Action.ALLOW
    for i, t in enumerate(texts):
        worst = max(worst, eng.evaluate(mk(400 + i, t)).action)
    assert worst <= Action.OBSERVE


def test_trusted_member_is_never_punished_even_with_two_keys(mk):
    eng = _engine()
    # Aged, high-volume member: two independent keys, still never punitive.
    d = None
    for i in range(4):
        d = eng.evaluate(mk(
            500 + i, "free nitro airdrop promo reward click the link now everyone",
            account_age_days=400, server_age_days=200, msg_count=8000,
            external_invite=True, invite_urls=("discord.gg/x",),
        ))
    assert d.action < Action.PUNITIVE


def test_staff_immune(mk):
    eng = _engine()
    d = eng.evaluate(mk(7, "discord.gg/x free nitro", is_staff=True,
                        external_invite=True, invite_urls=("discord.gg/x",)))
    assert d.action == Action.ALLOW


def test_single_generic_link_is_never_a_key(mk):
    eng = _engine()
    d = eng.evaluate(mk(800, "great article here https://blog.example/post",
                        unsafe_links=("https://blog.example/post",)))
    assert d.action <= Action.OBSERVE  # unsafe_link is LOW, never punitive alone
