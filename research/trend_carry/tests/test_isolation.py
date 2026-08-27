"""Isolation: Stage 3 must not touch brokers, orders, or execution paths."""

from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_IMPORT_TOKENS = {
    "alpaca",
    "alpaca_trade_api",
    "ib_insync",
    "ibapi",
    "ccxt",
    "broker",
    "hourlyMarketAgent",
    "paperPosition",
    "paperTrade",
    "RiskGovernor",
    "openai",
}

FORBIDDEN_CALL_NAMES = {
    "create_order",
    "submit_order",
    "place_order",
    "placeOrder",
    "send_order",
}


def _src_root() -> Path:
    return Path(__file__).resolve().parents[1] / "src" / "northstar_trend_carry"


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "docs" / "NorthstarAlpha_Chan_Integration_Roadmap.md").exists():
            return parent
    raise RuntimeError("Could not locate repository root")


def test_source_has_no_broker_or_order_api():
    hits: list[str] = []
    for path in _src_root().rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names.extend(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module.split(".")[0])
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    names.append(func.id)
                elif isinstance(func, ast.Attribute):
                    names.append(func.attr)
            for name in names:
                if name in FORBIDDEN_IMPORT_TOKENS or name in FORBIDDEN_CALL_NAMES:
                    hits.append(f"{path.name}:{name}")
    assert hits == []


def test_hourly_agent_and_rules_do_not_import_stage3():
    root = _repo_root()
    watched = [
        root / "apps/web/src/lib/jobs/hourlyMarketAgent.ts",
        root / "apps/web/src/lib/rules/buyRules.ts",
        root / "apps/web/src/lib/rules/sellRules.ts",
        root / "apps/web/src/lib/rules/shortRules.ts",
        root / "apps/web/src/lib/portfolio/sizing.ts",
    ]
    for path in watched:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        assert "northstar_trend_carry" not in text
        assert "trend_carry" not in text
        assert "evaluate_asset_trend" not in text
        assert "evaluate_carry" not in text


def test_legacy_momentum_lookback_threshold_unchanged():
    root = _repo_root()
    momentum = (root / "backend/strategies/momentum.py").read_text(encoding="utf-8")
    assert 'self.config.get("lookback_days", 126)' in momentum
    assert "northstar_trend_carry" not in momentum
