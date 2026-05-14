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
Each project is a separate plan with one dedicated CEO. ChangE owns reporting
and orchestration; worker roles do not wait for one another's internal reports.

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
      "objective": "Owner request",
      "orchestration_mode": "change_managed_async",
      "reporting_policy": "change_only",
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
    "ceo_count": 1,
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

`POST /api/plan/project/create`

Creates a new plan and its dedicated CEO in `YUANXIAO_PLAN_STATE_FILE`. This is
the phone-side entry for a new multi-agent plan. It writes state only and does
not call Codex/Hermes directly.

Request shape:

```json
{
  "title": "新品活动计划",
  "ceo_name": "活动 CEO",
  "owner_request": "拆解活动策划、执行层和检查层。",
  "orchestration_mode": "change_managed_async",
  "reporting_policy": "change_only"
}
```

Response shape:

```json
{
  "status": "ok",
  "capability": "plan-project-create",
  "quota_cost": "none_file_update_only",
  "project": {
    "id": "plan-id",
    "title": "新品活动计划",
    "reporting_policy": "change_only"
  }
}
```

`POST /api/plan/ceo/request`

Adds a new owner request to a plan's CEO. ChangE records the request, keeps the
project in `change_managed_async` mode, and keeps all progress reporting under
ChangE management.

Request shape:

```json
{
  "project_id": "plan-id",
  "message": "请先拆成活动策划、素材执行和复盘检查。",
  "reporting_policy": "change_only"
}
```

`POST /api/plan/ceo/session`

Ensures a plan CEO has a dedicated Codex session and returns the session record
that YuanXiao should open. If the CEO already has a valid session, this is a
database lookup only. If no valid session exists, the bridge creates and binds a
new Codex session for that CEO.

Request shape:

```json
{
  "project_id": "plan-id"
}
```

Response shape:

```json
{
  "status": "ok",
  "capability": "plan-ceo-session",
  "quota_cost": "none_db_lookup_only",
  "project_id": "plan-id",
  "ceo": {
    "id": "ceo-id",
    "name": "CEO",
    "role": "CEO",
    "session_id": "codex-session-id"
  },
  "session": {
    "id": "codex-session-id",
    "title": "CEO · Project title · CEO"
  }
}
```

When a new session must be created, `quota_cost` is
`codex_model_init_call`.

`POST /api/plan/agent/create`

Legacy local state helper for adding an execution role in `YUANXIAO_PLAN_STATE_FILE`. If `project_id`
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
YuanXiao v0.37 uses this data inside a specific Codex session chat page rather
than as a top-level tab.

Optional filters:

- `session_id`: return tasks linked to the current Codex/a session.
- `session_title`: fallback text match when a queue item has not stored a
  session id yet.

Response shape:

```json
{
  "status": "ok",
  "tasks": [
    {
      "queue_id": "20260508_120000_abcd1234",
      "short_id": "abcd1234",
      "codex_session_id": "optional-session-id",
      "agent_name": "optional-agent-name",
      "status": "queued",
      "status_label": "等待中",
      "position": 1,
      "task_summary": "Build task",
      "task_preview": "Longer task preview",
      "project_dir": "workspace:project",
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
  "scope_session_id": "optional-session-id",
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

## Agent Control Plane

These endpoints expose the first structured control-plane layer for YuanXiao.
They are designed for Android-native cards and status panels, and should avoid
model quota usage unless a future runner explicitly performs work.

`GET /api/v1/runner-adapters?status=`

Returns configured runner adapters such as Codex, Hermes, ChangE relay, and
future remote machines.

Response shape:

```json
{
  "status": "ok",
  "schema_version": 1,
  "adapters": [
    {
      "adapter_id": "runner_codex_local_default",
      "display_name": "Codex · Mac mini",
      "runner_type": "codex",
      "client_mode": "desktop_cli_resume",
      "machine_id": "macmini",
      "status": "available",
      "workspace_policy": {
        "allowlist": ["workspace:yuanxiao"],
        "denylist": ["secret:ssh"]
      },
      "capabilities": {
        "supports_checkpoint": true,
        "supports_subagents": true
      },
      "approval_policy": {
        "default_mode": "ask_high_impact"
      }
    }
  ],
  "quota_cost": "none_db_scan_only"
}
```

`GET /api/v1/capabilities?status=&side_effect_level=`

Returns the capability registry used by the MCP/tool gateway layer. Each record
includes source, protocol, side-effect level, secret policy, isolation, Android
renderer hints, and audit requirements.

`GET /api/v1/workflow-nodes?project_id=&workflow_id=&state=&limit=`

Returns Plan/CEO orchestration nodes. YuanXiao should use this for router,
orchestrator, subagent, evaluator, todo, checkpoint, failure, and verification
progress views.

`POST /api/v1/workflow-nodes`

Creates or updates a workflow node.

Request shape:

```json
{
  "workflow_id": "workflow-id",
  "node_id": "node-id",
  "project_id": "plan-id",
  "parent_node_id": "optional-parent",
  "node_type": "subagent",
  "state": "running",
  "title": "执行层整理素材",
  "owner": {
    "runner_adapter_id": "runner_codex_local_default",
    "session_id": "optional-session"
  },
  "todo": ["读取需求", "生成方案", "提交验证证据"],
  "checkpoint": {
    "label": "需求已确认"
  },
  "trace": {
    "trace_id": "trace-id"
  },
  "policy": {
    "approval_required": false
  }
}
```

`GET /api/v1/cards?task_id=&status=&card_type=&limit=`

Returns typed cards for Android-native rendering. Supported card types include
`approval`, `artifact`, `trace`, `failure`, `memory`, `checkpoint`, and
`report`.

`POST /api/v1/cards`

Creates or updates a typed card.

Request shape:

```json
{
  "card_id": "card-id",
  "card_type": "approval",
  "task_id": "task-id",
  "workflow_id": "workflow-id",
  "node_id": "node-id",
  "status": "pending",
  "title": "是否允许发送外部消息",
  "summary": "这会把内容发到外部服务。",
  "actions": ["approve", "reject"],
  "payload": {
    "risk": "external_send"
  }
}
```

`POST /api/v1/cards/answer`

Records an answer to a typed card without deleting the original card.

Request shape:

```json
{
  "card_id": "card-id",
  "answer": "approve",
  "actor": "主人",
  "fields": {
    "note": "允许本次发送"
  }
}
```

`GET /api/v1/mobile-smoke-runs?limit=`

Returns recent YuanXiao mobile smoke benchmark runs and the required case list.

`POST /api/v1/mobile-smoke-runs`

Creates or updates a smoke benchmark run.

Request shape:

```json
{
  "run_id": "smoke-run-id",
  "app_version": "0.49",
  "server_version": "control-plane-v1",
  "device": "Huawei test device",
  "status": "passed",
  "summary": {
    "passed": 10,
    "failed": 0
  },
  "cases": [
    {
      "id": "main_chat",
      "status": "passed"
    }
  ]
}
```
