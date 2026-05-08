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
