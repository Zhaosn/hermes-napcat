"""QQ (NapCat / OneBot 11) tools for Hermes Agent — plugin form.

All 48 tools are registered by :func:`register_all` via ``ctx.register_tool``
into the ``hermes-napcat`` toolset.  Handlers talk to NapCat through the live
``NapCatAdapter`` (set by ``_init``), which sends OneBot 11 actions over the
reverse-WebSocket connection (Universal mode) instead of an HTTP API.

Admin-required tools call ``_require_admin()`` inside the handler; the current
sender's context is set per-message by the adapter via ``_set_context``.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from tools.registry import tool_error, tool_result

logger = logging.getLogger(__name__)

# ── Runtime config (injected by NapCatAdapter.__init__) ───────────────────────

_adapter: Any = None
_current_sender: str = ""
_current_is_admin: bool = False


def _init(adapter: Any) -> None:
    """Called by NapCatAdapter.__init__ with the live adapter instance."""
    global _adapter
    _adapter = adapter


def _set_context(sender_id: str, is_admin: bool) -> None:
    """Called by the adapter before each message to set the current user context."""
    global _current_sender, _current_is_admin
    _current_sender = sender_id
    _current_is_admin = is_admin


def _check() -> str | None:
    """Return an error string if the tool is not ready, else None."""
    if _adapter is None or not getattr(_adapter, "connected", False):
        return "NapCat 尚未连接。请确认网关已启动且 NapCat 已拨入反向 WS。"
    return None


def _require_admin() -> str | None:
    """Return an error string if the current user is not an admin."""
    if not _current_is_admin:
        sender = _current_sender or "unknown"
        return f"此操作需要管理员权限（当前用户 {sender} 不是管理员）。"
    return None


# ── Core OneBot action helper ─────────────────────────────────────────────────

async def _call(endpoint: str, **params: Any) -> dict:
    if _adapter is None:
        raise RuntimeError("NapCat adapter not initialized")
    body = {k: v for k, v in params.items() if v is not None}
    return await _adapter.call_onebot_api(endpoint, params=body, timeout=30)


# ── Registration ──────────────────────────────────────────────────────────────

_REGISTRY_ENTRIES: list[tuple[str, dict, Callable]] = []


def _register(name: str, schema: dict, handler: Callable) -> None:
    _REGISTRY_ENTRIES.append((name, schema, handler))


def register_all(ctx: Any) -> None:
    """Register all QQ tools into the ``hermes-napcat`` toolset."""
    for name, schema, handler in _REGISTRY_ENTRIES:
        ctx.register_tool(
            name=name,
            toolset="hermes-napcat",
            schema=schema,
            handler=handler,
            is_async=True,
            emoji="🐧",
            description=schema.get("description", ""),
        )
    logger.debug("hermes-napcat: registered %d qq_* tools", len(_REGISTRY_ENTRIES))


# ── Schema helpers ─────────────────────────────────────────────────────────────

def _schema(name: str, desc: str, props: dict, required: list[str] | None = None) -> dict:
    return {
        "name": name,
        "description": desc,
        "parameters": {
            "type": "object",
            "properties": props,
            "required": required or [],
        },
    }


def _str(desc: str) -> dict:
    return {"type": "string", "description": desc}


def _int(desc: str) -> dict:
    return {"type": "integer", "description": desc}


def _bool(desc: str) -> dict:
    return {"type": "boolean", "description": desc}


# ══════════════════════════════════════════════════════════════════════════════
# 1. MESSAGING
# ══════════════════════════════════════════════════════════════════════════════

async def _qq_send_message(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call(
            "send_msg",
            message_type=args.get("message_type"),
            group_id=args.get("group_id"),
            user_id=args.get("user_id"),
            message=args["message"],
        )
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_send_message",
    _schema(
        "qq_send_message",
        "Send a QQ message to a group or private chat. "
        "message is a list of OneBot 11 segments, e.g. [{\"type\":\"text\",\"data\":{\"text\":\"hello\"}}].",
        {
            "message_type": _str("'group' or 'private'"),
            "group_id": _str("Group ID (required when message_type=group)"),
            "user_id": _str("User QQ number (required when message_type=private)"),
            "message": {
                "type": "array",
                "description": "OneBot 11 message segments",
                "items": {"type": "object"},
            },
        },
        required=["message_type", "message"],
    ),
    _qq_send_message,
)


async def _qq_recall_message(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        await _call("delete_msg", message_id=int(args["message_id"]))
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_recall_message",
    _schema(
        "qq_recall_message", "Recall (unsend) a QQ message by its message_id.",
        {"message_id": _str("Message ID to recall")},
        required=["message_id"],
    ),
    _qq_recall_message,
)


async def _qq_mark_msg_as_read(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        await _call("mark_msg_as_read", message_id=int(args["message_id"]))
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_mark_msg_as_read",
    _schema(
        "qq_mark_msg_as_read", "Mark a message as read.",
        {"message_id": _str("Message ID")},
        required=["message_id"],
    ),
    _qq_mark_msg_as_read,
)


async def _qq_set_msg_emoji_like(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        await _call(
            "set_msg_emoji_like",
            message_id=int(args["message_id"]),
            emoji_id=str(args["emoji_id"]),
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_set_msg_emoji_like",
    _schema(
        "qq_set_msg_emoji_like", "React to a message with an emoji (QQ emoji ID).",
        {
            "message_id": _str("Message ID"),
            "emoji_id": _str("QQ emoji ID (integer as string, e.g. '76' for 赞)"),
        },
        required=["message_id", "emoji_id"],
    ),
    _qq_set_msg_emoji_like,
)


async def _qq_forward_message(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call(
            "forward_friend_single_msg" if args.get("user_id") else "forward_group_single_msg",
            message_id=int(args["message_id"]),
            group_id=args.get("group_id"),
            user_id=args.get("user_id"),
        )
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_forward_message",
    _schema(
        "qq_forward_message", "Forward a single message to a group or private chat.",
        {
            "message_id": _str("Message ID to forward"),
            "group_id": _str("Destination group ID"),
            "user_id": _str("Destination user QQ number"),
        },
        required=["message_id"],
    ),
    _qq_forward_message,
)


async def _qq_send_group_forward_msg(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call(
            "send_group_forward_msg",
            group_id=int(args["group_id"]),
            messages=args["messages"],
        )
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_send_group_forward_msg",
    _schema(
        "qq_send_group_forward_msg",
        "Send a merged-forward message to a group. messages is a list of forward node segments.",
        {
            "group_id": _str("Target group ID"),
            "messages": {
                "type": "array",
                "description": "List of forward node segments",
                "items": {"type": "object"},
            },
        },
        required=["group_id", "messages"],
    ),
    _qq_send_group_forward_msg,
)


async def _qq_send_private_forward_msg(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call(
            "send_private_forward_msg",
            user_id=int(args["user_id"]),
            messages=args["messages"],
        )
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_send_private_forward_msg",
    _schema(
        "qq_send_private_forward_msg",
        "Send a merged-forward message to a private chat.",
        {
            "user_id": _str("Target user QQ number"),
            "messages": {
                "type": "array",
                "description": "List of forward node segments",
                "items": {"type": "object"},
            },
        },
        required=["user_id", "messages"],
    ),
    _qq_send_private_forward_msg,
)


# ══════════════════════════════════════════════════════════════════════════════
# 2. MESSAGE HISTORY & ESSENCE
# ══════════════════════════════════════════════════════════════════════════════

async def _qq_get_group_msg_history(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call(
            "get_group_msg_history",
            group_id=int(args["group_id"]),
            message_id=args.get("message_id"),
            count=int(args.get("count", 20)),
        )
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_get_group_msg_history",
    _schema(
        "qq_get_group_msg_history", "Fetch recent message history from a group.",
        {
            "group_id": _str("Group ID"),
            "message_id": _str("Fetch messages before this message_id (optional)"),
            "count": _int("Number of messages to fetch (default 20, max 100)"),
        },
        required=["group_id"],
    ),
    _qq_get_group_msg_history,
)


async def _qq_get_friend_msg_history(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call(
            "get_friend_msg_history",
            user_id=int(args["user_id"]),
            message_id=args.get("message_id"),
            count=int(args.get("count", 20)),
        )
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_get_friend_msg_history",
    _schema(
        "qq_get_friend_msg_history", "Fetch recent message history with a friend.",
        {
            "user_id": _str("Friend QQ number"),
            "message_id": _str("Fetch messages before this message_id (optional)"),
            "count": _int("Number of messages to fetch (default 20)"),
        },
        required=["user_id"],
    ),
    _qq_get_friend_msg_history,
)


async def _qq_get_essence_msg_list(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_essence_msg_list", group_id=int(args["group_id"]))
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_get_essence_msg_list",
    _schema(
        "qq_get_essence_msg_list", "Get the list of essence (pinned highlight) messages in a group.",
        {"group_id": _str("Group ID")},
        required=["group_id"],
    ),
    _qq_get_essence_msg_list,
)


async def _qq_set_essence_msg(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call("set_essence_msg", message_id=int(args["message_id"]))
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_set_essence_msg",
    _schema(
        "qq_set_essence_msg", "Set a message as an essence (highlight) message in a group. Requires admin.",
        {"message_id": _str("Message ID")},
        required=["message_id"],
    ),
    _qq_set_essence_msg,
)


async def _qq_delete_essence_msg(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call("delete_essence_msg", message_id=int(args["message_id"]))
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_delete_essence_msg",
    _schema(
        "qq_delete_essence_msg", "Remove a message from the group's essence list. Requires admin.",
        {"message_id": _str("Message ID")},
        required=["message_id"],
    ),
    _qq_delete_essence_msg,
)


# ══════════════════════════════════════════════════════════════════════════════
# 3. USER & FRIEND INFO
# ══════════════════════════════════════════════════════════════════════════════

async def _qq_get_user_info(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_stranger_info", user_id=int(args["user_id"]))
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_get_user_info",
    _schema(
        "qq_get_user_info", "Get basic info (nickname, avatar, etc.) for any QQ user.",
        {"user_id": _str("QQ number")},
        required=["user_id"],
    ),
    _qq_get_user_info,
)


async def _qq_get_friend_list(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_friend_list")
        return tool_result(data if isinstance(data, list) else [data])
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_get_friend_list",
    _schema("qq_get_friend_list", "Get the bot's friend list.", {}),
    _qq_get_friend_list,
)


async def _qq_like_user(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        await _call(
            "send_like",
            user_id=int(args["user_id"]),
            times=int(args.get("times", 1)),
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_like_user",
    _schema(
        "qq_like_user", "Send a profile like to a QQ user.",
        {
            "user_id": _str("QQ number to like"),
            "times": _int("Number of likes to send (default 1, max 10 per day)"),
        },
        required=["user_id"],
    ),
    _qq_like_user,
)


async def _qq_set_friend_remark(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        await _call(
            "set_friend_add_request",
            user_id=int(args["user_id"]),
            remark=args.get("remark", ""),
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_set_friend_remark",
    _schema(
        "qq_set_friend_remark", "Set or clear the remark (alias) for a friend.",
        {
            "user_id": _str("Friend QQ number"),
            "remark": _str("New remark (blank to clear)"),
        },
        required=["user_id"],
    ),
    _qq_set_friend_remark,
)


async def _qq_delete_friend(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call("delete_friend", user_id=int(args["user_id"]))
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_delete_friend",
    _schema(
        "qq_delete_friend", "Delete a friend. Requires admin.",
        {"user_id": _str("Friend QQ number to remove")},
        required=["user_id"],
    ),
    _qq_delete_friend,
)


async def _qq_handle_friend_request(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call(
            "set_friend_add_request",
            flag=args["flag"],
            approve=args.get("approve", True),
            remark=args.get("remark", ""),
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_handle_friend_request",
    _schema(
        "qq_handle_friend_request", "Accept or reject an incoming friend request. Requires admin.",
        {
            "flag": _str("Request flag from the friend_request event"),
            "approve": _bool("True to accept, False to reject (default True)"),
            "remark": _str("Remark to set on accept (optional)"),
        },
        required=["flag"],
    ),
    _qq_handle_friend_request,
)


async def _qq_poke(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        await _call(
            "group_poke" if args.get("group_id") else "friend_poke",
            user_id=int(args["user_id"]),
            group_id=args.get("group_id"),
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_poke",
    _schema(
        "qq_poke", "Poke (nudge) a user in a group or private chat.",
        {
            "user_id": _str("Target QQ number"),
            "group_id": _str("Group ID (omit for private poke)"),
        },
        required=["user_id"],
    ),
    _qq_poke,
)


# ══════════════════════════════════════════════════════════════════════════════
# 4. GROUP INFO
# ══════════════════════════════════════════════════════════════════════════════

async def _qq_get_group_info(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_group_info", group_id=int(args["group_id"]))
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_get_group_info",
    _schema(
        "qq_get_group_info", "Get basic info for a QQ group (name, member count, etc.).",
        {"group_id": _str("Group ID")},
        required=["group_id"],
    ),
    _qq_get_group_info,
)


async def _qq_get_group_list(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_group_list")
        return tool_result(data if isinstance(data, list) else [data])
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_get_group_list",
    _schema("qq_get_group_list", "Get the list of all groups the bot has joined.", {}),
    _qq_get_group_list,
)


async def _qq_get_group_member_info(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call(
            "get_group_member_info",
            group_id=int(args["group_id"]),
            user_id=int(args["user_id"]),
        )
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_get_group_member_info",
    _schema(
        "qq_get_group_member_info", "Get detailed info for a group member.",
        {
            "group_id": _str("Group ID"),
            "user_id": _str("Member QQ number"),
        },
        required=["group_id", "user_id"],
    ),
    _qq_get_group_member_info,
)


async def _qq_get_group_member_list(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_group_member_list", group_id=int(args["group_id"]))
        return tool_result(data if isinstance(data, list) else [data])
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_get_group_member_list",
    _schema(
        "qq_get_group_member_list", "List all members of a group.",
        {"group_id": _str("Group ID")},
        required=["group_id"],
    ),
    _qq_get_group_member_list,
)


async def _qq_get_group_honor_info(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call(
            "get_group_honor_info",
            group_id=int(args["group_id"]),
            type=args.get("type", "all"),
        )
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_get_group_honor_info",
    _schema(
        "qq_get_group_honor_info",
        "Get honor info (龙王/群聊之火/etc.) for a group.",
        {
            "group_id": _str("Group ID"),
            "type": _str("Honor type: talkative | performer | legend | strong_newbie | emotion | all (default)"),
        },
        required=["group_id"],
    ),
    _qq_get_group_honor_info,
)


async def _qq_get_group_at_all_remain(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_group_at_all_remain", group_id=int(args["group_id"]))
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_get_group_at_all_remain",
    _schema(
        "qq_get_group_at_all_remain",
        "Check remaining @all usage count for a group today.",
        {"group_id": _str("Group ID")},
        required=["group_id"],
    ),
    _qq_get_group_at_all_remain,
)


# ══════════════════════════════════════════════════════════════════════════════
# 5. GROUP MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

async def _qq_mute_group_member(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call(
            "set_group_ban",
            group_id=int(args["group_id"]),
            user_id=int(args["user_id"]),
            duration=int(args.get("duration", 600)),
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_mute_group_member",
    _schema(
        "qq_mute_group_member", "Mute a group member for a given duration (0 = unmute). Requires admin.",
        {
            "group_id": _str("Group ID"),
            "user_id": _str("Member QQ number"),
            "duration": _int("Mute duration in seconds (0 = unmute, default 600)"),
        },
        required=["group_id", "user_id"],
    ),
    _qq_mute_group_member,
)


async def _qq_kick_group_member(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call(
            "set_group_kick",
            group_id=int(args["group_id"]),
            user_id=int(args["user_id"]),
            reject_add_request=args.get("reject_add_request", False),
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_kick_group_member",
    _schema(
        "qq_kick_group_member", "Kick a member from a group. Requires admin.",
        {
            "group_id": _str("Group ID"),
            "user_id": _str("Member QQ number"),
            "reject_add_request": _bool("Also block them from rejoining (default false)"),
        },
        required=["group_id", "user_id"],
    ),
    _qq_kick_group_member,
)


async def _qq_set_group_admin(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call(
            "set_group_admin",
            group_id=int(args["group_id"]),
            user_id=int(args["user_id"]),
            enable=args.get("enable", True),
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_set_group_admin",
    _schema(
        "qq_set_group_admin", "Grant or revoke group admin for a member. Requires admin.",
        {
            "group_id": _str("Group ID"),
            "user_id": _str("Member QQ number"),
            "enable": _bool("True = grant admin, False = revoke (default True)"),
        },
        required=["group_id", "user_id"],
    ),
    _qq_set_group_admin,
)


async def _qq_set_group_name(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call(
            "set_group_name",
            group_id=int(args["group_id"]),
            group_name=args["group_name"],
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_set_group_name",
    _schema(
        "qq_set_group_name", "Rename a group. Requires admin.",
        {
            "group_id": _str("Group ID"),
            "group_name": _str("New group name"),
        },
        required=["group_id", "group_name"],
    ),
    _qq_set_group_name,
)


async def _qq_set_group_card(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        await _call(
            "set_group_card",
            group_id=int(args["group_id"]),
            user_id=int(args["user_id"]),
            card=args.get("card", ""),
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_set_group_card",
    _schema(
        "qq_set_group_card", "Set or clear a member's in-group nickname (card).",
        {
            "group_id": _str("Group ID"),
            "user_id": _str("Member QQ number"),
            "card": _str("New nickname (blank to reset to real name)"),
        },
        required=["group_id", "user_id"],
    ),
    _qq_set_group_card,
)


async def _qq_set_group_whole_ban(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call(
            "set_group_whole_ban",
            group_id=int(args["group_id"]),
            enable=args.get("enable", True),
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_set_group_whole_ban",
    _schema(
        "qq_set_group_whole_ban", "Enable or disable whole-group mute. Requires admin.",
        {
            "group_id": _str("Group ID"),
            "enable": _bool("True = mute all, False = unmute all (default True)"),
        },
        required=["group_id"],
    ),
    _qq_set_group_whole_ban,
)


async def _qq_set_group_special_title(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call(
            "set_group_special_title",
            group_id=int(args["group_id"]),
            user_id=int(args["user_id"]),
            special_title=args.get("special_title", ""),
            duration=-1,
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_set_group_special_title",
    _schema(
        "qq_set_group_special_title", "Set a custom special title for a group member (owner only). Requires admin.",
        {
            "group_id": _str("Group ID"),
            "user_id": _str("Member QQ number"),
            "special_title": _str("Title text (blank to clear)"),
        },
        required=["group_id", "user_id"],
    ),
    _qq_set_group_special_title,
)


async def _qq_leave_group(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call(
            "set_group_leave",
            group_id=int(args["group_id"]),
            is_dismiss=args.get("is_dismiss", False),
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_leave_group",
    _schema(
        "qq_leave_group", "Leave a group (or dismiss it if the bot is the owner). Requires admin.",
        {
            "group_id": _str("Group ID"),
            "is_dismiss": _bool("True to dismiss the group (bot must be owner)"),
        },
        required=["group_id"],
    ),
    _qq_leave_group,
)


async def _qq_set_group_sign(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        await _call("send_group_sign", group_id=int(args["group_id"]))
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_set_group_sign",
    _schema(
        "qq_set_group_sign", "Perform group sign-in (打卡).",
        {"group_id": _str("Group ID")},
        required=["group_id"],
    ),
    _qq_set_group_sign,
)


async def _qq_set_group_remark(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        await _call(
            "set_group_remark",
            group_id=int(args["group_id"]),
            remark=args.get("remark", ""),
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_set_group_remark",
    _schema(
        "qq_set_group_remark", "Set a personal remark for a group (visible only to you).",
        {
            "group_id": _str("Group ID"),
            "remark": _str("Remark text (blank to clear)"),
        },
        required=["group_id"],
    ),
    _qq_set_group_remark,
)


async def _qq_set_group_portrait(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call(
            "set_group_portrait",
            group_id=int(args["group_id"]),
            file=args["file"],
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_set_group_portrait",
    _schema(
        "qq_set_group_portrait", "Set the group avatar (owner/admin only). Requires admin.",
        {
            "group_id": _str("Group ID"),
            "file": _str("Image file path or URL"),
        },
        required=["group_id", "file"],
    ),
    _qq_set_group_portrait,
)


async def _qq_handle_group_request(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call(
            "set_group_add_request",
            flag=args["flag"],
            sub_type=args.get("sub_type", "add"),
            approve=args.get("approve", True),
            reason=args.get("reason", ""),
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_handle_group_request",
    _schema(
        "qq_handle_group_request", "Accept or reject a group join request or group invite. Requires admin.",
        {
            "flag": _str("Request flag from the group_request event"),
            "sub_type": _str("'add' for join request, 'invite' for bot invite (default 'add')"),
            "approve": _bool("True to approve, False to reject (default True)"),
            "reason": _str("Rejection reason (only used when approve=False)"),
        },
        required=["flag"],
    ),
    _qq_handle_group_request,
)


# ══════════════════════════════════════════════════════════════════════════════
# 6. GROUP NOTICES
# ══════════════════════════════════════════════════════════════════════════════

async def _qq_send_group_notice(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call(
            "_send_group_notice",
            group_id=int(args["group_id"]),
            content=args["content"],
            image=args.get("image", ""),
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_send_group_notice",
    _schema(
        "qq_send_group_notice", "Publish a group announcement. Requires admin.",
        {
            "group_id": _str("Group ID"),
            "content": _str("Announcement text"),
            "image": _str("Optional image path or URL to attach"),
        },
        required=["group_id", "content"],
    ),
    _qq_send_group_notice,
)


async def _qq_get_group_notice(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("_get_group_notice", group_id=int(args["group_id"]))
        return tool_result(data if isinstance(data, list) else [data])
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_get_group_notice",
    _schema(
        "qq_get_group_notice", "Get the list of group announcements.",
        {"group_id": _str("Group ID")},
        required=["group_id"],
    ),
    _qq_get_group_notice,
)


async def _qq_delete_group_notice(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call(
            "_del_group_notice",
            group_id=int(args["group_id"]),
            notice_id=args["notice_id"],
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_delete_group_notice",
    _schema(
        "qq_delete_group_notice", "Delete a group announcement. Requires admin.",
        {
            "group_id": _str("Group ID"),
            "notice_id": _str("Notice ID (from qq_get_group_notice)"),
        },
        required=["group_id", "notice_id"],
    ),
    _qq_delete_group_notice,
)


# ══════════════════════════════════════════════════════════════════════════════
# 7. FILE OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

async def _qq_upload_file(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        if args.get("group_id"):
            data = await _call(
                "upload_group_file",
                group_id=int(args["group_id"]),
                file=args["file"],
                name=args.get("name", ""),
                folder_id=args.get("folder_id", ""),
            )
        else:
            data = await _call(
                "upload_private_file",
                user_id=int(args["user_id"]),
                file=args["file"],
                name=args.get("name", ""),
            )
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_upload_file",
    _schema(
        "qq_upload_file", "Upload a file to a group or private chat.",
        {
            "file": _str("Local file path or URL"),
            "name": _str("Display name for the file"),
            "group_id": _str("Upload to this group (mutually exclusive with user_id)"),
            "user_id": _str("Upload to this user's private chat"),
            "folder_id": _str("Target folder ID within the group (optional)"),
        },
        required=["file"],
    ),
    _qq_upload_file,
)


async def _qq_get_group_root_files(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_group_root_files", group_id=int(args["group_id"]))
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_get_group_root_files",
    _schema(
        "qq_get_group_root_files", "List files and folders in a group's root file directory.",
        {"group_id": _str("Group ID")},
        required=["group_id"],
    ),
    _qq_get_group_root_files,
)


async def _qq_get_group_file_url(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call(
            "get_group_file_url",
            group_id=int(args["group_id"]),
            file_id=args["file_id"],
            busid=int(args.get("busid", 0)),
        )
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_get_group_file_url",
    _schema(
        "qq_get_group_file_url", "Get a temporary download URL for a group file.",
        {
            "group_id": _str("Group ID"),
            "file_id": _str("File ID (from qq_get_group_root_files)"),
            "busid": _int("busid from the file listing (default 0)"),
        },
        required=["group_id", "file_id"],
    ),
    _qq_get_group_file_url,
)


async def _qq_create_group_file_folder(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call(
            "create_group_file_folder",
            group_id=int(args["group_id"]),
            name=args["name"],
            parent_id=args.get("parent_id", "/"),
        )
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_create_group_file_folder",
    _schema(
        "qq_create_group_file_folder", "Create a folder in the group file system.",
        {
            "group_id": _str("Group ID"),
            "name": _str("Folder name"),
            "parent_id": _str("Parent folder ID (default '/' for root)"),
        },
        required=["group_id", "name"],
    ),
    _qq_create_group_file_folder,
)


async def _qq_delete_group_file(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call(
            "delete_group_file",
            group_id=int(args["group_id"]),
            file_id=args["file_id"],
            busid=int(args.get("busid", 0)),
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_delete_group_file",
    _schema(
        "qq_delete_group_file", "Delete a file from the group file system. Requires admin.",
        {
            "group_id": _str("Group ID"),
            "file_id": _str("File ID"),
            "busid": _int("busid from the file listing (default 0)"),
        },
        required=["group_id", "file_id"],
    ),
    _qq_delete_group_file,
)


async def _qq_download_file(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call(
            "download_file",
            url=args["url"],
            thread_count=int(args.get("thread_count", 1)),
            headers=args.get("headers", ""),
        )
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_download_file",
    _schema(
        "qq_download_file",
        "Ask NapCat to download a file from a URL and return the local path.",
        {
            "url": _str("URL to download"),
            "thread_count": _int("Download threads (default 1)"),
            "headers": _str("Extra HTTP headers as a string (optional)"),
        },
        required=["url"],
    ),
    _qq_download_file,
)


# ══════════════════════════════════════════════════════════════════════════════
# 8. MISC
# ══════════════════════════════════════════════════════════════════════════════

async def _qq_ocr_image(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("ocr_image", image=args["image"])
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_ocr_image",
    _schema(
        "qq_ocr_image", "Run OCR on an image and return the recognized text.",
        {"image": _str("Image file path or URL")},
        required=["image"],
    ),
    _qq_ocr_image,
)


async def _qq_translate_en2zh(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_word_slices", content=args["content"])
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))


_register(
    "qq_translate_en2zh",
    _schema(
        "qq_translate_en2zh", "Translate English text to Chinese using the QQ translation service.",
        {"content": _str("English text to translate")},
        required=["content"],
    ),
    _qq_translate_en2zh,
)
