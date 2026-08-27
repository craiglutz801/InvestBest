"""Isolation: Stage 5 evaluation must not touch brokers, orders, or execution."""

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
}

FORBIDDEN_CALL_NAMES = {
    "create_order",
    "submit_order",
    "place_order",
    "placeOrder",
    "send_order",
}


def _src_root() -> Path:
    return Path(__file__).resolve().parents[1] / "src" / "northstar_promotion"


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "docs" / "NorthstarAlpha_Chan_Integration_Roadmap.md").exists():
            return parent
    raise RuntimeError("Could not locate repository root")


def test_promotion_source_has_no_broker_or_order_api():
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


def test_hourly_agent_and_rules_do_not_import_stage5_promotion():
    root = _repo_root()
    watched = [
        root / "apps/web/src/lib/jobs/hourlyMarketAgent.ts",
        root / "apps/web/src/lib/rules/buyRules.ts",
        root / "apps/web/src/lib/rules/sellRules.ts",
        root / "apps/web/src/lib/rules/shortRules.ts",
        root / "apps/web/src/lib/portfolio/sizing.ts",
        root / "backend/services/backtest.py",
        root / "apps/ml-service/app/main.py",
    ]
    for path in watched:
        text = path.read_text(encoding="utf-8")
        assert "northstar_promotion" not in text
        assert "anti_overfit_promotion" not in text
        assert "evaluate_promotion" not in text
        assert "kelly_ceiling" not in text


def test_package_docstring_forbids_self_promotion_and_full_kelly():
    init = (_src_root() / "__init__.py").read_text(encoding="utf-8")
    assert "self-promote" in init
    assert "full Kelly" in init
    assert "live trading" in init
