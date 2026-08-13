"""NapCat (QQ / OneBot 11) platform plugin for Hermes Agent.

Drop-in plugin directory: copy (or symlink) this ``plugin/`` directory into
``~/.hermes/plugins/napcat/`` — no pip install, no CLI.  Hermes discovers any
subdirectory of ``~/.hermes/plugins/`` that has a ``plugin.yaml`` and an
``__init__.py`` exposing ``register(ctx)``.  Here ``register`` hooks the
adapter into the platform registry, registers the 74 ``qq_*`` tools (toolset
``hermes-napcat``), and registers the ``qq`` skill.
"""
from .adapter import register

__all__ = ["register"]
