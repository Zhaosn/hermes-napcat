"""NapCat (OneBot 11) platform adapter for Hermes Agent — plugin form.

Runs a reverse-WebSocket **server** on ``ws://0.0.0.0:{ws_port}{ws_path}``
(default ``ws://0.0.0.0:18801/onebot/v11``).  NapCat dials in as the WS
client in ``Universal`` mode, so inbound message events and outbound API
actions share one full-duplex connection (responses are correlated by
``echo`` — see :mod:`.api`).

Installed as a Hermes plugin to ``~/.hermes/plugins/napcat/`` — no core
Hermes source files are patched.  ``register(ctx)`` hooks the adapter into
the platform registry, registers the 48 ``qq_*`` tools, and registers the
``qq`` skill.

Configuration (``~/.hermes/config.yaml`` → ``gateway.platforms.napcat``, or
env vars prefixed ``NAPCAT_``):

    platforms:
      napcat:
        enabled: true
        extra:
          ws_port: 18801            # reverse-WS listen port
          ws_path: "/onebot/v11"    # reverse-WS path (must match NapCat's URL)
          access_token: ""          # NapCat reverse-WS 鉴权 Token
          self_id: ""               # bot QQ (auto-detected via get_login_info)
          dm_policy: "allowlist"    # allowlist | open | disabled
          allow_from: []            # QQ numbers allowed for DMs
          group_policy: "open"      # open | allowlist | disabled
          group_allow_from: []      # falls back to allow_from
          admins: []                # QQ numbers that can use admin-only tools
          media_max_mb: 5
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import aiohttp
import aiohttp.web

from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    SendResult,
    cache_image_from_bytes,
)
from gateway.config import Platform, PlatformConfig

from .api import (
    OneBot11Client,
    image_segment,
    record_segment,
    reply_segment,
    text_segment,
    video_segment,
)
from . import qq_tool as _qq_tool

logger = logging.getLogger(__name__)

_QQ_TEXT_LIMIT = 4500
_AUDIO_EXTS = {".mp3", ".opus", ".ogg", ".wav", ".flac", ".m4a", ".aac", ".silk", ".amr"}
_VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".flv", ".wmv"}
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".ico", ".svg"}


# ── Markdown → QQ plain-text ──────────────────────────────────────────────────

def _strip_markdown(text: str) -> str:
    """Convert Markdown to clean QQ-friendly plain text.

    QQ does not render Markdown; raw syntax like **bold** or ## heading
    appears as literal characters.  This function converts the most common
    constructs to readable Unicode equivalents.
    """
    lines = text.splitlines()
    out: list[str] = []
    in_code = False
    code_lang = ""
    code_lines: list[str] = []

    for line in lines:
        fence = re.match(r"^(`{3,}|~{3,})(.*)", line.strip())
        if fence:
            if not in_code:
                in_code = True
                code_lang = fence.group(2).strip()
                code_lines = []
            else:
                in_code = False
                label = f"[{code_lang}]" if code_lang else "[代码]"
                out.append(f"┌─{label}─")
                for cl in code_lines:
                    out.append("│ " + cl)
                out.append("└──────")
                code_lines = []
            continue
        if in_code:
            code_lines.append(line)
            continue

        h = re.match(r"^(#{1,6})\s+(.*)", line)
        if h:
            level, title = len(h.group(1)), h.group(2).strip()
            title = _inline(title)
            out.append(f"【{title}】" if level <= 2 else f"▌ {title}")
            continue

        if re.match(r"^\s*[-*_]{3,}\s*$", line):
            out.append("────────────────")
            continue

        bq = re.match(r"^>\s?(.*)", line)
        if bq:
            out.append("「" + _inline(bq.group(1)) + "」")
            continue

        ul = re.match(r"^(\s*)[-*+]\s+(.*)", line)
        if ul:
            indent = len(ul.group(1)) // 2
            out.append("  " * indent + "• " + _inline(ul.group(2)))
            continue

        ol = re.match(r"^(\s*)\d+[.)]\s+(.*)", line)
        if ol:
            indent = len(ol.group(1)) // 2
            num = re.match(r"^\s*(\d+)", line).group(1)
            out.append("  " * indent + num + ". " + _inline(ol.group(2)))
            continue

        if re.match(r"^\s*\|", line):
            if re.match(r"^\s*\|[\s\-:|]+\|\s*$", line):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            out.append("  ".join(_inline(c) for c in cells if c))
            continue

        out.append(_inline(line))

    return "\n".join(out).strip()


def _inline(text: str) -> str:
    """Strip inline Markdown from a single line."""
    text = re.sub(r"`([^`\n]+)`", r"\1", text)
    text = re.sub(r"\*{3}(.+?)\*{3}", r"\1", text)
    text = re.sub(r"_{3}(.+?)_{3}", r"\1", text)
    text = re.sub(r"\*{2}(.+?)\*{2}", r"\1", text)
    text = re.sub(r"_{2}(.+?)_{2}", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1（\2）", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"[\1]", text)
    text = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", text)
    return text


def _file_ext(url: str) -> str:
    path = url.split("?")[0]
    dot = path.rfind(".")
    return path[dot:].lower() if dot != -1 else ""


def _classify_media(url: str) -> str:
    ext = _file_ext(url)
    if ext in _AUDIO_EXTS:
        return "audio"
    if ext in _VIDEO_EXTS:
        return "video"
    if ext in _IMAGE_EXTS:
        return "image"
    return "file"


def _extract_text(segments: list[dict]) -> str:
    parts = []
    for s in segments:
        if s["type"] == "text":
            parts.append(s["data"].get("text", ""))
        elif s["type"] == "at":
            parts.append(f"@{s['data'].get('qq', '')}")
    return "".join(parts).strip()


def _extract_images(segments: list[dict]) -> list[str]:
    return [
        s["data"].get("url") or s["data"].get("file", "")
        for s in segments if s["type"] == "image"
        if s["data"].get("url") or s["data"].get("file")
    ]


def _extract_record(segments: list[dict]) -> str | None:
    for s in segments:
        if s["type"] == "record":
            return s["data"].get("url") or s["data"].get("file")
    return None


def _extract_reply_id(segments: list[dict]) -> int | None:
    for s in segments:
        if s["type"] == "reply":
            try:
                return int(s["data"]["id"])
            except (KeyError, ValueError):
                pass
    return None


def _has_bot_mention(segments: list[dict], self_id: str) -> bool:
    return any(
        s["type"] == "at" and str(s["data"].get("qq")) == self_id
        for s in segments
    )


def _strip_bot_mention(segments: list[dict], self_id: str) -> list[dict]:
    return [
        s for s in segments
        if not (s["type"] == "at" and str(s["data"].get("qq")) == self_id)
    ]


def _chunk_text(text: str, limit: int = _QQ_TEXT_LIMIT) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split = text.rfind("\n", 0, limit)
        if split <= 0:
            split = text.rfind(" ", 0, limit)
        if split <= 0:
            split = limit
        chunks.append(text[:split])
        text = text[split:].lstrip("\n")
    return chunks


async def _download_and_convert_wav(url: str, max_bytes: int) -> str | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                data = await resp.read()
        if len(data) > max_bytes:
            return None
        fd, in_path = tempfile.mkstemp(suffix=".silk")
        os.close(fd)
        out_path = in_path.replace(".silk", ".wav")
        with open(in_path, "wb") as f:
            f.write(data)
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", in_path, "-ar", "16000", "-ac", "1", "-f", "wav", out_path],
            capture_output=True, timeout=15,
        )
        os.unlink(in_path)
        if result.returncode != 0:
            return None
        return out_path
    except Exception as exc:
        logger.debug("Voice download/convert failed: %s", exc)
        return None


def _extract_ws_token(request: aiohttp.web.Request) -> str:
    """Pull the OneBot 11 access token from a WS handshake."""
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    q = request.query.get("access_token")
    if q:
        return q.strip()
    return ""


# ── Passive probes / config helpers (called by the plugin registry) ───────────

def check_requirements() -> bool:
    """PASSIVE probe: are our dependencies importable right now?"""
    try:
        import aiohttp  # noqa: F401
        return True
    except ImportError:
        return False


def validate_config(config) -> bool:
    """Return True when the platform has enough config to connect."""
    extra = getattr(config, "extra", None) or {}
    ws_port = extra.get("ws_port") or os.getenv("NAPCAT_WS_PORT")
    return bool(ws_port)


def is_connected(config) -> bool:
    """Check whether the platform is configured (env or config.yaml)."""
    extra = getattr(config, "extra", None) or {}
    return bool(extra.get("ws_port") or os.getenv("NAPCAT_WS_PORT"))


def _env_enablement() -> dict | None:
    """Seed ``PlatformConfig.extra`` from env vars during config load.

    Also makes the gateway-level user-auth gate permissive by default (the
    adapter enforces its own ``dm_policy``/``group_policy``), unless the
    operator has explicitly narrowed it via ``NAPCAT_ALLOWED_USERS`` or
    ``NAPCAT_ALLOW_ALL_USERS``.
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

    if not os.getenv("NAPCAT_ALLOW_ALL_USERS") and not os.getenv("NAPCAT_ALLOWED_USERS"):
        os.environ["NAPCAT_ALLOW_ALL_USERS"] = "true"

    return seed or None


