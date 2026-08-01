#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
"$project_root/tools/tailwindcss" -i "$project_root/src/input.css" -o "$project_root/css/output.css" --watch
