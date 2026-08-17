from contextvars import ContextVar
from typing import Any, Callable

from tools.registry import tool_error, tool_result


# ── Runtime config (injected by NapCatAdapter.__init__) ───────────────────────────────────────

# The adapter instance is a process-wide singleton (set once at construction).
_adapter: Any = None

# Per-message caller identity.  These are ContextVars, NOT module globals: each
# inbound message runs in its own asyncio task, and tasks (and their children)
# get an isolated context.  A module-global would leak one message's admin
# status into every concurrently-processed message — a privilege escalation.
_current_sender_var: ContextVar[str] = ContextVar("qq_current_sender", default="")
_current_is_admin_var: ContextVar[bool] = ContextVar("qq_current_is_admin", default=False)


def _init(adapter: Any) -> None:
    """Called by NapCatAdapter.__init__ with the live adapter instance."""
    global _adapter
    _adapter = adapter


def _set_context(sender_id: str, is_admin: bool) -> None:
    """Called by the adapter before each message to set the current user context."""
    _current_sender_var.set(sender_id)
    _current_is_admin_var.set(is_admin)


def _check() -> str | None:
    """Return an error string if the tool is not ready, else None."""
    if _adapter is None or not getattr(_adapter, "connected", False):
        return "NapCat 尚未连接。请确认网关已启动且 NapCat 已拨入反向 WS。"
    return None


def _require_admin() -> str | None:
    """Return an error string if the current user is not an admin.

    Defaults to not-admin when no message context is active (fail-closed).
    """
    if not _current_is_admin_var.get():
        sender = _current_sender_var.get() or "unknown"
        return f"此操作需要管理员权限（当前用户 {sender} 不是管理员）。"
    return None


# ── Core OneBot action helper ───────────────────────────────────────────────────────

async def _call(endpoint: str, **params: Any) -> dict:
    if _adapter is None:
        raise RuntimeError("NapCat adapter not initialized")
    body = {k: v for k, v in params.items() if v is not None}
    return await _adapter.call_onebot_api(endpoint, params=body, timeout=30)


HANDLERS: dict[str, Callable] = {}

# ══════════════════════════════════════════════════════════════════════════════
# 1. MESSAGING
# ══════════════════════════════════════════════════════════════════════════════

