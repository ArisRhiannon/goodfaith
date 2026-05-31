"""goodfaith — a trust-first Discord automoderation engine.

Precision over recall: it is built to make wrongful action against a regular far
costlier than missing a spammer — an explicit, tunable bias, not a guarantee.
The engine (:class:`Engine`) is pure Python with no discord.py dependency and
stores no personal data, so it can be unit-tested in isolation and dropped into
any bot via a thin adapter (see ``examples/discord_adapter.py``).
"""

from . import eval, extract
from .engine import Engine, ReadinessReport
from .policy import Policy
from .types import Account, Action, Decision, Message, Mode, Signal, Tier

__version__ = "0.5.1"

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
    "eval",
    "extract",
    "__version__",
]
