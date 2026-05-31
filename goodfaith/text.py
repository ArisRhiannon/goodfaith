"""Configurable-width SimHash + Hamming distance — a cheap near-duplicate primitive.

SimHash (Charikar) projects a document to a fixed-width fingerprint such that
similar documents have fingerprints differing in few bits. Comparing two
fingerprints is XOR + popcount → O(1), far cheaper than pairwise Jaccard.

Width matters. A 64-bit fingerprint with a Hamming tolerance is prone to
accidental near-collisions on short, low-entropy messages at chat scale, which
manifests as phantom "coordination". goodfaith therefore defaults to **128 bits**
(see ``GF_SIMHASH_BITS``) and additionally gates near-dup on a minimum token
count, so two unrelated short messages are very unlikely to be judged similar.
This is a heuristic, not a cryptographic guarantee.

Privacy note: only these integers are stored, never raw content.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_URL_RE = re.compile(r"https?://\S+|<a?:\w+:\d+>", re.IGNORECASE)
_ZERO_WIDTH = re.compile(
    r"[\u200b\u200c\u200d\u200e\u200f\u2060\ufeff\u00ad"
    r"\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069]"
)
# Cyrillic/Greek look-alikes → ASCII (NFKD does not fold these). Applied only to
# tokens that mix Latin with one of them — the homoglyph-evasion signature — so a
# pure non-Latin word (legit Russian/Greek) is left intact.
_CONF_MAP = {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y", "к": "k",
    "м": "m", "т": "t", "в": "b", "н": "h", "і": "i", "ј": "j", "ѕ": "s", "ԁ": "d",
    "ο": "o", "ε": "e", "α": "a", "ρ": "p", "ν": "v", "τ": "t", "υ": "u", "κ": "k", "ι": "i",
}
_CONFUSABLES = str.maketrans(_CONF_MAP)
_CONF_CHARS = frozenset(_CONF_MAP)
_HAS_LATIN = re.compile(r"[a-z]")

DEFAULT_BITS = 128
MAX_CONTENT = 10_000  # hard cap before tokenizing — bounds CPU on pathological input


def _defuse(tok: str) -> str:
    if _HAS_LATIN.search(tok) and any(c in _CONF_CHARS for c in tok):
        return tok.translate(_CONFUSABLES)
    return tok


def normalize(text: str) -> str:
    """Strip zero-width chars, fold diacritics, lowercase (defeats obfuscation).

    Decomposing (NFKD) and dropping combining marks folds diacritic tricks like
    ``fŕéé`` and makes matching accent-insensitive (two spellings of the same word
    match). Input is length-capped first so a giant message can't burn CPU.
    """
    text = _ZERO_WIDTH.sub("", (text or "")[:MAX_CONTENT])
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower().strip()


def tokens(text: str) -> list[str]:
    """Tokenize after removing URLs and custom emotes.

    Sharing the same GIF/link (reaction culture) is not "coordinated content",
    so URLs and ``<:emote:id>`` are dropped before tokenizing. Identical *text*
    spam is still caught; sharing the same link is not.
    """
    text = _URL_RE.sub(" ", text or "")
    return [_defuse(t) for t in _TOKEN_RE.findall(normalize(text))]


def _hash(token: str, nbytes: int) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=nbytes).digest()
    return int.from_bytes(digest, "big")


def simhash(text: str, bits: int = DEFAULT_BITS) -> int:
    """Return a ``bits``-wide fingerprint of ``text``; 0 when there are no tokens."""
    toks = tokens(text)
    if not toks:
        return 0
    nbytes = max(1, bits // 8)
    vector = [0] * bits
    for tok in toks:
        h = _hash(tok, nbytes)
        for i in range(bits):
            vector[i] += 1 if (h >> i) & 1 else -1
    fingerprint = 0
    for i in range(bits):
        if vector[i] > 0:
            fingerprint |= 1 << i
    return fingerprint


def hamming(a: int, b: int) -> int:
    """Number of differing bits between two fingerprints of equal width."""
    return (a ^ b).bit_count()


def near(a: int, b: int, max_distance: int) -> bool:
    """Are ``a`` and ``b`` near-identical? (both non-zero and within distance)."""
    if a == 0 or b == 0:
        return False
    return hamming(a, b) <= max_distance
