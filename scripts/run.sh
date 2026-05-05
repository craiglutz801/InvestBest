#!/usr/bin/env bash
# Run InvestBest API + dashboard from project root
set -e
cd "$(dirname "$0")/.."
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
if [ ! -d ".venv" ]; then
  echo "Creating .venv and installing deps..."
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi
. .venv/bin/activate
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
