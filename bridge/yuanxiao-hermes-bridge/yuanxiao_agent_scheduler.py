#!/usr/bin/env python3
"""YuanXiao async agent plan-state helper.

This script owns the lightweight project/CEO/agent state consumed by the
YuanXiao Plan tab.  It intentionally avoids calling Codex, Hermes, or any
remote model directly; workers can update this state asynchronously after they
finish or checkpoint work.
"""

from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_FILE = Path(os.environ.get("YUANXIAO_PLAN_STATE_FILE", str(Path.home() / ".yuanxiao/plan-state.json")))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def bounded_text(value: str, limit: int = 400) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + "…"


def normalized_progress(value: str | int | float | None) -> int:
    try:
        progress = float(value or 0)
    except (TypeError, ValueError):
        progress = 0
    if 0 < progress <= 1:
        progress *= 100
    return max(0, min(100, int(round(progress))))


def is_done(status: str) -> bool:
    return str(status or "").strip().lower() in {"done", "completed", "complete"}


def is_running(status: str) -> bool:
    return str(status or "").strip().lower() in {"active", "running", "review"}


def is_blocked(status: str) -> bool:
    return str(status or "").strip().lower() in {"blocked", "failed"}


def should_count_ceo(ceo: dict[str, Any]) -> bool:
    status = str(ceo.get("status") or "queued").strip().lower() or "queued"
    return (
        status not in {"queued", "waiting"}
        or normalized_progress(ceo.get("progress", 0)) > 0
        or bool(str(ceo.get("current_task") or "").strip())
        or bool(str(ceo.get("last_report") or "").strip())
    )


def recompute_project(project: dict[str, Any]) -> None:
    people: list[dict[str, Any]] = []
    agents = project.get("agents")
    if isinstance(agents, list):
        people.extend(agent for agent in agents if isinstance(agent, dict))
    ceo = project.get("ceo")
    if isinstance(ceo, dict) and (not people or should_count_ceo(ceo)):
        people.append(ceo)
    if not people:
        project["progress"] = normalized_progress(project.get("progress", 0))
        project["status"] = str(project.get("status") or "queued").strip().lower() or "queued"
        return
    progresses = [normalized_progress(person.get("progress", 0)) for person in people]
    project["progress"] = int(round(sum(progresses) / max(1, len(progresses))))
    statuses = [str(person.get("status") or "queued").strip().lower() or "queued" for person in people]
    if statuses and all(is_done(status) for status in statuses):
        project["status"] = "completed"
        project["progress"] = 100
    elif any(is_blocked(status) for status in statuses):
        project["status"] = "blocked"
    elif any(is_running(status) for status in statuses):
        project["status"] = "running"
    else:
        project["status"] = "queued"
    project["updated_at"] = now_iso()


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {"schema_version": 1, "updated_at": now_iso(), "projects": [], "events": []}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data.get("projects"), list):
        data["projects"] = []
    if not isinstance(data.get("events"), list):
        data["events"] = []
    data.setdefault("schema_version", 1)
    data.setdefault("updated_at", now_iso())
    return data


def save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = STATE_FILE.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(STATE_FILE)


def append_event(state: dict[str, Any], event: str, **fields: Any) -> None:
    events = state.setdefault("events", [])
    events.append({"id": uuid.uuid4().hex[:12], "event": event, "time": now_iso(), **fields})
    del events[:-200]


def find_project(state: dict[str, Any], project_id: str) -> dict[str, Any]:
    for project in state["projects"]:
        if str(project.get("id") or "") == project_id:
            return project
    raise SystemExit(f"project not found: {project_id}")


def find_or_create_agent(project: dict[str, Any], agent_id: str, name: str = "", role: str = "") -> dict[str, Any]:
    agents = project.setdefault("agents", [])
    for agent in agents:
        if str(agent.get("id") or "") == agent_id:
            return agent
    agent = {
        "id": agent_id or uuid.uuid4().hex[:12],
        "name": name or "未命名 Agent",
        "role": role,
        "status": "queued",
        "progress": 0,
        "last_report": "",
        "updated_at": now_iso(),
    }
    agents.append(agent)
    return agent


def cmd_init(_: argparse.Namespace) -> None:
    state = load_state()
    save_state(state)
    print(STATE_FILE)


