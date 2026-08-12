"""NapCat (QQ / OneBot 11) platform plugin for Hermes Agent.

Installed to ``~/.hermes/plugins/napcat/`` by ``hermes-napcat setup``.  The
Hermes plugin loader imports this package and calls ``register(ctx)``, which
hooks the adapter into the platform registry, registers the 48 ``qq_*`` tools
(toolset ``hermes-napcat``), and registers the ``qq`` skill.
"""
from .adapter import register

__all__ = ["register"]
