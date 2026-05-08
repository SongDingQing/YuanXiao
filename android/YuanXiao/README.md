# YuanXiao

Native Android text/image communication MVP for the Chang-e control-plane project.

Product language: the user-facing action is `和嫦娥沟通`; `元宵` is the phone-side bridge that carries messages to and from `嫦娥`.

Workflow nickname: `煮元宵` means run a YuanXiao-wide optimization pass, build/signature-verify the YuanXiao APK when needed, upload the latest delivery package to the existing home/root-level Quark Netdisk folder `元宵`, then send a Feishu/Yutu completion reminder. Any YuanXiao Quark upload request uses this full standard workflow. `汤圆` means the same thing as `元宵`; `煮汤圆` means the same thing as `煮元宵`. Do not create new Quark folders or use a `夸克上传文件` path for YuanXiao APK delivery.

## Current Build

- App package: `com.example.yuanxiao`
- Installed app name: `元宵`
- APK output: configured by `yuanxiao.apk.outputDir` in `local.properties`.
- APK naming rule: delivery builds use `yuanxiao-<version>.apk`; avoid feature/debug descriptors in the final file name.
- Relay base URL: configured by `yuanxiao.relay.baseUrl` in `local.properties`.
- Server URL in app: `${yuanxiao.relay.baseUrl}/api/chat`
- Health URL in app: `${yuanxiao.relay.baseUrl}/health`
- Inbox URL in app: `${yuanxiao.relay.baseUrl}/api/inbox`
- Codex dashboard URL in app: `${yuanxiao.relay.baseUrl}/api/codex/sessions?limit=50`
- Trust model: app bundles `app/src/main/res/raw/yuanxiao_ca.pem` and disables cleartext traffic.
- Current route: APK -> ChangE HTTPS relay -> SSH reverse tunnel -> Mac mini YuanXiao bridge.
- Current main ChangE conversation id: `yuanxiao-change-main`; the main chat page uses this stable conversation for ordinary Hermes/Codex route sends where possible.
- Text route: default `Hermes 日常` -> Mac mini YuanXiao bridge -> Hermes API; optional `Codex 专业` -> Mac mini YuanXiao bridge -> local Codex CLI text chat (`gpt-5.4`).
- Image route: Mac mini YuanXiao bridge -> local Codex CLI vision (`gpt-5.4-mini`) -> ChangE reply with `source=codex-via-hermes`.
- Current target selector support: v0.13 adds bottom chat controls for `Hermes 日常` and `Codex 专业`; the APK sends `target`/`route` with each message and remembers the selected target. v0.25 sends main chat through stable conversation `yuanxiao-change-main`.
- Current copy control support: v0.14 moves the copy action out of the chat bubble and shows it as a small icon at the bubble's lower-right outside edge.
- Current delivery-status support: v0.15 shows `发送中`, `嫦娥已收到，等待回复`, `嫦娥已回复`, or failure state under the input box.
- Current Codex session chat support: v0.16 adds a `对话` button to each Dashboard session card; v0.17 opens a dedicated Codex session page with its own message list and input box, then sends text with `codex_session_id` so the Mac mini bridge can resume that session. v0.19 sends the owner's original text into the resumed session instead of the YuanXiao routing wrapper. v0.21 syncs visible Codex session history from Mac mini rollout logs and polls the dedicated session page every 15 seconds. v0.22 sends `after_order` on follow-up polls so YuanXiao only fetches missing messages. v0.23 appends newly returned session messages to the visible page instead of re-rendering the full history when possible.
- Current reply behavior: main chat replies are displayed as `嫦娥：...` even when the internal source is Hermes; dedicated Codex session replies are displayed in their separate session page.
- Current main chat history support: v0.25 stores the main ChangE chat history locally in the APK preferences, capped at 180 messages with long text and large data attachments bounded.
- Current media support: pick an image from Android document picker, compress it locally, send it to the `嫦娥识图` route, and render image replies when the relay returns image URLs/data URLs.
- Current image relay limit: ChangE accepts request bodies up to 6,000,000 bytes; Mac mini bridge accepts image base64 payloads up to 4,500,000 characters.
- Current long reply transport: ChangE sends chunked keep-alive headers/newlines for Hermes text, Codex text, and Codex vision, then returns the final JSON reply on the same request.
- Current notification support: creates Android local notifications when a reply or ChangE downlink message arrives while the app process is alive; Android 13+ asks for `POST_NOTIFICATIONS` permission. v0.19 also shows an in-app top banner for incoming ChangE and Codex session replies so foreground messages still have a visible popup inside YuanXiao.
- Current downlink support: v0.9 polls ChangE `/api/inbox`, renders主动下发 messages in the chat page, and triggers local notification.
- Current Codex dashboard support: v0.10 adds a dashboard that polls `/api/codex/sessions` every 15 seconds while visible. v0.12 groups sessions into status sections and keeps archived sessions folded by default. v0.16 adds direct session chat entry buttons. v0.17 keeps those conversations separate from the main ChangE chat page. v0.21 adds `/api/codex/session/messages` for visible user/assistant history sync. v0.22 caches parsed session messages on the Mac mini bridge, uses file size/mtime/offset to read appended log tails only, and returns `scan_cost` so repeated polls can stay at `cache_hit`. v0.23 keeps the APK-side session history bounded and uses incremental view appends after the first render. v0.24 adds `last_message_preview` to the Mac mini bridge dashboard response and renders each agent row as name, recent message preview, and recent interaction time only. v0.28 prevents overlapping Dashboard and inbox polls when an earlier poll is still running. The polling paths read local Codex state/log files through the Mac mini bridge and do not call a Codex model.
- Current UI support: redesigned v0.6 native UI with a status header, fixed-height text controls, separate search/chat/composer areas, and no default Android buttons that clip labels. v0.7 uses the Q-style Chang'e eating yuanxiao launcher icon. v0.8 moves search into the menu and a separate page. v0.10 makes the chat title `嫦娥`, changes the top-left control to `返回`, and shows the Chang'e icon only beside incoming ChangE messages. v0.18 folds the main chat bottom choices into an `选项` panel so the default composer stays compact. v0.20 keeps the package/project naming as YuanXiao while the installed launcher app name displays as `元宵`. v0.24 makes the Dashboard session list more compact and row-tap opens the dedicated session chat.
- Current rich message support: v0.11 renders Markdown text, tables, clickable links, Markdown image references, image/file/link attachment cards, and a one-tap copy button on each chat bubble. v0.19 aligns Markdown table columns with stable per-column widths. v0.23 adds a bounded cache for small Markdown render results.
- Current search support: in-memory chat history search with `查`/`上`/`下`/`清`, result count, jump-to-result, and highlighted bubbles.
- Current log support: server/link/test/status logs are folded into the top-left `日志` button and no longer occupy the chat stream. v0.23 keeps only the latest 120 log lines and autoscrolls logs only while the log panel is visible.
- Current changelog support: top `记录` button opens a change log where major lines are folded and minor version changes are listed one line per change.

