"""hermes-napcat: NapCat (QQ/OneBot 11) platform **plugin** for Hermes Agent.

``hermes-napcat setup`` copies ``hermes_napcat/plugin/`` into
``~/.hermes/plugins/napcat/`` and merges the ``platforms.napcat`` config block.
Hermes' plugin loader discovers it and hooks the adapter into the platform
registry — no core source patching.
"""
from .installer import install, status, uninstall

__version__ = "0.3.0"
__all__ = ["install", "uninstall", "status"]
