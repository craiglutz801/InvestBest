#!/usr/bin/env bash
# Chan research test suite (Stages 1–6) on the assembled integration branch.
# Research/paper only. Does not deploy, merge, place orders, or require broker keys.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"

echo "==> Installing Chan research packages (editable, test extras)"
"$PYTHON" -m pip install -e "research/statistical_diagnostics[test]"
"$PYTHON" -m pip install -e "research/mean_reversion_eligibility[test]"
"$PYTHON" -m pip install -e "research/trend_carry[test]"
"$PYTHON" -m pip install -e "research/edge_health[test]"
"$PYTHON" -m pip install -e "research/anti_overfit_promotion[test]"
"$PYTHON" -m pip install -e "research/research_loop[test]"

# Run each package as its own pytest root so test_isolation.py names do not collide.
echo "==> Stage 1 statistical diagnostics"
"$PYTHON" -m pytest research/statistical_diagnostics

echo "==> Stage 2 mean-reversion eligibility"
"$PYTHON" -m pytest research/mean_reversion_eligibility

echo "==> Stage 3 trend/carry"
"$PYTHON" -m pytest research/trend_carry

echo "==> Stage 4 edge health"
"$PYTHON" -m pytest research/edge_health

echo "==> Stage 5 anti-overfit promotion"
"$PYTHON" -m pytest research/anti_overfit_promotion

echo "==> Stage 6 research loop + native contract tests"
"$PYTHON" -m pytest research/research_loop

echo "==> Synthetic end-to-end harness (requires native Stages 1–5)"
"$PYTHON" -m northstar_research_loop

echo "==> CHAN_RESEARCH_SUITE_OK"
