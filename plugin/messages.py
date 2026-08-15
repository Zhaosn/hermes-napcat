import logging
import mimetypes
import os
import subprocess
import tempfile
from datetime import datetime

import aiohttp

from gateway.platforms.base import (
    MessageEvent,
    MessageType,
    cache_image_from_bytes,
)

from . import tools as _qq_tools
from .formatting import (
    extract_images,
    extract_record,
    extract_reply_id,
    extract_text,
    has_bot_mention,
    strip_bot_mention,
)

logger = logging.getLogger(__name__)


# ── Media download / cache ────────────────────────────────────────────────────

def _guess_media_type(url: str) -> str:
    """Best-effort image MIME from a OneBot image URL (fallback image/jpeg)."""
    return mimetypes.guess_type(url.split("?", 1)[0])[0] or "image/jpeg"


async def cache_image(
    url: str, max_bytes: int, session: aiohttp.ClientSession | None = None
) -> str | None:
    """Download an image and cache it for the vision tool (None on failure).

    ``session`` is the adapter's long-lived HTTP client; a throwaway one is
    created only when the caller does not provide one (and then closed here).
    """
    owns_session = session is None
    session = session or aiohttp.ClientSession()
    try:
        async with session.get(url) as resp:
            resp.raise_for_status()
            img_data = await resp.read()
        if len(img_data) > max_bytes:
            return None
        return cache_image_from_bytes(img_data)
    except Exception as exc:
        logger.debug("NapCat: image download failed: %s", exc)
        return None
    finally:
        if owns_session:
            await session.close()


async def download_and_convert_wav(
    url: str, max_bytes: int, session: aiohttp.ClientSession | None = None
) -> str | None:
    """Download a OneBot ``record`` (silk) and transcode it to 16k mono WAV.

    Returns the path of the transcoded temp file (owned by the caller — it must
    be unlinked once the turn that consumes it is done).  Input and any partial
    output are always cleaned up here.
    """
    owns_session = session is None
    session = session or aiohttp.ClientSession()
    try:
        async with session.get(url) as resp:
            resp.raise_for_status()
            data = await resp.read()
        if len(data) > max_bytes:
            return None
        fd, in_path = tempfile.mkstemp(suffix=".silk")
        os.close(fd)
        out_path = in_path.replace(".silk", ".wav")
        try:
            with open(in_path, "wb") as f:
                f.write(data)
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", in_path, "-ar", "16000", "-ac", "1", "-f", "wav", out_path],
                capture_output=True, timeout=15,
            )
        finally:
            os.unlink(in_path)
        if result.returncode != 0:
            if os.path.exists(out_path):
                os.unlink(out_path)
            return None
        return out_path
    except Exception as exc:
        logger.debug("Voice download/convert failed: %s", exc)
        return None
    finally:
        if owns_session:
            await session.close()


# ── Inbound event pipeline ────────────────────────────────────────────────────