# ── Adapter ───────────────────────────────────────────────────────────────────

class NapCatAdapter(BasePlatformAdapter):
    """Hermes platform adapter for QQ via NapCat (OneBot 11 reverse WS).

    NapCat dials **out** to the reverse-WS server we start here; we reply by
    sending OneBot 11 actions back over the same full-duplex connection.
    """

    MAX_MESSAGE_LENGTH = _QQ_TEXT_LIMIT

    def __init__(self, config: PlatformConfig) -> None:
        super().__init__(config, Platform("napcat"))
        extra: dict[str, Any] = getattr(config, "extra", None) or {}

        self._ws_host: str = extra.get("ws_host") or os.getenv("NAPCAT_WS_HOST", "0.0.0.0")
        self._ws_port: int = int(extra.get("ws_port") or os.getenv("NAPCAT_WS_PORT", "18801"))
        self._ws_path: str = extra.get("ws_path") or os.getenv("NAPCAT_WS_PATH", "/onebot/v11")
        raw_token = str(extra.get("access_token") or os.getenv("NAPCAT_ACCESS_TOKEN", ""))
        self._access_token: str = "" if raw_token in ("YOUR_NAPCAT_TOKEN", "YOURQQ_NUMBER") else raw_token
        raw_self_id = str(extra.get("self_id") or "")
        self._self_id: str = "" if raw_self_id in ("YOUR_QQ_NUMBER", "YOURQQ_NUMBER") else raw_self_id
        self._dm_policy: str = str(extra.get("dm_policy", "allowlist")).lower()
        self._allow_from: list[str] = [str(x) for x in extra.get("allow_from", [])]
        self._group_policy: str = str(extra.get("group_policy", "open")).lower()
        self._group_allow_from: list[str] = [str(x) for x in extra.get("group_allow_from", [])]
        self._admins: list[str] = [str(x) for x in extra.get("admins", [])]
        self._media_max_mb: int = int(extra.get("media_max_mb", 5))

        self._client = OneBot11Client()
        self._runner: aiohttp.web.AppRunner | None = None
        self._active_ws: set[aiohttp.web.WebSocketResponse] = set()

        # Wire up the qq_* tools so handlers can send OneBot actions.
        _qq_tool._init(self)

    @property
    def name(self) -> str:
        return "NapCat (QQ)"

    @property
    def connected(self) -> bool:
        """True when a NapCat client is currently dialed into our WS server."""
        return self._client.is_connected()

    # ── Connection ─────────────────────────────────────────────────────────

    async def connect(self, *, is_reconnect: bool = False) -> bool:
        if not self._ws_path.startswith("/"):
            logger.error("NapCat: ws_path must start with '/' (got %r)", self._ws_path)
            return False

        app = aiohttp.web.Application()
        app.router.add_get(self._ws_path, self._ws_handler)
        self._runner = aiohttp.web.AppRunner(app)
        await self._runner.setup()
        site = aiohttp.web.TCPSite(self._runner, self._ws_host, self._ws_port)
        await site.start()
        self._mark_connected()
        logger.info(
            "NapCat: reverse WS listening on ws://%s:%d%s (waiting for NapCat to dial in)",
            self._ws_host, self._ws_port, self._ws_path,
        )

        # Fill in the bot's own QQ number once a connection is available.
        asyncio.create_task(self._fill_self_id())
        return True

    async def disconnect(self) -> None:
        self._mark_disconnected()
        for ws in list(self._active_ws):
            try:
                await ws.close()
            except Exception:
                pass
        self._active_ws.clear()
        if self._runner:
            try:
                await self._runner.cleanup()
            except Exception:
                pass
            self._runner = None
        logger.info("NapCat: disconnected")

    async def _fill_self_id(self) -> None:
        try:
            # Give NapCat a moment to dial in.
            for _ in range(10):
                if self.connected:
                    break
                await asyncio.sleep(1)
            info = await self._client.call("get_login_info")
            if not self._self_id:
                self._self_id = str(info.get("user_id", ""))
            logger.info(
                "NapCat: bot is %s (QQ:%s)",
                info.get("nickname", "?"), info.get("user_id", "?"),
            )
        except Exception as exc:
            logger.warning("NapCat: get_login_info probe failed (WS may not be connected yet): %s", exc)

    # ── Inbound WS server ──────────────────────────────────────────────────

    async def _ws_handler(self, request: aiohttp.web.Request) -> aiohttp.web.WebSocketResponse:
        if self._access_token and _extract_ws_token(request) != self._access_token:
            logger.warning("NapCat: rejected WS connection from %s (bad access token)", request.remote)
            return aiohttp.web.Response(status=403, text="forbidden")

        ws = aiohttp.web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        self._active_ws.add(ws)
        self._client.attach(ws)
        logger.info("NapCat WS connected from %s", request.remote)
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except json.JSONDecodeError:
                        continue
                    if not self._client.handle_message(data):
                        asyncio.create_task(self._process_message(data))
                elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE):
                    break
        finally:
            self._active_ws.discard(ws)
            self._client.detach(ws)
            logger.info("NapCat WS disconnected")
        return ws

    async def _process_message(self, data: dict) -> None:
        if data.get("post_type") != "message":
            return
        try:
            await self._handle_message_event(data)
        except Exception:
            logger.exception("NapCat: error processing message")

    async def _handle_message_event(self, event: dict) -> None:
        is_group = event.get("message_type") == "group"
        sender_id = str(event.get("user_id", ""))
        sender = event.get("sender", {}) or {}
        sender_name: str = sender.get("card") or sender.get("nickname") or sender_id
        group_id = str(event.get("group_id", "")) if is_group else ""
        chat_id = f"group:{group_id}" if is_group else sender_id
        segments: list[dict] = event.get("message", []) or []

        # Group: require @bot mention
        if is_group:
            if self._self_id and not _has_bot_mention(segments, self._self_id):
                return
            if self._self_id:
                segments = _strip_bot_mention(segments, self._self_id)

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

        text = _extract_text(segments)
        image_urls = _extract_images(segments)
        record_url = _extract_record(segments)

        # In group chats prefix every message with the sender's name so the
        # AI can tell participants apart when the group shares one session.
        # Skip the prefix for slash commands so the gateway can detect them
        # correctly — is_command() checks text.startswith("/").
        if is_group and text:
            if text.lstrip().startswith("/"):
                text = text.lstrip()  # preserve slash command, sender is in channel_prompt
            else:
                text = f"[{sender_name}]: {text}"

        # Fetch quoted message text for reply context
        reply_id = _extract_reply_id(segments)
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
                q_text = _extract_text(quoted.get("message", []) or [])
                if q_text:
                    reply_text = f"[{q_name}]: {q_text}"
                    text = f"[引用 {q_name} 的消息: {q_text}]\n{text}"
            except Exception:
                pass

        # Determine MessageType and media
        media_urls: list[str] = []
        media_types: list[str] = []
        msg_type = MessageType.TEXT

        if image_urls:
            msg_type = MessageType.PHOTO
            max_bytes = self._media_max_mb * 1024 * 1024
            for url in image_urls[:1]:  # cache first image for vision tool
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url) as resp:
                            resp.raise_for_status()
                            img_data = await resp.read()
                    if len(img_data) <= max_bytes:
                        cached = cache_image_from_bytes(img_data)
                        media_urls.append(cached)
                        media_types.append("image/jpeg")
                except Exception as exc:
                    logger.debug("NapCat: image download failed: %s", exc)

        elif record_url:
            msg_type = MessageType.VOICE
            max_bytes = self._media_max_mb * 1024 * 1024
            wav = await _download_and_convert_wav(record_url, max_bytes)
            if wav:
                media_urls.append(wav)
                media_types.append("audio/wav")
                logger.debug("NapCat: voice -> %s", wav)

        if not text and not media_urls:
            return

        is_admin = sender_id in self._admins
        if is_admin:
            permission_prompt = (
                f"[管理员] QQ:{sender_id}。"
                "你现在运行在本机 Hermes 环境，拥有完整本地工具访问权限。"
                "可直接调用：terminal（执行 shell 命令）、read_file（读取本机文件）、"
                "write_file、web_search、browser、vision_analyze 等所有工具。"
                "读取文件、查看日志、执行查询等只读操作直接执行，无需确认。"
                "仅对真正不可逆的操作（删除文件、踢人、禁言、修改配置等）需先说明再执行。"
            )
        else:
            permission_prompt = (
                f"[普通用户] QQ:{sender_id}。"
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

        # Set per-message context so admin-gated tools know who is asking
        _qq_tool._set_context(sender_id, is_admin=is_admin)

        await self.handle_message(message_event)

    # ── OneBot 11 actions (used by the qq_* tools) ─────────────────────────

    async def call_onebot_api(
        self,
        action: str,
        params: dict | None = None,
        timeout: float = 30.0,
    ) -> dict:
        """Send a OneBot 11 action over the Universal WS connection."""
        return await self._client.call(action, params, timeout=timeout)

    # ── Outbound ───────────────────────────────────────────────────────────

    def _parse_chat_id(self, chat_id: str) -> tuple[bool, int]:
        if chat_id.startswith("group:"):
            return True, int(chat_id[6:])
        return False, int(chat_id)

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: str | None = None,
        metadata: dict | None = None,
    ) -> SendResult:
        try:
            is_group, num_id = self._parse_chat_id(chat_id)
            chunks = _chunk_text(_strip_markdown(content))
            last_id: str | None = None
            for i, chunk in enumerate(chunks):
                segs: list[dict] = []
                if i == 0 and reply_to:
                    try:
                        segs.append(reply_segment(int(reply_to)))
                    except (ValueError, TypeError):
                        pass
                segs.append(text_segment(chunk))
                if is_group:
                    r = await self._client.call(
                        "send_group_msg", {"group_id": num_id, "message": segs}
                    )
                else:
                    r = await self._client.call(
                        "send_private_msg", {"user_id": num_id, "message": segs}
                    )
                last_id = str(r.get("message_id", ""))
            return SendResult(success=True, message_id=last_id)
        except Exception as exc:
            logger.error("NapCat send error: %s", exc)
            return SendResult(success=False, error=str(exc), retryable=True)

    async def send_image(
        self,
        chat_id: str,
        image_url: str,
        caption: str | None = None,
        metadata: dict | None = None,
    ) -> SendResult:
        try:
            is_group, num_id = self._parse_chat_id(chat_id)
            segs: list[dict] = [image_segment(image_url)]
            if caption:
                segs.append(text_segment(caption))
            if is_group:
                r = await self._client.call(
                    "send_group_msg", {"group_id": num_id, "message": segs}
                )
            else:
                r = await self._client.call(
                    "send_private_msg", {"user_id": num_id, "message": segs}
                )
            return SendResult(success=True, message_id=str(r.get("message_id", "")))
        except Exception as exc:
            return SendResult(success=False, error=str(exc), retryable=True)

    async def send_voice(
        self,
        chat_id: str,
        audio_path: str,
        metadata: dict | None = None,
    ) -> SendResult:
        try:
            is_group, num_id = self._parse_chat_id(chat_id)
            segs: list[dict] = [record_segment(audio_path)]
            if is_group:
                r = await self._client.call(
                    "send_group_msg", {"group_id": num_id, "message": segs}
                )
            else:
                r = await self._client.call(
                    "send_private_msg", {"user_id": num_id, "message": segs}
                )
            return SendResult(success=True, message_id=str(r.get("message_id", "")))
        except Exception as exc:
            return SendResult(success=False, error=str(exc))

    async def send_video(
        self,
        chat_id: str,
        video_path: str,
        metadata: dict | None = None,
    ) -> SendResult:
        try:
            is_group, num_id = self._parse_chat_id(chat_id)
            segs: list[dict] = [video_segment(video_path)]
            if is_group:
                r = await self._client.call(
                    "send_group_msg", {"group_id": num_id, "message": segs}
                )
            else:
                r = await self._client.call(
                    "send_private_msg", {"user_id": num_id, "message": segs}
                )
            return SendResult(success=True, message_id=str(r.get("message_id", "")))
        except Exception as exc:
            return SendResult(success=False, error=str(exc))

    async def send_document(
        self,
        chat_id: str,
        file_path: str,
        filename: str | None = None,
        metadata: dict | None = None,
    ) -> SendResult:
        try:
            is_group, num_id = self._parse_chat_id(chat_id)
            name = filename or os.path.basename(file_path)
            if is_group:
                await self._client.call(
                    "upload_group_file",
                    {"group_id": num_id, "file": file_path, "name": name},
                    timeout=60,
                )
            else:
                await self._client.call(
                    "upload_private_file",
                    {"user_id": num_id, "file": file_path, "name": name},
                    timeout=60,
                )
            return SendResult(success=True)
        except Exception as exc:
            return SendResult(success=False, error=str(exc))

    async def get_chat_info(self, chat_id: str) -> dict:
        try:
            is_group, num_id = self._parse_chat_id(chat_id)
            if is_group:
                g = await self._client.call(
                    "get_group_info", {"group_id": num_id, "no_cache": True}
                )
                return {"name": g.get("group_name", str(num_id)), "type": "group", "chat_id": chat_id}
            u = await self._client.call(
                "get_stranger_info", {"user_id": num_id, "no_cache": True}
            )
            return {"name": u.get("nickname", str(num_id)), "type": "dm", "chat_id": chat_id}
        except Exception as exc:
            return {"name": chat_id, "type": "unknown", "error": str(exc), "chat_id": chat_id}

    def format_message(self, content: str) -> str:
        return _strip_markdown(content)

    async def send_typing(self, chat_id: str, metadata: dict | None = None) -> None:
        pass  # QQ OneBot has no typing indicator

    async def stop_typing(self, chat_id: str) -> None:
        pass


