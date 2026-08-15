"""NapCat (QQ / OneBot 11) platform plugin for Hermes Agent — registration.

Drop-in plugin directory: copy (or symlink) this ``plugin/`` directory into
``~/.hermes/plugins/napcat/`` — no pip install, no CLI.  Hermes discovers any
subdirectory of ``~/.hermes/plugins/`` that has a ``plugin.yaml`` and an
``__init__.py`` exposing ``register(ctx)``.

This module is the registration entry point (per the Hermes plugin guide it is
the file that "connects schema → handler, registers hooks"): it hooks the
``NapCatAdapter`` into the platform registry, pairs every ``qq_*`` schema
(:mod:`.schemas`) with its handler (:mod:`.tools`), and registers the ``qq``
skill.

Module layout:
    __init__.py     registration entry (this file) + config probes
    adapter.py      NapCatAdapter — WS transport / outbound send
    schemas.py      qq_* tool schemas (what the LLM reads)
    tools.py        qq_* tool handlers (the code that runs)
    messages.py     inbound event → MessageEvent pipeline + media
    formatting.py   markdown→plain text, chunking, segment extraction
    api.py          OneBot 11 WS action client
"""
import os
from pathlib import Path
from typing import Any

from . import schemas, tools
from .adapter import NapCatAdapter, _standalone_send
from .formatting import QQ_TEXT_LIMIT


__all__ = ["register"]


# ── Passive probes / config helpers (called by the plugin registry) ───────────

def check_requirements() -> bool:
    """PASSIVE probe: are our dependencies importable right now?"""
    try:
        import aiohttp  # noqa: F401
        return True
    except ImportError:
        return False


def validate_config(config) -> bool:
    """Return True when both required settings are configured.

    ``NAPCAT_WS_PORT`` and ``NAPCAT_ACCESS_TOKEN`` are the minimal contract
    for a working reverse-WS link (both declared ``requires_env`` in
    ``plugin.yaml``): ``ws_port`` is where NapCat dials in, and the token
    authenticates the connection.  Each may come from
    ``PlatformConfig.extra`` (config.yaml) or its env var.  Placeholder token
    values are treated as unset, matching the adapter.
    """
    extra = getattr(config, "extra", None) or {}
    ws_port = extra.get("ws_port") or os.getenv("NAPCAT_WS_PORT")
    raw_token = str(extra.get("access_token") or os.getenv("NAPCAT_ACCESS_TOKEN") or "")
    has_token = bool(raw_token) and raw_token not in ("YOUR_NAPCAT_TOKEN", "YOURQQ_NUMBER")
    return bool(ws_port and has_token)


def is_connected(config) -> bool:
    """Whether the platform is configured enough to auto-enable.

    Same required settings as :func:`validate_config`: a platform the operator
    has not supplied both for must not auto-enable (gateway #31116).
    """
    return validate_config(config)


def _env_enablement() -> dict | None:
    """Seed ``PlatformConfig.extra`` from env vars during config load.

    Pure seeder — no side effects.  (The permissive gateway-auth default is set
    once in ``register()``, not here.)
    """
    seed: dict[str, Any] = {}
    if os.getenv("NAPCAT_WS_PORT"):
        seed["ws_port"] = int(os.getenv("NAPCAT_WS_PORT"))
    if os.getenv("NAPCAT_WS_HOST"):
        seed["ws_host"] = os.getenv("NAPCAT_WS_HOST")
    if os.getenv("NAPCAT_WS_PATH"):
        seed["ws_path"] = os.getenv("NAPCAT_WS_PATH")
    if os.getenv("NAPCAT_ACCESS_TOKEN"):
        seed["access_token"] = os.getenv("NAPCAT_ACCESS_TOKEN")
    if os.getenv("NAPCAT_HTTP_URL"):
        seed["http_url"] = os.getenv("NAPCAT_HTTP_URL")
    if os.getenv("NAPCAT_SELF_ID"):
        seed["self_id"] = os.getenv("NAPCAT_SELF_ID")
    if os.getenv("NAPCAT_DM_POLICY"):
        seed["dm_policy"] = os.getenv("NAPCAT_DM_POLICY")
    if os.getenv("NAPCAT_GROUP_POLICY"):
        seed["group_policy"] = os.getenv("NAPCAT_GROUP_POLICY")
    allowed = os.getenv("NAPCAT_ALLOWED_USERS")
    if allowed:
        seed["allow_from"] = [u.strip() for u in allowed.split(",") if u.strip()]
    admins = os.getenv("NAPCAT_ADMINS")
    if admins:
        seed["admins"] = [u.strip() for u in admins.split(",") if u.strip()]

    return seed or None


# ── Plugin entry point ────────────────────────────────────────────────────────

def _register_tools(ctx) -> None:
    """Pair every ``qq_*`` schema with its handler and register into the toolset."""
    for name, handler in tools.HANDLERS.items():
        schema = schemas.SCHEMAS[name]  # KeyError here = schema/handler name drift
        ctx.register_tool(
            name=name,
            toolset="hermes-napcat",
            schema=schema,
            handler=handler,
            is_async=True,
            description=schema.get("description", ""),
        )


def register(ctx) -> None:
    """Called by the Hermes plugin system during discovery."""
    # Make the gateway-level user-auth gate permissive by default (the adapter
    # enforces its own dm_policy / group_policy), unless the operator has
    # explicitly narrowed it.  Done once at registration, not inside the env
    # probe, which must stay pure.
    if not os.getenv("NAPCAT_ALLOW_ALL_USERS") and not os.getenv("NAPCAT_ALLOWED_USERS"):
        os.environ["NAPCAT_ALLOW_ALL_USERS"] = "true"

    ctx.register_platform(
        name="napcat",
        label="NapCat (QQ)",
        adapter_factory=lambda cfg: NapCatAdapter(cfg),
        check_fn=check_requirements,
        validate_config=validate_config,
        is_connected=is_connected,
        # Both are required: ws_port is where NapCat dials in, and the token
        # authenticates the reverse-WS link (validate_config enforces them).
        required_env=["NAPCAT_ACCESS_TOKEN", "NAPCAT_WS_PORT"],
        install_hint=(
            "Place the plugin/ directory into ~/.hermes/plugins/napcat/, make "
            "sure aiohttp is installed, and set NAPCAT_WS_PORT and "
            "NAPCAT_ACCESS_TOKEN to match your NapCat "
            "reverse-WebSocket."
        ),
        max_message_length=QQ_TEXT_LIMIT,
        allowed_users_env="NAPCAT_ALLOWED_USERS",
        allow_all_env="NAPCAT_ALLOW_ALL_USERS",
        env_enablement_fn=_env_enablement,
        cron_deliver_env_var="NAPCAT_HOME_CHANNEL",
        standalone_sender_fn=_standalone_send,
        platform_hint=(
            "You are chatting via QQ (NapCat / OneBot 11)."
        ),
        emoji="🐧",
    )

    _register_tools(ctx)

    skill_path = Path(__file__).parent / "skills" / "qq" / "SKILL.md"
    if skill_path.exists():
        ctx.register_skill(
            "qq",
            skill_path
        )
