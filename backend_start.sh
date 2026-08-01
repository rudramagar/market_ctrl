#!/usr/bin/env bash

set -euo pipefail

# ENV
export MARKET_CONTROL_DROP_USERNAME=''
export MARKET_CONTROL_DROP_PASSWORD=''

export MARKET_CONTROL_API_USERNAME=''
export MARKET_CONTROL_API_PASSWORD=''

# Backend configuration
export MARKET_CONTROL_CHECKPOINT_FILE='/tmp/market-control-current_session.json'
export MARKET_CONTROL_CHECKPOINT_SAVE_INTERVAL_MESSAGES='100'
export MARKET_CONTROL_CHECKPOINT_RESTORE_ENABLED='true'
export MARKET_CONTROL_CHECKPOINT_SAVE_ON_SHUTDOWN='true'

drop_host='xnt-dde1api01n'
drop_port='12001'

api_host='xnt-dde1api01n'
api_port='11005'

http_host='127.0.0.1'
http_port='8080'

log_level='INFO'


# Usages:
# ./backend_start.sh --log-level DEBUG

project_root="$(
    cd "$(dirname "${BASH_SOURCE[0]}")"
    pwd
)"

cd "$project_root"

echo "Starting Market Control backend"
echo "  Project:     ${project_root}"
echo "  DROP:        ${drop_host}:${drop_port}"
echo "  Mercury API: ${api_host}:${api_port}"
echo "  HTTP:        ${http_host}:${http_port}"
echo "  Checkpoint:  ${MARKET_CONTROL_CHECKPOINT_FILE}"

exec python3 -m backend.main \
    -H "$drop_host" \
    -p "$drop_port" \
    --api-host "$api_host" \
    --api-port "$api_port" \
    --http-host "$http_host" \
    --http-port "$http_port" \
    --log-level "$log_level" \
    "$@"
