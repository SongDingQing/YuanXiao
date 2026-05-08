#!/usr/bin/env python3
"""Local YuanXiao-to-Hermes bridge.

This service stays on the Mac mini and reads the Hermes API key from the local
Hermes env file.  The ChangE relay reaches it only through an SSH reverse
tunnel bound to localhost on both machines.
"""

from __future__ import annotations

import json
import os
import re
import base64
import sqlite3
import subprocess
import threading
import time
import urllib.parse
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


BRIDGE_DIR = Path(os.environ.get("YUANXIAO_BRIDGE_DIR", str(Path(__file__).resolve().parent)))
HOST = os.environ.get("YUANXIAO_BRIDGE_HOST", "localhost")
PORT = int(os.environ.get("YUANXIAO_BRIDGE_PORT", "18765"))
HERMES_BASE_URL = os.environ.get("HERMES_API_BASE_URL", "http://localhost:8642/v1").rstrip("/")
HERMES_ENV_FILE = Path(os.environ.get("HERMES_ENV_FILE", str(Path.home() / ".hermes/.env")))
HERMES_MODEL = os.environ.get("YUANXIAO_HERMES_MODEL", "hermes-agent")
DEFAULT_CONVERSATION = os.environ.get("YUANXIAO_HERMES_CONVERSATION", "yuanxiao-app")
MAX_REQUEST_BYTES = int(os.environ.get("YUANXIAO_BRIDGE_MAX_REQUEST_BYTES", "6000000"))
HERMES_TIMEOUT_SECONDS = int(os.environ.get("YUANXIAO_HERMES_TIMEOUT_SECONDS", "300"))
MAX_IMAGE_BASE64_CHARS = int(os.environ.get("YUANXIAO_MAX_IMAGE_BASE64_CHARS", "4500000"))
CODEX_BIN = os.environ.get("YUANXIAO_CODEX_BIN", "/Applications/Codex.app/Contents/Resources/codex")
CODEX_VISION_MODEL = os.environ.get("YUANXIAO_CODEX_VISION_MODEL", "gpt-5.4-mini")
CODEX_VISION_TIMEOUT_SECONDS = int(os.environ.get("YUANXIAO_CODEX_VISION_TIMEOUT_SECONDS", "240"))
CODEX_CHAT_MODEL = os.environ.get("YUANXIAO_CODEX_CHAT_MODEL", "gpt-5.4")
CODEX_CHAT_TIMEOUT_SECONDS = int(os.environ.get("YUANXIAO_CODEX_CHAT_TIMEOUT_SECONDS", "900"))
CODEX_SESSION_CREATE_MODEL = os.environ.get("YUANXIAO_CODEX_SESSION_CREATE_MODEL", "gpt-5.4-mini")
IMAGE_CACHE_DIR = Path(os.environ.get("YUANXIAO_IMAGE_CACHE_DIR", str(BRIDGE_DIR / "image-cache")))
CODEX_CHAT_CACHE_DIR = Path(os.environ.get("YUANXIAO_CODEX_CHAT_CACHE_DIR", str(BRIDGE_DIR / "codex-chat-cache")))
VISION_SESSION_STATE_FILE = Path(
    os.environ.get("YUANXIAO_VISION_SESSION_STATE_FILE", str(BRIDGE_DIR / "vision-session-state.json"))
)
CODEX_CHAT_SESSION_STATE_FILE = Path(
    os.environ.get("YUANXIAO_CODEX_CHAT_SESSION_STATE_FILE", str(BRIDGE_DIR / "codex-chat-session-state.json"))
)
VISION_SESSION_ENABLED = os.environ.get("YUANXIAO_VISION_SESSION_ENABLED", "1").strip().lower() not in {
    "0",
    "false",
    "no",
}
CODEX_CHAT_SESSION_ENABLED = os.environ.get("YUANXIAO_CODEX_CHAT_SESSION_ENABLED", "1").strip().lower() not in {
    "0",
    "false",
    "no",
}
VISION_SESSION_MAX_REQUESTS = int(os.environ.get("YUANXIAO_VISION_SESSION_MAX_REQUESTS", "20"))
CODEX_CHAT_SESSION_MAX_REQUESTS = int(os.environ.get("YUANXIAO_CODEX_CHAT_SESSION_MAX_REQUESTS", "200"))
CODEX_SESSION_INDEX_FILE = Path(os.environ.get("YUANXIAO_CODEX_SESSION_INDEX", str(Path.home() / ".codex/session_index.jsonl")))
CODEX_VISION_ERR_LOG = Path(os.environ.get("YUANXIAO_CODEX_VISION_ERR_LOG", str(BRIDGE_DIR / "logs/codex-vision.err.log")))
CODEX_SESSIONS_DIR = Path(os.environ.get("YUANXIAO_CODEX_SESSIONS_DIR", str(Path.home() / ".codex/sessions")))
CODEX_STATE_DB = Path(os.environ.get("YUANXIAO_CODEX_STATE_DB", str(Path.home() / ".codex/state_5.sqlite")))
CODEX_SESSION_ID_RE = re.compile(r"rollout-.*-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$")
CODEX_THREAD_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
MAX_CODEX_SESSION_TITLE_CHARS = int(os.environ.get("YUANXIAO_MAX_CODEX_SESSION_TITLE_CHARS", "80"))
MAX_CODEX_SESSION_MESSAGES = int(os.environ.get("YUANXIAO_MAX_CODEX_SESSION_MESSAGES", "200"))
MAX_CODEX_SESSION_MESSAGE_CHARS = int(os.environ.get("YUANXIAO_MAX_CODEX_SESSION_MESSAGE_CHARS", "12000"))
MAX_CODEX_SESSION_PREVIEW_CHARS = int(os.environ.get("YUANXIAO_MAX_CODEX_SESSION_PREVIEW_CHARS", "96"))
MAX_CODEX_SESSION_PREVIEW_TAIL_BYTES = int(os.environ.get("YUANXIAO_MAX_CODEX_SESSION_PREVIEW_TAIL_BYTES", "196608"))
CODEX_SESSION_MESSAGE_CACHE: dict[str, dict[str, Any]] = {}
CODEX_SESSION_MESSAGE_CACHE_LOCK = threading.Lock()
BRIDGE_REQUEST_LOG = Path(os.environ.get("YUANXIAO_BRIDGE_REQUEST_LOG", str(BRIDGE_DIR / "logs/bridge-requests.jsonl")))
BRIDGE_REQUEST_LOG_MAX_BYTES = int(os.environ.get("YUANXIAO_BRIDGE_REQUEST_LOG_MAX_BYTES", "1048576"))
PLAN_STATE_FILE = Path(os.environ.get("YUANXIAO_PLAN_STATE_FILE", str(Path.home() / ".yuanxiao/plan-state.json")))
MAX_PLAN_PROJECTS = int(os.environ.get("YUANXIAO_MAX_PLAN_PROJECTS", "50"))
PLAN_STATE_CACHE: dict[str, Any] = {}
PLAN_STATE_CACHE_LOCK = threading.Lock()
PLAN_STATE_LOCK = threading.Lock()
CODEX_HANDOFF_QUEUE_DIR = Path(
    os.environ.get("YUANXIAO_CODEX_HANDOFF_QUEUE_DIR", str(Path.home() / ".hermes/codex-handoff/queue"))
)
MAX_QUEUE_TASKS = int(os.environ.get("YUANXIAO_MAX_QUEUE_TASKS", "50"))
QUEUE_TERMINAL_STATUSES = {"completed", "failed", "canceled", "cancelled"}
QUEUE_LOCK = threading.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def iso_from_epoch_ms(value: Any) -> str:
    try:
        millis = int(value or 0)
    except (TypeError, ValueError):
        return ""
    if millis <= 0:
        return ""
    return datetime.fromtimestamp(millis / 1000, timezone.utc).isoformat(timespec="seconds")


def iso_from_epoch_seconds(value: Any) -> str:
    try:
        seconds = float(value or 0)
    except (TypeError, ValueError):
        return ""
    if seconds <= 0:
        return ""
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat(timespec="seconds")


def compact_path(path: str) -> str:
    home = str(Path.home())
    if path.startswith(home):
        return "~" + path[len(home):]
    return path


def compact_preview_text(text: str, limit: int = MAX_CODEX_SESSION_PREVIEW_CHARS) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(value) <= limit:
        return value
    return value[: max(1, limit - 1)].rstrip() + "…"


def compact_queue_text(text: str, limit: int = 160) -> str:
    return compact_preview_text(str(text or ""), limit)


def bounded_plan_text(text: Any, limit: int = 240) -> str:
    return compact_preview_text(str(text or ""), limit)


def normalized_progress(value: Any) -> int:
    try:
        progress = float(value or 0)
    except (TypeError, ValueError):
        progress = 0
    if 0 < progress <= 1:
        progress *= 100
    return max(0, min(100, int(round(progress))))


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def normalize_plan_person(raw: Any, default_name: str = "未命名") -> dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}
    status = str(raw.get("status") or "queued").strip().lower() or "queued"
    return {
        "id": str(raw.get("id") or raw.get("session_id") or uuid.uuid4().hex[:8]),
        "name": str(raw.get("name") or raw.get("title") or default_name).strip() or default_name,
        "role": str(raw.get("role") or "").strip(),
        "session_id": str(raw.get("session_id") or "").strip(),
        "status": status,
        "progress": normalized_progress(raw.get("progress", raw.get("progress_percent", 0))),
        "current_task": compact_preview_text(str(raw.get("current_task") or ""), 120),
        "last_report": compact_preview_text(str(raw.get("last_report") or raw.get("report") or ""), 160),
        "updated_at": str(raw.get("updated_at") or "").strip(),
    }