# ── Plugin entry point ────────────────────────────────────────────────────────

def register(ctx) -> None:
    """Called by the Hermes plugin system during discovery."""
    ctx.register_platform(
        name="napcat",
        label="🐧 NapCat (QQ)",
        adapter_factory=lambda cfg: NapCatAdapter(cfg),
        check_fn=check_requirements,
        validate_config=validate_config,
        is_connected=is_connected,
        required_env=["NAPCAT_ACCESS_TOKEN"],
        install_hint=(
            "hermes-napcat runs as a plugin — make sure aiohttp is installed "
            "and set NAPCAT_ACCESS_TOKEN / ws_port to match your NapCat "
            "reverse-WebSocket item."
        ),
        emoji="🐧",
        max_message_length=_QQ_TEXT_LIMIT,
        allowed_users_env="NAPCAT_ALLOWED_USERS",
        allow_all_env="NAPCAT_ALLOW_ALL_USERS",
        env_enablement_fn=_env_enablement,
        cron_deliver_env_var="NAPCAT_HOME_CHANNEL",
        platform_hint=(
            "You are chatting via QQ (NapCat / OneBot 11). QQ does not render "
            "Markdown — write plain text (the gateway strips Markdown before "
            "sending). Use the provided qq_* tools for messaging, group "
            "administration, files, OCR, and translation."
        ),
    )

    _qq_tool.register_all(ctx)

    skill_path = Path(__file__).parent / "skills" / "qq" / "SKILL.md"
    if skill_path.exists():
        ctx.register_skill(
            "qq",
            skill_path,
            "QQ (NapCat / OneBot 11) guide: chat conventions, group policy, "
            "admin permissions, and the available qq_* tools.",
        )
