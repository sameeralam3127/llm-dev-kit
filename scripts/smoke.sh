#!/usr/bin/env bash
# Smoke test of a running stack, through the gateway, as a client sees it.
#
#   docker compose up -d --build --wait
#   scripts/smoke.sh                     # read-only checks
#   SMOKE_REGISTER=1 scripts/smoke.sh    # also registers a throwaway account
#
# Read-only by default, so it is safe against an instance you use. CI sets
# SMOKE_REGISTER=1 against a fresh stack. Needs only bash and curl; no model
# is called, so it passes without Ollama.
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8080}"
WAIT_SECONDS="${WAIT_SECONDS:-180}"
failures=0

pass() { printf '  ok    %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1"; failures=$((failures + 1)); }

# status METHOD PATH [curl args...]: print the HTTP status, following nothing.
status() {
  local method=$1 path=$2
  shift 2
  curl -s -o /dev/null -w '%{http_code}' -X "$method" "$@" "$BASE$path"
}

expect() {
  local want=$1 what=$2 got=$3
  if [[ "$got" == "$want" ]]; then pass "$what ($got)"; else fail "$what: expected $want, got $got"; fi
}

echo "Smoke test against $BASE"

# 1. The gateway and every service are up. While the web app starts, nginx
# answers 200 with its "starting up" page, so wait for the real sign-in page
# and for both Python services, not just for a 200.
ready() {
  curl -s "$BASE/login" | grep -q '<title>Sign in' &&
    [[ "$(status GET /api/rag/health)" == "200" ]] &&
    [[ "$(status GET /api/llm/health)" == "200" ]]
}
deadline=$((SECONDS + WAIT_SECONDS))
until ready; do
  if ((SECONDS > deadline)); then
    echo "  FAIL  the stack at $BASE was not ready within ${WAIT_SECONDS}s"
    exit 1
  fi
  sleep 3
done
pass "sign-in page answers"

expect 307 "signed-out visitors are sent to sign-in" "$(status GET /)"
expect 307 "the admin console needs a session" "$(status GET /admin)"

headers=$(curl -s -D - -o /dev/null "$BASE/login")
grep -qi '^x-frame-options: *DENY' <<<"$headers" && pass "X-Frame-Options: DENY" || fail "X-Frame-Options header missing"
grep -qi '^x-content-type-options: *nosniff' <<<"$headers" && pass "X-Content-Type-Options: nosniff" || fail "X-Content-Type-Options header missing"

# 2. Every Python service answers its public health check through the gateway.
expect 200 "rag-service health" "$(status GET /api/rag/health)"
expect 200 "llm-service health" "$(status GET /api/llm/health)"

# 3. Nothing else is reachable without a credential, and errors use the envelope.
expect 401 "/v1/models needs a credential" "$(status GET /v1/models)"
expect 401 "chat needs a credential" "$(status POST /api/rag/chat -H 'Content-Type: application/json' -d '{"message":"hi"}')"
expect 401 "the document index needs a credential" "$(status GET /api/rag/documents/stats)"
expect 401 "admin APIs need a session" "$(status GET /api/admin/overview)"
expect 401 "an unknown API key is refused" "$(status GET /v1/models -H 'Authorization: Bearer sk-ldk-not-a-real-key')"
body=$(curl -s "$BASE/v1/models")
grep -q '"code": *"unauthorized"' <<<"$body" && pass "401s use the error envelope" || fail "401 body is not the error envelope: $body"

# 4. Optional: register a throwaway account (changes data; fresh stacks only).
if [[ "${SMOKE_REGISTER:-0}" == "1" ]]; then
  suffix=$(date +%s)$RANDOM
  password="Smoke-${suffix}-pw"
  expect 201 "registering an account" "$(status POST /api/auth/register \
    -H 'Content-Type: application/json' \
    -d "{\"name\":\"Smoke test\",\"email\":\"smoke-${suffix}@example.test\",\"password\":\"${password}\"}")"
  expect 409 "the same email cannot register twice" "$(status POST /api/auth/register \
    -H 'Content-Type: application/json' \
    -d "{\"name\":\"Smoke test\",\"email\":\"smoke-${suffix}@example.test\",\"password\":\"${password}\"}")"
fi

if ((failures > 0)); then
  echo "$failures check(s) failed"
  exit 1
fi
echo "All checks passed"
