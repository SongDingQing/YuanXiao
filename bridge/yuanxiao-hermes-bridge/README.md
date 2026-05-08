# YuanXiao Hermes Bridge

Local Mac mini bridge for the YuanXiao APK.

Route:

```text
YuanXiao APK
  -> ChangE relay HTTPS /api/chat
  -> SSH reverse tunnel on ChangE localhost:<remote-bridge-port>
  -> Mac mini bridge localhost:<bridge-port>
```

Text route:

```text
Mac mini bridge
  -> local Hermes API
```

Image route:

```text
Mac mini bridge
  -> local image cache
  -> Codex CLI vision model gpt-5.4-mini
  -> JSON reply with source=codex-via-hermes and capability=change-vision
```

The Hermes API key stays in the local Hermes env file and is not copied to the
ChangE server.

Current support:

- text input,
- image input as `image_base64` plus `image_mime_type` through the `嫦娥识图` route,
- returned `images` array parsed from Markdown image links/data URLs in the reply.
- returned `files` array parsed from Markdown/raw file links in the reply, so YuanXiao can render file cards.
- read-only Codex session status at `GET /api/codex/sessions?limit=`, backed by the local Codex state database configured through environment variables. This does not call a Codex model and is safe for continuous dashboard polling.
- read-only Plan tab state at `GET /api/plan/projects?limit=`, backed by `YUANXIAO_PLAN_STATE_FILE`, with cache hits when the state file is unchanged.
- handoff Queue tab state at `GET /api/queue/tasks?limit=`, backed by the local Hermes/Codex handoff queue directory, plus queued-only ordering updates at `POST /api/queue/reorder`.

The companion `yuanxiao_agent_scheduler.py` script updates the local plan-state
file for future async project/CEO/agent orchestration without making model
calls itself.

Current limits:

- bridge request body: 6,000,000 bytes,
- image base64 payload: 4,500,000 characters,
- Codex vision timeout: 240 seconds.

LaunchAgents:

- `com.yutu.yuanxiao.hermes-bridge`
- `com.yutu.yuanxiao.hermes-tunnel`

Smoke tests:

```bash
curl http://localhost:<bridge-port>/health
ssh -i <ssh-key> <ssh-user>@<relay-host> 'curl -sS http://localhost:<remote-bridge-port>/health'
curl --cacert android/YuanXiao/app/src/main/res/raw/yuanxiao_ca.pem \
  -H 'Content-Type: application/json' \
  -d '{"message":"元宵桥接测试"}' \
  https://<relay-host>/api/chat
curl --cacert android/YuanXiao/app/src/main/res/raw/yuanxiao_ca.pem \
  'https://<relay-host>/api/codex/sessions?limit=5'
curl --cacert android/YuanXiao/app/src/main/res/raw/yuanxiao_ca.pem \
  'https://<relay-host>/api/plan/projects?limit=5'
curl --cacert android/YuanXiao/app/src/main/res/raw/yuanxiao_ca.pem \
  'https://<relay-host>/api/queue/tasks?limit=5'
```
