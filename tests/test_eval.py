"""Efficacy contract over the labeled corpus — the test that isn't tautological.

These assert behavior against realistic benign/abuse/evasion scenarios, not
against the rules themselves, so they catch regressions in *moderation quality*.
"""

from goodfaith import eval as E


def test_cardinal_contract_no_wrongful_action_on_benign():
    card = E.evaluate()
    assert card.wrongful_punishments == 0   # never time out a benign member
    assert card.false_positives == 0        # never even touch a benign message
    assert card.fp_rate == 0.0


def test_catches_unsubtle_abuse_with_clean_precision():
    card = E.evaluate()
    assert card.recall >= 0.8
    assert card.precision == 1.0
    assert card.benign_scenarios >= 6 and card.abuse_scenarios >= 4


def test_evasions_are_reported_not_hidden():
    card = E.evaluate()
    assert card.evasion_scenarios >= 1
    assert card.evasion_recall < 1.0  # by design these slip; surface it honestly


def test_sweep_reveals_the_fp_cliff_that_justifies_the_default():
    rows = E.sweep("neardup_min_tokens", [1, 5])
    loose = next(r for r in rows if r["neardup_min_tokens"] == 1)
    tight = next(r for r in rows if r["neardup_min_tokens"] == 5)
    assert loose["fp_rate"] > tight["fp_rate"]
    assert tight["fp_rate"] == 0.0


def test_load_jsonl_lets_you_score_real_labeled_data(tmp_path):
    p = tmp_path / "corpus.jsonl"
    p.write_text(
        '{"name":"raid","kind":"abuse","messages":['
        '{"user_id":1,"content":"join now","external_invite":true,'
        '"invite_urls":["discord.gg/x"],"account_age_days":0.5}]}\n',
        encoding="utf-8",
    )
    scenarios = E.load_jsonl(str(p))
    assert len(scenarios) == 1 and scenarios[0].kind == "abuse"
    card = E.evaluate(scenarios)
    assert card.abuse_scenarios == 1 and card.abuse_caught == 1


def test_generated_corpus_holds_the_contract_at_scale():
    card = E.evaluate(E.generate())
    assert card.benign_messages >= 6000          # thousands, not dozens
    assert card.false_positives == 0
    assert card.wrongful_punishments == 0
    assert card.recall >= 0.8


def test_generated_corpus_is_deterministic():
    n = len(E.corpus())
    assert (E.generate(seed=1)[n].messages[0].content
            == E.generate(seed=1)[n].messages[0].content)
