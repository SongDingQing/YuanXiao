# Deployment

## Private Config

Copy the example and fill in private values locally:

```bash
cp ops/config/yuanxiao.env.example ops/config/yuanxiao.env
```

The example uses `a` placeholders to show the shape of required values without
leaking a real host, IP address, SSH user, SSH key path, local Mac path, or admin
token.

Android uses:

```bash
cp android/YuanXiao/local.properties.example android/YuanXiao/local.properties
```

## Server Deploy

```bash
ops/scripts/deploy_server.sh ops/config/yuanxiao.env
```

The script renders TLS and systemd templates, copies the relay source to the
configured server, creates the service user if needed, installs the systemd unit,
generates a relay certificate from the configured SAN, and restarts the service.

Cloud-provider firewall/security-group rules must be managed outside this
repository.

## Mac Mini LaunchAgents

```bash
ops/scripts/render_launchagents.sh ops/config/yuanxiao.env
launchctl kickstart -k gui/$(id -u)/com.yutu.yuanxiao.hermes-bridge
launchctl kickstart -k gui/$(id -u)/com.yutu.yuanxiao.hermes-tunnel
```

The rendered LaunchAgents are local machine artifacts and should not be
committed.
