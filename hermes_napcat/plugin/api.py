"""OneBot 11 Universal-WebSocket action client.

The NapCat adapter runs a reverse-WebSocket **server**; NapCat dials in as the
client in ``Universal`` mode (API + events over one full-duplex connection).
Outbound API actions are sent as ``{"action", "params", "echo"}`` JSON frames
over that same socket and correlated with responses by ``echo``.

Unlike the old HTTP-API design, nothing here depends on NapCat exposing an HTTP
endpoint — the reverse-WS connection carries both directions.
"""
from __future__ import annotations

import asyncio
import itertools
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_echo_seq = itertools.count(1)


class OneBot11Client:
    """Request/response correlation over a single Universal WS connection.

    The adapter attaches the active ``aiohttp`` server-side ``WebSocketResponse``
    here; ``call()`` sends an action frame and awaits the matching ``echo``.
    Inbound message events (which carry no ``echo``) are passed through to the
    adapter untouched via the boolean return of :meth:`handle_message`.
    """

    def __init__(self) -> None:
        self._ws: Optional[Any] = None
        self._pending: dict[str, asyncio.Future] = {}
        self._send_lock = asyncio.Lock()

    # ── Connection lifecycle ─────────────────────────────────────────────────

    def attach(self, ws: Any) -> None:
        """Adopt a freshly-accepted WS connection as the active transport."""
        self._ws = ws
        # Fail in-flight requests from the previous connection so callers don't
        # hang on a stale echo.
        pending, self._pending = self._pending, {}
        for fut in pending.values():
            if not fut.done():
                fut.set_exception(RuntimeError("NapCat WebSocket reconnected"))

    def detach(self, ws: Any) -> None:
        if self._ws is ws:
            self._ws = None

    def is_connected(self) -> bool:
        return self._ws is not None and not self._ws.closed

    # ── Frame routing ────────────────────────────────────────────────────────

    def handle_message(self, data: dict) -> bool:
        """Route a parsed WS frame.  Returns True if it was an API response.

        API responses carry the ``echo`` we set on the request; message events
        (``post_type``) and heartbeats (``meta_event``) do not, so they fall
        through to the caller as inbound events.
        """
        echo = data.get("echo")
        if echo and echo in self._pending:
            fut = self._pending.pop(echo)
            if not fut.done():
                fut.set_result(data)
            return True
        return False

    # ── OneBot 11 actions ────────────────────────────────────────────────────

    async def call(
        self,
        action: str,
        params: dict | None = None,
        timeout: float = 15.0,
    ) -> dict[str, Any]:
        """Send a OneBot 11 action over the WS and return its ``data`` dict.

        Raises RuntimeError if the socket is not connected, the request times
        out, or OneBot reports a non-zero ``retcode`` / non-``ok`` status.
        """
        ws = self._ws
        if ws is None or ws.closed:
            raise RuntimeError("NapCat WebSocket not connected")

        echo = f"h{next(_echo_seq)}"
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[echo] = fut
        try:
            async with self._send_lock:
                await ws.send_json(
                    {"action": action, "params": params or {}, "echo": echo}
                )
            resp = await asyncio.wait_for(fut, timeout=timeout)
        finally:
            self._pending.pop(echo, None)

        status = resp.get("status")
        retcode = resp.get("retcode")
        if status in ("ok",) or retcode == 0:
            return resp.get("data") or {}
        msg = resp.get("message") or resp.get("msg") or f"retcode={retcode}"
        raise RuntimeError(f"OneBot API error ({action}): {msg}")


# ── CQ segment builders ────────────────────────────────────────────────────────

def text_segment(text: str) -> dict:
    return {"type": "text", "data": {"text": text}}


def image_segment(file_url: str) -> dict:
    return {"type": "image", "data": {"file": file_url}}


def at_segment(qq: int | str) -> dict:
    return {"type": "at", "data": {"qq": str(qq)}}


def reply_segment(message_id: int | str) -> dict:
    return {"type": "reply", "data": {"id": str(message_id)}}


def record_segment(file_url: str) -> dict:
    return {"type": "record", "data": {"file": file_url}}


def video_segment(file_url: str) -> dict:
    return {"type": "video", "data": {"file": file_url}}
