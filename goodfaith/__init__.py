"""goodfaith — a trust-first Discord automoderation engine.

Zero false positives above all: it would rather miss a spammer than mute a
regular. The engine (:class:`Engine`) is pure Python with no discord.py
dependency and stores no personal data, so it can be unit-tested in isolation
and dropped into any bot via a thin adapter (see ``examples/discord_adapter.py``).
"""

from .engine import Engine, ReadinessReport
from .policy import Policy
from .types import Account, Action, Decision, Message, Mode, Signal, Tier

__version__ = "0.1.0"

__all__ = [
    "Engine",
    "ReadinessReport",
    "Policy",
    "Account",
    "Message",
    "Decision",
    "Signal",
    "Action",
    "Tier",
    "Mode",
    "__version__",
]
