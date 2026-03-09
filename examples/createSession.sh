#!/usr/bin/env bash

set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
USER_ID="${USER_ID:-u10001}"
TITLE="${TITLE:-新建会话}"
EXPIRE_SECONDS="${EXPIRE_SECONDS:-1200}"

curl --request POST "${BASE_URL}/chat/create" \
  --header "Content-Type: application/json" \
  --data-raw "{
    \"user_id\": \"${USER_ID}\",
    \"title\": \"${TITLE}\",
    \"expire_seconds\": ${EXPIRE_SECONDS},
    \"client_capabilities\": [\"web_search\", \"vision\"],
    \"metadata\": {
      \"source\": \"shell-example\"
    }
  }"
