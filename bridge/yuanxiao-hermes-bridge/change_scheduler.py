#!/usr/bin/env python3
"""Small durable task ledger for ChangE/YuanXiao orchestration.

The scheduler is intentionally conservative: it records task state and events,
detects stale running work, and exposes compact cards to YuanXiao.  It does not
own model execution yet; bridge adapters update it as work starts and finishes.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_DB = Path.home() / ".yuanxiao/change-tasks.sqlite3"
TASK_DB = Path(os.environ.get("YUANXIAO_TASK_DB", str(DEFAULT_DB)))
STALE_SECONDS = int(os.environ.get("YUANXIAO_TASK_STALE_SECONDS", "1200"))
MAX_TEXT_CHARS = 1200


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def now_epoch() -> int:
    return int(time.time())


def compact_text(value: Any, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + "..."


def bounded_text(value: Any, limit: int = MAX_TEXT_CHARS) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + "..."


def connect() -> sqlite3.Connection:
    TASK_DB.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(TASK_DB, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=5000")
    init_db(connection)
    return connection


def init_db(connection: sqlite3.Connection | None = None) -> None:
    owns_connection = connection is None
    if connection is None:
        TASK_DB.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(TASK_DB, timeout=5)
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                kind TEXT NOT NULL DEFAULT 'chat',
                route TEXT NOT NULL DEFAULT 'auto',
                status TEXT NOT NULL DEFAULT 'queued',
                progress INTEGER NOT NULL DEFAULT 0,
                project_id TEXT NOT NULL DEFAULT '',
                agent_id TEXT NOT NULL DEFAULT '',
                conversation TEXT NOT NULL DEFAULT '',
                codex_session_id TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                message TEXT NOT NULL DEFAULT '',
                latest_event TEXT NOT NULL DEFAULT '',
                result_preview TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                heartbeat_at TEXT NOT NULL,
                created_epoch INTEGER NOT NULL,
                updated_epoch INTEGER NOT NULL,
                heartbeat_epoch INTEGER NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_status_updated
                ON tasks(status, updated_epoch DESC);
            CREATE INDEX IF NOT EXISTS idx_tasks_updated
                ON tasks(updated_epoch DESC);

            CREATE TABLE IF NOT EXISTS task_events (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                event TEXT NOT NULL,
                message TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                created_epoch INTEGER NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_task_events_task_time
                ON task_events(task_id, created_epoch DESC);
            """
        )
        connection.commit()
    finally:
        if owns_connection:
            connection.close()


def task_exists(connection: sqlite3.Connection, task_id: str) -> bool:
    row = connection.execute("SELECT 1 FROM tasks WHERE task_id = ? LIMIT 1", (task_id,)).fetchone()
    return row is not None


