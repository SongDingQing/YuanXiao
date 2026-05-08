# API Contracts

All public endpoints are relative to the private `YUANXIAO_PUBLIC_BASE_URL`
configured outside Git.

## Health

`GET /health`

Returns relay status, mode, limits, and timeout metadata.

## Chat

`POST /api/chat`

Text body:

```json
{
  "message": "hello",
  "target": "hermes",
  "conversation_id": "yuanxiao-change-main"
}
```

Codex session body:

```json
{
  "message": "continue this task",
  "target": "codex",
  "codex_session_id": "session-id"
}
```

Codex, Codex-session, and image requests run asynchronously by default. The
immediate response includes `async=true`, `task_id`, and a short receipt; the
final answer is delivered through `/api/inbox`.

Image body:

```json
{
  "message": "describe this image",
  "image_base64": "...",
  "image_mime_type": "image/jpeg",
  "image_name": "image.jpg"
}
```

## Inbox

`GET /api/inbox?after=&limit=`

Returns downlink messages for the APK.

`POST /api/inbox/admin`

Local/admin-only endpoint for queuing ChangE messages to the APK. Admin token is
optional and must be supplied from private config when enabled.

## Codex Dashboard

`GET /api/codex/sessions?limit=`

Returns Codex session state from local files/database through the Mac mini
bridge. This path is designed to avoid model quota usage.

`GET /api/codex/session/messages?session_id=&limit=&after_order=`

Returns visible user/assistant messages parsed from local Codex rollout logs.

`POST /api/codex/session/create`

Creates a new Codex session from YuanXiao.

`POST /api/codex/session/rename`

Renames a Codex session in local Codex state.

## Plan View

`GET /api/plan/projects?limit=`

Returns local async orchestration state for YuanXiao's Plan tab. The bridge
reads this from the private `YUANXIAO_PLAN_STATE_FILE`; no model call is made.

Response shape:

```json
{
  "status": "ok",
  "projects": [
    {
      "id": "plan-id",
      "title": "Project title",
      "status": "running",
      "progress": 40,
      "updated_at": "2026-05-08T00:00:00+00:00",
      "last_report": "Latest summary",
      "ceo": {
        "id": "ceo-id",
        "name": "CEO",
        "session_id": "codex-or-worker-session",
        "status": "running",
        "progress": 35,
        "last_report": "CEO report"
      },
      "agents": [
        {
          "id": "agent-id",
          "name": "Implementation Agent",
          "role": "build",
          "session_id": "worker-session",
          "status": "running",
          "progress": 60,
          "last_report": "Agent report"
        }
      ]
    }
  ],
  "summary": {
    "project_count": 1,
    "agent_count": 1,
    "active_agents": 1,
    "blocked_agents": 0
  },
  "quota_cost": "none_file_scan_only",
  "scan_cost": "file_read"
}
```

When the plan state file has not changed, the bridge may return
`"scan_cost": "cache_hit"`.

`POST /api/plan/agent/create`

Creates a local Plan-tab Agent in `YUANXIAO_PLAN_STATE_FILE`. If `project_id`
is omitted and no project exists yet, the bridge creates a local test plan first.
This does not call a model.

Request shape:

```json
{
  "project_id": "optional-plan-id",
  "project_title": "元宵测试计划",
  "name": "测试 Agent",
  "role": "Agent",
  "current_task": "等待主人分配任务。",
  "status": "queued",
  "smoke_test": true
}
```

Response shape:

```json
{
  "status": "ok",
  "capability": "plan-agent-create",
  "quota_cost": "none_file_update_only",
  "created_project": false,
  "project_id": "plan-id",
  "agent": {
    "id": "agent-id",
    "name": "测试 Agent",
    "status": "completed",
    "progress": 100
  }
}
```

## Queue View

`GET /api/queue/tasks?limit=`

Returns current Hermes/Codex handoff queue state from local queue files through
the Mac mini bridge. This path is designed to avoid model quota usage.

Response shape:

```json
{
  "status": "ok",
  "tasks": [
    {
      "queue_id": "20260508_120000_abcd1234",
      "short_id": "abcd1234",
      "status": "queued",
      "status_label": "等待中",
      "position": 1,
      "task_summary": "Build task",
      "task_preview": "Longer task preview",
      "project_dir": "~/project",
      "platform": "feishu",
      "queued_at": "2026-05-08T00:00:00+00:00",
      "updated_at": "2026-05-08T00:00:00+00:00",
      "can_reorder": true
    }
  ],
  "summary": {
    "task_count": 1,
    "queued_count": 1,
    "running_count": 0
  },
  "quota_cost": "none_file_scan_only",
  "reorder_supported": true,
  "reorder_scope": "queued_only"
}
```

`POST /api/queue/reorder`

Updates queued-task positions. Running, completed, failed, or canceled tasks are
not reordered or interrupted.

Request shape:

```json
{
  "queue_ids": ["20260508_120000_abcd1234", "20260508_120010_efgh5678"]
}
```
