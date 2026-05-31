"""Pure, tested link/invite classification for adapters.

The riskiest part of any adapter is turning raw message text into the link
signals the engine consumes, and that is where bugs live — most notoriously,
flagging your OWN server's invite as "external". Do it once, here, with tests,
instead of reinventing it per bot.

No discord.py dependency: it works on plain text plus the small bits of context
only the bot knows (this guild's invite codes, your safe-host allowlist).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

_URL = re.compile(r"https?://\S+", re.IGNORECASE)
_INVITE = re.compile(
    r"(?:discord\.(?:gg|com/invite)|discordapp\.com/invite|dsc\.gg|discord\.me)/([\w-]+)",
    re.IGNORECASE,
)
# De-obfuscate the common "evil[.]com" / "evil (dot) com" / "evil dot com" tricks
# before scanning for scheme-less domains.
_DEOBF = re.compile(r"\s*[\[\(\{]\s*(?:\.|dot)\s*[\]\)\}]\s*|\s+dot\s+", re.IGNORECASE)
# Scheme-less domain with a high-signal TLD (not an exhaustive PSL — kept tight so
# "node.js"/"main.py" don't match). Result is LOW severity, never a key alone.
_BARE = re.compile(
    r"(?<![\w@.-])((?:[a-z0-9-]+\.)+(?:com|net|org|io|gg|xyz|info|biz|ru|tk|ml|ga|cf"
    r"|cc|link|click|app|me|top|live|online|shop|site|vip|fun|win|bet|co))(?:/\S*)?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Links:
    invite_urls: tuple[str, ...]
    external_invite: bool
    unsafe_links: tuple[str, ...]


def classify(content: str, *, own_invite_codes: tuple[str, ...] = (),
             safe_hosts: tuple[str, ...] = ()) -> Links:
    """Extract invite/link signals from message text.

    ``own_invite_codes`` are this guild's vanity/active invite codes; invites to
    any *other* code set ``external_invite``. ``safe_hosts`` are domains you trust
    (e.g. youtube.com); links elsewhere become ``unsafe_links``. Invite links are
    never also counted as unsafe links.
    """
    content = content or ""
    own = {c.lower() for c in own_invite_codes}
    invites: list[str] = []
    external = False
    for m in _INVITE.finditer(content):
        invites.append(m.group(0))
        if m.group(1).lower() not in own:
            external = True

    safe = {h.lower() for h in safe_hosts}
    unsafe: list[str] = []
    seen: set[str] = set()
    for url in _URL.findall(content):
        if _INVITE.search(url):
            continue
        host = (urlparse(url).hostname or "").lower().removeprefix("www.")
        if host and host not in safe:
            unsafe.append(url)
            seen.add(host)

    # Scheme-less / obfuscated domains: scan with URLs+invites stripped and the
    # common dot-obfuscations normalized. LOW signal by design (never a key alone).
    leftover = _DEOBF.sub(".", _INVITE.sub(" ", _URL.sub(" ", content)))
    for m in _BARE.finditer(leftover):
        host = m.group(1).lower().removeprefix("www.")
        if host not in safe and host not in seen:
            unsafe.append(m.group(0))
            seen.add(host)

    return Links(tuple(invites), external, tuple(unsafe))
