"""Stage 3 trend/carry adapter.

Wraps native `northstar_trend_carry` (draft PR #10) when importable:
AssetTrendSignal, evaluate_asset_trend, refuse_performance_sweep_selection.
Does not reimplement the multi-speed ensemble or futures carry math.
"""

from __future__ import annotations

from typing import Any, Mapping

from northstar_research_loop.adapters.discovery import native_module
from northstar_research_loop.contracts import TrendCarryContext


def _horizon_names(payload: Any) -> tuple[str, ...]:
    raw = getattr(payload, "horizons", None)
    if raw is None and isinstance(payload, Mapping):
        raw = payload.get("horizons")
    names: list[str] = []
    for item in raw or ():
        if isinstance(item, str):
            names.append(item)
            continue
        if isinstance(item, Mapping):
            nested = item.get("horizon") or item
            name = nested.get("name") if isinstance(nested, Mapping) else None
            if name:
                names.append(str(name))
            continue
        spec = getattr(item, "horizon", None)
        name = getattr(spec, "name", None) or getattr(item, "name", None)
        if name:
            names.append(str(name))
    return tuple(names)


class Stage3TrendCarryAdapter:
    def __init__(self) -> None:
        self.module = native_module(3)

    def evaluate(self, evidence: Mapping[str, Any]) -> TrendCarryContext:
        explicit = evidence.get("trend")
        native = self.module
        source = native.__name__ if native is not None else None

        if native is not None and explicit is None:
            series = evidence.get("price_series") or evidence.get("prices")
            evaluate_asset_trend = getattr(native, "evaluate_asset_trend", None)
            if series is not None and callable(evaluate_asset_trend):
                try:
                    signal = evaluate_asset_trend(series, as_of=evidence.get("as_of"))
                    return self._wrap(signal, source)
                except Exception as exc:  # fail closed; do not invent a trend pass
                    return TrendCarryContext(
                        usable=False,
                        reason_codes=("trend.native_evaluate_failed",),
                        source_package=source,
                        details={"error": str(exc)},
                    )
            sweep = evidence.get("performance_sweep")
            refuse = getattr(native, "refuse_performance_sweep_selection", None)
            if sweep is not None and callable(refuse):
                refusal = refuse(sweep)
                return self._wrap(refusal, source)

        if explicit is None:
            family = str(evidence.get("family") or "")
            if family in {"trend", "futures_carry", "trend_carry"}:
                return TrendCarryContext(
                    usable=False,
                    reason_codes=("trend.missing_stage3_fail_closed",),
                    source_package=source,
                )
            return TrendCarryContext(
                usable=True,
                reason_codes=("trend.not_required_for_family",),
                chose_single_optimized_horizon=False,
                source_package=source,
            )
        return self._wrap(explicit, source or "explicit_evidence")

    @staticmethod
    def _wrap(payload: Any, source: str | None) -> TrendCarryContext:
        if isinstance(payload, TrendCarryContext):
            return payload

        data = dict(payload) if isinstance(payload, Mapping) else {}
        refuses = bool(
            data.get("refuses_single_horizon_selection")
            or getattr(payload, "refuses_single_horizon_selection", False)
        )
        selected = data.get("selected_lookback", getattr(payload, "selected_lookback", None))
        chose_single = bool(
            data.get("chose_single_optimized_horizon")
            or getattr(payload, "chose_single_optimized_horizon", False)
            or (selected is not None and not refuses)
        )
        if hasattr(payload, "is_usable"):
            usable = bool(payload.is_usable) and not chose_single
        elif "usable" in data:
            usable = bool(data.get("usable")) and not chose_single
        elif "is_usable" in data:
            usable = bool(data.get("is_usable")) and not chose_single
        else:
            usable = (not chose_single) and (
                getattr(payload, "ensemble_strength", data.get("ensemble_strength")) is not None
                or bool(data)
            )

        reasons = tuple(data.get("reason_codes") or ())
        if chose_single:
            usable = False
            reasons = tuple(dict.fromkeys((*reasons, "trend.single_optimized_horizon_forbidden")))
        elif refuses:
            reasons = tuple(dict.fromkeys((*reasons, "trend.refuses_single_horizon_selection")))
        if not reasons:
            reasons = ("trend.ok",) if usable else ("trend.unusable",)

        agreement = data.get("horizon_agreement")
        if agreement is None:
            agreement = getattr(payload, "horizon_agreement", None)

        details = dict(data.get("details") or {})
        if hasattr(payload, "to_dict"):
            details.setdefault("native", payload.to_dict())
        details.setdefault("is_order", False)
        details.setdefault("wired_to_live_portfolio_engine", False)

        return TrendCarryContext(
            usable=usable,
            reason_codes=reasons,
            horizons=_horizon_names(payload) or tuple(data.get("horizons") or ()),
            horizon_agreement=agreement,
            chose_single_optimized_horizon=chose_single,
            source_package=source,
            details=details,
        )
