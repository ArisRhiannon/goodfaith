"""v0.2 hardening: account-takeover guard, auditable vouches, burst raids, locale.

These directly address the technical critique that prompted v0.2.
"""

from goodfaith import Action, Engine, Mode, Policy
from goodfaith.behavior import is_agreement_word, is_substantial

_SPAM = "free nitro airdrop promo reward click the link now everyone join"


# ── Trust is not a blanket bypass (compromised account / abused vouch) ────────

def test_trusted_account_with_corroborated_danger_is_held_for_review(mk):
    eng = Engine(Policy(mode=Mode.ENFORCE))
    text = "buy followers cheap onlyfans promo discord.gg/x"
    eng.add_known_bad(1, text)
    # Veteran account (would normally be immune) posts known-bad + external invite
    # → two independent families → likely compromise → HOLD, not waved through.
    d = eng.evaluate(mk(1, text, account_age_days=400, server_age_days=300, msg_count=9000,
                        external_invite=True, invite_urls=("discord.gg/x",)))
    assert d.action == Action.HOLD
    assert d.action < Action.PUNITIVE  # still never auto-punished


def test_trusted_account_single_signal_still_protected(mk):
    eng = Engine(Policy(mode=Mode.ENFORCE))
    d = eng.evaluate(mk(1, "hey join discord.gg/x", account_age_days=400,
                        server_age_days=300, msg_count=9000,
                        external_invite=True, invite_urls=("discord.gg/x",)))
    assert d.action <= Action.OBSERVE  # one family from a veteran → no action


def test_vouch_is_auditable():
    eng = Engine()
    eng.vouch(1, 42, actor_id=7, reason="known irl", now=123.0)
    assert eng.is_vouched(1, 42)
    record = eng.list_vouches(1)[42]
    assert record == {"actor_id": 7, "reason": "known irl", "ts": 123.0}
    eng.unvouch(1, 42)
    assert not eng.is_vouched(1, 42)
    assert eng.list_vouches(1) == {}


def test_abused_vouch_cannot_grant_immunity_to_corroborated_danger(mk):
    eng = Engine(Policy(mode=Mode.ENFORCE))
    text = "buy followers cheap onlyfans promo discord.gg/x"
    eng.add_known_bad(1, text)
    eng.vouch(1, 42, actor_id=666, reason="compromised mod")  # bad vouch
    d = eng.evaluate(mk(42, text, external_invite=True, invite_urls=("discord.gg/x",)))
    assert d.action == Action.HOLD  # contained: routed to review, not allowed


# ── Single-vector mass raid self-corroborates (critique #7) ───────────────────

def test_single_vector_invite_raid_escalates_without_mods(mk):
    eng = Engine(Policy(mode=Mode.ENFORCE))
    # Many fresh accounts each post ONLY a short invite (no @everyone, not
    # known-bad, too short for near-dup) — one vector. The cross-user burst makes
    # it self-corroborating once enough distinct accounts pile in.
    actions = [
        eng.evaluate(mk(600 + i, "join discord.gg/raid", external_invite=True,
                        invite_urls=("discord.gg/raid",), message_id=600 + i)).action
        for i in range(6)
    ]
    assert actions[0] == Action.QUARANTINE       # first arrivals: review only
    assert Action.PUNITIVE in actions            # the raid eventually self-corroborates


def test_lone_invite_is_never_escalated_by_burst(mk):
    eng = Engine(Policy(mode=Mode.ENFORCE))
    d = eng.evaluate(mk(700, "join discord.gg/x", external_invite=True,
                        invite_urls=("discord.gg/x",)))
    assert d.action == Action.QUARANTINE and d.action < Action.PUNITIVE


def test_copypasta_is_not_escalated_by_burst(mk):
    # Many users posting identical SUBSTANTIAL text (a meme/copypasta) trips
    # near-dup, but burst excludes the neardup family → stays review-only.
    eng = Engine(Policy(mode=Mode.ENFORCE))
    actions = [eng.evaluate(mk(750 + i, _SPAM, message_id=750 + i)).action for i in range(6)]
    assert Action.PUNITIVE not in actions


# ── Lexicon is replaceable / structure is language-agnostic (critique #6) ─────

def test_agreement_lexicon_is_replaceable():
    p = Policy(agreement_words=frozenset({"foo"}))
    assert is_agreement_word("foo", p)
    assert not is_agreement_word("same", p)  # default English lexicon replaced


def test_short_messages_are_shielded_without_any_lexicon():
    # Empty lexicon (e.g. a non-English server): short pile-ons are still shielded
    # structurally because short content is never "substantial" for near-dup.
    p = Policy(agreement_words=frozenset())
    assert not is_agreement_word("同意", p)
    assert not is_substantial("同意", p)
