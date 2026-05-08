# YuanXiao / ChangE Control Plane

Native Android client and relay-side source for the private YuanXiao bridge used to communicate with ChangE.

## Layout

- `android/YuanXiao/` - Huawei-installable Android app source.
- `server/yuanxiao-server/` - ChangE Ubuntu HTTPS relay service source and systemd unit.
- `bridge/yuanxiao-hermes-bridge/` - Mac mini bridge from ChangE to Hermes, Codex, vision, session dashboard, Codex session chat, plan-state reads, and handoff queue reads.
- `ops/launchagents/` - Mac mini LaunchAgent definitions for the local bridge and SSH reverse tunnel.
- `docs/chang-e-android-control-plane/` - durable project docs, workflow notes, changelog, API contracts, and delivery checklist.

## Current Source Line

- Current app version: `0.41`
- Delivery APK name: `yuanxiao-0.41.apk`
- Latest Quark delivery APK: `yuanxiao-0.41.apk`
- Installed Android app label: `元宵`
- Public relay: configured locally through `android/YuanXiao/local.properties` and `ops/config/yuanxiao.env`.
- Standard delivery workflow: `煮元宵` means optimize, build, signature-verify, upload to Quark Netdisk folder `元宵`, push this repository, and send the Feishu/Yutu completion reminder.

## Safety Notes

This repository intentionally excludes private keys, `.env` files, local Android SDK paths, build products, bridge logs, image caches, Codex cache files, and runtime session-state files.

The Hermes API key stays on the Mac mini in the Hermes environment file and is not copied into the ChangE server or this repository.

Private relay hosts, IP addresses, SSH users, SSH keys, local paths, and admin tokens must stay in untracked config files. Start from:

- `android/YuanXiao/local.properties.example`
- `ops/config/yuanxiao.env.example`

## Local Build

The repository does not commit `local.properties`. On the Mac mini, build from the Android project with:

```bash
cd android/YuanXiao
JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" \
ANDROID_HOME="/Users/a/Library/Android/sdk" \
./gradlew assembleDebug
```

## Deployment

Server and Mac mini configuration is rendered from templates:

```bash
cp ops/config/yuanxiao.env.example ops/config/yuanxiao.env
# Edit ops/config/yuanxiao.env with private values.
ops/scripts/deploy_server.sh ops/config/yuanxiao.env
ops/scripts/render_launchagents.sh ops/config/yuanxiao.env
```

The example file uses `a` placeholders so another developer can see the shape without receiving private infrastructure details.
