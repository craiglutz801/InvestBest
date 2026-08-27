"""Reason-code catalogue stays complete and documented."""

from __future__ import annotations

from pathlib import Path

from northstar_edge_health.states import ALL_REASON_CODES, ReasonCode


def test_reason_code_constants_are_unique():
    assert len(ALL_REASON_CODES) == len(set(ALL_REASON_CODES))
    assert ReasonCode.MR_STRUCTURAL_BREAK in ALL_REASON_CODES
    assert ReasonCode.TREND_VOLATILITY_SHOCK in ALL_REASON_CODES
    assert ReasonCode.MISSING_EVIDENCE in ALL_REASON_CODES


def test_docs_mention_each_reason_code():
    docs = Path(__file__).resolve().parents[3] / "docs" / "edge_health.md"
    text = docs.read_text(encoding="utf-8")
    missing = [code for code in ALL_REASON_CODES if code not in text]
    assert missing == []
