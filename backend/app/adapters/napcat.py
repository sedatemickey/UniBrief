"""NapCat OneBot 11 event mapping and default-disabled bridge client."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from urllib.parse import urlsplit

import httpx
import websockets

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class NapCatOneBotAdapter:
    """Convert supported OneBot message events into unified import payloads."""

    attachment_types = {"image", "file", "record", "video"}

    @staticmethod
    def _string_id(value: Any) -> str:
        if value is None:
            raise ValueError("OneBot event is missing a required ID")
        return str(value)

    @staticmethod
    def _attachment_id(
        message_id: str, segment_index: int, file_name: str, url: str, stable_id: Any
    ) -> str:
        if stable_id not in {None, ""}:
            return str(stable_id)
        material = f"{message_id}\n{segment_index}\n{file_name}\n{url}".encode()
        return sha256(material).hexdigest()

    def map_event(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """Map group/private post_type=message events; ignore all other events."""

        if event.get("post_type") != "message":
            return None
        message_type = event.get("message_type")
        if message_type not in {"group", "private"}:
            return None
        message_id = self._string_id(event.get("message_id"))
        user_id = self._string_id(event.get("user_id"))
        sender_data = event.get("sender") if isinstance(event.get("sender"), dict) else {}
        display_name = sender_data.get("card") or sender_data.get("nickname") or f"QQ用户 {user_id}"
        if message_type == "group":
            channel_external_id = self._string_id(event.get("group_id"))
            channel_name = event.get("group_name") or f"QQ群 {channel_external_id}"
            channel_type = "GROUP"
        else:
            channel_external_id = user_id
            channel_name = display_name or f"QQ私聊 {user_id}"
            channel_type = "PRIVATE"

        segments = event.get("message")
        if not isinstance(segments, list):
            segments = [{"type": "text", "data": {"text": event.get("raw_message", "")}}]
        content_parts: list[str] = []
        attachments: list[dict[str, str | None]] = []
        for index, segment in enumerate(segments):
            if not isinstance(segment, dict):
                continue
            segment_type = str(segment.get("type", ""))
            data = segment.get("data") if isinstance(segment.get("data"), dict) else {}
            if segment_type == "text":
                content_parts.append(str(data.get("text", "")))
            elif segment_type == "at":
                content_parts.append(f"@{data.get('qq', 'unknown')}")
            elif segment_type == "reply":
                content_parts.append(f"[回复 {data.get('id', '')}]".rstrip())
            elif segment_type in self.attachment_types:
                url = str(data.get("url") or "")
                parsed = urlsplit(url)
                placeholder = {
                    "image": "[图片]",
                    "file": "[文件]",
                    "record": "[语音]",
                    "video": "[视频]",
                }[segment_type]
                content_parts.append(placeholder)
                if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
                    continue
                file_name = str(
                    data.get("file_name")
                    or data.get("name")
                    or data.get("file")
                    or f"{segment_type}-{index}"
                )
                stable_id = data.get("file_id") or data.get("file")
                attachments.append(
                    {
                        "external_id": self._attachment_id(
                            message_id, index, file_name, url, stable_id
                        ),
                        "file_name": file_name,
                        "file_type": data.get("mime_type"),
                        "file_url": url,
                    }
                )
        content = "".join(content_parts).strip()
        event_time = event.get("time")
        try:
            sent_at = datetime.fromtimestamp(int(event_time), UTC)
        except (TypeError, ValueError, OSError):
            sent_at = datetime.now(UTC)
        return {
            "platform": {"name": "QQ", "type": "IM"},
            "channel": {
                "external_id": channel_external_id,
                "name": str(channel_name),
                "channel_type": channel_type,
            },
            "messages": [
                {
                    "external_id": message_id,
                    "sender": {
                        "external_id": user_id,
                        "display_name": str(display_name),
                        "source_type": "UNKNOWN",
                    },
                    "content": content,
                    "sent_at": sent_at.isoformat().replace("+00:00", "Z"),
                    "attachments": attachments,
                }
            ],
        }


class UniBriefBridgeClient:
    """Hold one normal-user Cookie/CSRF session and call the import API."""

    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.username = username
        self.password = password
        self.csrf_token: str | None = None
        self.client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=30)

    async def close(self) -> None:
        """Close the bridge HTTP client."""

        await self.client.aclose()

    async def login(self) -> None:
        """Establish the bound normal-user UniBrief session."""

        response = await self.client.post(
            "/api/v1/auth/login",
            json={"username": self.username, "password": self.password},
        )
        response.raise_for_status()
        self.csrf_token = self.client.cookies.get("unibrief_csrf")
        if not self.csrf_token:
            raise RuntimeError("UniBrief login did not return a CSRF cookie")
        logger.info("UniBrief normal-user session established for %s", self.username)

    async def import_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Submit one mapped batch with CSRF and session recovery."""

        if not self.csrf_token:
            await self.login()
        response = await self.client.post(
            "/api/v1/messages/import",
            headers={"X-CSRF-Token": self.csrf_token or ""},
            json=payload,
        )
        if response.status_code == 401:
            self.csrf_token = None
            await self.login()
            response = await self.client.post(
                "/api/v1/messages/import",
                headers={"X-CSRF-Token": self.csrf_token or ""},
                json=payload,
            )
        response.raise_for_status()
        return response.json()


