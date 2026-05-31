from goodfaith.text import hamming, near, normalize, simhash, tokens


def test_normalize_strips_zero_width_and_lowercases():
    assert normalize("HeLLo\u200b\u200dWorld") == "helloworld"


def test_tokens_drop_urls_and_custom_emotes():
    toks = tokens("check https://evil.example/x and <:pog:123> now")
    assert "https" not in toks and "pog" not in toks
    assert "check" in toks and "now" in toks


def test_simhash_empty_is_zero():
    assert simhash("") == 0
    assert simhash("   ") == 0


def test_near_identical_text_is_near():
    a = simhash("join my free nitro giveaway server right now")
    b = simhash("join my free nitro giveaway server right now!!!")
    assert near(a, b, 6)


def test_different_text_is_not_near():
    a = simhash("the weather today is lovely and warm outside")
    b = simhash("compiling the kernel takes forever on this laptop")
    assert not near(a, b, 6)


def test_hamming_zero_for_equal():
    assert hamming(123456789, 123456789) == 0


def test_zero_fingerprint_never_near():
    assert not near(0, simhash("anything here"), 6)


def test_default_width_is_128_bit():
    fp = simhash("a reasonably long message with several distinct tokens here")
    assert 0 < fp < (1 << 128)


def test_width_is_configurable():
    fp64 = simhash("a reasonably long message with several distinct tokens here", bits=64)
    assert 0 < fp64 < (1 << 64)


def test_near_works_at_128_bit():
    a = simhash("join my free nitro giveaway server right now please everyone")
    b = simhash("join my free nitro giveaway server right now please everyone!!!")
    assert near(a, b, 12)
