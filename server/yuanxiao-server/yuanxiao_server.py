#!/usr/bin/env python3
"""HTTPS relay for the YuanXiao Android MVP."""

from __future__ import annotations

import json
import ipaddress
import os
import queue
import uuid
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


HOST = os.environ.get("YUANXIAO_HOST", "")
PORT = int(os.environ.get("YUANXIAO_PORT", "443"))
CERT_FILE = Path(os.environ.get("YUANXIAO_CERT_FILE", "/opt/yuanxiao/certs/server.crt"))
KEY_FILE = Path(os.environ.get("YUANXIAO_KEY_FILE", "/opt/yuanxiao/certs/server.key"))
HERMES_BRIDGE_URL = os.environ.get("YUANXIAO_HERMES_BRIDGE_URL", "http://localhost:18642/api/chat")
HERMES_BRIDGE_TIMEOUT_SECONDS = int(os.environ.get("YUANXIAO_HERMES_BRIDGE_TIMEOUT_SECONDS", "900"))
MAX_REQUEST_BYTES = int(os.environ.get("YUANXIAO_MAX_REQUEST_BYTES", "6000000"))
KEEPALIVE_INTERVAL_SECONDS = int(os.environ.get("YUANXIAO_KEEPALIVE_INTERVAL_SECONDS", "10"))
TLS_HANDSHAKE_TIMEOUT_SECONDS = int(os.environ.get("YUANXIAO_TLS_HANDSHAKE_TIMEOUT_SECONDS", "5"))
REQUEST_SOCKET_TIMEOUT_SECONDS = int(os.environ.get("YUANXIAO_REQUEST_SOCKET_TIMEOUT_SECONDS", "960"))
INBOX_FILE = Path(os.environ.get("YUANXIAO_INBOX_FILE", "/opt/yuanxiao/data/app_inbox.jsonl"))
MAX_INBOX_MESSAGES = int(os.environ.get("YUANXIAO_MAX_INBOX_MESSAGES", "200"))
ADMIN_TOKEN = os.environ.get("YUANXIAO_ADMIN_TOKEN", "").strip()
INBOX_LOCK = threading.Lock()
ASYNC_CHAT_DEFAULT = os.environ.get("YUANXIAO_ASYNC_CHAT_DEFAULT", "1").strip().lower() not in {"0", "false", "no"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log_event(event: str, **fields: object) -> None:
    payload = {"time": now_iso(), "event": event, **fields}
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def load_inbox_messages() -> list[dict[str, object]]:
    if not INBOX_FILE.exists():
        return []
    messages: list[dict[str, object]] = []
    with INBOX_FILE.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                messages.append(item)
    return messages[-MAX_INBOX_MESSAGES:]


def save_inbox_messages(messages: list[dict[str, object]]) -> None:
    INBOX_FILE.parent.mkdir(parents=True, exist_ok=True)
    recent = messages[-MAX_INBOX_MESSAGES:]
    tmp_path = INBOX_FILE.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        for item in recent:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    tmp_path.replace(INBOX_FILE)


def append_inbox_message(payload: dict[str, object]) -> dict[str, object]:
    text = str(payload.get("text") or payload.get("message") or "").strip()
    images = payload.get("images") if isinstance(payload.get("images"), list) else []
    files = payload.get("files") if isinstance(payload.get("files"), list) else []
    attachments = payload.get("attachments") if isinstance(payload.get("attachments"), list) else []
    links = payload.get("links") if isinstance(payload.get("links"), list) else []
    if not text and not images and not files and not attachments and not links:
        raise ValueError("empty_message")
    message = {
        "id": f"msg_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}",
        "speaker": str(payload.get("speaker") or "嫦娥"),
        "text": text,
        "conversation": str(payload.get("conversation") or "yuanxiao-app"),
        "created_at": now_iso(),
        "source": str(payload.get("source") or "change"),
        "format": str(payload.get("format") or "markdown"),
    }
    if payload.get("task_id"):
        message["task_id"] = str(payload.get("task_id") or "")
    if images:
        message["images"] = images
    if files:
        message["files"] = files
    if attachments:
        message["attachments"] = attachments
    if links:
        message["links"] = links
    with INBOX_LOCK:
        messages = load_inbox_messages()
        messages.append(message)
        save_inbox_messages(messages)
    return message


def inbox_messages_after(after_id: str, limit: int) -> list[dict[str, object]]:
    with INBOX_LOCK:
        messages = load_inbox_messages()
    if after_id:
        for index, item in enumerate(messages):
            if str(item.get("id") or "") == after_id:
                return messages[index + 1:index + 1 + limit]
    return messages[-limit:]


def payload_bool(payload: dict[str, object], key: str, default: bool) -> bool:
    if key not in payload:
        return default
    value = payload.get(key)
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def normalized_chat_target(payload: dict[str, object], has_image: bool) -> str:
    if has_image:
        return "codex"
    target = str(payload.get("target") or payload.get("route") or "hermes").strip().lower()
    return "codex" if target == "codex" else "hermes"


def should_run_chat_async(payload: dict[str, object], has_image: bool) -> bool:
    if not payload_bool(payload, "async", ASYNC_CHAT_DEFAULT):
        return False
    if has_image:
        return True
    if str(payload.get("codex_session_id") or "").strip():
        return True
    return normalized_chat_target(payload, has_image) == "codex"


def new_chat_task_id() -> str:
    return f"chat_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"


def forward_to_hermes_bridge(payload: dict[str, object], conversation: str) -> tuple[int, dict[str, object]]:
    forward_payload = {
        "message": str(payload.get("message") or ""),
        "conversation": conversation,
    }
    for key in ("target", "route", "codex_session_id", "task_id", "image_base64", "image_mime_type", "image_name"):
        if payload.get(key):
            forward_payload[key] = payload[key]
    request = urllib.request.Request(
        HERMES_BRIDGE_URL,
        data=json.dumps(forward_payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=HERMES_BRIDGE_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
            return int(response.status), data
    except urllib.error.HTTPError as exc:
        try:
            data = json.loads(exc.read().decode("utf-8"))
        except Exception:
            data = {"status": "error", "error": "hermes_bridge_http_error", "detail": f"HTTP {exc.code}"}
        return int(exc.code), data


def bridge_url_for(path: str, query: str = "") -> str:
    parsed = urllib.parse.urlparse(HERMES_BRIDGE_URL)
    rebuilt = parsed._replace(path=path, query=query, params="", fragment="")
    return urllib.parse.urlunparse(rebuilt)


def forward_bridge_get(path: str, query: str = "") -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(
        bridge_url_for(path, query),
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            return int(response.status), data
    except urllib.error.HTTPError as exc:
        try:
            data = json.loads(exc.read().decode("utf-8"))
        except Exception:
            data = {"status": "error", "error": "bridge_http_error", "detail": f"HTTP {exc.code}"}
        return int(exc.code), data


def forward_bridge_post(path: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(
        bridge_url_for(path),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=HERMES_BRIDGE_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
            return int(response.status), data
    except urllib.error.HTTPError as exc:
        try:
            data = json.loads(exc.read().decode("utf-8"))
        except Exception:
            data = {"status": "error", "error": "bridge_http_error", "detail": f"HTTP {exc.code}"}
        return int(exc.code), data


class YuanXiaoHandler(BaseHTTPRequestHandler):
    server_version = "YuanXiao/0.4"
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/health":
            self._send_json(
                {
                    "status": "ok",
                    "service": "yuanxiao",
                    "server": "change",
                    "mode": "hermes-relay-vision",
                    "text_routes": ["hermes", "codex"],
                    "default_text_route": "hermes",
                    "image_recognition": "change-vision",
                    "inbox": True,
                    "codex_session_create": True,
                    "codex_session_rename": True,
                    "plan_view": True,
                    "plan_agent_create": True,
                    "plan_project_create": True,
                    "plan_ceo_request": True,
                    "plan_ceo_session": True,
                    "plan_reporting_policy": "change_only",
                    "task_queue": True,
                    "task_queue_scope": "session_chat",
                    "task_ledger": True,
                    "stuck_task_detection": True,
                    "task_events_api": True,
                    "task_agents_api": True,
                    "queue_reorder": "queued_only",
                    "async_chat_default": ASYNC_CHAT_DEFAULT,
                    "bridge_timeout_seconds": HERMES_BRIDGE_TIMEOUT_SECONDS,
                    "request_socket_timeout_seconds": REQUEST_SOCKET_TIMEOUT_SECONDS,
                    "max_request_bytes": MAX_REQUEST_BYTES,
                    "time": now_iso(),
                }
            )
            return
        if parsed.path == "/api/inbox":
            query = urllib.parse.parse_qs(parsed.query)
            after_id = str((query.get("after") or [""])[0]).strip()
            try:
                limit = max(1, min(50, int((query.get("limit") or ["20"])[0])))
            except ValueError:
                limit = 20
            messages = inbox_messages_after(after_id, limit)
            self._send_json(
                {
                    "status": "ok",
                    "messages": messages,
                    "next_cursor": str(messages[-1].get("id") or "") if messages else after_id,
                    "server": "change",
                    "time": now_iso(),
                }
            )
            return
        if parsed.path == "/api/codex/sessions":
            try:
                status, response = forward_bridge_get("/api/codex/sessions", parsed.query)
            except Exception as exc:
                self._send_json(
                    {
                        "status": "error",
                        "error": "codex_dashboard_unavailable",
                        "detail": str(exc),
                        "server": "change",
                        "time": now_iso(),
                    },
                    status=504,
                )
                return
            response["server"] = "change"
            response.setdefault("time", now_iso())
            self._send_json(response, status=status)
            return
        if parsed.path == "/api/plan/projects":
            try:
                status, response = forward_bridge_get("/api/plan/projects", parsed.query)
            except Exception as exc:
                self._send_json(
                    {
                        "status": "error",
                        "error": "plan_view_unavailable",
                        "detail": str(exc),
                        "server": "change",
                        "time": now_iso(),
                    },
                    status=504,
                )
                return
            response["server"] = "change"
            response.setdefault("time", now_iso())
            self._send_json(response, status=status)
            return
        if parsed.path == "/api/queue/tasks":
            try:
                status, response = forward_bridge_get("/api/queue/tasks", parsed.query)
            except Exception as exc:
                self._send_json(
                    {
                        "status": "error",
                        "error": "queue_view_unavailable",
                        "detail": str(exc),
                        "server": "change",
                        "time": now_iso(),
                    },
                    status=504,
                )
                return
            response["server"] = "change"
            response.setdefault("time", now_iso())
            self._send_json(response, status=status)
            return
        if parsed.path in {"/api/v1/tasks", "/api/tasks", "/api/v1/events", "/api/events", "/api/v1/agents", "/api/agents"}:
            try:
                status, response = forward_bridge_get(parsed.path, parsed.query)
            except Exception as exc:
                self._send_json(
                    {
                        "status": "error",
                        "error": "task_ledger_unavailable",
                        "detail": str(exc),
                        "server": "change",
                        "time": now_iso(),
                    },
                    status=504,
                )
                return
            response["server"] = "change"
            response.setdefault("time", now_iso())
            self._send_json(response, status=status)
            return
        if parsed.path == "/api/codex/session/messages":
            try:
                status, response = forward_bridge_get("/api/codex/session/messages", parsed.query)
            except Exception as exc:
                self._send_json(
                    {
                        "status": "error",
                        "error": "codex_session_history_unavailable",
                        "detail": str(exc),
                        "server": "change",
                        "time": now_iso(),
                    },
                    status=504,
                )
                return
            response["server"] = "change"
            response.setdefault("time", now_iso())
            self._send_json(response, status=status)
            return
        self._send_json({"error": "not_found"}, status=404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/inbox/admin":
            if not self._is_admin_request():
                self._send_json({"error": "forbidden"}, status=403)
                return
            try:
                payload = self._read_json_payload()
                message = append_inbox_message(payload)
            except ValueError:
                self._send_json({"error": "empty_message"}, status=400)
                return
            except Exception as exc:
                self._send_json({"error": "inbox_write_failed", "detail": str(exc)}, status=500)
                return
            self._send_json({"status": "ok", "message": message, "server": "change", "time": now_iso()})
            return

        if parsed.path in {
            "/api/codex/session/create",
            "/api/codex/session/rename",
            "/api/plan/agent/create",
            "/api/plan/project/create",
            "/api/plan/ceo/request",
            "/api/plan/ceo/session",
            "/api/queue/reorder",
            "/api/v1/tasks",
        }:
            try:
                payload = self._read_json_payload()
            except ValueError as exc:
                error = str(exc)
                if error == "payload_too_large":
                    self._send_json({"error": "payload_too_large"}, status=413)
                else:
                    self._send_json({"error": "invalid_json"}, status=400)
                return
            self._send_bridge_post_keepalive(parsed.path, payload)
            return

        if parsed.path != "/api/chat":
            self._send_json({"error": "not_found"}, status=404)
            return

        try:
            payload = self._read_json_payload()
        except ValueError as exc:
            error = str(exc)
            if error == "payload_too_large":
                self._send_json({"error": "payload_too_large"}, status=413)
            else:
                self._send_json({"error": "invalid_json"}, status=400)
            return

        message = str(payload.get("message") or "").strip()
        has_image = bool(str(payload.get("image_base64") or "").strip())
        if not message and not has_image:
            self._send_json({"error": "empty_message"}, status=400)
            return
        conversation = str(payload.get("conversation") or "yuanxiao-app").strip() or "yuanxiao-app"
        if should_run_chat_async(payload, has_image):
            self._send_bridge_response_async(payload, conversation, message)
            return
        self._send_bridge_response_keepalive(payload, conversation, message)

    def _read_json_payload(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length") or "0")
        if length > MAX_REQUEST_BYTES:
            raise ValueError("payload_too_large")

        try:
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body or "{}")
        except Exception:
            raise ValueError("invalid_json")
        if not isinstance(payload, dict):
            raise ValueError("invalid_json")
        return payload

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}", flush=True)

    def _is_admin_request(self) -> bool:
        client_ip = self.client_address[0] if self.client_address else ""
        try:
            if ipaddress.ip_address(client_ip).is_loopback:
                return True
        except ValueError:
            pass
        supplied = self.headers.get("X-YuanXiao-Admin-Token", "").strip()
        return bool(ADMIN_TOKEN and supplied and supplied == ADMIN_TOKEN)

    def _send_bridge_response_async(
        self,
        payload: dict[str, object],
        conversation: str,
        message: str,
    ) -> None:
        task_id = new_chat_task_id()
        client_ip = self.client_address[0] if self.client_address else ""
        target = normalized_chat_target(payload, bool(str(payload.get("image_base64") or "").strip()))
        codex_session_id = str(payload.get("codex_session_id") or "").strip()
        started = time.monotonic()
        log_event(
            "chat_async_accepted",
            task_id=task_id,
            client_ip=client_ip,
            target=target,
            codex_session_id=codex_session_id,
            conversation=conversation,
            message_chars=len(message),
            has_image=bool(str(payload.get("image_base64") or "").strip()),
        )

        def worker() -> None:
            try:
                forward_payload = dict(payload)
                forward_payload["task_id"] = task_id
                status, response = forward_to_hermes_bridge(forward_payload, conversation)
            except Exception as exc:
                status, response = (
                    504,
                    {
                        "status": "error",
                        "error": "hermes_bridge_unavailable",
                        "detail": str(exc),
                        "reply": "嫦娥后台处理这次请求时没有拿到回复，请稍后重试。",
                        "time": now_iso(),
                    },
                )
            response["task_id"] = task_id
            response["server"] = "change"
            response["upstream_status"] = status
            response.setdefault("received", message)
            response.setdefault("time", now_iso())
            response.setdefault("relay_duration_ms", int((time.monotonic() - started) * 1000))
            self._enqueue_async_chat_reply(payload, conversation, status, response, started, reason="async_complete")
            log_event(
                "chat_async_finish",
                task_id=task_id,
                target=target,
                codex_session_id=codex_session_id,
                conversation=conversation,
                upstream_status=status,
                duration_ms=response.get("relay_duration_ms"),
                error=response.get("error", ""),
            )

        threading.Thread(target=worker, daemon=True).start()
        reply = "嫦娥已收到，已转入后台处理；完成后会在元宵里通知。"
        if codex_session_id:
            reply = "嫦娥已收到，已转入后台处理；完成后会提醒你回到这个 Codex session 查看。"
        elif str(payload.get("image_base64") or "").strip():
            reply = "嫦娥已收到图片，识图已转入后台处理；完成后会在元宵里通知。"
        self._send_json(
            {
                "status": "ok",
                "async": True,
                "task_id": task_id,
                "source": "change-async-chat",
                "target": target,
                "route": target,
                "capability": "async-chat",
                "received": message,
                "received_image": bool(str(payload.get("image_base64") or "").strip()),
                "reply": reply,
                "conversation": conversation,
                "codex_session_id": codex_session_id if target == "codex" else "",
                "time": now_iso(),
            }
        )

    def _send_bridge_response_keepalive(
        self,
        payload: dict[str, object],
        conversation: str,
        message: str,
    ) -> None:
        result_queue: queue.Queue[tuple[int, dict[str, object]]] = queue.Queue(maxsize=1)

        def worker() -> None:
            try:
                result_queue.put(forward_to_hermes_bridge(payload, conversation))
            except Exception as exc:
                result_queue.put(
                    (
                        504,
                        {
                            "status": "error",
                            "error": "hermes_bridge_unavailable",
                            "detail": str(exc),
                            "reply": "嫦娥暂时没有返回，请稍后重试。",
                            "time": now_iso(),
                        },
                    )
                )

        threading.Thread(target=worker, daemon=True).start()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Transfer-Encoding", "chunked")
        self.send_header("Connection", "close")
        self.end_headers()

        started = time.monotonic()
        client_ip = self.client_address[0] if self.client_address else ""
        log_event(
            "chat_start",
            client_ip=client_ip,
            target=str(payload.get("target") or payload.get("route") or ""),
            codex_session_id=str(payload.get("codex_session_id") or ""),
            conversation=conversation,
            message_chars=len(message),
            has_image=bool(str(payload.get("image_base64") or "").strip()),
        )
        client_connected = True
        while True:
            try:
                status, response = result_queue.get(timeout=KEEPALIVE_INTERVAL_SECONDS)
                break
            except queue.Empty:
                if client_connected:
                    try:
                        self._write_chunk(b"\n")
                    except (BrokenPipeError, ConnectionResetError, ssl.SSLError, OSError) as exc:
                        client_connected = False
                        log_event(
                            "chat_client_disconnected",
                            client_ip=client_ip,
                            target=str(payload.get("target") or payload.get("route") or ""),
                            codex_session_id=str(payload.get("codex_session_id") or ""),
                            conversation=conversation,
                            duration_ms=int((time.monotonic() - started) * 1000),
                            detail=exc.__class__.__name__,
                        )

        response["server"] = "change"
        response["upstream_status"] = status
        response.setdefault("received", message)
        response.setdefault("time", now_iso())
        response.setdefault("relay_duration_ms", int((time.monotonic() - started) * 1000))
        log_event(
            "chat_finish",
            client_ip=client_ip,
            upstream_status=status,
            target=str(payload.get("target") or payload.get("route") or ""),
            codex_session_id=str(payload.get("codex_session_id") or ""),
            duration_ms=response.get("relay_duration_ms"),
            error=response.get("error", ""),
        )
        if not client_connected:
            self._enqueue_async_chat_reply(payload, conversation, status, response, started, reason="client_disconnected")
            return
        try:
            self._write_chunk(json.dumps(response, ensure_ascii=False).encode("utf-8"))
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ssl.SSLError, OSError):
            self._enqueue_async_chat_reply(payload, conversation, status, response, started, reason="final_write_failed")
            return

    def _enqueue_async_chat_reply(
        self,
        payload: dict[str, object],
        conversation: str,
        status: int,
        response: dict[str, object],
        started: float,
        *,
        reason: str,
    ) -> None:
        reply = str(response.get("reply") or "").strip()
        if not reply:
            detail = str(response.get("detail") or response.get("error") or "unknown_error")
            reply = f"嫦娥处理这次请求时没有拿到完整回复：{detail}"
        codex_session_id = str(payload.get("codex_session_id") or "").strip()
        if codex_session_id and int(status) < 400:
            reply = "Codex session 后台回复已完成，请打开对应会话查看最新内容。"
        elif codex_session_id:
            reply = f"Codex session 后台请求失败：{reply}"
        inbox_payload: dict[str, object] = {
            "speaker": "嫦娥",
            "text": reply,
            "conversation": conversation,
            "source": "change-async-chat",
            "format": "markdown",
        }
        if response.get("task_id"):
            inbox_payload["task_id"] = response.get("task_id")
        for key in ("images", "files", "attachments", "links"):
            value = response.get(key)
            if isinstance(value, list) and value and not codex_session_id:
                inbox_payload[key] = value
        try:
            message = append_inbox_message(inbox_payload)
            log_event(
                "chat_async_inbox_queued",
                reason=reason,
                target=str(payload.get("target") or payload.get("route") or ""),
                codex_session_id=str(payload.get("codex_session_id") or ""),
                conversation=conversation,
                upstream_status=status,
                inbox_id=str(message.get("id") or ""),
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        except Exception as exc:
            log_event(
                "chat_async_inbox_failed",
                reason=reason,
                target=str(payload.get("target") or payload.get("route") or ""),
                codex_session_id=str(payload.get("codex_session_id") or ""),
                conversation=conversation,
                detail=str(exc),
                duration_ms=int((time.monotonic() - started) * 1000),
            )

    def _send_bridge_post_keepalive(self, path: str, payload: dict[str, object]) -> None:
        result_queue: queue.Queue[tuple[int, dict[str, object]]] = queue.Queue(maxsize=1)

        def worker() -> None:
            try:
                result_queue.put(forward_bridge_post(path, payload))
            except Exception as exc:
                result_queue.put(
                    (
                        504,
                        {
                            "status": "error",
                            "error": "bridge_unavailable",
                            "detail": str(exc),
                            "time": now_iso(),
                        },
                    )
                )

        threading.Thread(target=worker, daemon=True).start()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Transfer-Encoding", "chunked")
        self.send_header("Connection", "close")
        self.end_headers()

        started = time.monotonic()
        while True:
            try:
                status, response = result_queue.get(timeout=KEEPALIVE_INTERVAL_SECONDS)
                break
            except queue.Empty:
                try:
                    self._write_chunk(b"\n")
                except (BrokenPipeError, ConnectionResetError, ssl.SSLError, OSError):
                    return

        response["server"] = "change"
        response["upstream_status"] = status
        response.setdefault("time", now_iso())
        response.setdefault("relay_duration_ms", int((time.monotonic() - started) * 1000))
        try:
            self._write_chunk(json.dumps(response, ensure_ascii=False).encode("utf-8"))
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ssl.SSLError, OSError):
            return

    def _write_chunk(self, data: bytes) -> None:
        self.wfile.write(f"{len(data):X}\r\n".encode("ascii"))
        self.wfile.write(data)
        self.wfile.write(b"\r\n")
        self.wfile.flush()

    def _send_json(self, payload: dict[str, object], *, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)
        self.close_connection = True


class YuanXiaoHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = int(os.environ.get("YUANXIAO_REQUEST_QUEUE_SIZE", "128"))

    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        tls_context: ssl.SSLContext,
    ) -> None:
        self.tls_context = tls_context
        super().__init__(server_address, handler_class)

    def get_request(self) -> tuple[object, tuple[str, int]]:
        request, client_address = super().get_request()
        request.settimeout(TLS_HANDSHAKE_TIMEOUT_SECONDS)
        return request, client_address

    def process_request_thread(self, request: object, client_address: tuple[str, int]) -> None:
        tls_request = None
        try:
            tls_request = self.tls_context.wrap_socket(request, server_side=True)
            tls_request.settimeout(REQUEST_SOCKET_TIMEOUT_SECONDS)
            self.finish_request(tls_request, client_address)
        except (TimeoutError, ssl.SSLError, OSError):
            pass
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(tls_request or request)


def main() -> int:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile=str(CERT_FILE), keyfile=str(KEY_FILE))
    httpd = YuanXiaoHTTPServer((HOST, PORT), YuanXiaoHandler, context)
    print(f"yuanxiao server listening on https://{HOST}:{PORT}", flush=True)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
