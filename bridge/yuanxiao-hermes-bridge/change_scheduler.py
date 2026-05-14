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
CONTROL_PLANE_SCHEMA_VERSION = 1


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


def json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)


def json_loads_dict(value: Any) -> dict[str, Any]:
    try:
        data = json.loads(str(value or "{}"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def json_loads_list(value: Any) -> list[Any]:
    try:
        data = json.loads(str(value or "[]"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


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

            CREATE TABLE IF NOT EXISTS runner_adapters (
                adapter_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL DEFAULT '',
                runner_type TEXT NOT NULL DEFAULT 'custom',
                client_mode TEXT NOT NULL DEFAULT 'cli',
                machine_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'available',
                model_hint TEXT NOT NULL DEFAULT '',
                session_endpoint_json TEXT NOT NULL DEFAULT '{}',
                workspace_policy_json TEXT NOT NULL DEFAULT '{}',
                capabilities_json TEXT NOT NULL DEFAULT '{}',
                approval_policy_json TEXT NOT NULL DEFAULT '{}',
                audit_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_runner_adapters_type_status
                ON runner_adapters(runner_type, status);

            CREATE TABLE IF NOT EXISTS capability_registry (
                capability_id TEXT PRIMARY KEY,
                name TEXT NOT NULL DEFAULT '',
                provider TEXT NOT NULL DEFAULT '',
                protocol TEXT NOT NULL DEFAULT '',
                tool_source TEXT NOT NULL DEFAULT '',
                version TEXT NOT NULL DEFAULT '0.1',
                status TEXT NOT NULL DEFAULT 'quarantined',
                side_effect_level TEXT NOT NULL DEFAULT 'none',
                workspace_allowlist_json TEXT NOT NULL DEFAULT '[]',
                secret_policy_json TEXT NOT NULL DEFAULT '{}',
                isolation_json TEXT NOT NULL DEFAULT '{}',
                approval_policy_json TEXT NOT NULL DEFAULT '{}',
                schemas_json TEXT NOT NULL DEFAULT '{}',
                android_renderer_json TEXT NOT NULL DEFAULT '{}',
                audit_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_capability_registry_status
                ON capability_registry(status, side_effect_level);

            CREATE TABLE IF NOT EXISTS workflow_nodes (
                node_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL DEFAULT '',
                project_id TEXT NOT NULL DEFAULT '',
                parent_node_id TEXT NOT NULL DEFAULT '',
                node_type TEXT NOT NULL DEFAULT 'subagent',
                state TEXT NOT NULL DEFAULT 'created',
                title TEXT NOT NULL DEFAULT '',
                owner_json TEXT NOT NULL DEFAULT '{}',
                dependencies_json TEXT NOT NULL DEFAULT '{}',
                todo_json TEXT NOT NULL DEFAULT '[]',
                checkpoint_json TEXT NOT NULL DEFAULT '{}',
                inputs_json TEXT NOT NULL DEFAULT '{}',
                outputs_json TEXT NOT NULL DEFAULT '{}',
                trace_json TEXT NOT NULL DEFAULT '{}',
                policy_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_workflow_nodes_project_state
                ON workflow_nodes(project_id, state, updated_at DESC);

            CREATE TABLE IF NOT EXISTS typed_cards (
                card_id TEXT PRIMARY KEY,
                card_type TEXT NOT NULL DEFAULT 'report',
                task_id TEXT NOT NULL DEFAULT '',
                workflow_id TEXT NOT NULL DEFAULT '',
                node_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                title TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                renderer TEXT NOT NULL DEFAULT 'android_v1',
                actions_json TEXT NOT NULL DEFAULT '[]',
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_typed_cards_status_task
                ON typed_cards(status, task_id, updated_at DESC);

            CREATE TABLE IF NOT EXISTS mobile_smoke_runs (
                run_id TEXT PRIMARY KEY,
                app_version TEXT NOT NULL DEFAULT '',
                server_version TEXT NOT NULL DEFAULT '',
                device TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'created',
                summary_json TEXT NOT NULL DEFAULT '{}',
                cases_json TEXT NOT NULL DEFAULT '[]',
                started_at TEXT NOT NULL DEFAULT '',
                completed_at TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_mobile_smoke_runs_updated
                ON mobile_smoke_runs(updated_at DESC);

            CREATE TABLE IF NOT EXISTS control_audit_events (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                subject_type TEXT NOT NULL DEFAULT '',
                subject_id TEXT NOT NULL DEFAULT '',
                actor TEXT NOT NULL DEFAULT 'change',
                trace_id TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                created_epoch INTEGER NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_control_audit_events_subject
                ON control_audit_events(subject_type, subject_id, created_epoch DESC);
            """
        )
        seed_control_plane_defaults(connection)
        connection.commit()
    finally:
        if owns_connection:
            connection.close()


def record_audit_event(
    event_type: str,
    *,
    subject_type: str = "",
    subject_id: str = "",
    actor: str = "change",
    trace_id: str = "",
    metadata: dict[str, Any] | None = None,
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
            INSERT INTO control_audit_events (
                id, event_type, subject_type, subject_id, actor, trace_id,
                created_at, created_epoch, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"audit_{created_epoch}_{uuid.uuid4().hex[:8]}",
                compact_text(event_type, 80),
                compact_text(subject_type, 60),
                compact_text(subject_id, 120),
                compact_text(actor, 60),
                compact_text(trace_id, 120),
                created_at,
                created_epoch,
                json_dumps(metadata or {}),
            ),
        )
        connection.commit()
    finally:
        if owns_connection:
            connection.close()


def seed_control_plane_defaults(connection: sqlite3.Connection) -> None:
    current = now_iso()
    runner_rows = [
        {
            "adapter_id": "runner_codex_local_default",
            "display_name": "Codex · Mac mini",
            "runner_type": "codex",
            "client_mode": "desktop_cli_resume",
            "machine_id": "macmini",
            "status": "available",
            "model_hint": "gpt-5.5",
            "session_endpoint": {"kind": "local_state_db", "safe_label": "Codex state DB", "secret_ref": ""},
            "workspace_policy": {
                "default_cwd": "workspace:yuanxiao",
                "allowlist": ["workspace:yuanxiao", "workspace:change-runtime", "workspace:active-projects"],
                "denylist": ["secret:ssh", "secret:hermes-env", "system:user-library"],
                "requires_worktree": False,
                "sandbox_class": "local_user",
            },
            "capabilities": {
                "supports_mcp": False,
                "supports_checkpoint": True,
                "supports_headless": True,
                "supports_streaming": False,
                "supports_subagents": True,
                "supports_human_approval": True,
                "supports_daemon_resume": False,
                "supports_artifact_upload": True,
            },
            "approval_policy": {
                "default_mode": "ask_high_impact",
                "dangerous_actions": ["external_send", "delete", "credential_change", "public_expose"],
                "preapproved_scopes": ["yuanxiao_quark_delivery_after_build_verify"],
            },
        },
        {
            "adapter_id": "runner_hermes_local_frontdoor",
            "display_name": "Hermes · 玉兔",
            "runner_type": "hermes",
            "client_mode": "local_api",
            "machine_id": "macmini",
            "status": "available",
            "model_hint": "hermes-agent",
            "session_endpoint": {"kind": "loopback_http", "safe_label": "Hermes API", "secret_ref": "hermes_api_key"},
            "workspace_policy": {
                "default_cwd": "workspace:hermes-runtime",
                "allowlist": ["workspace:hermes-runtime", "workspace:yuanxiao"],
                "denylist": ["secret:ssh", "secret:hermes-env"],
                "requires_worktree": False,
                "sandbox_class": "local_user",
            },
            "capabilities": {
                "supports_mcp": True,
                "supports_checkpoint": False,
                "supports_headless": True,
                "supports_streaming": False,
                "supports_subagents": False,
                "supports_human_approval": True,
                "supports_daemon_resume": False,
                "supports_artifact_upload": False,
            },
            "approval_policy": {"default_mode": "ask_external_send", "dangerous_actions": ["external_send"]},
        },
        {
            "adapter_id": "runner_change_relay",
            "display_name": "ChangE · Relay",
            "runner_type": "custom",
            "client_mode": "https_relay",
            "machine_id": "change",
            "status": "available",
            "model_hint": "",
            "session_endpoint": {"kind": "https_relay", "safe_label": "ChangE public relay", "secret_ref": ""},
            "workspace_policy": {
                "default_cwd": "/opt/yuanxiao",
                "allowlist": ["/opt/yuanxiao"],
                "denylist": ["/home", "/root", "/etc"],
                "requires_worktree": False,
                "sandbox_class": "relay_only",
            },
            "capabilities": {
                "supports_mcp": False,
                "supports_checkpoint": False,
                "supports_headless": True,
                "supports_streaming": False,
                "supports_subagents": False,
                "supports_human_approval": False,
                "supports_daemon_resume": False,
                "supports_artifact_upload": True,
            },
            "approval_policy": {"default_mode": "relay_only", "dangerous_actions": ["public_expose"]},
        },
        {
            "adapter_id": "runner_legend_remote_placeholder",
            "display_name": "传奇 · Remote Agent",
            "runner_type": "remote_agent",
            "client_mode": "ssh_worker",
            "machine_id": "legend",
            "status": "degraded",
            "model_hint": "",
            "session_endpoint": {"kind": "ssh", "safe_label": "configured outside repo", "secret_ref": "external"},
            "workspace_policy": {
                "default_cwd": "",
                "allowlist": [],
                "denylist": ["secrets", "private_keys"],
                "requires_worktree": False,
                "sandbox_class": "remote_worker",
            },
            "capabilities": {
                "supports_mcp": False,
                "supports_checkpoint": False,
                "supports_headless": True,
                "supports_streaming": False,
                "supports_subagents": False,
                "supports_human_approval": False,
                "supports_daemon_resume": False,
                "supports_artifact_upload": False,
            },
            "approval_policy": {"default_mode": "downlink_only", "dangerous_actions": ["external_send"]},
        },
    ]
    for item in runner_rows:
        connection.execute(
            """
            INSERT INTO runner_adapters (
                adapter_id, display_name, runner_type, client_mode, machine_id, status,
                model_hint, session_endpoint_json, workspace_policy_json, capabilities_json,
                approval_policy_json, audit_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(adapter_id) DO UPDATE SET
                display_name = excluded.display_name,
                runner_type = excluded.runner_type,
                client_mode = excluded.client_mode,
                machine_id = excluded.machine_id,
                status = excluded.status,
                model_hint = excluded.model_hint,
                session_endpoint_json = excluded.session_endpoint_json,
                workspace_policy_json = excluded.workspace_policy_json,
                capabilities_json = excluded.capabilities_json,
                approval_policy_json = excluded.approval_policy_json,
                audit_json = excluded.audit_json,
                updated_at = excluded.updated_at
            """,
            (
                item["adapter_id"],
                item["display_name"],
                item["runner_type"],
                item["client_mode"],
                item["machine_id"],
                item["status"],
                item["model_hint"],
                json_dumps(item["session_endpoint"]),
                json_dumps(item["workspace_policy"]),
                json_dumps(item["capabilities"]),
                json_dumps(item["approval_policy"]),
                json_dumps({"seeded_by": "change_scheduler", "schema_version": CONTROL_PLANE_SCHEMA_VERSION}),
                current,
                current,
            ),
        )

    capability_rows = [
        ("cap_task_ledger_read", "Read ChangE task ledger", "change_scheduler", "python_call", "bridge/change_scheduler.py", "enabled", "none", "task_list", ["open_task", "refresh"]),
        ("cap_task_events_read", "Read task events", "change_scheduler", "python_call", "bridge/change_scheduler.py", "enabled", "none", "trace", ["open_task", "copy"]),
        ("cap_task_card_write", "Create or update task card", "change_scheduler", "python_call", "bridge/change_scheduler.py", "enabled", "local_write", "task_list", ["open_task"]),
        ("cap_codex_session_summary", "Summarize Codex session metadata", "codex_bridge", "sqlite_read", "bridge/yuanxiao_hermes_bridge.py", "enabled", "local_read", "trace", ["open_session", "copy"]),
        ("cap_codex_session_history_read", "Read Codex session history incrementally", "codex_bridge", "file_tail", "bridge/yuanxiao_hermes_bridge.py", "enabled", "local_read", "trace", ["open_session", "refresh"]),
        ("cap_report_lookup", "Lookup research report metadata", "change_scheduler", "file_read", "reports", "enabled", "local_read", "artifact", ["open_report", "copy"]),
        ("cap_artifact_metadata_list", "List artifact metadata", "change_scheduler", "db_file_scan", "artifact-ledger", "quarantined", "local_read", "artifact", ["open_artifact", "copy"]),
        ("cap_queue_reorder", "Reorder queued-only tasks", "codex_bridge", "json_file_update", "bridge/yuanxiao_hermes_bridge.py", "enabled", "local_write", "approval", ["move_up", "move_down"]),
        ("cap_approval_card_create", "Create approval card", "change_scheduler", "python_call", "bridge/change_scheduler.py", "enabled", "local_write", "approval", ["approve", "reject"]),
        ("cap_approval_card_answer", "Answer approval card", "change_scheduler", "python_call", "bridge/change_scheduler.py", "enabled", "local_write", "approval", ["approve", "reject"]),
    ]
    for capability_id, name, provider, protocol, tool_source, status, side_effect, card_type, actions in capability_rows:
        connection.execute(
            """
            INSERT INTO capability_registry (
                capability_id, name, provider, protocol, tool_source, version, status,
                side_effect_level, workspace_allowlist_json, secret_policy_json,
                isolation_json, approval_policy_json, schemas_json, android_renderer_json,
                audit_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, '0.1', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(capability_id) DO UPDATE SET
                name = excluded.name,
                provider = excluded.provider,
                protocol = excluded.protocol,
                tool_source = excluded.tool_source,
                version = excluded.version,
                status = excluded.status,
                side_effect_level = excluded.side_effect_level,
                workspace_allowlist_json = excluded.workspace_allowlist_json,
                secret_policy_json = excluded.secret_policy_json,
                isolation_json = excluded.isolation_json,
                approval_policy_json = excluded.approval_policy_json,
                schemas_json = excluded.schemas_json,
                android_renderer_json = excluded.android_renderer_json,
                audit_json = excluded.audit_json,
                updated_at = excluded.updated_at
            """,
            (
                capability_id,
                name,
                provider,
                protocol,
                tool_source,
                status,
                side_effect,
                json_dumps(["ledger:yuanxiao", "workspace:yuanxiao"]),
                json_dumps({"secret_refs": [], "secret_source": "none", "redaction_rule": "never_log_values"}),
                json_dumps({"mode": "same_process", "network": "loopback", "filesystem": "allowlisted_write" if side_effect == "local_write" else "read_only"}),
                json_dumps({"required": side_effect in {"external_send", "destructive"}, "approval_card_type": "approval" if side_effect in {"external_send", "destructive"} else ""}),
                json_dumps({"input_schema_ref": f"schema://{capability_id}/input", "output_schema_ref": f"schema://{capability_id}/output"}),
                json_dumps({"card_type": card_type, "summary_fields": ["title", "status", "updated_at"], "actions": actions}),
                json_dumps({"audit_event_required": True, "trace_span_name": f"capability.{capability_id}"}),
                current,
                current,
            ),
        )


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


def runner_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "adapter_id": str(row["adapter_id"] or ""),
        "display_name": str(row["display_name"] or ""),
        "runner_type": str(row["runner_type"] or ""),
        "client_mode": str(row["client_mode"] or ""),
        "machine_id": str(row["machine_id"] or ""),
        "status": str(row["status"] or ""),
        "model_hint": str(row["model_hint"] or ""),
        "session_endpoint": json_loads_dict(row["session_endpoint_json"]),
        "workspace_policy": json_loads_dict(row["workspace_policy_json"]),
        "capabilities": json_loads_dict(row["capabilities_json"]),
        "approval_policy": json_loads_dict(row["approval_policy_json"]),
        "audit": json_loads_dict(row["audit_json"]),
        "created_at": str(row["created_at"] or ""),
        "updated_at": str(row["updated_at"] or ""),
    }


def list_runner_adapters(status: str = "") -> dict[str, Any]:
    init_db()
    normalized_status = compact_text(status, 40).lower()
    with connect() as connection:
        if normalized_status:
            rows = connection.execute(
                """
                SELECT * FROM runner_adapters
                WHERE status = ?
                ORDER BY runner_type ASC, display_name ASC
                """,
                (normalized_status,),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT * FROM runner_adapters
                ORDER BY
                    CASE status WHEN 'available' THEN 0 WHEN 'degraded' THEN 1 ELSE 2 END,
                    runner_type ASC,
                    display_name ASC
                """
            ).fetchall()
    adapters = [runner_from_row(row) for row in rows]
    return {
        "status": "ok",
        "source": "change-runner-adapter-registry",
        "schema_version": CONTROL_PLANE_SCHEMA_VERSION,
        "adapters": adapters,
        "summary": {
            "adapter_count": len(adapters),
            "available_count": sum(1 for item in adapters if item.get("status") == "available"),
            "degraded_count": sum(1 for item in adapters if item.get("status") == "degraded"),
        },
        "quota_cost": "none_db_scan_only",
        "time": now_iso(),
    }


def capability_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "capability_id": str(row["capability_id"] or ""),
        "name": str(row["name"] or ""),
        "provider": str(row["provider"] or ""),
        "protocol": str(row["protocol"] or ""),
        "tool_source": str(row["tool_source"] or ""),
        "version": str(row["version"] or ""),
        "status": str(row["status"] or ""),
        "side_effect_level": str(row["side_effect_level"] or ""),
        "workspace_allowlist": json_loads_list(row["workspace_allowlist_json"]),
        "secret_policy": json_loads_dict(row["secret_policy_json"]),
        "isolation": json_loads_dict(row["isolation_json"]),
        "approval_policy": json_loads_dict(row["approval_policy_json"]),
        "schemas": json_loads_dict(row["schemas_json"]),
        "android_renderer": json_loads_dict(row["android_renderer_json"]),
        "audit": json_loads_dict(row["audit_json"]),
        "created_at": str(row["created_at"] or ""),
        "updated_at": str(row["updated_at"] or ""),
    }


def list_capabilities(status: str = "", side_effect_level: str = "") -> dict[str, Any]:
    init_db()
    normalized_status = compact_text(status, 40).lower()
    normalized_side_effect = compact_text(side_effect_level, 40).lower()
    clauses: list[str] = []
    args: list[Any] = []
    if normalized_status:
        clauses.append("status = ?")
        args.append(normalized_status)
    if normalized_side_effect:
        clauses.append("side_effect_level = ?")
        args.append(normalized_side_effect)
    query = "SELECT * FROM capability_registry"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY status ASC, side_effect_level ASC, capability_id ASC"
    with connect() as connection:
        rows = connection.execute(query, args).fetchall()
    capabilities = [capability_from_row(row) for row in rows]
    return {
        "status": "ok",
        "source": "change-capability-registry",
        "schema_version": CONTROL_PLANE_SCHEMA_VERSION,
        "capabilities": capabilities,
        "summary": {
            "capability_count": len(capabilities),
            "enabled_count": sum(1 for item in capabilities if item.get("status") == "enabled"),
            "quarantined_count": sum(1 for item in capabilities if item.get("status") == "quarantined"),
            "local_write_count": sum(1 for item in capabilities if item.get("side_effect_level") == "local_write"),
        },
        "quota_cost": "none_db_scan_only",
        "time": now_iso(),
    }


def workflow_node_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "workflow_id": str(row["workflow_id"] or ""),
        "node_id": str(row["node_id"] or ""),
        "project_id": str(row["project_id"] or ""),
        "parent_node_id": str(row["parent_node_id"] or ""),
        "node_type": str(row["node_type"] or ""),
        "state": str(row["state"] or ""),
        "title": str(row["title"] or ""),
        "owner": json_loads_dict(row["owner_json"]),
        "dependencies": json_loads_dict(row["dependencies_json"]),
        "todo": json_loads_list(row["todo_json"]),
        "checkpoint": json_loads_dict(row["checkpoint_json"]),
        "inputs": json_loads_dict(row["inputs_json"]),
        "outputs": json_loads_dict(row["outputs_json"]),
        "trace": json_loads_dict(row["trace_json"]),
        "policy": json_loads_dict(row["policy_json"]),
        "created_at": str(row["created_at"] or ""),
        "updated_at": str(row["updated_at"] or ""),
    }


def list_workflow_nodes(
    *,
    project_id: str = "",
    workflow_id: str = "",
    state: str = "",
    limit: int = 50,
) -> dict[str, Any]:
    init_db()
    safe_limit = max(1, min(200, int(limit or 50)))
    clauses: list[str] = []
    args: list[Any] = []
    for column, value in (
        ("project_id", project_id),
        ("workflow_id", workflow_id),
        ("state", state),
    ):
        cleaned = compact_text(value, 120).lower() if column == "state" else compact_text(value, 120)
        if cleaned:
            clauses.append(f"{column} = ?")
            args.append(cleaned)
    query = "SELECT * FROM workflow_nodes"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY updated_at DESC LIMIT ?"
    args.append(safe_limit)
    with connect() as connection:
        rows = connection.execute(query, args).fetchall()
    nodes = [workflow_node_from_row(row) for row in rows]
    return {
        "status": "ok",
        "source": "change-workflow-node-ledger",
        "schema_version": CONTROL_PLANE_SCHEMA_VERSION,
        "nodes": nodes,
        "summary": {
            "node_count": len(nodes),
            "running_count": sum(1 for item in nodes if item.get("state") == "running"),
            "blocked_count": sum(1 for item in nodes if item.get("state") in {"blocked", "failed"}),
            "waiting_approval_count": sum(1 for item in nodes if item.get("state") == "waiting_approval"),
        },
        "quota_cost": "none_db_scan_only",
        "time": now_iso(),
    }


def upsert_workflow_node(payload: dict[str, Any]) -> dict[str, Any]:
    current = now_iso()
    workflow_id = compact_text(payload.get("workflow_id") or f"wf_{int(time.time() * 1000)}", 120)
    node_id = compact_text(payload.get("node_id") or f"node_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}", 120)
    state = compact_text(payload.get("state") or "created", 40).lower()
    node_type = compact_text(payload.get("node_type") or "subagent", 40).lower()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO workflow_nodes (
                node_id, workflow_id, project_id, parent_node_id, node_type, state,
                title, owner_json, dependencies_json, todo_json, checkpoint_json,
                inputs_json, outputs_json, trace_json, policy_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(node_id) DO UPDATE SET
                workflow_id = excluded.workflow_id,
                project_id = excluded.project_id,
                parent_node_id = excluded.parent_node_id,
                node_type = excluded.node_type,
                state = excluded.state,
                title = excluded.title,
                owner_json = excluded.owner_json,
                dependencies_json = excluded.dependencies_json,
                todo_json = excluded.todo_json,
                checkpoint_json = excluded.checkpoint_json,
                inputs_json = excluded.inputs_json,
                outputs_json = excluded.outputs_json,
                trace_json = excluded.trace_json,
                policy_json = excluded.policy_json,
                updated_at = excluded.updated_at
            """,
            (
                node_id,
                workflow_id,
                compact_text(payload.get("project_id"), 120),
                compact_text(payload.get("parent_node_id"), 120),
                node_type,
                state,
                compact_text(payload.get("title") or node_id, 160),
                json_dumps(payload.get("owner") or {}),
                json_dumps(payload.get("dependencies") or {}),
                json_dumps(payload.get("todo") if isinstance(payload.get("todo"), list) else []),
                json_dumps(payload.get("checkpoint") or {}),
                json_dumps(payload.get("inputs") or {}),
                json_dumps(payload.get("outputs") or {}),
                json_dumps(payload.get("trace") or {}),
                json_dumps(payload.get("policy") or {}),
                current,
                current,
            ),
        )
        record_audit_event(
            "workflow_node.upserted",
            subject_type="workflow_node",
            subject_id=node_id,
            actor=compact_text(payload.get("actor") or "yuanxiao-api", 60),
            trace_id=compact_text((payload.get("trace") or {}).get("trace_id") if isinstance(payload.get("trace"), dict) else "", 120),
            metadata={"workflow_id": workflow_id, "state": state, "node_type": node_type},
            connection=connection,
        )
    return {"status": "ok", "node": (get_workflow_node(node_id) or {}), "quota_cost": "none_db_update_only", "time": now_iso()}


def get_workflow_node(node_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute("SELECT * FROM workflow_nodes WHERE node_id = ? LIMIT 1", (node_id,)).fetchone()
    return workflow_node_from_row(row) if row else None


def typed_card_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "card_id": str(row["card_id"] or ""),
        "card_type": str(row["card_type"] or ""),
        "task_id": str(row["task_id"] or ""),
        "workflow_id": str(row["workflow_id"] or ""),
        "node_id": str(row["node_id"] or ""),
        "status": str(row["status"] or ""),
        "title": str(row["title"] or ""),
        "summary": str(row["summary"] or ""),
        "renderer": str(row["renderer"] or ""),
        "actions": json_loads_list(row["actions_json"]),
        "payload": json_loads_dict(row["payload_json"]),
        "created_at": str(row["created_at"] or ""),
        "updated_at": str(row["updated_at"] or ""),
    }


def list_typed_cards(task_id: str = "", status: str = "", card_type: str = "", limit: int = 50) -> dict[str, Any]:
    init_db()
    safe_limit = max(1, min(200, int(limit or 50)))
    clauses: list[str] = []
    args: list[Any] = []
    for column, value in (
        ("task_id", task_id),
        ("status", status),
        ("card_type", card_type),
    ):
        cleaned = compact_text(value, 120).lower() if column in {"status", "card_type"} else compact_text(value, 120)
        if cleaned:
            clauses.append(f"{column} = ?")
            args.append(cleaned)
    query = "SELECT * FROM typed_cards"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY updated_at DESC LIMIT ?"
    args.append(safe_limit)
    with connect() as connection:
        rows = connection.execute(query, args).fetchall()
    cards = [typed_card_from_row(row) for row in rows]
    return {
        "status": "ok",
        "source": "change-typed-card-ledger",
        "schema_version": CONTROL_PLANE_SCHEMA_VERSION,
        "cards": cards,
        "summary": {
            "card_count": len(cards),
            "pending_count": sum(1 for item in cards if item.get("status") == "pending"),
            "approval_count": sum(1 for item in cards if item.get("card_type") == "approval"),
            "failure_count": sum(1 for item in cards if item.get("card_type") == "failure"),
        },
        "quota_cost": "none_db_scan_only",
        "time": now_iso(),
    }


def upsert_typed_card(payload: dict[str, Any]) -> dict[str, Any]:
    current = now_iso()
    card_id = compact_text(payload.get("card_id") or f"card_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}", 120)
    card_type = compact_text(payload.get("card_type") or payload.get("type") or "report", 40).lower()
    status = compact_text(payload.get("status") or "pending", 40).lower()
    actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
    payload_body = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO typed_cards (
                card_id, card_type, task_id, workflow_id, node_id, status, title,
                summary, renderer, actions_json, payload_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(card_id) DO UPDATE SET
                card_type = excluded.card_type,
                task_id = excluded.task_id,
                workflow_id = excluded.workflow_id,
                node_id = excluded.node_id,
                status = excluded.status,
                title = excluded.title,
                summary = excluded.summary,
                renderer = excluded.renderer,
                actions_json = excluded.actions_json,
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at
            """,
            (
                card_id,
                card_type,
                compact_text(payload.get("task_id"), 120),
                compact_text(payload.get("workflow_id"), 120),
                compact_text(payload.get("node_id"), 120),
                status,
                compact_text(payload.get("title") or card_id, 160),
                compact_text(payload.get("summary"), 500),
                compact_text(payload.get("renderer") or "android_v1", 60),
                json_dumps(actions),
                json_dumps(payload_body),
                current,
                current,
            ),
        )
        record_audit_event(
            "typed_card.upserted",
            subject_type="typed_card",
            subject_id=card_id,
            actor=compact_text(payload.get("actor") or "yuanxiao-api", 60),
            metadata={"card_type": card_type, "status": status},
            connection=connection,
        )
    return {"status": "ok", "card": (get_typed_card(card_id) or {}), "quota_cost": "none_db_update_only", "time": now_iso()}


def answer_typed_card(payload: dict[str, Any]) -> dict[str, Any]:
    card_id = compact_text(payload.get("card_id"), 120)
    answer = compact_text(payload.get("answer") or "answered", 80)
    actor = compact_text(payload.get("actor") or "主人", 60)
    if not card_id:
        return {"status": "error", "error": "missing_card_id", "time": now_iso()}
    current = now_iso()
    with connect() as connection:
        row = connection.execute("SELECT * FROM typed_cards WHERE card_id = ? LIMIT 1", (card_id,)).fetchone()
        if not row:
            return {"status": "error", "error": "card_not_found", "card_id": card_id, "time": now_iso()}
        payload_body = json_loads_dict(row["payload_json"])
        answers = payload_body.get("answers") if isinstance(payload_body.get("answers"), list) else []
        answers.append({"answer": answer, "actor": actor, "fields": payload.get("fields") or {}, "answered_at": current})
        payload_body["answers"] = answers[-20:]
        payload_body["last_answer"] = answer
        connection.execute(
            """
            UPDATE typed_cards
            SET status = ?, payload_json = ?, updated_at = ?
            WHERE card_id = ?
            """,
            ("answered", json_dumps(payload_body), current, card_id),
        )
        record_audit_event(
            "typed_card.answered",
            subject_type="typed_card",
            subject_id=card_id,
            actor=actor,
            metadata={"answer": answer},
            connection=connection,
        )
    return {"status": "ok", "card": (get_typed_card(card_id) or {}), "quota_cost": "none_db_update_only", "time": now_iso()}


def get_typed_card(card_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute("SELECT * FROM typed_cards WHERE card_id = ? LIMIT 1", (card_id,)).fetchone()
    return typed_card_from_row(row) if row else None


def smoke_run_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "run_id": str(row["run_id"] or ""),
        "app_version": str(row["app_version"] or ""),
        "server_version": str(row["server_version"] or ""),
        "device": str(row["device"] or ""),
        "status": str(row["status"] or ""),
        "summary": json_loads_dict(row["summary_json"]),
        "cases": json_loads_list(row["cases_json"]),
        "started_at": str(row["started_at"] or ""),
        "completed_at": str(row["completed_at"] or ""),
        "created_at": str(row["created_at"] or ""),
        "updated_at": str(row["updated_at"] or ""),
    }


def list_mobile_smoke_runs(limit: int = 20) -> dict[str, Any]:
    init_db()
    safe_limit = max(1, min(100, int(limit or 20)))
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM mobile_smoke_runs ORDER BY updated_at DESC LIMIT ?",
            (safe_limit,),
        ).fetchall()
    runs = [smoke_run_from_row(row) for row in rows]
    return {
        "status": "ok",
        "source": "change-mobile-smoke-ledger",
        "schema_version": CONTROL_PLANE_SCHEMA_VERSION,
        "runs": runs,
        "required_cases": [
            "main_chat",
            "codex_async_receipt",
            "task_cards",
            "approval_reject",
            "attachments",
            "disconnect_resume",
            "queue_reorder",
            "report_lookup",
            "failure_card",
            "memory_card",
        ],
        "quota_cost": "none_db_scan_only",
        "time": now_iso(),
    }


def upsert_mobile_smoke_run(payload: dict[str, Any]) -> dict[str, Any]:
    current = now_iso()
    run_id = compact_text(payload.get("run_id") or f"smoke_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}", 120)
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO mobile_smoke_runs (
                run_id, app_version, server_version, device, status, summary_json,
                cases_json, started_at, completed_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                app_version = excluded.app_version,
                server_version = excluded.server_version,
                device = excluded.device,
                status = excluded.status,
                summary_json = excluded.summary_json,
                cases_json = excluded.cases_json,
                started_at = excluded.started_at,
                completed_at = excluded.completed_at,
                updated_at = excluded.updated_at
            """,
            (
                run_id,
                compact_text(payload.get("app_version"), 40),
                compact_text(payload.get("server_version"), 80),
                compact_text(payload.get("device"), 80),
                compact_text(payload.get("status") or "created", 40).lower(),
                json_dumps(payload.get("summary") or {}),
                json_dumps(payload.get("cases") if isinstance(payload.get("cases"), list) else []),
                compact_text(payload.get("started_at") or current, 80),
                compact_text(payload.get("completed_at"), 80),
                current,
                current,
            ),
        )
        record_audit_event(
            "mobile_smoke_run.upserted",
            subject_type="mobile_smoke_run",
            subject_id=run_id,
            actor=compact_text(payload.get("actor") or "yuanxiao-api", 60),
            metadata={"status": payload.get("status") or "created"},
            connection=connection,
        )
    return {"status": "ok", "run": (get_mobile_smoke_run(run_id) or {}), "quota_cost": "none_db_update_only", "time": now_iso()}


def get_mobile_smoke_run(run_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute("SELECT * FROM mobile_smoke_runs WHERE run_id = ? LIMIT 1", (run_id,)).fetchone()
    return smoke_run_from_row(row) if row else None


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
