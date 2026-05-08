# ChangE Android Control Plane

YuanXiao is a native Android bridge for talking with ChangE. The APK sends chat,
image, file-oriented, and Codex-session control requests to a public relay. The
relay forwards work to a Mac mini bridge that can route ordinary chat to Hermes
and professional/code work to Codex.

## Components

- Android APK: `android/YuanXiao`
- Public relay service: `server/yuanxiao-server`
- Mac mini bridge: `bridge/yuanxiao-hermes-bridge`
- Deployment templates and scripts: `ops`

Private infrastructure details, including relay hosts, IP addresses, SSH users,
SSH keys, local Mac paths, admin tokens, and runtime logs, are not committed.
Use the example config files as templates.

## Current Version

- App version: `0.28`
- APK delivery name: `yuanxiao-0.28.apk`
- Installed Android label: `元宵`
- Latest major behavior: compact dashboard rows, persistent main ChangE chat,
  Codex session chat/history sync, Codex session create/rename, long-session
  timeout handling, and duplicate-poll guards.
