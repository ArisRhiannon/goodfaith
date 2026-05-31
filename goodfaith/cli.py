"""``goodfaith`` CLI — replay a message log through the engine in shadow mode.

Feed it a JSONL file (one message per line) and it reports, per guild, what the
engine *would* have done without touching anyone — the same shadow-mode workflow
used to field-validate the defaults (see ``docs/METHODOLOGY.md``).

Each line needs at least ``guild_id``, ``user_id`` and ``content``; any field of
:class:`goodfaith.Account` / :class:`goodfaith.Message` may be supplied.

Usage:
    goodfaith replay messages.jsonl
    cat messages.jsonl | goodfaith replay --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable

from .engine import Engine
from .types import Account, Message


def _message_from(obj: dict) -> Message:
    acc = Account(
        user_id=int(obj["user_id"]),
        account_age_days=float(obj.get("account_age_days", 999.0)),
        server_age_days=float(obj.get("server_age_days", 999.0)),
        msg_count=int(obj.get("msg_count", 0)),
        active_days=int(obj.get("active_days", 0)),
        is_staff=bool(obj.get("is_staff", False)),
    )
    return Message(
        guild_id=int(obj["guild_id"]),
        channel_id=int(obj.get("channel_id", 0)),
        message_id=int(obj.get("message_id", 0)),
        author=acc,
        content=obj.get("content", ""),
        created_at=float(obj.get("created_at", 0.0)),
        mentions_everyone=bool(obj.get("mentions_everyone", False)),
        has_attachments=bool(obj.get("has_attachments", False)),
        sticker_count=int(obj.get("sticker_count", 0)),
        invite_urls=tuple(obj.get("invite_urls", ())),
        external_invite=bool(obj.get("external_invite", False)),
        unsafe_links=tuple(obj.get("unsafe_links", ())),
    )


def replay(lines: Iterable[str], engine: Engine) -> Engine:
    for raw in lines:
        raw = raw.strip()
        if raw:
            engine.evaluate(_message_from(json.loads(raw)))
    return engine


def _report(engine: Engine, as_json: bool) -> None:
    guilds = sorted(engine._stats)  # noqa: SLF001 - reporting on own state
    if as_json:
        out = {}
        for gid in guilds:
            r = engine.readiness(gid)
            s = engine._stats[gid]  # noqa: SLF001
            out[str(gid)] = {
                "seen": r.seen,
                "would_touch": r.would_touch,
                "would_review": r.would_review,
                "would_punish": r.would_punish,
                "punish_rate": r.punish_rate,
                "review_rate": r.review_rate,
                "ready": r.ready(),
                "by_action": dict(s.by_action),
            }
        print(json.dumps(out, indent=2))
        return
    for gid in guilds:
        r = engine.readiness(gid)
        s = engine._stats[gid]  # noqa: SLF001
        breakdown = ", ".join(f"{k}={v}" for k, v in sorted(s.by_action.items()))
        print(f"guild {gid}: seen={r.seen} would_touch={r.would_touch} "
              f"would_review={r.would_review} would_punish={r.would_punish} "
              f"punish_rate={r.punish_rate:.4f} review_rate={r.review_rate:.4f} "
              f"ready={r.ready()}")
        print(f"  actions: {breakdown}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="goodfaith", description=__doc__)
    sub = parser.add_subparsers(dest="cmd")
    rp = sub.add_parser("replay", help="replay a JSONL message log in shadow mode")
    rp.add_argument("file", nargs="?", help="JSONL file (default: stdin)")
    rp.add_argument("--json", action="store_true", help="machine-readable output")
    ev = sub.add_parser("eval", help="score the labeled corpus (or a JSONL corpus)")
    ev.add_argument("file", nargs="?", help="labeled JSONL corpus (default: bundled)")
    ev.add_argument("--json", action="store_true", help="machine-readable output")
    ev.add_argument("--sweep", metavar="POLICY_FIELD",
                    help="re-score while varying one Policy int field")
    ev.add_argument("--values", default="1,2,3,5,8",
                    help="comma-separated values for --sweep (ints)")
    args = parser.parse_args(argv)

    if args.cmd == "replay":
        engine = Engine()
        if args.file:
            with open(args.file, encoding="utf-8") as fh:
                replay(fh, engine)
        else:
            replay(sys.stdin, engine)
        _report(engine, args.json)
        return 0

    if args.cmd == "eval":
        from . import eval as _eval
        scenarios = _eval.load_jsonl(args.file) if args.file else None
        if args.sweep:
            rows = _eval.sweep(args.sweep, [int(v) for v in args.values.split(",")], scenarios)
            print(json.dumps(rows, indent=2) if args.json else "\n".join(map(str, rows)))
            return 0
        card = _eval.evaluate(scenarios)
        print(json.dumps(card.as_dict(), indent=2) if args.json else card.format_text())
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
