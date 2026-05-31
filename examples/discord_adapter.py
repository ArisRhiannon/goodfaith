"""Example discord.py adapter for goodfaith.

This is illustrative, not part of the core package — install the optional extra
(``pip install "goodfaith[discord]"``) to run it. The core engine never imports
discord.py; this thin cog does all the translation.

It starts every guild in SHADOW mode. Flip a guild to CANARY/ENFORCE only after
``engine.readiness(guild_id)`` looks clean (see docs/METHODOLOGY.md).
"""

from __future__ import annotations

import datetime
import re
import time
from urllib.parse import urlparse

import discord
from discord.ext import commands

from goodfaith import Account, Action, Engine, Message, Mode, Policy

_URL = re.compile(r"https?://\S+", re.IGNORECASE)
_INVITE = re.compile(
    r"(?:discord\.(?:gg|com/invite)|discordapp\.com/invite|dsc\.gg|discord\.me)/\S+",
    re.IGNORECASE,
)
_DISCORD_EPOCH_MS = 1420070400000

# Replace with your own allowlist of domains you consider safe.
SAFE_HOSTS = {"discord.com", "tenor.com", "giphy.com", "youtube.com", "youtu.be"}


def _account_age_days(user_id: int) -> float:
    created_ms = (user_id >> 22) + _DISCORD_EPOCH_MS
    return (time.time() - created_ms / 1000) / 86400


class GoodFaith(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.engine = Engine(Policy(mode=Mode.SHADOW))  # safe default
        self.timeout = datetime.timedelta(hours=1)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        decision = self.engine.evaluate(self._to_message(message))
        if not decision.enforced:
            return  # shadow / no-op: log decision.explain() to your audit channel
        if decision.touches_message:
            try:
                await message.delete()  # reversible: the content stays in your logs
            except discord.HTTPException:
                pass
        if decision.action == Action.PUNITIVE and isinstance(message.author, discord.Member):
            until = discord.utils.utcnow() + self.timeout
            try:
                await message.author.timeout(until, reason=decision.explain()[:400])
            except discord.HTTPException:
                pass

    def _to_message(self, message: discord.Message) -> Message:
        member = message.author
        content = message.content or ""

        invites = _INVITE.findall(content)
        unsafe = []
        for url in _URL.findall(content):
            if _INVITE.search(url):
                continue
            host = (urlparse(url).hostname or "").lower().removeprefix("www.")
            if host and host not in SAFE_HOSTS:
                unsafe.append(url)

        server_age = 999.0
        if getattr(member, "joined_at", None):
            server_age = (discord.utils.utcnow() - member.joined_at).total_seconds() / 86400

        perms = getattr(member, "guild_permissions", None)
        is_staff = bool(perms and (
            perms.administrator or perms.ban_members
            or perms.kick_members or perms.manage_messages
        ))

        acc = Account(
            user_id=member.id,
            account_age_days=_account_age_days(member.id),
            server_age_days=server_age,
            msg_count=self._message_count(message.guild.id, member.id),
            has_avatar=getattr(member, "avatar", None) is not None,
            is_staff=is_staff,
        )
        return Message(
            guild_id=message.guild.id,
            channel_id=message.channel.id,
            message_id=message.id,
            author=acc,
            content=content,
            created_at=time.time(),
            mention_count=len(message.mentions or []),
            mentions_everyone=message.mention_everyone,
            has_attachments=bool(message.attachments),
            sticker_count=len(message.stickers or []),
            invite_urls=tuple(invites),
            external_invite=bool(invites),  # refine: only True for OTHER guilds
            unsafe_links=tuple(unsafe),
            is_reply=message.reference is not None,
        )

    def _message_count(self, guild_id: int, user_id: int) -> int:
        # Plug in your own per-guild message counter — the core trust signal.
        return 0


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GoodFaith(bot))
