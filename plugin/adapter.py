import asyncio
import json
import logging
import os
from typing import Any

import aiohttp
import aiohttp.web

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, SendResult

from . import tools as _qq_tools
from .api import (
    OneBot11Client,
    image_segment,
    record_segment,
    reply_segment,
    text_segment,
    video_segment,
)
from .formatting import QQ_TEXT_LIMIT, chunk_text, strip_markdown
from .messages import InboundHandlerMixin

logger = logging.getLogger(__name__)


def _extract_ws_token(request: aiohttp.web.Request) -> str:
    """Pull the OneBot 11 access token from a WS handshake."""
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    q = request.query.get("access_token")
    if q:
        return q.strip()
    return ""


class NapCatAdapter(InboundHandlerMixin, BasePlatformAdapter):
    """Hermes platform adapter for QQ via NapCat (OneBot 11 reverse WS).

    NapCat dials **out** to the reverse-WS server we start here; we reply by
    sending OneBot 11 actions back over the same full-duplex connection.

    Configuration (``~/.hermes/config.yaml`` → ``gateway.platforms.napcat``, or
    env vars prefixed ``NAPCAT_``):

        platforms:
          napcat:
            enabled: true
            extra:
              ws_port: 18801            # reverse-WS listen port
              ws_path: "/onebot/v11"    # reverse-WS path (must match NapCat's URL)
              access_token: ""          # NapCat reverse-WS 鉴权 Token
              http_url: ""              # NapCat OneBot HTTP API base URL (standalone/cron delivery)
              self_id: ""               # bot QQ (auto-detected via get_login_info)
              dm_policy: "allowlist"    # allowlist | open | disabled
              allow_from: []            # QQ numbers allowed for DMs
              group_policy: "open"      # open | allowlist | disabled
              group_allow_from: []      # falls back to allow_from
              admins: []                # QQ numbers that can use admin-only tools
              media_max_mb: 5
    """

    MAX_MESSAGE_LENGTH = QQ_TEXT_LIMIT

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
        # Bot display name (from get_login_info); used to recognize
        # copy-pasted plain-text mentions like "@Atri" in groups.
        self._bot_name: str = ""
        self._dm_policy: str = str(extra.get("dm_policy", "allowlist")).lower()
        self._allow_from: list[str] = [str(x) for x in extra.get("allow_from", [])]
        self._group_policy: str = str(extra.get("group_policy", "open")).lower()
        self._group_allow_from: list[str] = [str(x) for x in extra.get("group_allow_from", [])]
        self._admins: list[str] = [str(x) for x in extra.get("admins", [])]
        self._media_max_mb: int = int(extra.get("media_max_mb", 5))

        self._client = OneBot11Client()
        self._runner: aiohttp.web.AppRunner | None = None
        self._active_ws: set[aiohttp.web.WebSocketResponse] = set()
        self._http: aiohttp.ClientSession | None = None
        self._self_id_task: asyncio.Task | None = None

        # Wire up the qq_* tools so handlers can send OneBot actions.
        _qq_tools._init(self)

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

        # Long-lived HTTP client for inbound media downloads; closed in
        # disconnect().  Recreate if a stale one survived a previous connect.
        if self._http is not None:
            await self._http.close()
        self._http = aiohttp.ClientSession()

        # Fill in the bot's own QQ number once a connection is available.
        # Keep the task reference so disconnect() can cancel it.
        self._self_id_task = asyncio.create_task(self._fill_self_id())
        return True

    async def disconnect(self) -> None:
        self._mark_disconnected()
        # Fail in-flight OneBot calls so waiters don't hang until their timeout.
        self._client.shutdown()
        if self._self_id_task and not self._self_id_task.done():
            self._self_id_task.cancel()
        self._self_id_task = None
        if self._http is not None:
            await self._http.close()
            self._http = None
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
            if not self._bot_name:
                self._bot_name = str(info.get("nickname", "") or "")
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
        # If the startup self_id probe ran before NapCat dialed in, self_id
        # is still empty and every group message is silently dropped
        # (fail-closed in _handle_message_event).  Re-probe now that a
        # connection actually exists.
        if not self._self_id and (self._self_id_task is None or self._self_id_task.done()):
            self._self_id_task = asyncio.create_task(self._fill_self_id())
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except json.JSONDecodeError:
                        continue
                    if not self._client.handle_message(data):
                        # Only message / request events are inbound events;
                        # heartbeats (meta_event) and unknown frames are skipped
                        # without spawning a no-op task.
                        if data.get("post_type") in ("message", "request"):
                            asyncio.create_task(self._process_message(data))
                elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE):
                    break
        finally:
            self._active_ws.discard(ws)
            self._client.detach(ws)
            logger.info("NapCat WS disconnected")
        return ws

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
            chunks = chunk_text(strip_markdown(content))
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
        return strip_markdown(content)

    async def send_typing(self, chat_id: str, metadata: dict | None = None) -> None:
        pass  # QQ OneBot has no typing indicator

    async def stop_typing(self, chat_id: str) -> None:
        pass


