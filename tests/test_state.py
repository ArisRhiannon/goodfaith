import json

from goodfaith import Action, Engine, Mode, Policy

_BAD = "buy cheap followers onlyfans promo link spam service"


def test_state_survives_a_restart_through_json(mk):
    eng = Engine(Policy(mode=Mode.ENFORCE))
    eng.vouch(1, 42, actor_id=7, reason="known irl")
    eng.add_known_bad(1, _BAD)

    # Serialize → JSON → deserialize into a fresh engine (a "restart").
    snapshot = json.loads(json.dumps(eng.export_state()))
    fresh = Engine(Policy(mode=Mode.ENFORCE))
    fresh.load_state(snapshot)

    assert fresh.is_vouched(1, 42)
    assert fresh.list_vouches(1)[42]["actor_id"] == 7
    # The curated known-bad bank survived: a newcomer posting it is still acted on.
    assert fresh.evaluate(mk(50, _BAD)).action >= Action.QUARANTINE


def test_false_positive_feedback_survives_restart(mk):
    eng = Engine(Policy(mode=Mode.ENFORCE))
    eng.add_known_bad(1, _BAD)
    eng.mark_false_positive(1, _BAD)  # operator corrected a wrongful flag
    fresh = Engine(Policy(mode=Mode.ENFORCE))
    fresh.load_state(json.loads(json.dumps(eng.export_state())))
    assert fresh.evaluate(mk(51, _BAD)).action == Action.ALLOW
