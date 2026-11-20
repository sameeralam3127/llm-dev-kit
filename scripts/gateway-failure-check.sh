#!/usr/bin/env bash
# What the gateway says when the web app is down, against a running stack.
#
#   docker compose up -d --build --wait
#   scripts/gateway-failure-check.sh
#
# Stops the web container, checks the gateway's answers, and starts web again.
# Run it after scripts/smoke.sh, on a stack you can interrupt for a minute.
#
#   - Page navigations (Accept: text/html) get the friendly "starting up" page.
#   - The web app's own API routes get a real 502, 503 or 504, never a 200.
#
# COMPOSE sets the compose command, for a stack that is not the default one:
#   COMPOSE="docker compose -p other -f docker-compose.yml" BASE=http://127.0.0.1:8083 ...
# Needs bash, curl and docker compose. No model is called.
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8080}"
COMPOSE="${COMPOSE:-docker compose}"
WAIT_SECONDS="${WAIT_SECONDS:-180}"
failures=0
web_stopped=0

pass() { printf '  ok    %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1"; failures=$((failures + 1)); }

# status METHOD PATH [curl args...]: print the HTTP status, following nothing.
status() {
  local method=$1 path=$2
  shift 2
  curl -s -o /dev/null -w '%{http_code}' --max-time 20 -X "$method" "$@" "$BASE$path"
}

# is_gateway_error CODE: the statuses nginx gives for an upstream that is down.
is_gateway_error() { [[ "$1" == "502" || "$1" == "503" || "$1" == "504" ]]; }

expect_gateway_error() {
  local what=$1 got=$2
  if is_gateway_error "$got"; then pass "$what ($got)"; else fail "$what: expected 502, 503 or 504, got $got"; fi
}

# Bring web back whatever happens, so a failed run does not leave the stack down.
restore_web() {
  if ((web_stopped)); then
    $COMPOSE start web >/dev/null 2>&1 || true
    web_stopped=0
  fi
}
trap restore_web EXIT

wait_for() {
  local what=$1
  shift
  local deadline=$((SECONDS + WAIT_SECONDS))
  until "$@"; do
    if ((SECONDS > deadline)); then
      echo "  FAIL  $what was not true within ${WAIT_SECONDS}s"
      return 1
    fi
    sleep 2
  done
}

sign_in_page_up() {
  local body
  body=$(curl -s --max-time 10 "$BASE/login") || return 1
  grep -q '<title>Sign in' <<<"$body"
}
api_answers_for_real() { [[ "$(status GET /api/admin/overview)" == "401" ]]; }
# The gateway serves its starting page only once a request to web fails
# outright, so this is true only after nginx has noticed web is down.
starting_page_shown() {
  local body
  body=$(curl -s --max-time 10 -H 'Accept: text/html' "$BASE/") || return 1
  grep -qi 'starting up' <<<"$body"
}

echo "Gateway failure check against $BASE"

wait_for "the sign-in page" sign_in_page_up || exit 1
pass "web is up before the check"

$COMPOSE stop web >/dev/null
web_stopped=1
# nginx re-resolves web every 10 s. Until then it still holds the stopped
# container's address, and a request there hangs instead of failing, so
# "the sign-in page is gone" is not enough (a timeout looks the same). Wait
# until the gateway really answers with its starting page, then check what
# the API routes get.
wait_for "the gateway to notice web is down" starting_page_shown || exit 1

expect_gateway_error "GET /api/health with web down" "$(status GET /api/health)"
expect_gateway_error "POST /api/chat with web down" "$(status POST /api/chat \
  -H 'Content-Type: application/json' -d '{"message":"hi"}')"
expect_gateway_error "GET /api/admin/overview with web down" "$(status GET /api/admin/overview)"

page=$(curl -s --max-time 20 -H 'Accept: text/html' -w '\n%{http_code}' "$BASE/")
code=${page##*$'\n'}
if [[ "$code" == "200" ]] && grep -qi 'starting up' <<<"$page"; then
  pass "GET / with Accept: text/html still shows the starting page"
else
  fail "GET / with Accept: text/html: expected the starting page with 200, got $code"
fi

# The Python services do not depend on web being up to answer their health check.
if [[ "$(status GET /api/rag/health)" == "200" ]]; then
  pass "/api/rag/health is not affected by web being down"
else
  fail "/api/rag/health changed while web was down"
fi

$COMPOSE start web >/dev/null
web_stopped=0
wait_for "the real sign-in page" sign_in_page_up || exit 1
pass "the real sign-in page is served again"
wait_for "web API routes to answer for real" api_answers_for_real || exit 1
pass "web API routes answer for real again (GET /api/admin/overview: 401)"

if ((failures > 0)); then
  echo "$failures check(s) failed"
  exit 1
fi
echo "All checks passed"