def read_plan_projects(limit: int = 30) -> dict[str, Any]:
    normalized_limit = max(1, min(MAX_PLAN_PROJECTS, limit))
    if not PLAN_STATE_FILE.exists():
        return {
            "status": "ok",
            "projects": [],
            "summary": {
                "project_count": 0,
                "agent_count": 0,
                "active_agents": 0,
                "blocked_agents": 0,
            },
            "updated_at": "",
            "state_file": compact_path(str(PLAN_STATE_FILE)),
            "quota_cost": "none_file_scan_only",
            "scan_cost": "missing_state_file",
            "time": now_iso(),
        }
    try:
        stat = PLAN_STATE_FILE.stat()
        cache_key = f"{PLAN_STATE_FILE}:{stat.st_mtime_ns}:{stat.st_size}:{normalized_limit}"
        with PLAN_STATE_CACHE_LOCK:
            cached_key = str(PLAN_STATE_CACHE.get("key") or "")
            cached_payload = PLAN_STATE_CACHE.get("payload")
            if cached_key == cache_key and isinstance(cached_payload, dict):
                return {**cached_payload, "scan_cost": "cache_hit", "time": now_iso()}
    except Exception:
        cache_key = ""
    try:
        data = json.loads(PLAN_STATE_FILE.read_text(encoding="utf-8") or "{}")
    except Exception as exc:
        return {
            "status": "error",
            "error": "plan_state_read_failed",
            "detail": str(exc),
            "projects": [],
            "summary": {
                "project_count": 0,
                "agent_count": 0,
                "active_agents": 0,
                "blocked_agents": 0,
            },
            "quota_cost": "none_file_scan_only",
            "scan_cost": "read_error",
            "time": now_iso(),
        }

    raw_projects = data.get("projects") if isinstance(data.get("projects"), list) else []
    projects: list[dict[str, Any]] = []
    agent_count = 0
    active_agents = 0
    blocked_agents = 0
    for index, raw_project in enumerate(raw_projects[:normalized_limit]):
        if not isinstance(raw_project, dict):
            continue
        agents = [
            normalize_plan_person(agent, f"Agent {agent_index + 1}")
            for agent_index, agent in enumerate(raw_project.get("agents") if isinstance(raw_project.get("agents"), list) else [])
        ]
        agent_count += len(agents)
        active_agents += sum(1 for agent in agents if agent.get("status") in {"active", "running"})
        blocked_agents += sum(1 for agent in agents if agent.get("status") in {"blocked", "failed"})
        project = {
            "id": str(raw_project.get("id") or f"project-{index + 1}"),
            "title": str(raw_project.get("title") or raw_project.get("name") or "未命名项目").strip() or "未命名项目",
            "status": str(raw_project.get("status") or "queued").strip().lower() or "queued",
            "progress": normalized_progress(raw_project.get("progress", raw_project.get("progress_percent", 0))),
            "updated_at": str(raw_project.get("updated_at") or data.get("updated_at") or "").strip(),
            "last_report": compact_preview_text(str(raw_project.get("last_report") or ""), 180),
            "ceo": normalize_plan_person(raw_project.get("ceo"), "CEO"),
            "agents": agents,
        }
        projects.append(project)

    payload = {
        "status": "ok",
        "projects": projects,
        "summary": {
            "project_count": len(projects),
            "agent_count": agent_count,
            "active_agents": active_agents,
            "blocked_agents": blocked_agents,
        },
        "updated_at": str(data.get("updated_at") or "").strip(),
        "state_file": compact_path(str(PLAN_STATE_FILE)),
        "quota_cost": "none_file_scan_only",
        "scan_cost": "file_read",
        "time": now_iso(),
    }
    if cache_key:
        with PLAN_STATE_CACHE_LOCK:
            PLAN_STATE_CACHE["key"] = cache_key
            PLAN_STATE_CACHE["payload"] = payload
    return payload


def load_plan_state_for_write() -> dict[str, Any]:
    if not PLAN_STATE_FILE.exists():
        return {"schema_version": 1, "updated_at": now_iso(), "projects": [], "events": []}
    try:
        data = json.loads(PLAN_STATE_FILE.read_text(encoding="utf-8") or "{}")
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    if not isinstance(data.get("projects"), list):
        data["projects"] = []
    if not isinstance(data.get("events"), list):
        data["events"] = []
    data.setdefault("schema_version", 1)
    data.setdefault("updated_at", now_iso())
    return data


