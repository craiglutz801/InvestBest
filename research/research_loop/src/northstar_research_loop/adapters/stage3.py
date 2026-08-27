"""Stage 3 trend/carry adapter — explicit northstar_trend_carry API.

Calls ``evaluate_asset_trend(series, config=..., *, as_of=...)`` and, when a
lookback→metric table is supplied, ``refuse_performance_sweep_selection``.
"""

from __future__ import annotations

from typing import Any, Mapping

from northstar_research_loop.contracts import TrendCarryContext


def _horizon_names(signal: Any) -> tuple[str, ...]:
    names: list[str] = []
    for item in getattr(signal, "horizons", ()) or ():
        spec = getattr(item, "horizon", None)
        name = getattr(spec, "name", None) or getattr(item, "name", None)
        if name:
            names.append(str(name))
    return tuple(names)


class Stage3TrendCarryAdapter:
    def __init__(self) -> None:
        try:
            from northstar_trend_carry import (
                EnsembleConfig,
                PriceSeries,
                evaluate_asset_trend,
                refuse_performance_sweep_selection,
            )
        except ImportError:
            self.evaluate_asset_trend = None
            self.refuse_performance_sweep_selection = None
            self.PriceSeries = None
            self.EnsembleConfig = None
            self.source_package = None
        else:
            self.evaluate_asset_trend = evaluate_asset_trend
            self.refuse_performance_sweep_selection = refuse_performance_sweep_selection
            self.PriceSeries = PriceSeries
            self.EnsembleConfig = EnsembleConfig
            self.source_package = "northstar_trend_carry"

    def evaluate(self, evidence: Mapping[str, Any]) -> TrendCarryContext:
        if self.evaluate_asset_trend is None:
            family = str(evidence.get("family") or "")
            if family in {"trend", "futures_carry", "trend_carry"}:
                return TrendCarryContext(
                    usable=False,
                    reason_codes=("trend.stage3_unavailable_fail_closed",),
                    source_package=None,
                )
            return TrendCarryContext(
                usable=False,
                reason_codes=("trend.stage3_unavailable_fail_closed",),
                source_package=None,
            )

        series = evidence.get("price_series")
        if series is None:
            # Mean-reversion families still must invoke Stage 3 on this integration
            # branch when a series is provided. Missing series is fail-closed so
            # the harness cannot silently skip native Stage 3.
            return TrendCarryContext(
                usable=False,
                reason_codes=("trend.missing_price_series_fail_closed",),
                source_package=self.source_package,
            )

        if self.PriceSeries is not None and not isinstance(series, self.PriceSeries):
            return TrendCarryContext(
                usable=False,
                reason_codes=("trend.series_not_price_series",),
                source_package=self.source_package,
            )

        config = evidence.get("trend_config")
        signal = self.evaluate_asset_trend(
            series,
            config,
            as_of=evidence.get("as_of"),
        )

        chose_single = False
        sweep = evidence.get("performance_sweep")
        details: dict[str, Any] = {"native": signal.to_dict() if hasattr(signal, "to_dict") else {}}
        details["is_order"] = False
        details["wired_to_live_portfolio_engine"] = False
        details["chose_single_optimized_horizon"] = False
        if sweep is not None and self.refuse_performance_sweep_selection is not None:
            refusal = self.refuse_performance_sweep_selection(sweep)
            details["sweep_refusal"] = refusal.to_dict() if hasattr(refusal, "to_dict") else {}
            if getattr(refusal, "selected_lookback", None) is not None:
                chose_single = True

        usable = bool(getattr(signal, "is_usable", False)) and not chose_single
        reasons: tuple[str, ...]
        if chose_single:
            reasons = ("trend.single_optimized_horizon_forbidden",)
        elif usable:
            reasons = ("trend.ok",)
        else:
            reasons = ("trend.unusable",)

        agreement = None
        health = evidence.get("trend_health")
        if health is not None:
            agreement = getattr(health, "horizon_agreement", None)

        return TrendCarryContext(
            usable=usable,
            reason_codes=reasons,
            horizons=_horizon_names(signal),
            horizon_agreement=agreement,
            chose_single_optimized_horizon=chose_single,
            source_package=self.source_package,
            details=details,
        )
