#!/usr/bin/env bash
# Chan research test suite (Stages 1 + 6). Research/paper only.
# Does not deploy, merge, place orders, or require broker credentials.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"

echo "==> Installing Stage 1 diagnostics (editable, test extra)"
"$PYTHON" -m pip install -e "research/statistical_diagnostics[test]"

echo "==> Installing Stage 6 research loop (editable, test extra)"
"$PYTHON" -m pip install -e "research/research_loop[test]"

if [ -d "research/trend_carry" ]; then
  echo "==> Installing Stage 3 trend/carry (present on this checkout)"
  "$PYTHON" -m pip install -e "research/trend_carry[test]"
fi

echo "==> Stage 1 unit tests"
"$PYTHON" -m pytest research/statistical_diagnostics

echo "==> Stage 6 unit + harness tests"
"$PYTHON" -m pytest research/research_loop

if [ -d "research/trend_carry" ]; then
  echo "==> Stage 3 unit tests"
  "$PYTHON" -m pytest research/trend_carry
fi

echo "==> Synthetic end-to-end harness (JSON report)"
"$PYTHON" -m northstar_research_loop

echo "==> CHAN_RESEARCH_SUITE_OK"
