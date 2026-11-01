#!/bin/bash
# SessionStart hook for Claude Code cloud sessions (human decision, 2026-10-14).
#
# Installs what the quality gate needs, so that the linters and every test,
# including the browser tests in Chromium, Firefox and WebKit (the engines CI
# runs), work from the first prompt; and the backlog's CLI.
#
# Idempotent: each step skips work that is already done, and the container is
# cached after this hook, so later sessions start fast. A failed step does not
# stop the others: the summary printed at the end names it, and the gate leaves
# out a browser engine that is missing, with a warning.
set -uo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}" || exit 1

log_file="/tmp/nock-session-start.log"
: >"$log_file"
failed_steps=()

# Run one step, its output going to the log; remember it when it fails.
run_step() {
  local label="$1"
  shift
  echo "=== $label" >>"$log_file"
  if ! "$@" >>"$log_file" 2>&1; then
    failed_steps+=("$label")
    return 1
  fi
  return 0
}

# Python: the project and its dev tools (ruff, black, pyrefly, pytest).
run_step "uv sync" uv sync

# Web client: install again only when the lockfile changed since the last one.
if [ ! -f web/node_modules/.package-lock.json ] ||
  [ web/package-lock.json -nt web/node_modules/.package-lock.json ]; then
  run_step "npm --prefix web ci" npm --prefix web ci
fi

# The backlog's CLI, pinned (human decision, 2026-11-01): its commands change
# between versions. A 130 MB binary, installed once per container.
backlog_version="1.55.3"
if [ "$(backlog --version 2>/dev/null)" != "$backlog_version" ]; then
  run_step "backlog.md" npm install --global "backlog.md@$backlog_version"
fi

# Browsers for the browser tests. Builds already installed are skipped.
run_step "playwright install" \
  uv run playwright install chromium firefox webkit

# CI's fonts: the browsers fall back to DejaVu Sans as on CI's Ubuntu runner,
# not to the image's Inter (human decision, 2026-10-16; see ci-fonts.conf).
fontconfig_dir="${XDG_CONFIG_HOME:-$HOME/.config}/fontconfig/conf.d"
run_step "CI fonts" install -D -m 644 .claude/hooks/ci-fonts.conf \
  "$fontconfig_dir/90-nock-ci-fonts.conf"

# Their system libraries, once per Playwright version (apt is slow).
browsers_dir="${PLAYWRIGHT_BROWSERS_PATH:-$HOME/.cache/ms-playwright}"
playwright_version="$(uv run playwright --version 2>/dev/null | awk '{print $2}')"
deps_marker="$browsers_dir/.nock-deps-${playwright_version:-unknown}"
if [ ! -f "$deps_marker" ]; then
  if run_step "playwright install-deps" \
    uv run playwright install-deps chromium firefox webkit; then
    touch "$deps_marker"
  fi
fi

if [ "${#failed_steps[@]}" -gt 0 ]; then
  echo "Session setup incomplete, failed: ${failed_steps[*]}. Log: $log_file"
  exit 0
fi
echo "Session setup done: Python and web dependencies, backlog.md" \
  "$backlog_version, Playwright" \
  "${playwright_version:-?} browsers (chromium, firefox, webkit), CI's fonts."
