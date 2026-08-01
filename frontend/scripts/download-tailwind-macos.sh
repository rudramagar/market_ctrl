#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$project_root/tools"
case "$(uname -m)" in
  arm64) asset="tailwindcss-macos-arm64" ;;
  x86_64) asset="tailwindcss-macos-x64" ;;
  *) echo "Unsupported macOS architecture: $(uname -m)" >&2; exit 1 ;;
esac
curl -sSL "https://github.com/tailwindlabs/tailwindcss/releases/latest/download/$asset" -o "$project_root/tools/tailwindcss"
chmod +x "$project_root/tools/tailwindcss"
echo "Installed $project_root/tools/tailwindcss"
