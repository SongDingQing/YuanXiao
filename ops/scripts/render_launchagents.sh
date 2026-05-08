#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG_FILE="${1:-"$ROOT_DIR/ops/config/yuanxiao.env"}"
OUTPUT_DIR="${2:-"$HOME/Library/LaunchAgents"}"

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Missing config: $CONFIG_FILE"
  echo "Copy ops/config/yuanxiao.env.example to ops/config/yuanxiao.env and fill private values first."
  exit 1
fi

set -a
# shellcheck source=/dev/null
source "$CONFIG_FILE"
set +a

mkdir -p "$OUTPUT_DIR"

render_template() {
  local input="$1"
  local output="$2"
  python3 - "$input" "$output" <<'PY'
import os
import sys
from pathlib import Path

source = Path(sys.argv[1]).read_text()
for key, value in os.environ.items():
    source = source.replace(f"__{key}__", value)
Path(sys.argv[2]).write_text(source)
PY
}

render_template \
  "$ROOT_DIR/ops/launchagents/com.yutu.yuanxiao.hermes-bridge.plist.template" \
  "$OUTPUT_DIR/com.yutu.yuanxiao.hermes-bridge.plist"

render_template \
  "$ROOT_DIR/ops/launchagents/com.yutu.yuanxiao.hermes-tunnel.plist.template" \
  "$OUTPUT_DIR/com.yutu.yuanxiao.hermes-tunnel.plist"

echo "Rendered LaunchAgents into $OUTPUT_DIR"