# ── Standalone out-of-process sender (cron delivery) ─────────────────────────

_PLACEHOLDER_TOKENS = ("YOUR_NAPCAT_TOKEN", "YOURQQ_NUMBER")


async def _standalone_send(
    pconfig,
    chat_id: str,
    message: str,
    *,
    thread_id=None,
    media_files=None,
    force_document=False,
) -> dict:
    """Deliver a QQ message from a process with no live gateway adapter.

    Used by ``tools/send_message_tool._send_via_adapter`` when the gateway
    runner is not in this process (e.g. ``hermes cron run`` as a separate
    process from ``hermes gateway``).  Without this hook, ``deliver=napcat``
    cron jobs fail with ``No live adapter for platform 'napcat'``.

    NapCat's link to Hermes is a *reverse* WebSocket — NapCat dials INTO the
    gateway's listener, which a cron subprocess cannot reproduce (the gateway
    already holds the port, and NapCat will not dial a second target on its
    own).  So the standalone path uses NapCat's **OneBot 11 HTTP API**
    instead: enable the HTTP server in NapCat and point this plugin at its
    base URL via ``http_url`` (extra) or ``NAPCAT_HTTP_URL`` (env).  The
    access token is the same ``NAPCAT_ACCESS_TOKEN`` used for the WS.

    ``thread_id`` and ``media_files`` are accepted for signature parity; the
    standalone HTTP path delivers plain text only (the live adapter handles
    media).  ``force_document`` is ignored.
    """
    extra = getattr(pconfig, "extra", None) or {}
    base_url = str(os.getenv("NAPCAT_HTTP_URL") or extra.get("http_url") or "").rstrip("/")
    if not base_url:
        return {
            "error": (
                "NapCat standalone send: set NAPCAT_HTTP_URL (or "
                "http_url under platforms.napcat.extra) to your NapCat "
                "OneBot HTTP API base URL to enable out-of-process delivery"
            )
        }
    raw_token = str(extra.get("access_token") or os.getenv("NAPCAT_ACCESS_TOKEN") or "")
    token = "" if raw_token in _PLACEHOLDER_TOKENS else raw_token

    is_group = chat_id.startswith("group:")
    try:
        target_id = int(chat_id[6:] if is_group else chat_id)
    except (TypeError, ValueError):
        return {"error": f"NapCat standalone send: invalid chat_id {chat_id!r}"}

    action = "send_group_msg" if is_group else "send_private_msg"
    id_key = "group_id" if is_group else "user_id"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    last_id: str | None = None
    try:
        async with aiohttp.ClientSession() as session:
            for chunk in chunk_text(strip_markdown(message)):
                payload = {id_key: target_id, "message": [text_segment(chunk)]}
                try:
                    async with session.post(
                        f"{base_url}/{action}",
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        try:
                            body = await resp.json(content_type=None)
                        except ValueError:
                            body = {}
                        if not resp.ok:
                            return {
                                "error": (
                                    f"NapCat standalone send: HTTP {resp.status}: {body}"
                                )
                            }
                except aiohttp.ClientError as exc:
                    return {"error": f"NapCat standalone send: connection failed: {exc}"}
                status = body.get("status")
                retcode = body.get("retcode")
                if status not in ("ok",) and retcode not in (0, None):
                    msg = body.get("message") or body.get("msg") or f"retcode={retcode}"
                    return {"error": f"NapCat standalone send ({action}): {msg}"}
                data = body.get("data") or {}
                if data.get("message_id"):
                    last_id = str(data["message_id"])
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        return {"error": f"NapCat standalone send failed: {exc}"}

    return {"success": True, "message_id": last_id}
