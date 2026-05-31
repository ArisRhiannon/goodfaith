"""Legitimate-behavior allowlist — the heart of zero false positives.

Grounded in how real Discord communities actually talk: terminally-online chat,
neurodivergent info-dumping, emote/GIF walls, agreement pile-ons, copypasta.
These patterns must NEVER be a false positive.

These functions do not decide punishments. They decide which *frequency /
repetition* signals to suppress. Dangerous-content signals (external invites,
phishing, known-bad) are never suppressed by a legitimate pattern.
"""

from __future__ import annotations

import re

from .policy import Policy
from .text import normalize, tokens
from .types import Message

_CUSTOM_EMOTE = re.compile(r"<a?:\w+:\d+>")
_EMOJI = re.compile(
    "[\U0001f000-\U0001faff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff"
    "\U00002190-\U000021ff\U00002b00-\U00002bff\ufe0f\u200d\u2640\u2642]"
)
_MARKDOWN_SUBTEXT = re.compile(r"^-#\s", re.MULTILINE)
_SPOILER = re.compile(r"\|\|.+?\|\|", re.DOTALL)
_CODEBLOCK = re.compile(r"```.+?```", re.DOTALL)


def is_agreement_word(content: str, policy: Policy) -> bool:
    """Cross-user agreement pile-on ('same', 'this', 'W', 'real', 'fr'…)."""
    norm = normalize(content)
    if not norm:
        return False
    stripped = re.sub(r"[!?.,~\s]+", " ", norm).strip()
    words = policy.all_agreement_words()
    if stripped in words:
        return True
    toks = stripped.split()
    if not toks:
        return False
    # "same same", "W W W", "real real real" → still agreement.
    return all(t in words for t in toks) and len(set(toks)) <= 2


def is_emote_emoji_only(content: str) -> bool:
    """Message composed only of emotes/emoji/whitespace (emote walls)."""
    if not content or not content.strip():
        return False
    no_emotes = _CUSTOM_EMOTE.sub("", content)
    return _EMOJI.sub("", no_emotes).strip() == ""


def is_media_only(msg: Message) -> bool:
    """Media only (GIF/sticker/image) with no meaningful text."""
    has_media = msg.has_attachments or msg.sticker_count > 0
    return has_media and not normalize(msg.content)


def is_short(content: str, policy: Policy) -> bool:
    """One-thought-per-message / rapid texting."""
    return len(tokens(content)) <= policy.short_message_tokens


def is_emphasis_repetition(content: str, policy: Policy) -> bool:
    """Short tokens repeated for emphasis ('no no no', 'WWWW', 'LETS GOOO')."""
    toks = tokens(content)
    if not toks:
        return False
    uniq = set(toks)
    if len(uniq) <= 2 and all(len(t) <= policy.emphasis_max_token_len for t in toks):
        return True
    # Single char-run token like "WWWWWW" / "aaaaa".
    return len(toks) == 1 and len(set(toks[0])) <= 2


def has_markdown_formatting(content: str) -> bool:
    """Subtext, spoilers, code blocks → normal formatting use."""
    c = content or ""
    return bool(_MARKDOWN_SUBTEXT.search(c) or _SPOILER.search(c) or _CODEBLOCK.search(c))


def is_substantial(content: str, policy: Policy) -> bool:
    """Is this SUBSTANTIAL content (eligible for cross-user near-dup)?

    Short or agreement messages are not substantial, so they never trigger
    near-dup — which is what shields legitimate pile-ons.
    """
    if is_agreement_word(content, policy):
        return False
    if is_emphasis_repetition(content, policy):
        return False
    return len(tokens(content)) >= policy.neardup_min_tokens


def legitimate_patterns(msg: Message, policy: Policy) -> list[str]:
    """Names of the legitimate patterns that apply (for transparency/logging)."""
    c = msg.content
    out: list[str] = []
    if is_agreement_word(c, policy):
        out.append("agreement_pileon")
    if is_emote_emoji_only(c):
        out.append("emote_emoji_only")
    if is_media_only(msg):
        out.append("media_only")
    if is_emphasis_repetition(c, policy):
        out.append("emphasis_repetition")
    if has_markdown_formatting(c):
        out.append("markdown_formatting")
    if is_short(c, policy):
        out.append("short_message")
    return out
