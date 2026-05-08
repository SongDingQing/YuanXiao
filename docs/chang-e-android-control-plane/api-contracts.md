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
