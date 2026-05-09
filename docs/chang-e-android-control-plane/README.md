# ChangE Android Control Plane

YuanXiao is a native Android bridge for talking with ChangE. The APK sends chat,
image, file-oriented, and Codex-session control requests to a public relay. The
relay forwards work to a Mac mini bridge that can route ordinary chat to Hermes
and professional/code work to Codex.

## Components

- Android APK: `android/YuanXiao`
- Public relay service: `server/yuanxiao-server`
- Mac mini bridge: `bridge/yuanxiao-hermes-bridge`
- Async plan-state helper: `bridge/yuanxiao-hermes-bridge/yuanxiao_agent_scheduler.py`
- Deployment templates and scripts: `ops`

Private infrastructure details, including relay hosts, IP addresses, SSH users,
SSH keys, local Mac paths, admin tokens, and runtime logs, are not committed.
Use the example config files as templates.

## Current Version

- App version: `0.49`
- Local build APK name: `yuanxiao-0.49.apk`
- Latest Quark delivery APK: `yuanxiao-0.49.apk`
- Installed Android label: `元宵`
- Latest major behavior: bottom Hermes/Codex/Plan tabs, compact Codex session
  rows, persistent main ChangE chat, Codex session chat/history sync, Codex
  session create/rename, duplicate-poll guards, plan-state API foundation,
  cached plan-state reads, handoff queue sync, queued-task reordering, and
  Plan-tab Agent creation, async Codex/image replies, smoke-test Plan progress
  completion, chat "jump to latest" controls, self-drawn copy icons, and a
  multi-plan CEO orchestration view with ChangE-managed reporting,
  session-scoped request queues inside each Codex session chat, optimized
  session-queue polling/rendering, direct CEO chat entry from each plan, and
  cleaner Codex session chat where ChangE transport receipts stay out of the
  message stream, lighter initial session-history rendering, the first ChangE
  task-center tab backed by a durable task ledger, event API, agent registry,
  stale-task blocking, and tighter chat spacing with a subtler copy icon.