class NapCatBridge:
    """Consume OneBot WebSocket events with bounded batches and reconnect backoff."""

    def __init__(self, password: str, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.adapter = NapCatOneBotAdapter()
        self.api = UniBriefBridgeClient(
            self.settings.unibrief_base_url,
            self.settings.unibrief_username,
            password,
        )
        self.pending: dict[tuple[str, str], dict[str, Any]] = {}

    def _enqueue(self, payload: dict[str, Any]) -> None:
        channel = payload["channel"]
        key = (payload["platform"]["name"], channel["external_id"])
        existing = self.pending.get(key)
        if existing is None:
            self.pending[key] = payload
        else:
            existing["messages"].extend(payload["messages"])

    async def _flush(self, *, force: bool = False) -> None:
        for key, payload in list(self.pending.items()):
            if not force and len(payload["messages"]) < self.settings.napcat_import_batch_size:
                continue
            result = await self.api.import_payload(payload)
            logger.info(
                "NapCat import channel=%s received=%s inserted=%s duplicates=%s failed=%s",
                key[1],
                result.get("received", 0),
                result.get("inserted", 0),
                result.get("duplicates", 0),
                result.get("failed", 0),
            )
            del self.pending[key]

    async def _consume_connection(self) -> None:
        headers = None
        if self.settings.napcat_access_token:
            headers = {"Authorization": f"Bearer {self.settings.napcat_access_token}"}
        async with websockets.connect(
            self.settings.napcat_ws_url,
            additional_headers=headers,
            max_size=2 * 1024 * 1024,
            ping_timeout=self.settings.napcat_heartbeat_timeout_seconds,
        ) as websocket:
            logger.info("Connected to NapCat WebSocket host")
            while True:
                try:
                    raw = await asyncio.wait_for(
                        websocket.recv(), timeout=self.settings.napcat_import_flush_seconds
                    )
                except TimeoutError:
                    await self._flush(force=True)
                    continue
                event = json.loads(raw)
                if not isinstance(event, dict):
                    continue
                payload = self.adapter.map_event(event)
                if payload is None:
                    continue
                self._enqueue(payload)
                await self._flush()

    async def run(self) -> None:
        """Reconnect indefinitely using a capped 1/2/5/10/30-second schedule."""

        if not self.settings.napcat_enabled:
            raise RuntimeError("NAPCAT_ENABLED=false; bridge will not connect")
        if not self.settings.unibrief_username:
            raise RuntimeError("UNIBRIEF_USERNAME is required")
        backoff = [1, 2, 5, 10, self.settings.napcat_reconnect_max_seconds]
        attempt = 0
        try:
            await self.api.login()
            while True:
                try:
                    await self._consume_connection()
                    attempt = 0
                except asyncio.CancelledError:
                    raise
                except (OSError, httpx.HTTPError, websockets.WebSocketException, ValueError):
                    delay = backoff[min(attempt, len(backoff) - 1)]
                    attempt += 1
                    logger.warning("NapCat bridge disconnected; retrying in %s seconds", delay)
                    await asyncio.sleep(delay)
        finally:
            await self._flush(force=True)
            await self.api.close()