def cmd_create_project(args: argparse.Namespace) -> None:
    state = load_state()
    project_id = args.project_id or f"plan-{uuid.uuid4().hex[:8]}"
    owner_request = bounded_text(args.owner_request, 700)
    project = {
        "id": project_id,
        "title": args.title,
        "status": args.status,
        "progress": normalized_progress(args.progress),
        "objective": owner_request,
        "orchestration_mode": "change_managed_async",
        "reporting_policy": "change_only",
        "last_report": "嫦娥已记录主人要求，等待 CEO 拆解。" if owner_request else "",
        "updated_at": now_iso(),
        "ceo": {
            "id": args.ceo_id or f"ceo-{uuid.uuid4().hex[:8]}",
            "name": args.ceo_name,
            "role": "CEO",
            "session_id": args.ceo_session_id,
            "status": "running" if owner_request else "queued",
            "progress": 5 if owner_request else 0,
            "current_task": owner_request or "等待主人提出计划目标。",
            "last_report": "只向嫦娥汇报，由嫦娥统一调度后续角色。" if owner_request else "",
            "updated_at": now_iso(),
        },
        "agents": [],
        "requests": [
            {
                "id": f"req-{uuid.uuid4().hex[:8]}",
                "from": "owner",
                "text": owner_request,
                "created_at": now_iso(),
                "status": "received_by_change",
            }
        ]
        if owner_request
        else [],
    }
    state["projects"].insert(0, project)
    append_event(state, "project_created", project_id=project_id, title=args.title)
    save_state(state)
    print(project_id)


def cmd_add_agent(args: argparse.Namespace) -> None:
    state = load_state()
    project = find_project(state, args.project_id)
    agent_id = args.agent_id or f"agent-{uuid.uuid4().hex[:8]}"
    agent = find_or_create_agent(project, agent_id, args.name, args.role)
    agent.update(
        {
            "name": args.name,
            "role": args.role,
            "session_id": args.session_id,
            "status": args.status,
            "progress": normalized_progress(args.progress),
            "updated_at": now_iso(),
        }
    )
    recompute_project(project)
    append_event(state, "agent_added", project_id=args.project_id, agent_id=agent_id, name=args.name)
    save_state(state)
    print(agent_id)


def cmd_update_agent(args: argparse.Namespace) -> None:
    state = load_state()
    project = find_project(state, args.project_id)
    agent = find_or_create_agent(project, args.agent_id)
    agent["status"] = args.status
    agent["progress"] = normalized_progress(args.progress)
    if args.report:
        agent["last_report"] = bounded_text(args.report)
        project["last_report"] = bounded_text(f"{agent.get('name')}: {args.report}")
    agent["updated_at"] = now_iso()
    recompute_project(project)
    append_event(state, "agent_updated", project_id=args.project_id, agent_id=args.agent_id, status=args.status)
    save_state(state)
    print(args.agent_id)


def cmd_report(args: argparse.Namespace) -> None:
    state = load_state()
    project = find_project(state, args.project_id)
    report = bounded_text(args.text, 800)
    project["last_report"] = report
    project["updated_at"] = now_iso()
    if args.from_role.lower() == "ceo":
        ceo = project.setdefault("ceo", {})
        ceo["last_report"] = report
        ceo["status"] = args.status
        ceo["progress"] = normalized_progress(args.progress)
        ceo["updated_at"] = now_iso()
    recompute_project(project)
    append_event(state, "project_report", project_id=args.project_id, from_role=args.from_role, text=report)
    save_state(state)
    print(args.project_id)


def cmd_list(_: argparse.Namespace) -> None:
    print(json.dumps(load_state(), ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Maintain YuanXiao async agent plan state.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init")
    init.set_defaults(func=cmd_init)

    create = subparsers.add_parser("create-project")
    create.add_argument("--project-id", default="")
    create.add_argument("--title", required=True)
    create.add_argument("--status", default="queued")
    create.add_argument("--progress", default="0")
    create.add_argument("--ceo-id", default="")
    create.add_argument("--ceo-name", default="CEO")
    create.add_argument("--ceo-session-id", default="")
    create.add_argument("--owner-request", default="")
    create.set_defaults(func=cmd_create_project)

    add_agent = subparsers.add_parser("add-agent")
    add_agent.add_argument("--project-id", required=True)
    add_agent.add_argument("--agent-id", default="")
    add_agent.add_argument("--name", required=True)
    add_agent.add_argument("--role", default="")
    add_agent.add_argument("--session-id", default="")
    add_agent.add_argument("--status", default="queued")
    add_agent.add_argument("--progress", default="0")
    add_agent.set_defaults(func=cmd_add_agent)

    update_agent = subparsers.add_parser("update-agent")
    update_agent.add_argument("--project-id", required=True)
    update_agent.add_argument("--agent-id", required=True)
    update_agent.add_argument("--status", default="running")
    update_agent.add_argument("--progress", default="0")
    update_agent.add_argument("--report", default="")
    update_agent.set_defaults(func=cmd_update_agent)

    report = subparsers.add_parser("report")
    report.add_argument("--project-id", required=True)
    report.add_argument("--from-role", default="ceo")
    report.add_argument("--status", default="running")
    report.add_argument("--progress", default="0")
    report.add_argument("--text", required=True)
    report.set_defaults(func=cmd_report)

    list_state = subparsers.add_parser("list")
    list_state.set_defaults(func=cmd_list)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