def record_event(
    task_id: str,
    event: str,
    message: str = "",
    metadata: dict[str, Any] | None = None,
    *,
    connection: sqlite3.Connection | None = None,
) -> None:
    owns_connection = connection is None
    if connection is None:
        connection = connect()
    try:
        created_at = now_iso()
        created_epoch = now_epoch()
        connection.execute(
            """
            INSERT INTO task_events (id, task_id, event, message, created_at, created_epoch, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"evt_{created_epoch}_{uuid.uuid4().hex[:8]}",
                task_id,
                compact_text(event, 80),
                bounded_text(message, 500),
                created_at,
                created_epoch,
                json.dumps(metadata or {}, ensure_ascii=False),
            ),
        )
        connection.execute(
            """
            UPDATE tasks
            SET latest_event = ?, updated_at = ?, updated_epoch = ?
            WHERE task_id = ?
            """,
            (compact_text(message or event, 180), created_at, created_epoch, task_id),
        )
        connection.commit()
    finally:
        if owns_connection:
            connection.close()


def upsert_task(
    task_id: str,
    *,
    title: str = "",
    kind: str = "chat",
    route: str = "auto",
    status: str = "queued",
    progress: int = 0,
    project_id: str = "",
    agent_id: str = "",
    conversation: str = "",
    codex_session_id: str = "",
    source: str = "",
    message: str = "",
    latest_event: str = "",
    result_preview: str = "",
    error: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean_task_id = compact_text(task_id or f"task_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}", 80)
    current_iso = now_iso()
    current_epoch = now_epoch()
    safe_progress = max(0, min(100, int(progress or 0)))
    clean_status = compact_text(status or "queued", 40).lower()
    with connect() as connection:
        existed = task_exists(connection, clean_task_id)
        if existed:
            connection.execute(
                """
                UPDATE tasks
                SET title = COALESCE(NULLIF(?, ''), title),
                    kind = COALESCE(NULLIF(?, ''), kind),
                    route = COALESCE(NULLIF(?, ''), route),
                    status = ?,
                    progress = ?,
                    project_id = COALESCE(NULLIF(?, ''), project_id),
                    agent_id = COALESCE(NULLIF(?, ''), agent_id),
                    conversation = COALESCE(NULLIF(?, ''), conversation),
                    codex_session_id = COALESCE(NULLIF(?, ''), codex_session_id),
                    source = COALESCE(NULLIF(?, ''), source),
                    message = COALESCE(NULLIF(?, ''), message),
                    latest_event = COALESCE(NULLIF(?, ''), latest_event),
                    result_preview = COALESCE(NULLIF(?, ''), result_preview),
                    error = ?,
                    updated_at = ?,
                    heartbeat_at = ?,
                    updated_epoch = ?,
                    heartbeat_epoch = ?,
                    metadata_json = CASE WHEN ? = '{}' THEN metadata_json ELSE ? END
                WHERE task_id = ?
                """,
                (
                    compact_text(title, 120),
                    compact_text(kind, 40),
                    compact_text(route, 40),
                    clean_status,
                    safe_progress,
                    compact_text(project_id, 80),
                    compact_text(agent_id, 80),
                    compact_text(conversation, 120),
                    compact_text(codex_session_id, 80),
                    compact_text(source, 80),
                    bounded_text(message),
                    compact_text(latest_event, 180),
                    compact_text(result_preview, 300),
                    compact_text(error, 300),
                    current_iso,
                    current_iso,
                    current_epoch,
                    current_epoch,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    json.dumps(metadata or {}, ensure_ascii=False),
                    clean_task_id,
                ),
            )
        else:
            connection.execute(
                """
                INSERT INTO tasks (
                    task_id, title, kind, route, status, progress, project_id, agent_id,
                    conversation, codex_session_id, source, message, latest_event,
                    result_preview, error, created_at, updated_at, heartbeat_at,
                    created_epoch, updated_epoch, heartbeat_epoch, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clean_task_id,
                    compact_text(title or message or clean_task_id, 120),
                    compact_text(kind, 40),
                    compact_text(route, 40),
                    clean_status,
                    safe_progress,
                    compact_text(project_id, 80),
                    compact_text(agent_id, 80),
                    compact_text(conversation, 120),
                    compact_text(codex_session_id, 80),
                    compact_text(source, 80),
                    bounded_text(message),
                    compact_text(latest_event, 180),
                    compact_text(result_preview, 300),
                    compact_text(error, 300),
                    current_iso,
                    current_iso,
                    current_iso,
                    current_epoch,
                    current_epoch,
                    current_epoch,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
        record_event(
            clean_task_id,
            "task.updated" if existed else "task.created",
            latest_event or clean_status,
            {"status": clean_status, "route": route, "kind": kind},
            connection=connection,
        )
        connection.commit()
    return get_task(clean_task_id) or {"task_id": clean_task_id}


def update_task_status(
    task_id: str,
    status: str,
    *,
    progress: int | None = None,
    latest_event: str = "",
    result_preview: str = "",
    error: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current_iso = now_iso()
    current_epoch = now_epoch()
    clean_status = compact_text(status or "queued", 40).lower()
    with connect() as connection:
        if not task_exists(connection, task_id):
            upsert_task(task_id, status=clean_status, progress=progress or 0, latest_event=latest_event, metadata=metadata)
            return get_task(task_id) or {"task_id": task_id}
        existing = connection.execute("SELECT progress FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        next_progress = int(existing["progress"] if existing else 0)
        if progress is not None:
            next_progress = max(0, min(100, int(progress)))
        connection.execute(
            """
            UPDATE tasks
            SET status = ?, progress = ?, latest_event = COALESCE(NULLIF(?, ''), latest_event),
                result_preview = COALESCE(NULLIF(?, ''), result_preview),
                error = ?, updated_at = ?, heartbeat_at = ?,
                updated_epoch = ?, heartbeat_epoch = ?,
                metadata_json = CASE WHEN ? = '{}' THEN metadata_json ELSE ? END
            WHERE task_id = ?
            """,
            (
                clean_status,
                next_progress,
                compact_text(latest_event, 180),
                compact_text(result_preview, 300),
                compact_text(error, 300),
                current_iso,
                current_iso,
                current_epoch,
                current_epoch,
                json.dumps(metadata or {}, ensure_ascii=False),
                json.dumps(metadata or {}, ensure_ascii=False),
                task_id,
            ),
        )
        record_event(
            task_id,
            f"task.{clean_status}",
            latest_event or clean_status,
            {"status": clean_status},
            connection=connection,
        )
        connection.commit()
    return get_task(task_id) or {"task_id": task_id}


def get_task(task_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute("SELECT * FROM tasks WHERE task_id = ? LIMIT 1", (task_id,)).fetchone()
    return task_from_row(row) if row else None


def task_from_row(row: sqlite3.Row) -> dict[str, Any]:
    age_seconds = max(0, now_epoch() - int(row["updated_epoch"] or 0))
    heartbeat_age_seconds = max(0, now_epoch() - int(row["heartbeat_epoch"] or 0))
    return {
        "task_id": str(row["task_id"] or ""),
        "title": str(row["title"] or ""),
        "kind": str(row["kind"] or ""),
        "route": str(row["route"] or ""),
        "status": str(row["status"] or ""),
        "status_label": status_label(str(row["status"] or "")),
        "progress": int(row["progress"] or 0),
        "project_id": str(row["project_id"] or ""),
        "agent_id": str(row["agent_id"] or ""),
        "conversation": str(row["conversation"] or ""),
        "codex_session_id": str(row["codex_session_id"] or ""),
        "source": str(row["source"] or ""),
        "message_preview": compact_text(row["message"], 160),
        "latest_event": str(row["latest_event"] or ""),
        "result_preview": str(row["result_preview"] or ""),
        "error": str(row["error"] or ""),
        "created_at": str(row["created_at"] or ""),
        "updated_at": str(row["updated_at"] or ""),
        "heartbeat_at": str(row["heartbeat_at"] or ""),
        "age_seconds": age_seconds,
        "heartbeat_age_seconds": heartbeat_age_seconds,
        "stale": is_task_stale(str(row["status"] or ""), heartbeat_age_seconds),
    }


def status_label(status: str) -> str:
    normalized = str(status or "").lower()
    return {
        "received": "已收到",
        "queued": "等待中",
        "running": "运行中",
        "waiting_external": "等待外部",
        "blocked": "已阻塞",
        "failed": "失败",
        "completed": "完成",
        "cancelled": "已取消",
        "canceled": "已取消",
    }.get(normalized, normalized or "未知")


def is_task_stale(status: str, heartbeat_age_seconds: int) -> bool:
    return str(status or "").lower() in {"received", "queued", "running", "waiting_external"} and heartbeat_age_seconds > STALE_SECONDS


def mark_stale_tasks() -> int:
    current_iso = now_iso()
    current_epoch = now_epoch()
    changed = 0
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT task_id, status, heartbeat_epoch
            FROM tasks
            WHERE status IN ('received', 'queued', 'running', 'waiting_external')
            """
        ).fetchall()
        for row in rows:
            task_id = str(row["task_id"] or "")
            heartbeat_age = max(0, current_epoch - int(row["heartbeat_epoch"] or 0))
            if heartbeat_age <= STALE_SECONDS:
                continue
            message = f"超过 {STALE_SECONDS // 60} 分钟没有心跳，已标记为阻塞。"
            connection.execute(
                """
                UPDATE tasks
                SET status = 'blocked', latest_event = ?, error = ?,
                    updated_at = ?, updated_epoch = ?
                WHERE task_id = ?
                """,
                (message, message, current_iso, current_epoch, task_id),
            )
            record_event(task_id, "task.blocked", message, connection=connection)
            changed += 1
        connection.commit()
    return changed


def list_tasks(limit: int = 50, status: str = "") -> dict[str, Any]:
    init_db()
    stale_marked = mark_stale_tasks()
    safe_limit = max(1, min(100, int(limit or 50)))
    normalized_status = str(status or "").strip().lower()
    with connect() as connection:
        if normalized_status:
            rows = connection.execute(
                """
                SELECT * FROM tasks
                WHERE status = ?
                ORDER BY updated_epoch DESC
                LIMIT ?
                """,
                (normalized_status, safe_limit),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT * FROM tasks
                ORDER BY
                    CASE status
                        WHEN 'blocked' THEN 0
                        WHEN 'failed' THEN 1
                        WHEN 'running' THEN 2
                        WHEN 'received' THEN 3
                        WHEN 'queued' THEN 4
                        ELSE 5
                    END,
                    updated_epoch DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
    tasks = [task_from_row(row) for row in rows]
    return {
        "status": "ok",
        "source": "change-task-ledger",
        "tasks": tasks,
        "summary": summarize_tasks(tasks),
        "stale_marked": stale_marked,
        "stale_seconds": STALE_SECONDS,
        "quota_cost": "none_db_scan_only",
        "time": now_iso(),
    }


def summarize_tasks(tasks: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "task_count": len(tasks),
        "running_count": sum(1 for task in tasks if task.get("status") == "running"),
        "queued_count": sum(1 for task in tasks if task.get("status") in {"queued", "received"}),
        "blocked_count": sum(1 for task in tasks if task.get("status") == "blocked"),
        "failed_count": sum(1 for task in tasks if task.get("status") == "failed"),
        "completed_count": sum(1 for task in tasks if task.get("status") == "completed"),
    }


def list_events(task_id: str = "", limit: int = 80) -> dict[str, Any]:
    init_db()
    safe_limit = max(1, min(200, int(limit or 80)))
    with connect() as connection:
        if task_id:
            rows = connection.execute(
                """
                SELECT * FROM task_events
                WHERE task_id = ?
                ORDER BY created_epoch DESC
                LIMIT ?
                """,
                (task_id, safe_limit),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT * FROM task_events
                ORDER BY created_epoch DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
    return {
        "status": "ok",
        "source": "change-task-ledger",
        "events": [
            {
                "id": str(row["id"] or ""),
                "task_id": str(row["task_id"] or ""),
                "event": str(row["event"] or ""),
                "message": str(row["message"] or ""),
                "created_at": str(row["created_at"] or ""),
            }
            for row in rows
        ],
        "quota_cost": "none_db_scan_only",
        "time": now_iso(),
    }


def list_agents() -> dict[str, Any]:
    return {
        "status": "ok",
        "source": "change-static-agent-registry",
        "agents": [
            {"agent_id": "hermes-frontdoor", "name": "Hermes", "role": "日常对话/飞书/语音", "status": "available"},
            {"agent_id": "codex-chief", "name": "Codex Chief", "role": "架构/拆解/审查", "status": "available"},
            {"agent_id": "codex-worker", "name": "Codex Worker", "role": "代码/构建/长任务", "status": "available"},
            {"agent_id": "ops-controller", "name": "Ops Controller", "role": "卡住检测/取消/重试", "status": "available"},
        ],
        "quota_cost": "none_static_only",
        "time": now_iso(),
    }


def cmd_init(_: argparse.Namespace) -> None:
    init_db()
    print(TASK_DB)


def cmd_list(args: argparse.Namespace) -> None:
    print(json.dumps(list_tasks(args.limit, args.status), ensure_ascii=False, indent=2))


def cmd_mark_stale(_: argparse.Namespace) -> None:
    print(mark_stale_tasks())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Maintain ChangE/YuanXiao task ledger.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init").set_defaults(func=cmd_init)
    list_parser = sub.add_parser("list")
    list_parser.add_argument("--limit", type=int, default=50)
    list_parser.add_argument("--status", default="")
    list_parser.set_defaults(func=cmd_list)
    sub.add_parser("mark-stale").set_defaults(func=cmd_mark_stale)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
