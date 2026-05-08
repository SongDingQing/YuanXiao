# YuanXiao Change Log

## 0.39

- Plan CEO rows now open the dedicated CEO chat page from YuanXiao.
- Added `/api/plan/ceo/session` so a CEO chat can be created and bound lazily.
- Returning from a CEO chat opened from Plan goes back to the Plan tab.
- Built and signature-verified local `yuanxiao-0.39.apk`; SHA256 `61b0db56f87b9b22c3a84c2cf6ef8c18fad7438051445ade5229c875abcccaf9`.
- Deployed the bridge/server route and smoke-tested public forwarding with `upstream_status=400` for a missing `project_id`; latest Quark delivery remains `yuanxiao-0.38.apk` until the next `煮元宵`.

## 0.38

- Optimized the session-scoped request queue polling path for `煮元宵`.
- Removed obsolete global Queue-page Android code now that queues live inside session chats.
- Avoids rebuilding the session queue UI when the scoped queue state has not changed.
- Built, signature-verified, smoke-tested, and uploaded `yuanxiao-0.38.apk` to the existing Quark `元宵` folder; SHA256 `5e816443a13b8f693fa5dcb1e7141db8d1c2110cf9239fdb6acfa98f565a2f7f`.

## 0.37

- Removed the top-level Queue tab from the bottom navigation.
- Added a request queue panel inside each dedicated Codex session chat page.
- Queue reads now expose and filter session/agent fields so YuanXiao can show the current agent's own request queue.
- Built and signature-verified local `yuanxiao-0.37.apk`; SHA256 `be86b91ab20e94811a0c99fe4bf21f6b5d3e79665cd12c67217d6ba72e88e4a8`; Quark latest remains v0.35 until the next `煮元宵`.

## 0.36

- Changed the Plan tab into a multi-plan CEO orchestration view.
- Added plan creation that creates a dedicated CEO instead of a test Agent.
- Added per-plan `交给 CEO` requests while keeping ChangE as the only reporting manager.
- Added plan state fields for `change_managed_async` orchestration and `change_only` reporting.
- Built and signature-verified local `yuanxiao-0.36.apk`; SHA256 `dccd9c28913cd5cac2a198ca66fb82866ce13127bf8bc12d9e8ff7c2352b0ee1`; Quark latest remains v0.35 until the next `煮元宵`.

## 0.35

- Replaced the font-dependent copy glyph with a self-drawn two-card copy icon.
- Keeps the copy action outside the bubble while making the icon visible on Huawei/Android fonts.
- Built, signature-verified, smoke-tested, and uploaded `yuanxiao-0.35.apk` to the existing Quark `元宵` folder; SHA256 `e6daa20cd6622fb5296c3ab2614ae252ba4d9cd485dd164dc596f2855d201567`.

## 0.34

- Added a `↓ 最新` button above the main chat composer while browsing older messages.
- Added the same `↓ 最新` button above the dedicated Codex-session composer.
- Chat history re-render and session refresh now scroll back to the latest record.
- Built and signature-verified local `yuanxiao-0.34.apk`; SHA256 `a726152e00f40a5bcdc5ff8676d9f67f707f61288ca3fdcefa7a56de16fee80d`; Quark latest remains v0.33 until the next `煮元宵`.

## 0.33

- Changed Codex, Codex-session, and image chat requests to async relay mode by default.
- Added immediate Android delivery status for background chat tasks.
- Queues final async replies through the YuanXiao inbox so phone HTTPS timeouts do not drop the answer.
- Keeps Codex-session completion notices in the dedicated session flow instead of the main ChangE chat.
- Marks Plan-tab smoke-test Agents completed and recomputes project progress from current Agent state.
- Built, signature-verified, smoke-tested, and uploaded `yuanxiao-0.33.apk` to the existing Quark `元宵` folder; SHA256 `7038a9589c6ab7254d7d75c086be35129266ddaf4335e0cd590dd3064eb9fc9f`.

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
