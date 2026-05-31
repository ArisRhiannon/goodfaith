from goodfaith import Account, Message, Policy
from goodfaith.behavior import (
    has_markdown_formatting,
    is_agreement_word,
    is_emote_emoji_only,
    is_emphasis_repetition,
    is_media_only,
    is_short,
    is_substantial,
    legitimate_patterns,
)

P = Policy()


def _msg(content="", **kw):
    return Message(
        guild_id=1, channel_id=1, message_id=1,
        author=Account(user_id=1), content=content, **kw,
    )


def test_agreement_words_single_and_repeated():
    assert is_agreement_word("same", P)
    assert is_agreement_word("THIS!!", P)
    assert is_agreement_word("W W W", P)
    assert is_agreement_word("real real", P)
    assert not is_agreement_word("buy my product at this store now", P)


def test_emote_emoji_only():
    assert is_emote_emoji_only("<:pog:123><a:dance:456>")
    assert is_emote_emoji_only("🎉🎉🎉")
    assert not is_emote_emoji_only("lol 🎉")


def test_media_only():
    assert is_media_only(_msg("", has_attachments=True))
    assert is_media_only(_msg("", sticker_count=2))
    assert not is_media_only(_msg("look at this", has_attachments=True))


def test_short_and_emphasis():
    assert is_short("ok sounds good", P)
    assert is_emphasis_repetition("no no no no", P)
    assert is_emphasis_repetition("WWWWWW", P)


def test_markdown_formatting():
    assert has_markdown_formatting("-# subtext here")
    assert has_markdown_formatting("spoiler ||secret||")
    assert has_markdown_formatting("```code block```")


def test_substantial_gating():
    # Agreement / short content is NOT substantial → shields pile-ons from near-dup.
    assert not is_substantial("same", P)
    assert not is_substantial("W", P)
    assert is_substantial("here is a genuinely long sentence with many tokens", P)


def test_legitimate_patterns_lists_applied():
    pats = legitimate_patterns(_msg("same"), P)
    assert "agreement_pileon" in pats and "short_message" in pats
