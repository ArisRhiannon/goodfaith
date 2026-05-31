from goodfaith import Account, Policy
from goodfaith.reputation import (
    ESTABLISHED,
    NEWCOMER,
    REGULAR,
    TRUSTED,
    is_new_account,
    is_trusted,
    tier,
)

P = Policy()


def test_newcomer_by_default():
    acc = Account(user_id=1, account_age_days=0.5, server_age_days=0.0, msg_count=0)
    assert tier(acc, P) == NEWCOMER


def test_trusted_by_tenure_and_volume():
    acc = Account(user_id=1, account_age_days=400, server_age_days=120, msg_count=5000)
    assert tier(acc, P) == TRUSTED
    assert is_trusted(acc, P)


def test_established_by_volume_requires_non_new_account_and_active_days():
    # 100+ msgs but a brand-new account → NOT established (patient spammer guard).
    spammer = Account(user_id=1, account_age_days=0.2, server_age_days=0.0, msg_count=500,
                      active_days=1)
    assert tier(spammer, P) == NEWCOMER
    # Aged account + volume + activity across several days → established.
    real = Account(user_id=2, account_age_days=90, server_age_days=0.0, msg_count=500,
                   active_days=20)
    assert tier(real, P) == ESTABLISHED
    # Aged burner: 500 msgs dumped over a single day → denied the volume shortcut.
    burner = Account(user_id=3, account_age_days=14, server_age_days=0.0, msg_count=500,
                     active_days=1)
    assert tier(burner, P) == NEWCOMER


def test_regular_tier():
    acc = Account(user_id=1, account_age_days=30, server_age_days=3, msg_count=10)
    assert tier(acc, P) == REGULAR
    assert not is_trusted(acc, P)


def test_override_and_new_account():
    assert tier(Account(user_id=1, reputation_override=TRUSTED), P) == TRUSTED
    assert is_new_account(Account(user_id=1, account_age_days=0.5), P)
    assert not is_new_account(Account(user_id=1, account_age_days=365), P)
