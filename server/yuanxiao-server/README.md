# YuanXiao Server

HTTPS relay for the YuanXiao Android APK. Current mode supports text payloads with Hermes/Codex target routing, `嫦娥识图` image payloads, ChangE-to-APK downlink messages, rich downlink attachments, a read-only Codex session dashboard, Plan view reads and Agent creation, and a queued-only handoff queue control path.

Route:

```text
YuanXiao APK
  -> https://<relay-host>/api/chat
  -> yuanxiao.service on ChangE
  -> http://localhost:<remote-bridge-port>/api/chat on ChangE
  -> SSH reverse tunnel to Mac mini
  -> local YuanXiao Hermes bridge
```

The Mac mini bridge sends default daily text to the local Hermes API.
When the APK sends `target=codex`, the bridge sends text to local Codex CLI professional chat (`gpt-5.4`) and returns `source=codex`.
Image messages are cached locally and analyzed by Codex CLI vision (`gpt-5.4-mini`), then returned to ChangE as `source=codex-via-hermes`.

Endpoints:

- `GET /health`
- `GET /api/inbox?after=&limit=` for YuanXiao APK downlink polling.
- `POST /api/inbox/admin` from localhost only, for Codex/ChangE to queue messages to the APK. Payloads may include `images`, `files`, `attachments`, or `links` arrays; the APK renders them as rich message attachments.
- `GET /api/codex/sessions?limit=` forwards to the Mac mini bridge and returns the current Codex session list from local state. This is file/database scanning, not a Codex model call.
- `GET /api/plan/projects?limit=` forwards to the Mac mini bridge and returns async project/CEO/agent status from local plan state. This is file scanning, not a model call.
- `POST /api/plan/agent/create` forwards to the Mac mini bridge and writes a new Agent into local plan state. This is file updating, not a model call.
- `GET /api/queue/tasks?limit=` forwards to the Mac mini bridge and returns Hermes/Codex handoff queue state from local queue files. This is file scanning, not a model call.
- `POST /api/queue/reorder` forwards queued-task ordering changes to the Mac mini bridge. Running tasks are not interrupted.
- `POST /api/chat` with JSON body `{"message":"...","target":"hermes"}` for daily Hermes replies.
- `POST /api/chat` with JSON body `{"message":"...","target":"codex"}` for Codex professional replies.
- `POST /api/chat` with image body:

```json
{
  "message": "optional text",
  "image_base64": "...",
  "image_mime_type": "image/jpeg",
  "image_name": "yuanxiao-image.jpg"
}
```

The service listens on the configured HTTPS port and uses a YuanXiao-specific CA bundled into the Android app.
Current relay request body limit is 6,000,000 bytes to avoid Android large image uploads surfacing as `software caused connection abort`.
Image requests and Codex text requests use a chunked keep-alive response while Codex is running, so mobile networks do not close the HTTPS connection before the final JSON reply arrives.
If the phone still disconnects during a long Codex run, ChangE waits for the bridge result in the background and queues the final reply into the YuanXiao inbox so the APK can receive it on the next inbox poll.
Short JSON responses explicitly close the HTTPS connection to avoid long-lived idle sockets showing up as later read-timeout noise.

The Hermes API key stays on the Mac mini in the Hermes env file. It is not copied to the ChangE server.

Private deployment values are intentionally kept out of this repository. Copy
`ops/config/yuanxiao.env.example` to an untracked `ops/config/yuanxiao.env`,
fill in host, SSH, certificate, and path values, then use
`ops/scripts/deploy_server.sh`.