## Build

```bash
cd android/YuanXiao
JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" \
ANDROID_HOME="/Users/a/Library/Android/sdk" \
./gradlew assembleDebug
```

Private values live in `local.properties`; use `local.properties.example` as the public template.

`assembleDebug` also copies the debug APK to:

```text
<yuanxiao.apk.outputDir>/yuanxiao-0.28.apk
```

## Verification

```bash
JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" \
  <android-sdk>/build-tools/<version>/apksigner verify --verbose \
  <yuanxiao.apk.outputDir>/yuanxiao-0.28.apk
```

Server local verification through SSH works:

```bash
ssh -i <ssh-key> <ssh-user>@<relay-host> \
  'curl -k https://localhost/health'
```

Public HTTPS, text relay, and `嫦娥识图` are verified from the Mac mini as of 2026-05-04 21:53 CST:

```bash
curl --cacert app/src/main/res/raw/yuanxiao_ca.pem https://<relay-host>/health
curl --cacert app/src/main/res/raw/yuanxiao_ca.pem \
  -H 'Content-Type: application/json' \
  -d '{"message":"元宵公网完整链路测试，请只回复：公网桥接正常。"}' \
  https://<relay-host>/api/chat
IMG="$(base64 < app/src/main/res/mipmap-xxxhdpi/ic_launcher.png | tr -d '\n')"
curl --cacert app/src/main/res/raw/yuanxiao_ca.pem \
  -H 'Content-Type: application/json' \
  -d "{\"message\":\"嫦娥识图链路测试：请用一句话说这张图是什么。\",\"image_base64\":\"$IMG\",\"image_mime_type\":\"image/png\"}" \
  https://<relay-host>/api/chat
```

Large mixed text/image public smoke test passed with a 2,564,006-byte upload and returned `source=codex-via-hermes`.
Mobile keep-alive smoke test passed with chunked newlines during a 115-second Codex vision run and then returned HTTP 200.
Codex dashboard smoke test passed on 2026-05-05 through public HTTPS; `/api/codex/sessions?limit=5` returned `status=ok`, `source=codex-state-db`, and `quota_cost=none_file_scan_only`.
Hermes route smoke test passed on 2026-05-06 through public HTTPS with `target=hermes` and returned `source=hermes`.
Codex text route smoke test passed on 2026-05-06 through public HTTPS with `target=codex` and returned `source=codex`, `capability=codex-chat`, and `engine=codex-cli:gpt-5.4`.
Delivery status smoke test passed on 2026-05-06 through public HTTPS; `/api/chat` returns `Transfer-Encoding: chunked` for Hermes text, letting the APK mark `嫦娥已收到` before the final reply.
Codex session chat plumbing smoke test passed on 2026-05-06: an invalid `codex_session_id` is forwarded through ChangE to the Mac mini bridge and rejected in 248ms without calling a Codex model.
Codex session history sync smoke test passed on 2026-05-08: public HTTPS `/api/codex/session/messages?session_id=...&limit=3` returned `status=ok`, `source=codex-session-log`, `server=change`, and `quota_cost=none_file_scan_only`.
Codex session incremental sync smoke test passed on 2026-05-08: public reads return `next_cursor`; repeated reads with `after_order` returned zero messages with `scan_cost=cache_hit`.

The latest Quark Netdisk folder `元宵` upload is:

- 首页的 `元宵` 文件夹 / `yuanxiao-0.28.apk`
- Future YuanXiao packages must be uploaded into this existing folder only.

The latest local built APK is `<yuanxiao.apk.outputDir>/yuanxiao-0.28.apk`. The latest Quark delivery APK is `yuanxiao-0.28.apk`, uploaded to the existing home/root-level `元宵` folder on 2026-05-08 as part of the standard `煮元宵` workflow. YuanXiao v0.28 includes Dashboard/inbox poll in-flight guards, bridge structured request-log trimming, and the long Codex session timeout fixes from v0.27.
