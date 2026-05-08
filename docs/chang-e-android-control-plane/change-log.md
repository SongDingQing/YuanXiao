# YuanXiao Change Log

## 0.33

- Changed Codex, Codex-session, and image chat requests to async relay mode by default.
- Added immediate Android delivery status for background chat tasks.
- Queues final async replies through the YuanXiao inbox so phone HTTPS timeouts do not drop the answer.
- Keeps Codex-session completion notices in the dedicated session flow instead of the main ChangE chat.
- Marks Plan-tab smoke-test Agents completed and recomputes project progress from current Agent state.
- Built and signature-verified local `yuanxiao-0.33.apk`; SHA256 `7038a9589c6ab7254d7d75c086be35129266ddaf4335e0cd590dd3064eb9fc9f`; Quark latest remains v0.32 until the next `煮元宵`.

## 0.32

- Added Plan-tab Agent creation from the Android app.
- Added `/api/plan/agent/create` through ChangE and the Mac mini bridge.
- Auto-creates a local test plan when the Plan tab has no project yet.
- Bumped the delivery APK version to `yuanxiao-0.32.apk`.
- Server hotfix: if the phone disconnects during a long Codex reply, ChangE now queues the final reply into the YuanXiao inbox instead of dropping it.
- Server hotfix: normal JSON responses now close the HTTPS connection explicitly to reduce idle socket timeout noise.

## 0.31

- Added a bottom Queue tab for Hermes/Codex handoff queue sync.
- Added collapsible queue guide text and queued-only up/down reordering.
- Added `/api/queue/tasks` and `/api/queue/reorder` through ChangE and the Mac mini bridge.
- Built and signature-verified local `yuanxiao-0.31.apk`; Quark latest remains v0.30 until the next `煮元宵`.

## 0.30

- Added bridge-side plan-state cache hits when the plan JSON file is unchanged.
- Bumped the delivery APK version to `yuanxiao-0.30.apk`.
- Built, signature-verified, smoke-tested, and uploaded `yuanxiao-0.30.apk` to the existing Quark `元宵` folder.

## 0.29

- Reworked the top-level Android navigation into bottom Hermes, Codex, and Plan tabs.
- Added a Plan tab that renders project, CEO, and agent status from a local plan-state API.
- Added `/api/plan/projects` through the ChangE relay and Mac mini bridge.
- Added `yuanxiao_agent_scheduler.py` as the first dedicated async plan-state helper.

## 0.28

- Prevented overlapping Dashboard and inbox polling in the Android app.
- Added bounded structured request-log retention in the Mac mini bridge.
- Kept the long Codex session timeout fixes from v0.27.
- Moved private relay base URL and APK output path into local-only Android
  properties with a committed example template.
- Replaced committed private deployment details with public templates.

## 0.27

- Raised long targeted Codex session chat timeouts to handle very large sessions.
- Added structured timing/error logs around Codex chat requests.

## 0.26

- Added Codex session creation from the Dashboard.
- Added Codex session rename from the dedicated session page.

## 0.25

- Preserved the main ChangE chat history locally on the phone.
- Reused a stable main ChangE conversation for normal chat.

## 0.24

- Made the Dashboard compact: name, recent message preview, and recent time.
- Added bridge-side last-message previews without model quota usage.

## 0.23

- Added incremental session-history appends and bounded UI/log/Markdown caches.

## Earlier Highlights

- Added direct ChangE downlink inbox polling.
- Added local notifications and in-app incoming-message banners.
- Added Markdown, clickable links, table rendering, image/file/link cards, and
  external copy buttons.
- Added Hermes/Codex route selection.
- Added dedicated Codex session chat pages.
- Added image upload and Codex vision routing.
- Added the Q-style ChangE eating yuanxiao launcher icon.