async def _qq_send_message(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        message_type = args.get("message_type")
        if message_type == "group":
            data = await _call(
                "send_group_msg",
                group_id=int(args["group_id"]),
                message=args["message"],
            )
        elif message_type == "private":
            data = await _call(
                "send_private_msg",
                user_id=int(args["user_id"]),
                message=args["message"],
            )
        else:
            return tool_error(f"Invalid message_type: {message_type!r}. Must be 'group' or 'private'.")
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_send_message"] = _qq_send_message


async def _qq_recall_message(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        await _call("delete_msg", message_id=int(args["message_id"]))
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_recall_message"] = _qq_recall_message


async def _qq_mark_msg_as_read(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        await _call("mark_msg_as_read", message_id=int(args["message_id"]))
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_mark_msg_as_read"] = _qq_mark_msg_as_read


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

HANDLERS["qq_set_msg_emoji_like"] = _qq_set_msg_emoji_like


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

HANDLERS["qq_forward_message"] = _qq_forward_message


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

HANDLERS["qq_send_group_forward_msg"] = _qq_send_group_forward_msg


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

HANDLERS["qq_send_private_forward_msg"] = _qq_send_private_forward_msg


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
            message_seq=args.get("message_seq"),
            count=int(args.get("count", 20)),
        )
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_group_msg_history"] = _qq_get_group_msg_history


async def _qq_get_friend_msg_history(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call(
            "get_friend_msg_history",
            user_id=int(args["user_id"]),
            message_seq=args.get("message_seq"),
            count=int(args.get("count", 20)),
        )
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_friend_msg_history"] = _qq_get_friend_msg_history


async def _qq_get_essence_msg_list(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_essence_msg_list", group_id=int(args["group_id"]))
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_essence_msg_list"] = _qq_get_essence_msg_list


async def _qq_set_essence_msg(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call("set_essence_msg", message_id=int(args["message_id"]))
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_set_essence_msg"] = _qq_set_essence_msg


async def _qq_delete_essence_msg(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call("delete_essence_msg", message_id=int(args["message_id"]))
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_delete_essence_msg"] = _qq_delete_essence_msg


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

HANDLERS["qq_get_user_info"] = _qq_get_user_info


async def _qq_get_friend_list(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_friend_list")
        return tool_result(data if isinstance(data, list) else [data])
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_friend_list"] = _qq_get_friend_list


async def _qq_set_friend_remark(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        await _call(
            "set_friend_remark",
            user_id=int(args["user_id"]),
            remark=args.get("remark", ""),
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_set_friend_remark"] = _qq_set_friend_remark


async def _qq_delete_friend(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call("delete_friend", user_id=int(args["user_id"]))
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_delete_friend"] = _qq_delete_friend


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

HANDLERS["qq_handle_friend_request"] = _qq_handle_friend_request


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

HANDLERS["qq_poke"] = _qq_poke


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

HANDLERS["qq_get_group_info"] = _qq_get_group_info


async def _qq_get_group_list(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_group_list")
        return tool_result(data if isinstance(data, list) else [data])
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_group_list"] = _qq_get_group_list


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

HANDLERS["qq_get_group_member_info"] = _qq_get_group_member_info


async def _qq_get_group_member_list(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_group_member_list", group_id=int(args["group_id"]))
        return tool_result(data if isinstance(data, list) else [data])
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_group_member_list"] = _qq_get_group_member_list


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

HANDLERS["qq_get_group_honor_info"] = _qq_get_group_honor_info


async def _qq_get_group_at_all_remain(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_group_at_all_remain", group_id=int(args["group_id"]))
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_group_at_all_remain"] = _qq_get_group_at_all_remain


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

HANDLERS["qq_mute_group_member"] = _qq_mute_group_member


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

HANDLERS["qq_kick_group_member"] = _qq_kick_group_member


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

HANDLERS["qq_set_group_admin"] = _qq_set_group_admin


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

HANDLERS["qq_set_group_name"] = _qq_set_group_name


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

HANDLERS["qq_set_group_card"] = _qq_set_group_card


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

HANDLERS["qq_set_group_whole_ban"] = _qq_set_group_whole_ban


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

HANDLERS["qq_set_group_special_title"] = _qq_set_group_special_title


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

HANDLERS["qq_leave_group"] = _qq_leave_group


async def _qq_set_group_sign(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        await _call("send_group_sign", group_id=int(args["group_id"]))
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_set_group_sign"] = _qq_set_group_sign


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

HANDLERS["qq_set_group_remark"] = _qq_set_group_remark


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

HANDLERS["qq_set_group_portrait"] = _qq_set_group_portrait


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

HANDLERS["qq_handle_group_request"] = _qq_handle_group_request


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

HANDLERS["qq_send_group_notice"] = _qq_send_group_notice


async def _qq_get_group_notice(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("_get_group_notice", group_id=int(args["group_id"]))
        return tool_result(data if isinstance(data, list) else [data])
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_group_notice"] = _qq_get_group_notice


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

HANDLERS["qq_delete_group_notice"] = _qq_delete_group_notice


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

HANDLERS["qq_upload_file"] = _qq_upload_file


async def _qq_get_group_root_files(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_group_root_files", group_id=int(args["group_id"]))
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_group_root_files"] = _qq_get_group_root_files


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

HANDLERS["qq_get_group_file_url"] = _qq_get_group_file_url


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

HANDLERS["qq_create_group_file_folder"] = _qq_create_group_file_folder


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

HANDLERS["qq_delete_group_file"] = _qq_delete_group_file


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

HANDLERS["qq_download_file"] = _qq_download_file


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

HANDLERS["qq_ocr_image"] = _qq_ocr_image


async def _qq_translate_en2zh(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        words = args["words"]
        if isinstance(words, str):
            words = [words]
        data = await _call("translate_en2zh", words=list(words))
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_translate_en2zh"] = _qq_translate_en2zh


# ══════════════════════════════════════════════════════════════════════════════
# 9. MEDIA & CONTENT
# ══════════════════════════════════════════════════════════════════════════════

async def _qq_get_file(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_file", file=args["file"])
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_file"] = _qq_get_file


async def _qq_get_image(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_image", file=args["file"])
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_image"] = _qq_get_image


async def _qq_get_record(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call(
            "get_record",
            file=args["file"],
            out_format=args.get("out_format", "mp3"),
        )
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_record"] = _qq_get_record


async def _qq_get_emoji_likes(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call(
            "get_emoji_likes",
            message_id=str(args["message_id"]),
            emoji_id=str(args["emoji_id"]),
            group_id=args.get("group_id"),
            count=int(args.get("count", 0)),
        )
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_emoji_likes"] = _qq_get_emoji_likes


async def _qq_get_recent_contact(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_recent_contact", count=int(args.get("count", 10)))
        return tool_result(data if isinstance(data, list) else [data])
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_recent_contact"] = _qq_get_recent_contact


async def _qq_create_flash_task(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        files = args["files"]
        if isinstance(files, str):
            files = [files]
        data = await _call(
            "create_flash_task",
            files=list(files),
            name=args.get("name", ""),
        )
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_create_flash_task"] = _qq_create_flash_task


async def _qq_send_flash_msg(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call(
            "send_flash_msg",
            fileset_id=args["fileset_id"],
            user_id=args.get("user_id"),
            group_id=args.get("group_id"),
        )
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_send_flash_msg"] = _qq_send_flash_msg


# ══════════════════════════════════════════════════════════════════════════════
# 10. GROUP EXTENDED
# ══════════════════════════════════════════════════════════════════════════════

async def _qq_kick_group_members(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        users = args["user_id"]
        if isinstance(users, str):
            users = [users]
        await _call(
            "set_group_kick_members",
            group_id=int(args["group_id"]),
            user_id=[str(u) for u in users],
            reject_add_request=args.get("reject_add_request", False),
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_kick_group_members"] = _qq_kick_group_members


async def _qq_get_group_shut_list(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_group_shut_list", group_id=int(args["group_id"]))
        return tool_result(data if isinstance(data, list) else [data])
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_group_shut_list"] = _qq_get_group_shut_list


async def _qq_get_group_detail_info(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_group_detail_info", group_id=int(args["group_id"]))
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_group_detail_info"] = _qq_get_group_detail_info


async def _qq_get_group_files_by_folder(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call(
            "get_group_files_by_folder",
            group_id=int(args["group_id"]),
            folder_id=args.get("folder_id", "/"),
            file_count=int(args.get("file_count", 50)),
        )
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_group_files_by_folder"] = _qq_get_group_files_by_folder


async def _qq_delete_group_folder(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call(
            "delete_group_folder",
            group_id=int(args["group_id"]),
            folder_id=args["folder_id"],
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_delete_group_folder"] = _qq_delete_group_folder


async def _qq_get_group_file_system_info(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_group_file_system_info", group_id=int(args["group_id"]))
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_group_file_system_info"] = _qq_get_group_file_system_info


async def _qq_set_group_todo(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call(
            "set_group_todo",
            group_id=int(args["group_id"]),
            message_id=str(args["message_id"]),
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_set_group_todo"] = _qq_set_group_todo


async def _qq_complete_group_todo(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        await _call(
            "complete_group_todo",
            group_id=int(args["group_id"]),
            message_id=str(args["message_id"]),
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_complete_group_todo"] = _qq_complete_group_todo


async def _qq_get_group_signed_list(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_group_signed_list", group_id=int(args["group_id"]))
        return tool_result(data if isinstance(data, list) else [data])
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_group_signed_list"] = _qq_get_group_signed_list


# ══════════════════════════════════════════════════════════════════════════════
# 11. USER & SELF
# ══════════════════════════════════════════════════════════════════════════════

async def _qq_get_friends_with_category(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_friends_with_category")
        return tool_result(data if isinstance(data, list) else [data])
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_friends_with_category"] = _qq_get_friends_with_category


async def _qq_get_unidirectional_friend_list(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_unidirectional_friend_list")
        return tool_result(data if isinstance(data, list) else [data])
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_unidirectional_friend_list"] = _qq_get_unidirectional_friend_list


async def _qq_set_qq_avatar(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call("set_qq_avatar", file=args["file"])
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_set_qq_avatar"] = _qq_set_qq_avatar


async def _qq_set_self_longnick(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call("set_self_longnick", longNick=args["long_nick"])
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_set_self_longnick"] = _qq_set_self_longnick


async def _qq_set_online_status(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call(
            "set_diy_online_status",
            face_id=str(args.get("face_id", "")),
            face_type=str(args.get("face_type", "1")),
            wording=str(args.get("wording", " ")),
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_set_online_status"] = _qq_set_online_status


# ══════════════════════════════════════════════════════════════════════════════
# 12. QZONE, ALBUMS & SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

async def _qq_send_qzone_msg(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        data = await _call(
            "send_qzone_msg",
            content=args["content"],
            images=args.get("images", []),
            ugc_right=int(args.get("ugc_right", 1)),
            target_uins=args.get("target_uins", []),
        )
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_send_qzone_msg"] = _qq_send_qzone_msg


async def _qq_get_qun_album_list(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call(
            "get_qun_album_list",
            group_id=int(args["group_id"]),
            attach_info=args.get("attach_info", ""),
        )
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_qun_album_list"] = _qq_get_qun_album_list


async def _qq_upload_image_to_qun_album(args: dict, **_) -> str:
    err = _check() or _require_admin()
    if err:
        return tool_error(err)
    try:
        await _call(
            "upload_image_to_qun_album",
            group_id=int(args["group_id"]),
            album_id=args["album_id"],
            album_name=args.get("album_name", ""),
            file=args["file"],
        )
        return tool_result(success=True)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_upload_image_to_qun_album"] = _qq_upload_image_to_qun_album


async def _qq_get_version_info(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_version_info")
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_version_info"] = _qq_get_version_info


async def _qq_get_status(args: dict, **_) -> str:
    err = _check()
    if err:
        return tool_error(err)
    try:
        data = await _call("get_status")
        return tool_result(data)
    except Exception as e:
        return tool_error(str(e))

HANDLERS["qq_get_status"] = _qq_get_status