def save_plan_state(state: dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    PLAN_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = PLAN_STATE_FILE.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(PLAN_STATE_FILE)
    with PLAN_STATE_CACHE_LOCK:
        PLAN_STATE_CACHE.clear()


def append_plan_event(state: dict[str, Any], event: str, **fields: Any) -> None:
    events = state.setdefault("events", [])
    if not isinstance(events, list):
        events = []
        state["events"] = events
    events.append({"id": uuid.uuid4().hex[:12], "event": event, "time": now_iso(), **fields})
    del events[:-200]


def default_plan_project(title: str = "元宵测试计划") -> dict[str, Any]:
    return {
        "id": f"plan-{uuid.uuid4().hex[:8]}",
        "title": bounded_plan_text(title or "元宵测试计划", 80),
        "status": "running",
        "progress": 0,
        "last_report": "等待 Agent 汇报。",
        "updated_at": now_iso(),
        "ceo": {
            "id": f"ceo-{uuid.uuid4().hex[:8]}",
            "name": "CEO",
            "role": "CEO",
            "session_id": "",
            "status": "queued",
            "progress": 0,
            "last_report": "",
            "updated_at": now_iso(),
        },
        "agents": [],
    }


def find_writable_plan_project(state: dict[str, Any], project_id: str = "", project_title: str = "") -> tuple[dict[str, Any], bool]:
    projects = state.setdefault("projects", [])
    if not isinstance(projects, list):
        projects = []
        state["projects"] = projects
    wanted = str(project_id or "").strip()
    if wanted:
        for project in projects:
            if isinstance(project, dict) and str(project.get("id") or "") == wanted:
                return project, False
        raise LookupError("plan_project_not_found")
    for project in projects:
        if isinstance(project, dict):
            return project, False
    project = default_plan_project(project_title)
    projects.insert(0, project)
    append_plan_event(state, "project_created_by_yuanxiao", project_id=project["id"], title=project["title"])
    return project, True


def create_plan_agent(payload: dict[str, Any]) -> dict[str, Any]:
    name = bounded_plan_text(payload.get("name") or payload.get("title") or "测试 Agent", 80)
    if not name:
        name = "测试 Agent"
    role = bounded_plan_text(payload.get("role") or "Agent", 60)
    current_task = bounded_plan_text(payload.get("current_task") or payload.get("task") or "等待分配任务。", 180)
    session_id = str(payload.get("session_id") or "").strip()
    status = str(payload.get("status") or "queued").strip().lower() or "queued"
    if status not in {"queued", "running", "active", "waiting", "blocked", "review", "done", "completed"}:
        status = "queued"
    with PLAN_STATE_LOCK:
        state = load_plan_state_for_write()
        project, created_project = find_writable_plan_project(
            state,
            str(payload.get("project_id") or "").strip(),
            str(payload.get("project_title") or "").strip(),
        )
        agents = project.setdefault("agents", [])
        if not isinstance(agents, list):
            agents = []
            project["agents"] = agents
        agent = {
            "id": str(payload.get("agent_id") or f"agent-{uuid.uuid4().hex[:8]}"),
            "name": name,
            "role": role,
            "session_id": session_id,
            "status": status,
            "progress": normalized_progress(payload.get("progress", 0)),
            "current_task": current_task,
            "last_report": bounded_plan_text(payload.get("last_report") or "新 Agent 已创建。", 180),
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        agents.insert(0, agent)
        project["updated_at"] = now_iso()
        if str(project.get("status") or "queued").lower() == "queued":
            project["status"] = "running"
        project["last_report"] = bounded_plan_text(f"{name} 已加入计划。", 180)
        append_plan_event(
            state,
            "agent_created_by_yuanxiao",
            project_id=str(project.get("id") or ""),
            agent_id=agent["id"],
            name=name,
        )
        save_plan_state(state)
    return {
        "status": "ok",
        "source": "plan-state-file",
        "capability": "plan-agent-create",
        "quota_cost": "none_file_update_only",
        "created_project": created_project,
        "project_id": str(project.get("id") or ""),
        "project_title": str(project.get("title") or ""),
        "agent": normalize_plan_person(agent, name),
        "time": now_iso(),
    }


def queue_item_path(queue_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", str(queue_id or "").strip())
    return CODEX_HANDOFF_QUEUE_DIR / f"{safe}.json"


def load_queue_item(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def queue_short_id(queue_id: str) -> str:
    text = str(queue_id or "").strip()
    if not text:
        return ""
    tail = text.rsplit("_", 1)[-1]
    return tail[-8:] if len(tail) >= 8 else text[-8:]


def queue_status_label(status: str) -> str:
    normalized = str(status or "").strip().lower()
    if normalized == "running":
        return "运行中"
    if normalized == "queued":
        return "等待中"
    if normalized in {"canceled", "cancelled"}:
        return "已取消"
    if normalized == "failed":
        return "失败"
    if normalized == "completed":
        return "完成"
    return normalized or "未知"


def queue_sort_key(item: dict[str, Any]) -> tuple[int, int, float, str]:
    status = str(item.get("status") or "").strip().lower()
    status_rank = 0 if status == "running" else 1 if status == "queued" else 2
    position = safe_int(item.get("position"), 9999)
    queued_at = 0.0
    try:
        queued_at = float(item.get("queued_at") or item.get("updated_at") or 0)
    except (TypeError, ValueError):
        queued_at = 0.0
    return status_rank, position, queued_at, str(item.get("queue_id") or "")


def normalize_queue_task(raw: dict[str, Any], path: Path) -> dict[str, Any]:
    queue_id = str(raw.get("queue_id") or path.stem).strip()
    status = str(raw.get("status") or "queued").strip().lower() or "queued"
    task = str(raw.get("task") or raw.get("source_text") or raw.get("task_summary") or "").strip()
    source_text = str(raw.get("source_text") or "").strip()
    return {
        "queue_id": queue_id,
        "short_id": queue_short_id(queue_id),
        "status": status,
        "status_label": queue_status_label(status),
        "position": safe_int(raw.get("position"), 0),
        "task_summary": compact_queue_text(str(raw.get("task_summary") or task or "未命名任务"), 48),
        "task_preview": compact_queue_text(task, 160),
        "source_preview": compact_queue_text(source_text, 120),
        "project_dir": compact_path(str(raw.get("project_dir") or "")),
        "platform": str(raw.get("platform_name") or "").strip(),
        "queued_at": iso_from_epoch_seconds(raw.get("queued_at")),
        "updated_at": iso_from_epoch_seconds(raw.get("updated_at")),
        "started_at": iso_from_epoch_seconds(raw.get("started_at")),
        "message": compact_queue_text(str(raw.get("message") or raw.get("error") or ""), 120),
        "can_reorder": status == "queued",
    }


def read_handoff_queue_tasks(limit: int = 30) -> dict[str, Any]:
    normalized_limit = max(1, min(MAX_QUEUE_TASKS, limit))
    if not CODEX_HANDOFF_QUEUE_DIR.exists():
        return {
            "status": "ok",
            "tasks": [],
            "summary": {"task_count": 0, "queued_count": 0, "running_count": 0},
            "queue_dir": compact_path(str(CODEX_HANDOFF_QUEUE_DIR)),
            "quota_cost": "none_file_scan_only",
            "scan_cost": "missing_queue_dir",
            "reorder_supported": True,
            "reorder_scope": "queued_only",
            "guide": [
                "运行中的任务不会被打断。",
                "等待中的任务可以上移或下移，下一个取任务时生效。",
                "这个队列来自 Hermes/Codex handoff，不消耗 Codex 模型额度。",
            ],
            "time": now_iso(),
        }
    raw_items: list[dict[str, Any]] = []
    scan_errors = 0
    with QUEUE_LOCK:
        paths = list(CODEX_HANDOFF_QUEUE_DIR.glob("*.json"))
        for path in paths:
            item = load_queue_item(path)
            if not item:
                scan_errors += 1
                continue
            status = str(item.get("status") or "").strip().lower()
            if status in QUEUE_TERMINAL_STATUSES:
                continue
            raw_items.append(normalize_queue_task(item, path))
    raw_items.sort(key=queue_sort_key)
    tasks = raw_items[:normalized_limit]
    queued_count = sum(1 for item in raw_items if item.get("status") == "queued")
    running_count = sum(1 for item in raw_items if item.get("status") == "running")
    return {
        "status": "ok",
        "tasks": tasks,
        "summary": {
            "task_count": len(raw_items),
            "queued_count": queued_count,
            "running_count": running_count,
        },
        "queue_dir": compact_path(str(CODEX_HANDOFF_QUEUE_DIR)),
        "quota_cost": "none_file_scan_only",
        "scan_cost": "file_scan",
        "scan_errors": scan_errors,
        "reorder_supported": True,
        "reorder_scope": "queued_only",
        "guide": [
            "运行中的任务不会被打断。",
            "等待中的任务可以上移或下移，下一个取任务时生效。",
            "这个队列来自 Hermes/Codex handoff，不消耗 Codex 模型额度。",
        ],
        "time": now_iso(),
    }


def reorder_handoff_queue_tasks(queue_ids: Any) -> dict[str, Any]:
    if not isinstance(queue_ids, list):
        raise ValueError("queue_ids_required")
    requested_ids = [str(item or "").strip() for item in queue_ids]
    requested_ids = [item for item in requested_ids if item]
    if len(set(requested_ids)) != len(requested_ids):
        raise ValueError("duplicate_queue_ids")
    with QUEUE_LOCK:
        queued_items: dict[str, tuple[Path, dict[str, Any]]] = {}
        for path in CODEX_HANDOFF_QUEUE_DIR.glob("*.json"):
            item = load_queue_item(path)
            if not item:
                continue
            queue_id = str(item.get("queue_id") or path.stem).strip()
            status = str(item.get("status") or "").strip().lower()
            if queue_id and status == "queued":
                queued_items[queue_id] = (path, item)
        missing = [queue_id for queue_id in requested_ids if queue_id not in queued_items]
        if missing:
            raise LookupError(",".join(missing[:5]))
        remaining = [
            queue_id
            for queue_id, (_, item) in sorted(queued_items.items(), key=lambda pair: queue_sort_key(pair[1][1]))
            if queue_id not in requested_ids
        ]
        new_order = requested_ids + remaining
        changed = 0
        for index, queue_id in enumerate(new_order, start=1):
            path, item = queued_items[queue_id]
            old_position = safe_int(item.get("position"), 0)
            item["position"] = index
            item["updated_at"] = time.time()
            item["message"] = "Reordered from YuanXiao."
            if old_position != index:
                changed += 1
            tmp_path = path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp_path.replace(path)
    payload = read_handoff_queue_tasks(MAX_QUEUE_TASKS)
    payload["reordered"] = changed
    payload["reorder_effect"] = "queued_tasks_next_pick"
    return payload


def last_visible_session_preview(session_id: str, rollout_path: str, fallback: str = "") -> str:
    path = Path(str(rollout_path or "").strip())
    if path.is_file():
        try:
            size = path.stat().st_size
            start = max(0, size - MAX_CODEX_SESSION_PREVIEW_TAIL_BYTES)
            with path.open("rb") as handle:
                handle.seek(start)
                data = handle.read()
            if start > 0 and b"\n" in data:
                data = data.split(b"\n", 1)[1]
            for raw_line in reversed(data.splitlines()):
                message = parse_codex_session_log_line(session_id, 0, raw_line)
                if not message:
                    continue
                text = compact_preview_text(str(message.get("text") or ""))
                if text:
                    speaker = str(message.get("speaker") or "").strip()
                    return f"{speaker}：{text}" if speaker else text
        except Exception:
            pass
    return compact_preview_text(fallback) or "暂无最近消息"


def codex_process_summary() -> dict[str, Any]:
    try:
        output = subprocess.check_output(
            ["pgrep", "-fl", "Codex|codex"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
    except Exception:
        output = ""
    lines = [
        line.strip()
        for line in output.splitlines()
        if line.strip() and "rg -i" not in line and "pgrep -fl" not in line
    ]
    app_running = any("/Applications/Codex.app" in line or "Codex.app" in line for line in lines)
    return {
        "app_running": app_running,
        "process_count": len(lines),
    }


def thread_status(archived: int, updated_ms: int, now_ms: int) -> str:
    if archived:
        return "archived"
    age_minutes = max(0, (now_ms - updated_ms) // 60000) if updated_ms else 999999
    if age_minutes <= 10:
        return "active"
    if age_minutes <= 120:
        return "recent"
    return "idle"


def read_codex_sessions(limit: int = 20) -> dict[str, Any]:
    process = codex_process_summary()
    if not CODEX_STATE_DB.exists():
        return {
            "status": "error",
            "error": "codex_state_db_missing",
            "process": process,
            "sessions": [],
            "time": now_iso(),
            "quota_cost": "none_file_scan_only",
        }

    now_ms = int(time.time() * 1000)
    sessions: list[dict[str, Any]] = []
    with sqlite3.connect(f"file:{CODEX_STATE_DB}?mode=ro", uri=True, timeout=2) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, title, source, model, agent_nickname, agent_role, archived,
                   updated_at_ms, created_at_ms, tokens_used, cwd, rollout_path,
                   first_user_message
            FROM threads
            ORDER BY archived ASC, updated_at_ms DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    active_count = 0
    archived_count = 0
    for row in rows:
        updated_ms = int(row["updated_at_ms"] or 0)
        archived = int(row["archived"] or 0)
        status = thread_status(archived, updated_ms, now_ms)
        if status == "active":
            active_count += 1
        if archived:
            archived_count += 1
        title = str(row["title"] or "").strip() or "未命名会话"
        if len(title) > 80:
            title = title[:77] + "..."
        sessions.append(
            {
                "id": str(row["id"] or ""),
                "title": title,
                "status": status,
                "source": str(row["source"] or ""),
                "model": str(row["model"] or ""),
                "agent_nickname": str(row["agent_nickname"] or ""),
                "agent_role": str(row["agent_role"] or ""),
                "archived": bool(archived),
                "updated_at": iso_from_epoch_ms(updated_ms),
                "created_at": iso_from_epoch_ms(row["created_at_ms"]),
                "tokens_used": int(row["tokens_used"] or 0),
                "cwd": compact_path(str(row["cwd"] or "")),
                "last_message_preview": last_visible_session_preview(
                    str(row["id"] or ""),
                    str(row["rollout_path"] or ""),
                    str(row["first_user_message"] or ""),
                ),
            }
        )

    return {
        "status": "ok",
        "source": "codex-state-db",
        "quota_cost": "none_file_scan_only",
        "process": process,
        "summary": {
            "visible_sessions": len(sessions),
            "active_sessions": active_count,
            "archived_in_page": archived_count,
            "polling_safe": True,
        },
        "sessions": sessions,
        "time": now_iso(),
    }


def codex_thread_record(session_id: str) -> dict[str, Any] | None:
    if not session_id or not CODEX_STATE_DB.exists():
        return None
    try:
        with sqlite3.connect(f"file:{CODEX_STATE_DB}?mode=ro", uri=True, timeout=2) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT id, title, rollout_path, updated_at_ms, archived
                FROM threads
                WHERE id = ?
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    return {
        "id": str(row["id"] or ""),
        "title": str(row["title"] or "").strip() or "未命名会话",
        "rollout_path": str(row["rollout_path"] or "").strip(),
        "updated_at": iso_from_epoch_ms(row["updated_at_ms"]),
        "archived": bool(int(row["archived"] or 0)),
    }


def sanitize_codex_session_title(title: Any) -> str:
    value = re.sub(r"\s+", " ", str(title or "")).strip()
    if not value:
        value = "元宵新会话"
    if len(value) > MAX_CODEX_SESSION_TITLE_CHARS:
        value = value[:MAX_CODEX_SESSION_TITLE_CHARS].rstrip()
    return value or "元宵新会话"


def read_state_thread_ids() -> set[str]:
    if not CODEX_STATE_DB.exists():
        return set()
    try:
        with sqlite3.connect(f"file:{CODEX_STATE_DB}?mode=ro", uri=True, timeout=2) as connection:
            rows = connection.execute("SELECT id FROM threads").fetchall()
        return {str(row[0] or "") for row in rows if str(row[0] or "")}
    except Exception:
        return set()


def newest_state_thread_id(exclude: set[str], min_created_ms: int, title_marker: str = "") -> str:
    if not CODEX_STATE_DB.exists():
        return ""
    marker = str(title_marker or "").strip()
    try:
        with sqlite3.connect(f"file:{CODEX_STATE_DB}?mode=ro", uri=True, timeout=2) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT id, title, first_user_message, cwd, created_at_ms, updated_at_ms
                FROM threads
                WHERE source = 'exec'
                  AND (created_at_ms >= ? OR updated_at_ms >= ?)
                ORDER BY updated_at_ms DESC, created_at_ms DESC
                LIMIT 20
                """,
                (min_created_ms, min_created_ms),
            ).fetchall()
    except Exception:
        return ""
    for row in rows:
        session_id = str(row["id"] or "")
        if not session_id or session_id in exclude:
            continue
        cwd = str(row["cwd"] or "")
        if cwd != str(BRIDGE_DIR):
            continue
        haystack = f"{row['title'] or ''}\n{row['first_user_message'] or ''}"
        if marker and marker not in haystack:
            continue
        return session_id
    return ""


def rename_codex_thread(session_id: str, title: Any) -> dict[str, Any]:
    session_id = str(session_id or "").strip()
    if not CODEX_THREAD_ID_RE.match(session_id):
        raise ValueError("invalid_session_id")
    clean_title = sanitize_codex_session_title(title)
    if not CODEX_STATE_DB.exists():
        raise RuntimeError("Codex state DB is missing")
    now_ms = int(time.time() * 1000)
    with sqlite3.connect(f"file:{CODEX_STATE_DB}?mode=rw", uri=True, timeout=5) as connection:
        row = connection.execute(
            "SELECT id FROM threads WHERE id = ? LIMIT 1",
            (session_id,),
        ).fetchone()
        if row is None:
            raise LookupError("codex_session_not_found")
        connection.execute(
            """
            UPDATE threads
            SET title = ?, updated_at = ?, updated_at_ms = ?
            WHERE id = ?
            """,
            (clean_title, now_ms // 1000, now_ms, session_id),
        )
        connection.commit()
    record = codex_thread_record(session_id)
    if not record:
        raise RuntimeError("codex_session_rename_not_visible")
    return record


def rollout_path_for_session(session_id: str) -> tuple[Path | None, dict[str, Any]]:
    record = codex_thread_record(session_id) or {"id": session_id, "title": "未命名会话"}
    raw_path = str(record.get("rollout_path") or "").strip()
    if raw_path:
        path = Path(raw_path)
        if path.is_file():
            return path, record
    if CODEX_SESSIONS_DIR.exists():
        for path in CODEX_SESSIONS_DIR.rglob(f"*{session_id}.jsonl"):
            if path.is_file():
                record["rollout_path"] = str(path)
                return path, record
    return None, record


def text_from_message_content(content: Any) -> str:
    parts: list[str] = []
    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type") or "").strip()
            if item_type in {"input_text", "output_text", "text"}:
                value = str(item.get("text") or "").strip()
                if value:
                    parts.append(value)
            elif item_type in {"input_image", "image", "local_image"}:
                parts.append("[图片]")
            elif item.get("image_url"):
                parts.append("[图片]")
    elif isinstance(content, dict):
        value = str(content.get("text") or "").strip()
        if value:
            parts.append(value)
    return "\n".join(part for part in parts if part).strip()


def should_skip_visible_message(role: str, text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if role not in {"user", "assistant"}:
        return True
    hidden_prefixes = (
        "<environment_context>",
        "<developer",
        "<permissions instructions>",
        "<app-context>",
        "<skills_instructions>",
        "<plugins_instructions>",
        "<collaboration_mode>",
    )
    return any(stripped.startswith(prefix) for prefix in hidden_prefixes)


def truncate_session_text(text: str) -> str:
    if len(text) <= MAX_CODEX_SESSION_MESSAGE_CHARS:
        return text
    return text[:MAX_CODEX_SESSION_MESSAGE_CHARS].rstrip() + "\n\n…（内容过长，已截断）"


def parse_codex_session_log_line(session_id: str, line_number: int, raw_line: bytes) -> dict[str, Any] | None:
    try:
        line = raw_line.decode("utf-8").strip()
    except UnicodeDecodeError:
        line = raw_line.decode("utf-8", errors="replace").strip()
    if not line:
        return None
    try:
        item = json.loads(line)
    except json.JSONDecodeError:
        return None
    if item.get("type") != "response_item":
        return None
    payload = item.get("payload")
    if not isinstance(payload, dict) or payload.get("type") != "message":
        return None
    role = str(payload.get("role") or "").strip()
    text = text_from_message_content(payload.get("content"))
    if should_skip_visible_message(role, text):
        return None
    speaker = "我" if role == "user" else "Codex"
    return {
        "id": f"{session_id}:{line_number}",
        "role": role,
        "speaker": speaker,
        "text": truncate_session_text(text),
        "created_at": str(item.get("timestamp") or ""),
        "order": line_number,
        "source": "codex-session-log",
    }


def full_session_message_cache(session_id: str, path: Path, stat: os.stat_result) -> dict[str, Any]:
    messages: list[dict[str, Any]] = []
    line_number = 0
    with path.open("rb") as handle:
        for raw_line in handle:
            line_number += 1
            message = parse_codex_session_log_line(session_id, line_number, raw_line)
            if message is not None:
                messages.append(message)
        offset = handle.tell()
    return {
        "path": str(path),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "offset": offset,
        "line_number": line_number,
        "messages": messages,
        "cache_status": "full_file",
    }


def incremental_session_message_cache(
    session_id: str,
    path: Path,
    stat: os.stat_result,
    cached: dict[str, Any],
) -> dict[str, Any]:
    messages = list(cached.get("messages") or [])
    line_number = int(cached.get("line_number") or 0)
    offset = int(cached.get("offset") or 0)
    with path.open("rb") as handle:
        handle.seek(offset)
        for raw_line in handle:
            line_number += 1
            message = parse_codex_session_log_line(session_id, line_number, raw_line)
            if message is not None:
                messages.append(message)
        offset = handle.tell()
    return {
        "path": str(path),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "offset": offset,
        "line_number": line_number,
        "messages": messages,
        "cache_status": "incremental_tail",
    }


def cached_codex_session_messages(session_id: str, path: Path) -> tuple[list[dict[str, Any]], str]:
    stat = path.stat()
    with CODEX_SESSION_MESSAGE_CACHE_LOCK:
        cached = CODEX_SESSION_MESSAGE_CACHE.get(session_id)
        if cached and cached.get("path") == str(path):
            cached_size = int(cached.get("size") or 0)
            cached_mtime_ns = int(cached.get("mtime_ns") or 0)
            cached_offset = int(cached.get("offset") or 0)
            if cached_size == stat.st_size and cached_mtime_ns == stat.st_mtime_ns:
                return list(cached.get("messages") or []), "cache_hit"
            if stat.st_size >= cached_offset and stat.st_size >= cached_size:
                updated = incremental_session_message_cache(session_id, path, stat, cached)
            else:
                updated = full_session_message_cache(session_id, path, stat)
        else:
            updated = full_session_message_cache(session_id, path, stat)
        CODEX_SESSION_MESSAGE_CACHE[session_id] = updated
        return list(updated.get("messages") or []), str(updated.get("cache_status") or "full_file")


def read_codex_session_messages(session_id: str, limit: int = 80, after_order: int = 0) -> dict[str, Any]:
    session_id = str(session_id or "").strip()
    if not session_id:
        return {"status": "error", "error": "missing_session_id", "messages": [], "time": now_iso()}

    path, record = rollout_path_for_session(session_id)
    if path is None:
        return {
            "status": "error",
            "error": "codex_session_log_missing",
            "session_id": session_id,
            "title": str(record.get("title") or "未命名会话"),
            "messages": [],
            "quota_cost": "none_file_scan_only",
            "time": now_iso(),
        }

    try:
        messages, cache_status = cached_codex_session_messages(session_id, path)
    except Exception as exc:
        return {
            "status": "error",
            "error": "codex_session_log_read_failed",
            "detail": str(exc),
            "session_id": session_id,
            "title": str(record.get("title") or "未命名会话"),
            "messages": [],
            "quota_cost": "none_file_scan_only",
            "time": now_iso(),
        }

    safe_limit = max(1, min(MAX_CODEX_SESSION_MESSAGES, int(limit or 80)))
    safe_after_order = max(0, int(after_order or 0))
    if safe_after_order:
        filtered = [message for message in messages if int(message.get("order") or 0) > safe_after_order]
        visible = filtered[:safe_limit]
    else:
        visible = messages[-safe_limit:]
    next_cursor = safe_after_order
    if visible:
        next_cursor = max(int(message.get("order") or 0) for message in visible)
    return {
        "status": "ok",
        "source": "codex-session-log",
        "quota_cost": "none_file_scan_only",
        "scan_cost": cache_status,
        "session_id": session_id,
        "title": str(record.get("title") or "未命名会话"),
        "updated_at": str(record.get("updated_at") or ""),
        "archived": bool(record.get("archived") or False),
        "message_count": len(messages),
        "after_order": safe_after_order,
        "next_cursor": next_cursor,
        "messages": visible,
        "time": now_iso(),
    }


def load_env_value(path: Path, key: str) -> str:
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        lines = path.read_text().splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name.strip() != key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        return value
    return ""


def extract_hermes_text(response: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") == "output_text":
                text = str(content.get("text") or "").strip()
                if text:
                    parts.append(text)
    if parts:
        return "\n".join(parts).strip()
    text = response.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return ""


def extract_image_refs(reply: str) -> list[dict[str, str]]:
    images: list[dict[str, str]] = []
    for match in re.finditer(r"!\[[^\]]*]\(([^)\s]+)[^)]*\)", reply or ""):
        url = match.group(1).strip()
        if url.startswith(("http://", "https://", "data:image/")):
            images.append({"url": url} if not url.startswith("data:image/") else {"data_url": url})
    return images[:6]


def extract_file_refs(reply: str) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    seen: set[str] = set()
    file_ext_re = re.compile(
        r"\.(pdf|doc|docx|xls|xlsx|ppt|pptx|txt|md|csv|zip|rar|7z|apk|mp4|mov|mp3|wav)(\?|#|$)",
        re.IGNORECASE,
    )
    for match in re.finditer(r"\[([^\]]+)]\((https?://[^)\s]+)[^)]*\)", reply or ""):
        name = match.group(1).strip() or "文件"
        url = match.group(2).strip()
        if url in seen or not file_ext_re.search(url):
            continue
        seen.add(url)
        files.append({"type": "file", "name": name, "url": url})
    for match in re.finditer(r"https?://\S+", reply or ""):
        url = match.group(0).rstrip(".,，。)）")
        if url in seen or not file_ext_re.search(url):
            continue
        seen.add(url)
        files.append({"type": "file", "name": Path(urllib.parse.urlparse(url).path).name or "文件", "url": url})
    return files[:10]


def image_suffix_for_mime(image_mime_type: str) -> str:
    mime_type = (image_mime_type or "image/jpeg").split(";", 1)[0].lower().strip()
    return {
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/bmp": ".bmp",
    }.get(mime_type, ".jpg")


def save_image_from_base64(image_base64: str, image_mime_type: str) -> Path:
    try:
        raw = base64.b64decode(image_base64, validate=True)
    except Exception as exc:
        raise ValueError("invalid_image_base64") from exc
    if not raw:
        raise ValueError("empty_image")
    IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    suffix = image_suffix_for_mime(image_mime_type)
    image_path = IMAGE_CACHE_DIR / f"yuanxiao-vision-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}{suffix}"
    image_path.write_bytes(raw)
    return image_path


def read_vision_session_state() -> dict[str, Any]:
    if not VISION_SESSION_STATE_FILE.exists():
        return {}
    try:
        data = json.loads(VISION_SESSION_STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_vision_session_state(state: dict[str, Any]) -> None:
    VISION_SESSION_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = VISION_SESSION_STATE_FILE.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(VISION_SESSION_STATE_FILE)


def read_codex_chat_session_state() -> dict[str, Any]:
    if not CODEX_CHAT_SESSION_STATE_FILE.exists():
        return {}
    try:
        data = json.loads(CODEX_CHAT_SESSION_STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_codex_chat_session_state(state: dict[str, Any]) -> None:
    CODEX_CHAT_SESSION_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = CODEX_CHAT_SESSION_STATE_FILE.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(CODEX_CHAT_SESSION_STATE_FILE)


def append_codex_vision_error(message: str) -> None:
    CODEX_VISION_ERR_LOG.parent.mkdir(parents=True, exist_ok=True)
    with CODEX_VISION_ERR_LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"[{now_iso()}] {message}\n")


def append_bridge_request_log(payload: dict[str, Any]) -> None:
    try:
        BRIDGE_REQUEST_LOG.parent.mkdir(parents=True, exist_ok=True)
        item = {"time": now_iso(), **payload}
        with BRIDGE_REQUEST_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
        trim_bridge_request_log()
    except Exception:
        pass


def trim_bridge_request_log() -> None:
    if BRIDGE_REQUEST_LOG_MAX_BYTES <= 0 or not BRIDGE_REQUEST_LOG.exists():
        return
    try:
        size = BRIDGE_REQUEST_LOG.stat().st_size
        if size <= BRIDGE_REQUEST_LOG_MAX_BYTES:
            return
        keep_bytes = max(4096, BRIDGE_REQUEST_LOG_MAX_BYTES)
        with BRIDGE_REQUEST_LOG.open("rb") as handle:
            handle.seek(max(0, size - keep_bytes))
            data = handle.read()
        if b"\n" in data:
            data = data.split(b"\n", 1)[1]
        tmp_path = BRIDGE_REQUEST_LOG.with_suffix(".tmp")
        tmp_path.write_bytes(data)
        tmp_path.replace(BRIDGE_REQUEST_LOG)
    except Exception:
        pass


def normalize_chat_target(target: Any, image_base64: str = "") -> str:
    raw = str(target or "").strip().lower()
    if raw in {"codex", "code"}:
        return "codex"
    if raw in {"hermes", "daily", "default"}:
        return "hermes"
    return "codex" if image_base64 else "hermes"


def read_session_index_ids() -> set[str]:
    ids: set[str] = set()
    if not CODEX_SESSION_INDEX_FILE.exists():
        return ids
    try:
        lines = CODEX_SESSION_INDEX_FILE.read_text(encoding="utf-8").splitlines()
    except Exception:
        return ids
    for line in lines:
        try:
            item = json.loads(line)
        except Exception:
            continue
        session_id = str(item.get("id") or "").strip()
        if session_id:
            ids.add(session_id)
    return ids


def session_file_items() -> list[tuple[str, float]]:
    items: list[tuple[str, float]] = []
    if not CODEX_SESSIONS_DIR.exists():
        return items
    for path in CODEX_SESSIONS_DIR.rglob("rollout-*.jsonl"):
        match = CODEX_SESSION_ID_RE.match(path.name)
        if not match:
            continue
        try:
            modified = path.stat().st_mtime
        except OSError:
            modified = 0.0
        items.append((match.group(1), modified))
    return items


def read_all_session_ids() -> set[str]:
    ids = read_session_index_ids()
    ids.update(read_state_thread_ids())
    ids.update(session_id for session_id, _modified in session_file_items())
    return ids


def codex_thread_id_exists(session_id: str) -> bool:
    if not session_id or not CODEX_STATE_DB.exists():
        return False
    try:
        with sqlite3.connect(f"file:{CODEX_STATE_DB}?mode=ro", uri=True, timeout=2) as connection:
            row = connection.execute("SELECT 1 FROM threads WHERE id = ? LIMIT 1", (session_id,)).fetchone()
        return row is not None
    except Exception:
        return False


def session_id_exists(session_id: str) -> bool:
    if not session_id:
        return False
    if codex_thread_id_exists(session_id):
        return True
    index_ids = read_session_index_ids()
    if session_id in index_ids:
        return True
    return session_id in {file_id for file_id, _modified in session_file_items()}


def newest_session_file_id(exclude: set[str] | None = None) -> str:
    exclude = exclude or set()
    newest_id = ""
    newest_modified = -1.0
    for session_id, modified in session_file_items():
        if session_id in exclude:
            continue
        if modified >= newest_modified:
            newest_id = session_id
            newest_modified = modified
    return newest_id


def latest_session_index_id(exclude: set[str] | None = None) -> str:
    exclude = exclude or set()
    latest_id = ""
    latest_updated = ""
    if not CODEX_SESSION_INDEX_FILE.exists():
        return ""
    try:
        lines = CODEX_SESSION_INDEX_FILE.read_text(encoding="utf-8").splitlines()
    except Exception:
        return ""
    for line in lines:
        try:
            item = json.loads(line)
        except Exception:
            continue
        session_id = str(item.get("id") or "").strip()
        updated = str(item.get("updated_at") or "")
        if not session_id or session_id in exclude:
            continue
        if updated >= latest_updated:
            latest_id = session_id
            latest_updated = updated
    return latest_id


def base_codex_cmd() -> list[str]:
    return [
        CODEX_BIN,
        "exec",
        "--skip-git-repo-check",
        "-C",
        str(BRIDGE_DIR),
        "-s",
        "read-only",
        "-c",
        'approval_policy="never"',
        "-c",
        'model_reasoning_effort="low"',
        "-m",
        CODEX_VISION_MODEL,
    ]


def create_vision_session() -> str:
    before_ids = read_all_session_ids()
    output_path = BRIDGE_DIR / "vision-session-init.txt"
    prompt = (
        "你是嫦娥识图专用会话，只负责识别主人通过元宵发送的图片。"
        "后续每次请求都只分析当前附加图片和当前文字，不要沿用旧图片内容。"
        "回复必须是简洁中文，不能提到内部链路、Codex CLI、session 或系统实现。"
        "本次只回复 READY。"
    )
    cmd = base_codex_cmd() + ["-o", str(output_path), prompt]
    result = subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        timeout=CODEX_VISION_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0:
        append_codex_vision_error(f"create session failed code={result.returncode}: {result.stderr[-1000:]}")
        raise RuntimeError(f"Codex vision session init failed with exit code {result.returncode}")
    session_id = newest_session_file_id(exclude=before_ids) or latest_session_index_id(exclude=before_ids)
    if not session_id:
        raise RuntimeError("Codex vision session id was not recorded")
    write_vision_session_state(
        {
            "purpose": "yuanxiao-vision-helper",
            "session_id": session_id,
            "created_at": now_iso(),
            "request_count": 0,
            "last_used_at": "",
            "last_engine": f"codex-session:{CODEX_VISION_MODEL}",
        }
    )
    return session_id


def ensure_vision_session() -> tuple[str, dict[str, Any]]:
    state = read_vision_session_state()
    purpose = str(state.get("purpose") or "")
    session_id = str(state.get("session_id") or "").strip()
    request_count = int(state.get("request_count") or 0)
    if (
        purpose == "yuanxiao-vision-helper"
        and session_id
        and session_id_exists(session_id)
        and request_count < VISION_SESSION_MAX_REQUESTS
    ):
        return session_id, state
    return create_vision_session(), read_vision_session_state()


def create_user_codex_session(title: Any) -> dict[str, Any]:
    clean_title = sanitize_codex_session_title(title)
    before_ids = read_all_session_ids()
    before_ms = int(time.time() * 1000) - 5000
    output_path = CODEX_CHAT_CACHE_DIR / f"new-session-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}.txt"
    CODEX_CHAT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    marker = f"元宵新建 Codex 会话：{clean_title}"
    prompt = (
        "你是主人通过元宵手机端新建的 Codex 工作会话。"
        "这个会话后续可能用于代码、设计、复杂分析或长任务沟通。"
        "请保持会话可继续承接后续指令。"
        "本次初始化只回复 READY。"
        f"\n\n{marker}"
    )
    cmd = [
        CODEX_BIN,
        "exec",
        "--skip-git-repo-check",
        "--ignore-user-config",
        "--ignore-rules",
        "-C",
        str(BRIDGE_DIR),
        "-s",
        "read-only",
        "-c",
        'approval_policy="never"',
        "-c",
        'model_reasoning_effort="low"',
        "-m",
        CODEX_SESSION_CREATE_MODEL,
        "-o",
        str(output_path),
        prompt,
    ]
    result = subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        timeout=CODEX_CHAT_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0:
        append_codex_vision_error(f"create user codex session failed code={result.returncode}: {result.stderr[-1000:]}")
        raise RuntimeError(f"Codex session init failed with exit code {result.returncode}")
    session_id = (
        newest_state_thread_id(before_ids, before_ms, marker)
        or newest_session_file_id(exclude=before_ids)
        or latest_session_index_id(exclude=before_ids)
    )
    if not session_id:
        raise RuntimeError("Codex session id was not recorded")
    return rename_codex_thread(session_id, clean_title)


def create_codex_chat_session(conversation: str) -> str:
    before_ids = read_all_session_ids()
    output_path = CODEX_CHAT_CACHE_DIR / "main-chat-session-init.txt"
    CODEX_CHAT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    prompt = (
        "你是嫦娥主聊天里的 Codex 专业会话。"
        "这个 session 会尽量长期承接主人通过元宵发来的复杂问题。"
        "请记住：用户看到的是在和嫦娥沟通；你可以处理设计、代码、复杂分析。"
        "回复必须直接面向主人，中文表达，不要提到 CLI、内部链路、服务器或 session。"
        "如果问题需要真正改本地文件，请说明需要进入 Codex 工作会话继续执行。"
        f"\n\n稳定会话标识：{conversation}\n本次只回复 READY。"
    )
    cmd = [
        CODEX_BIN,
        "exec",
        "--skip-git-repo-check",
        "-C",
        str(BRIDGE_DIR),
        "-s",
        "read-only",
        "-c",
        'approval_policy="never"',
        "-c",
        'model_reasoning_effort="medium"',
        "-m",
        CODEX_CHAT_MODEL,
        "-o",
        str(output_path),
        prompt,
    ]
    result = subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        timeout=CODEX_CHAT_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0:
        append_codex_vision_error(f"create codex chat session failed code={result.returncode}: {result.stderr[-1000:]}")
        raise RuntimeError(f"Codex chat session init failed with exit code {result.returncode}")
    session_id = newest_session_file_id(exclude=before_ids) or latest_session_index_id(exclude=before_ids)
    if not session_id:
        raise RuntimeError("Codex chat session id was not recorded")
    write_codex_chat_session_state(
        {
            "purpose": "yuanxiao-main-chat",
            "conversation": conversation,
            "session_id": session_id,
            "created_at": now_iso(),
            "request_count": 0,
            "last_used_at": "",
            "last_engine": f"codex-session:{CODEX_CHAT_MODEL}",
        }
    )
    return session_id


def ensure_codex_chat_session(conversation: str) -> tuple[str, dict[str, Any]]:
    state = read_codex_chat_session_state()
    purpose = str(state.get("purpose") or "")
    session_id = str(state.get("session_id") or "").strip()
    state_conversation = str(state.get("conversation") or "")
    request_count = int(state.get("request_count") or 0)
    if (
        purpose == "yuanxiao-main-chat"
        and session_id
        and state_conversation == conversation
        and session_id_exists(session_id)
        and request_count < CODEX_CHAT_SESSION_MAX_REQUESTS
    ):
        return session_id, state
    return create_codex_chat_session(conversation), read_codex_chat_session_state()


def run_codex_vision_command(
    cmd: list[str],
    output_path: Path,
    *,
    timeout_seconds: int,
    error_label: str,
) -> str:
    try:
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        partial = ""
        if output_path.exists():
            try:
                partial = output_path.read_text(encoding="utf-8").strip()
            except Exception:
                partial = ""
        append_codex_vision_error(
            f"{error_label} timed out after {timeout_seconds}s; partial_output={bool(partial)}"
        )
        if partial:
            return partial
        raise RuntimeError(f"{error_label} timed out after {timeout_seconds}s") from exc
    if result.returncode != 0:
        append_codex_vision_error(f"{error_label} failed code={result.returncode}: {result.stderr[-1000:]}")
        raise RuntimeError(f"{error_label} failed with exit code {result.returncode}")
    reply = output_path.read_text(encoding="utf-8").strip() if output_path.exists() else ""
    if not reply:
        raise RuntimeError(f"{error_label} returned empty output")
    return reply


def codex_vision_prompt(message: str) -> str:
    return (
        "请识别当前附加图片，并用中文直接回答主人。"
        "只分析当前图片，不要引用或比较历史图片。"
        "不要解释内部链路，不要输出 Markdown，不要提到你是命令行程序。"
        "如果主人有附加问题，请围绕问题回答；如果没有，就简洁描述图片内容。"
        f"\n\n主人附加文字：{message or '请识别这张图片。'}"
    )


def codex_vision_request_ephemeral(image_path: Path, message: str) -> tuple[str, str]:
    prompt = (
        "你是嫦娥识图功能背后的 Codex 视觉分析能力。"
        "请识别主人通过元宵发送的图片，并用中文直接回答主人。"
        "不要解释内部链路，不要输出 Markdown，不要提到你是命令行程序。"
        "如果主人有附加问题，请围绕问题回答；如果没有，就简洁描述图片内容。"
        f"\n\n主人附加文字：{message or '请识别这张图片。'}"
    )
    output_path = image_path.with_suffix(image_path.suffix + ".codex.txt")
    cmd = base_codex_cmd() + [
        "--ephemeral",
        "-i",
        str(image_path),
        "-o",
        str(output_path),
        prompt,
    ]
    reply = run_codex_vision_command(
        cmd,
        output_path,
        timeout_seconds=CODEX_VISION_TIMEOUT_SECONDS,
        error_label="Codex ephemeral vision",
    )
    return reply, f"codex-cli:{CODEX_VISION_MODEL}"


def codex_vision_request_session(image_path: Path, message: str) -> tuple[str, str]:
    session_id, state = ensure_vision_session()
    output_path = image_path.with_suffix(image_path.suffix + ".codex.txt")
    cmd = [
        CODEX_BIN,
        "exec",
        "resume",
        "--skip-git-repo-check",
        "-c",
        'model_reasoning_effort="low"',
        "-m",
        CODEX_VISION_MODEL,
        "-i",
        str(image_path),
        "-o",
        str(output_path),
        session_id,
        codex_vision_prompt(message),
    ]
    reply = run_codex_vision_command(
        cmd,
        output_path,
        timeout_seconds=CODEX_VISION_TIMEOUT_SECONDS,
        error_label=f"Codex vision session {session_id}",
    )
    state["session_id"] = session_id
    state["request_count"] = int(state.get("request_count") or 0) + 1
    state["last_used_at"] = now_iso()
    state["last_engine"] = f"codex-session:{CODEX_VISION_MODEL}"
    write_vision_session_state(state)
    return reply, f"codex-session:{CODEX_VISION_MODEL}"


def codex_vision_request(image_path: Path, message: str) -> tuple[str, str]:
    if VISION_SESSION_ENABLED:
        try:
            return codex_vision_request_session(image_path, message)
        except Exception as exc:
            append_codex_vision_error(f"session fallback: {exc}")
    return codex_vision_request_ephemeral(image_path, message)


def codex_text_request(message: str, conversation: str, codex_session_id: str = "") -> tuple[str, str]:
    CODEX_CHAT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    output_path = CODEX_CHAT_CACHE_DIR / f"yuanxiao-codex-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}.txt"
    prompt = (
        "你是嫦娥系统里的 Codex 专业模式，适合处理设计、代码编写、复杂分析和需要结构化推理的问题。"
        "请直接用中文回答主人，不要提到命令行、CLI、内部链路、服务器或 session。"
        "可以使用简洁 Markdown、表格和代码块；如果问题需要真正改本地文件，请说明需要进入 Codex 工作会话继续执行。"
        f"\n\n会话：{conversation}\n主人消息：{message}"
    )
    if codex_session_id:
        if not codex_thread_id_exists(codex_session_id):
            raise RuntimeError("指定的 Codex session 不存在或已不可用")
        # For targeted session chat, preserve the owner's original text in the
        # resumed Codex thread instead of writing the YuanXiao routing wrapper
        # into the visible conversation history.
        cmd = [
            CODEX_BIN,
            "exec",
            "resume",
            "--skip-git-repo-check",
            "-c",
            'approval_policy="never"',
            "-c",
            'model_reasoning_effort="medium"',
            "-m",
            CODEX_CHAT_MODEL,
            "-o",
            str(output_path),
            codex_session_id,
            message,
        ]
        reply = run_codex_vision_command(
            cmd,
            output_path,
            timeout_seconds=CODEX_CHAT_TIMEOUT_SECONDS,
            error_label=f"Codex session chat {codex_session_id}",
        )
        return reply, f"codex-session:{CODEX_CHAT_MODEL}"

    if CODEX_CHAT_SESSION_ENABLED:
        try:
            session_id, state = ensure_codex_chat_session(conversation)
            cmd = [
                CODEX_BIN,
                "exec",
                "resume",
                "--skip-git-repo-check",
                "-c",
                'approval_policy="never"',
                "-c",
                'model_reasoning_effort="medium"',
                "-m",
                CODEX_CHAT_MODEL,
                "-o",
                str(output_path),
                session_id,
                message,
            ]
            reply = run_codex_vision_command(
                cmd,
                output_path,
                timeout_seconds=CODEX_CHAT_TIMEOUT_SECONDS,
                error_label=f"Codex main chat session {session_id}",
            )
            state["session_id"] = session_id
            state["conversation"] = conversation
            state["request_count"] = int(state.get("request_count") or 0) + 1
            state["last_used_at"] = now_iso()
            state["last_engine"] = f"codex-session:{CODEX_CHAT_MODEL}"
            write_codex_chat_session_state(state)
            return reply, f"codex-session:{CODEX_CHAT_MODEL}"
        except Exception as exc:
            append_codex_vision_error(f"codex main chat session fallback: {exc}")

    cmd = [
        CODEX_BIN,
        "exec",
        "--skip-git-repo-check",
        "-C",
        str(BRIDGE_DIR),
        "-s",
        "read-only",
        "-c",
        'approval_policy="never"',
        "-c",
        'model_reasoning_effort="medium"',
        "-m",
        CODEX_CHAT_MODEL,
        "--ephemeral",
        "-o",
        str(output_path),
        prompt,
    ]
    reply = run_codex_vision_command(
        cmd,
        output_path,
        timeout_seconds=CODEX_CHAT_TIMEOUT_SECONDS,
        error_label="Codex text chat",
    )
    return reply, f"codex-cli:{CODEX_CHAT_MODEL}"


def build_hermes_input(message: str, image_base64: str, image_mime_type: str) -> Any:
    if not image_base64:
        return message
    mime_type = image_mime_type if image_mime_type.startswith("image/") else "image/jpeg"
    content: list[dict[str, Any]] = []
    content.append(
        {
            "type": "input_text",
            "text": (
                "这是嫦娥识图请求。主人通过元宵发送了一张图片，"
                "请识别图片内容并把答案返回给嫦娥。"
                f"附加文字：{message}" if message else
                "这是嫦娥识图请求。主人通过元宵发送了一张图片，请识别图片内容并把答案返回给嫦娥。"
            ),
        }
    )
    content.append(
        {
            "type": "input_image",
            "image_url": f"data:{mime_type};base64,{image_base64}",
        }
    )
    return [{"role": "user", "content": content}]


def hermes_request(
    message: str,
    conversation: str,
    *,
    target: str = "hermes",
    image_base64: str = "",
    image_mime_type: str = "image/jpeg",
    codex_session_id: str = "",
) -> tuple[str, str, list[dict[str, str]], list[dict[str, str]], str, str]:
    target = normalize_chat_target(target, image_base64)
    if image_base64:
        image_path = save_image_from_base64(image_base64, image_mime_type)
        reply, engine = codex_vision_request(image_path, message)
        source = "codex" if target == "codex" else "codex-via-hermes"
        return reply, "", [], [], source, engine

    if target == "codex":
        reply, engine = codex_text_request(message, conversation, codex_session_id)
        return reply, "", extract_image_refs(reply), extract_file_refs(reply), "codex", engine

    api_key = os.environ.get("API_SERVER_KEY") or load_env_value(HERMES_ENV_FILE, "API_SERVER_KEY")
    if not api_key:
        raise RuntimeError("Hermes API key is missing on the Mac mini.")

    instructions = (
        "你是嫦娥系统背后的回应能力，正在通过元宵手机 APK 和主人沟通。"
        "请直接回复主人，使用中文，保持简洁清楚。"
        "如果主人发送图片，这属于嫦娥识图功能；请接收图片、识别内容，并结合文字给出答案。"
        "不要解释 Hermes、Codex、中转服务器、反向隧道或内部桥接实现。"
    )
    payload = {
        "model": HERMES_MODEL,
        "instructions": instructions,
        "input": build_hermes_input(message, image_base64, image_mime_type),
        "conversation": conversation,
        "store": True,
    }
    request = urllib.request.Request(
        f"{HERMES_BASE_URL}/responses",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=HERMES_TIMEOUT_SECONDS) as response:
        data = json.loads(response.read().decode("utf-8"))
    reply = extract_hermes_text(data)
    if not reply:
        reply = "Hermes 没有返回文字内容。"
    return reply, str(data.get("id") or ""), extract_image_refs(reply), extract_file_refs(reply), "hermes", HERMES_MODEL


class YuanXiaoHermesBridgeHandler(BaseHTTPRequestHandler):
    server_version = "YuanXiaoHermesBridge/0.1"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/health":
            self._send_json(
                {
                    "status": "ok",
                    "service": "yuanxiao-hermes-bridge",
                    "hermes_base_url": HERMES_BASE_URL,
                    "api_key": "present"
                    if (os.environ.get("API_SERVER_KEY") or load_env_value(HERMES_ENV_FILE, "API_SERVER_KEY"))
                    else "missing",
                    "text_routes": ["hermes", "codex"],
                    "default_text_route": "hermes",
                    "codex_chat_engine": f"codex-cli:{CODEX_CHAT_MODEL}",
                    "codex_chat_timeout_seconds": CODEX_CHAT_TIMEOUT_SECONDS,
                    "codex_session_chat": True,
                    "codex_session_history": True,
                    "codex_session_create": True,
                    "codex_session_rename": True,
                    "plan_view": True,
                    "plan_agent_create": True,
                    "task_queue": True,
                    "queue_reorder": "queued_only",
                    "image_input": "enabled",
                    "image_recognition": "change-vision",
                    "vision_engine": f"codex-cli:{CODEX_VISION_MODEL}",
                    "max_request_bytes": MAX_REQUEST_BYTES,
                    "time": now_iso(),
                }
            )
            return
        if parsed.path == "/api/codex/sessions":
            query = urllib.parse.parse_qs(parsed.query)
            try:
                limit = max(1, min(50, int((query.get("limit") or ["20"])[0])))
            except ValueError:
                limit = 20
            self._send_json(read_codex_sessions(limit))
            return
        if parsed.path == "/api/queue/tasks":
            query = urllib.parse.parse_qs(parsed.query)
            try:
                limit = max(1, min(MAX_QUEUE_TASKS, int((query.get("limit") or ["30"])[0])))
            except ValueError:
                limit = 30
            self._send_json(read_handoff_queue_tasks(limit))
            return
        if parsed.path == "/api/plan/projects":
            query = urllib.parse.parse_qs(parsed.query)
            try:
                limit = max(1, min(MAX_PLAN_PROJECTS, int((query.get("limit") or ["30"])[0])))
            except ValueError:
                limit = 30
            payload = read_plan_projects(limit)
            status = 200 if payload.get("status") == "ok" else 500
            self._send_json(payload, status=status)
            return
        if parsed.path == "/api/codex/session/messages":
            query = urllib.parse.parse_qs(parsed.query)
            session_id = str((query.get("session_id") or [""])[0]).strip()
            try:
                limit = max(1, min(MAX_CODEX_SESSION_MESSAGES, int((query.get("limit") or ["80"])[0])))
            except ValueError:
                limit = 80
            try:
                after_order = max(0, int((query.get("after_order") or query.get("after") or ["0"])[0]))
            except ValueError:
                after_order = 0
            payload = read_codex_session_messages(session_id, limit, after_order)
            status = 200 if payload.get("status") == "ok" else 404
            if payload.get("error") == "missing_session_id":
                status = 400
            self._send_json(payload, status=status)
            return
        self._send_json({"error": "not_found"}, status=404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path not in {
            "/api/chat",
            "/api/codex/session/create",
            "/api/codex/session/rename",
            "/api/plan/agent/create",
            "/api/queue/reorder",
        }:
            self._send_json({"error": "not_found"}, status=404)
            return

        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            self._send_json({"error": "invalid_content_length"}, status=400)
            return
        if length <= 0:
            self._send_json({"error": "empty_body"}, status=400)
            return
        if length > MAX_REQUEST_BYTES:
            self._send_json({"error": "payload_too_large"}, status=413)
            return

        try:
            raw = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw or "{}")
        except Exception:
            self._send_json({"error": "invalid_json"}, status=400)
            return

        if parsed.path == "/api/plan/agent/create":
            try:
                response = create_plan_agent(payload)
            except LookupError as exc:
                self._send_json({"status": "error", "error": str(exc), "time": now_iso()}, status=404)
                return
            except Exception as exc:
                self._send_json(
                    {
                        "status": "error",
                        "error": "plan_agent_create_failed",
                        "detail": str(exc),
                        "time": now_iso(),
                    },
                    status=500,
                )
                return
            self._send_json(response)
            return

        if parsed.path == "/api/queue/reorder":
            try:
                response = reorder_handoff_queue_tasks(payload.get("queue_ids"))
            except ValueError as exc:
                self._send_json({"status": "error", "error": str(exc), "time": now_iso()}, status=400)
                return
            except LookupError as exc:
                self._send_json(
                    {
                        "status": "error",
                        "error": "queue_task_not_found_or_not_queued",
                        "detail": str(exc),
                        "time": now_iso(),
                    },
                    status=404,
                )
                return
            except Exception as exc:
                self._send_json(
                    {
                        "status": "error",
                        "error": "queue_reorder_failed",
                        "detail": str(exc),
                        "time": now_iso(),
                    },
                    status=500,
                )
                return
            self._send_json(response)
            return

        if parsed.path == "/api/codex/session/create":
            started = time.monotonic()
            try:
                record = create_user_codex_session(payload.get("title"))
            except Exception as exc:
                self._send_json(
                    {
                        "status": "error",
                        "error": "codex_session_create_failed",
                        "detail": str(exc),
                        "time": now_iso(),
                    },
                    status=504,
                )
                return
            self._send_json(
                {
                    "status": "ok",
                    "source": "codex-cli",
                    "capability": "codex-session-create",
                    "quota_cost": "codex_model_init_call",
                    "session": record,
                    "duration_ms": int((time.monotonic() - started) * 1000),
                    "time": now_iso(),
                }
            )
            return

        if parsed.path == "/api/codex/session/rename":
            try:
                record = rename_codex_thread(payload.get("session_id"), payload.get("title"))
            except ValueError as exc:
                self._send_json({"status": "error", "error": str(exc), "time": now_iso()}, status=400)
                return
            except LookupError:
                self._send_json({"status": "error", "error": "codex_session_not_found", "time": now_iso()}, status=404)
                return
            except Exception as exc:
                self._send_json(
                    {
                        "status": "error",
                        "error": "codex_session_rename_failed",
                        "detail": str(exc),
                        "time": now_iso(),
                    },
                    status=500,
                )
                return
            self._send_json(
                {
                    "status": "ok",
                    "source": "codex-state-db",
                    "capability": "codex-session-rename",
                    "quota_cost": "none_db_update_only",
                    "session": record,
                    "time": now_iso(),
                }
            )
            return

        message = str(payload.get("message") or "").strip()
        image_base64 = str(payload.get("image_base64") or "").strip()
        image_mime_type = str(payload.get("image_mime_type") or "image/jpeg").strip()
        if image_base64 and len(image_base64) > MAX_IMAGE_BASE64_CHARS:
            self._send_json({"error": "image_too_large"}, status=413)
            return
        if image_mime_type and not image_mime_type.startswith("image/"):
            self._send_json({"error": "unsupported_image_type"}, status=415)
            return
        if not message and not image_base64:
            self._send_json({"error": "empty_message"}, status=400)
            return
        conversation = str(payload.get("conversation") or DEFAULT_CONVERSATION).strip() or DEFAULT_CONVERSATION
        target = normalize_chat_target(payload.get("target") or payload.get("route"), image_base64)
        codex_session_id = str(payload.get("codex_session_id") or "").strip()

        started = time.monotonic()
        append_bridge_request_log(
            {
                "event": "chat_start",
                "target": target,
                "conversation": conversation,
                "codex_session_id": codex_session_id,
                "has_image": bool(image_base64),
                "message_chars": len(message),
            }
        )
        try:
            reply, response_id, images, files, source, vision_engine = hermes_request(
                message,
                conversation,
                target=target,
                image_base64=image_base64,
                image_mime_type=image_mime_type,
                codex_session_id=codex_session_id,
            )
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:1000]
            append_bridge_request_log(
                {
                    "event": "chat_error",
                    "target": target,
                    "conversation": conversation,
                    "codex_session_id": codex_session_id,
                    "error": "hermes_http_error",
                    "detail": f"HTTP {exc.code}",
                    "duration_ms": int((time.monotonic() - started) * 1000),
                }
            )
            self._send_json(
                {
                    "status": "error",
                    "error": "hermes_http_error",
                    "detail": f"HTTP {exc.code}",
                    "body": body,
                    "time": now_iso(),
                },
                status=502,
            )
            return
        except Exception as exc:
            append_bridge_request_log(
                {
                    "event": "chat_error",
                    "target": target,
                    "conversation": conversation,
                    "codex_session_id": codex_session_id,
                    "error": "hermes_unavailable",
                    "detail": str(exc),
                    "duration_ms": int((time.monotonic() - started) * 1000),
                }
            )
            self._send_json(
                {
                    "status": "error",
                    "error": "hermes_unavailable",
                    "detail": str(exc),
                    "time": now_iso(),
                },
                status=504,
            )
            return

        duration_ms = int((time.monotonic() - started) * 1000)
        append_bridge_request_log(
            {
                "event": "chat_ok",
                "target": target,
                "conversation": conversation,
                "codex_session_id": codex_session_id,
                "source": source,
                "engine": vision_engine,
                "duration_ms": duration_ms,
                "reply_chars": len(reply),
            }
        )
        self._send_json(
            {
                "status": "ok",
                "source": source,
                "target": target,
                "route": target,
                "capability": "change-vision" if image_base64 else ("codex-chat" if target == "codex" else "chat"),
                "engine": vision_engine,
                "vision_engine": vision_engine if image_base64 else "",
                "received": message,
                "received_image": bool(image_base64),
                "reply": reply,
                "images": images,
                "files": files,
                "conversation": conversation,
                "codex_session_id": codex_session_id if target == "codex" else "",
                "hermes_response_id": response_id,
                "duration_ms": duration_ms,
                "time": now_iso(),
            }
        )

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}", flush=True)

    def _send_json(self, payload: dict[str, object], *, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> int:
    httpd = ThreadingHTTPServer((HOST, PORT), YuanXiaoHermesBridgeHandler)
    print(f"yuanxiao hermes bridge listening on http://{HOST}:{PORT}", flush=True)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
