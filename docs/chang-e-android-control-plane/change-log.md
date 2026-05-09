# YuanXiao Change Log

## 0.48

- Optimized the Codex-session receipt path so a server echo for an already visible outgoing message updates the receipt state without forcing a full session chat re-render.
- Kept full re-render only for matched non-user local messages or attachment-count changes where visual content may differ.
- Deferred larger chat virtualization and API-v1 message migration because they need broader device and server compatibility validation.
- Built and signature-verified `yuanxiao-0.48.apk`; SHA256 `2822b1af7990326f0194efe86196f330ef594d8a25c4106c2e54b0a94af5c440`.
- Public `/health` and Codex session-list smoke tests returned `status=ok` with file/db-only read paths.
- Uploaded `yuanxiao-0.48.apk` to the existing Quark root/home `元宵` folder; Quark showed it in that folder with timestamp 2026-05-09 21:43.
- Included this source update in the standard GitHub delivery push for `SongDingQing/YuanXiao`.

## 0.47

- Added a tiny hollow-circle receipt indicator below outgoing user messages in dedicated Codex-session chats.
- The receipt indicator turns into a check mark after ChangE confirms the session request has been accepted.
- Persisted receipt state in local session history so re-rendered sent messages keep their checked state.
- Built and signature-verified local `yuanxiao-0.47.apk`; SHA256 `b41398449e1b0f5b50023244ef7b8cce79361df7ad9b9575afbccf3c7000629d`; latest Quark delivery remains `yuanxiao-0.42.apk` until the next `煮元宵`.

## 0.46

- Moved the dedicated Codex-session delivery/sync status from below the input box into the conversation header area.
- Replaced the raw session id subtitle with a compact `复制 Session ID` button.
- The session id button copies the full selected Codex session id to the Android clipboard and writes a short success log.
- Built and signature-verified local `yuanxiao-0.46.apk`; SHA256 `6fc39549cb2279671fb01d3e19c6fd0b28f416e810102ca436130bcf29da063f`; latest Quark delivery remains `yuanxiao-0.42.apk` until the next `煮元宵`.

## 0.45

- Replaced the old full-width in-app message banner with a compact card-style notification.
- Shortened the in-app notification auto-hide delay from 5.2 seconds to 3.2 seconds.
- Added upward swipe-to-dismiss for the in-app notification card.
- Added tap-to-open routing for the in-app card: main ChangE messages open the Hermes chat, and Codex-session messages open the matching dedicated session.
- Added the same destination extras to Android system notifications so tapping them can jump to the right conversation.
- Built and signature-verified local `yuanxiao-0.45.apk`; SHA256 `7c76861db82e021d72d762fd1d2dfe64adbbded297a1d855bba983b365e5358f`; latest Quark delivery remains `yuanxiao-0.42.apk` until the next `煮元宵`.

## 0.44

- Enabled Android-native text selection on rendered chat text and markdown table cells.
- Added whole-message quote/copy actions from a long-press menu on chat bubbles.
- Added selected-text quote support through the Android text selection action menu.
- Quote context now prefixes outgoing main ChangE and dedicated Codex-session requests with `参考你刚刚发送的消息：...`.
- Added a compact quote preview above both chat composers with a cancel action.
- Built and signature-verified local `yuanxiao-0.44.apk`; SHA256 `8c02b75de68488abdb206a5c6d40247ac91eff26f6d29cf9f62a6c006ad4bfb8`; latest Quark delivery remains `yuanxiao-0.42.apk` until the next `煮元宵`.

## 0.43

- Shrank the external chat-copy icon from a prominent button into a smaller transparent two-rectangle icon.
- Moved the copy icon beside the lower-right of the bubble instead of giving it a separate full-width row.
- Reduced chat row vertical padding so adjacent conversation bubbles sit closer together.
- Built and signature-verified local `yuanxiao-0.43.apk`; SHA256 `e231965aa0034b2e9b64abc7a052e58a893bf3023abb69a43e1f1218c1162f6e`; latest Quark delivery remains `yuanxiao-0.42.apk` until the next `煮元宵`.

## 0.42

- Added `change_scheduler.py`, a durable SQLite task ledger for ChangE/YuanXiao task cards, task events, static agent registry, and stale-task blocking.
- Added public/bridge `/api/v1/tasks`, `/api/v1/events`, and `/api/v1/agents` routes; `/health` now advertises task ledger, stuck detection, event API, and agent API support.
- Added a bottom `任务` tab in the APK with compact task cards, progress bars, latest event text, blocker/error fields, and 12-second polling only while visible.
- Task cards sort blocked/failed work first, then newest same-status updates first so old tasks do not bury fresh activity.
- Codex/image/session async requests now create/update task cards and return `task_id`; background receipt chatter stays in status/notice areas instead of crowding the main chat stream.
- Link optimization: status/task reads use shorter timeouts, POST paths close connections explicitly, and the Android executor pool was widened so polling and sending do not block each other as easily.
- Built and signature-verified `yuanxiao-0.42.apk`; SHA256 `35fa651ba18ca90e713e3e45ff59741271c7de69990104795a92cca5d4418c67`.
- Public task-center smoke test returned `status=ok`, `source=change-task-ledger+compat`, task summary data, and health flags for task ledger/event/agent APIs.
- Uploaded `yuanxiao-0.42.apk` to the existing Quark root/home `元宵` folder; Quark showed it in that folder with timestamp 2026-05-09 10:49.

## 0.41

- Optimized the `煮元宵` session-history path so initial Codex-session sync no longer forces a full chat re-render when nothing changed.
- Keeps local session history on screen and only appends newly returned messages unless a full render is required.
- Bumped the delivery APK to `yuanxiao-0.41.apk`.
- Built and signature-verified `yuanxiao-0.41.apk`; SHA256 `1f75842ab3505827c5f535e9363de84036cd8768a6eedb96c8c40e5988e1979b`.
- Public session-history smoke test returned `status=ok`, `source=codex-session-log`, `quota_cost=none_file_scan_only`, and 3 messages.
- Uploaded `yuanxiao-0.41.apk` to the existing Quark root/home `元宵` folder; Quark showed it at the top of the folder with timestamp 2026-05-08 15:42.
- Pushed GitHub `SongDingQing/YuanXiao` main and recorded this delivery.

## 0.40

- Codex-session async receipt text is no longer inserted as a ChangE chat bubble.
- Codex-session background completion notices now update the status bar and notification, then sync the real Codex history.
- Keeps the dedicated session message stream focused on the actual user/Codex conversation.
- Built and signature-verified local `yuanxiao-0.40.apk`; SHA256 `55cb98addc7df304b8eb196afe478386cd1dc8ed28fe29828ebd06038d2e773e`.
- Latest Quark delivery remains `yuanxiao-0.38.apk` until the next `煮元宵`.

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
