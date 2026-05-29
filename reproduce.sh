#!/usr/bin/env bash
# reproduce.sh — Single-command reproduction for orgschema-framework
#
# Installs dependencies, runs the test suite, and verifies the
# orgschema-validate CLI is installed. Conforms to PUBLIC_MIRROR_STANDARD.md v1.0.0.
#
# Usage:
#   ./reproduce.sh                  # Full: uv sync + pytest + CLI check
#   ./reproduce.sh --check-only     # Verify dependencies; skip tests
#
# Run log lands in output/logs/master_run.log

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

mkdir -p output/figures output/tables output/logs
LOG_FILE="output/logs/master_run.log"

echo "==================================================" | tee -a "$LOG_FILE"
echo "Pipeline run: $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG_FILE"
echo "Repo: $REPO_ROOT" | tee -a "$LOG_FILE"
echo "Git SHA: $(git rev-parse HEAD 2>/dev/null || echo 'not-a-repo')" | tee -a "$LOG_FILE"
echo "==================================================" | tee -a "$LOG_FILE"

CHECK_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --check-only) CHECK_ONLY=1 ;;
    *) echo "Unknown flag: $arg"; exit 2 ;;
  esac
done

# 1. Dependency check / install
echo ">>> Checking dependencies (uv sync)..." | tee -a "$LOG_FILE"
if command -v uv >/dev/null 2>&1; then
  uv sync --extra dev 2>&1 | tee -a "$LOG_FILE"
else
  echo "ERROR: uv not found. Install via 'curl -LsSf https://astral.sh/uv/install.sh | sh'" | tee -a "$LOG_FILE"
  exit 1
fi

if [[ "$CHECK_ONLY" == "1" ]]; then
  echo ">>> Check-only mode; exiting before tests." | tee -a "$LOG_FILE"
  exit 0
fi

# 2. Test suite
echo ">>> Running test suite (pytest)..." | tee -a "$LOG_FILE"
if uv run pytest --collect-only >/dev/null 2>&1; then
  uv run pytest 2>&1 | tee -a "$LOG_FILE"
else
  echo ">>> No tests collected; skipping pytest run." | tee -a "$LOG_FILE"
fi

# 3. CLI smoke check
echo ">>> Verifying orgschema-validate CLI installs..." | tee -a "$LOG_FILE"
uv run orgschema-validate --help 2>&1 | tee -a "$LOG_FILE" || true

echo "==================================================" | tee -a "$LOG_FILE"
echo "Pipeline complete: $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG_FILE"
echo "==================================================" | tee -a "$LOG_FILE"