class InboundHandlerMixin:
    """Turns raw OneBot 11 WS frames into ``MessageEvent``s for the gateway.

    Host adapter must expose these attributes (all set from config in
    ``NapCatAdapter.__init__``): ``_client`` (OneBot11Client), ``_self_id``,
    ``_dm_policy``, ``_allow_from``, ``_group_policy``, ``_group_allow_from``,
    ``_admins``, ``_media_max_mb``, ``_http`` (aiohttp session for media, or
    None) — plus the ``build_source`` / ``handle_message`` methods of
    ``BasePlatformAdapter``.
    """

    async def _process_message(self, data: dict) -> None:
        post_type = data.get("post_type")
        try:
            if post_type == "message":
                await self._handle_message_event(data)
            elif post_type == "request":
                await self._handle_request_event(data)
        except Exception:
            logger.exception("NapCat: error processing %s event", post_type)

    async def _handle_message_event(self, event: dict) -> None:
        is_group = event.get("message_type") == "group"
        sender_id = str(event.get("user_id", ""))
        sender = event.get("sender", {}) or {}
        sender_name: str = sender.get("card") or sender.get("nickname") or sender_id
        group_id = str(event.get("group_id", "")) if is_group else ""
        chat_id = f"group:{group_id}" if is_group else sender_id
        segments: list[dict] = event.get("message", []) or []

        # Group: require @bot mention.  Unknown self_id (not yet discovered via
        # get_login_info) is fail-closed — ignore the message rather than
        # replying to every group message.
        if is_group:
            if not self._self_id:
                return
            if not has_bot_mention(segments, self._self_id):
                return
            segments = strip_bot_mention(segments, self._self_id)

        # Policy checks
        if is_group:
            if self._group_policy == "disabled":
                return
            if self._group_policy == "allowlist":
                effective = self._group_allow_from or self._allow_from
                if effective and sender_id not in effective:
                    return
        else:
            if self._dm_policy == "disabled":
                return
            if self._dm_policy == "allowlist":
                if self._allow_from and sender_id not in self._allow_from:
                    return

        text = extract_text(segments)
        image_urls = extract_images(segments)
        record_url = extract_record(segments)

        # Sender identity is passed separately (source.user_id/user_name and
        # the channel_prompt below), not embedded in the message text — so it
        # is never duplicated when the message is rendered in a group session.

        # Fetch quoted message text for reply context
        reply_id = extract_reply_id(segments)
        reply_text: str | None = None
        if reply_id:
            try:
                quoted = await self._client.call("get_msg", {"message_id": int(reply_id)})
                q_sender = quoted.get("sender", {}) or {}
                q_name = (
                    q_sender.get("card")
                    or q_sender.get("nickname")
                    or str(q_sender.get("user_id", ""))
                )
                q_text = extract_text(quoted.get("message", []) or [])
                if q_text:
                    reply_text = f"[{q_name}]: {q_text}"
                    text = f"[引用 {q_name} 的消息: {q_text}]\n{text}"
            except Exception:
                pass

        # Determine MessageType and media
        media_urls: list[str] = []
        media_types: list[str] = []
        temp_paths: list[str] = []  # temp files we own; cleaned after the turn
        msg_type = MessageType.TEXT
        max_bytes = self._media_max_mb * 1024 * 1024

        if image_urls:
            msg_type = MessageType.PHOTO
            for url in image_urls:
                cached = await cache_image(url, max_bytes, session=self._http)
                if cached:
                    media_urls.append(cached)
                    media_types.append(_guess_media_type(url))

        elif record_url:
            msg_type = MessageType.VOICE
            wav = await download_and_convert_wav(record_url, max_bytes, session=self._http)
            if wav:
                media_urls.append(wav)
                media_types.append("audio/wav")
                temp_paths.append(wav)
                logger.debug("NapCat: voice -> %s", wav)

        if not text and not media_urls:
            return

        is_admin = sender_id in self._admins
        name_tag = f"（{sender_name}）" if sender_name != sender_id else ""
        if is_admin:
            permission_prompt = (
                f"[管理员] QQ:{sender_id}{name_tag}。"
                "你现在运行在本机 Hermes 环境，拥有完整本地工具访问权限。"
                "可直接调用：terminal（执行 shell 命令）、read_file（读取本机文件）、"
                "write_file、web_search、browser、vision_analyze 等所有工具。"
                "读取文件、查看日志、执行查询等只读操作直接执行，无需确认。"
                "仅对真正不可逆的操作（删除文件、踢人、禁言、修改配置等）需先说明再执行。"
            )
        else:
            permission_prompt = (
                f"[普通用户] QQ:{sender_id}{name_tag}。"
                "你现在运行在本机 Hermes 环境，可直接调用：web_search（搜索）、"
                "read_file（只读访问本机文件）、terminal（只读/非破坏性命令）、"
                "vision_analyze、skills_list 等工具。"
                "禁止：写入/删除系统文件、执行破坏性 shell 命令、"
                "调用 QQ 管理工具（踢人/禁言等）。"
                "如请求管理操作，告知需联系管理员。"
            )

        source = self.build_source(
            chat_id=chat_id,
            chat_name=sender_name if not is_group else group_id,
            chat_type="group" if is_group else "dm",
            user_id=sender_id,
            user_name=sender_name,
        )

        message_event = MessageEvent(
            text=text,
            message_type=msg_type,
            source=source,
            raw_message=event,
            message_id=str(event.get("message_id", "")),
            media_urls=media_urls,
            media_types=media_types,
            reply_to_message_id=str(reply_id) if reply_id else None,
            reply_to_text=reply_text,
            timestamp=datetime.fromtimestamp(event["time"]) if event.get("time") else datetime.now(),
            channel_prompt=permission_prompt,
        )

        # Set per-message context so admin-gated tools know who is asking.
        # (ContextVars, not globals — safe when messages are processed
        # concurrently; child tasks of this message inherit the context.)
        _qq_tools._set_context(sender_id, is_admin=is_admin)

        try:
            await self.handle_message(message_event)
        finally:
            # Remove temp media we created (e.g. transcoded WAVs) once the
            # turn that consumed them has finished.
            for path in temp_paths:
                try:
                    os.unlink(path)
                except OSError:
                    pass

    async def _handle_request_event(self, event: dict) -> None:
        """Surface OneBot 11 ``request`` events (friend/group requests) to the model.

        These events carry the ``flag`` consumed by ``qq_handle_friend_request`` /
        ``qq_handle_group_request``.  They are treated as admin-routed system
        events, so ``dm_policy``/``group_policy`` do not apply — the model (acting
        for the operator) decides whether to approve or reject via the tools.
        """
        request_type = event.get("request_type")
        flag = str(event.get("flag", ""))
        user_id = str(event.get("user_id", ""))
        sub_type = event.get("sub_type", "")
        comment = str(event.get("comment", "") or "")

        if request_type == "friend":
            chat_id = user_id
            chat_type = "dm"
            text = (
                f"[好友申请] QQ:{user_id} 请求添加你为好友"
                + (f"，附言：{comment}" if comment else "")
                + f'。请调用 qq_handle_friend_request(flag="{flag}", approve=...) 处理。'
            )
        elif request_type == "group":
            group_id = str(event.get("group_id", ""))
            chat_id = f"group:{group_id}"
            chat_type = "group"
            if sub_type == "invite":
                text = (
                    f"[群邀请] 群 {group_id} 邀请机器人入群（来自 QQ:{user_id}"
                    + (f"，附言：{comment}" if comment else "")
                    + f'）。请调用 qq_handle_group_request(flag="{flag}", sub_type="invite", approve=...) 处理。'
                )
            else:
                text = (
                    f"[加群申请] QQ:{user_id} 申请加入群 {group_id}"
                    + (f"，附言：{comment}" if comment else "")
                    + f'。请调用 qq_handle_group_request(flag="{flag}", sub_type="add", approve=...) 处理。'
                )
        else:
            return

        permission_prompt = (
            f"[系统事件-管理员] 这是一条系统级申请事件，已授予管理员权限。"
            "如需处理，请调用 qq_handle_friend_request / qq_handle_group_request 工具。"
        )

        source = self.build_source(
            chat_id=chat_id,
            chat_name=chat_id,
            chat_type=chat_type,
            user_id=user_id,
            user_name=user_id,
        )

        message_event = MessageEvent(
            text=text,
            message_type=MessageType.TEXT,
            source=source,
            raw_message=event,
            message_id="",
            media_urls=[],
            media_types=[],
            reply_to_message_id=None,
            reply_to_text=None,
            timestamp=datetime.fromtimestamp(event["time"]) if event.get("time") else datetime.now(),
            channel_prompt=permission_prompt,
        )

        _qq_tools._set_context(user_id, is_admin=True)

        await self.handle_message(message_event)
