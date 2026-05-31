"""64-bit SimHash + Hamming distance — a cheap near-duplicate primitive.

SimHash (Charikar) projects a document to a 64-bit fingerprint such that similar
documents have fingerprints differing in few bits. Comparing two fingerprints is
a XOR + popcount → O(1), far cheaper than pairwise Jaccard.

Privacy note: the engine stores only these 64-bit integers, never raw content.
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
_MASK64 = 0xFFFFFFFFFFFFFFFF


def normalize(text: str) -> str:
    """Strip zero-width chars, NFKC-normalize, lowercase (defeats obfuscation)."""
    text = _ZERO_WIDTH.sub("", text or "")
    text = unicodedata.normalize("NFKC", text)
    return text.lower().strip()


def tokens(text: str) -> list[str]:
    """Tokenize after removing URLs and custom emotes.

    Sharing the same GIF/link (reaction culture) is not "coordinated content",
    so URLs and ``<:emote:id>`` are dropped before tokenizing. Identical *text*
    spam is still caught; sharing the same link is not.
    """
    text = _URL_RE.sub(" ", text or "")
    return _TOKEN_RE.findall(normalize(text))


def _hash64(token: str) -> int:
    return int.from_bytes(hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(), "big")


def simhash(text: str) -> int:
    """Return a 64-bit fingerprint of ``text``; 0 when there are no tokens."""
    toks = tokens(text)
    if not toks:
        return 0
    vector = [0] * 64
    for tok in toks:
        h = _hash64(tok)
        for i in range(64):
            vector[i] += 1 if (h >> i) & 1 else -1
    fingerprint = 0
    for i in range(64):
        if vector[i] > 0:
            fingerprint |= 1 << i
    return fingerprint


def hamming(a: int, b: int) -> int:
    """Number of differing bits between two 64-bit fingerprints."""
    return ((a ^ b) & _MASK64).bit_count()


def near(a: int, b: int, max_distance: int) -> bool:
    """Are ``a`` and ``b`` near-identical? (both non-zero and within distance)."""
    if a == 0 or b == 0:
        return False
    return hamming(a, b) <= max_distance
