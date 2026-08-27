"""Stage 2 eligibility adapter — explicit northstar_mean_reversion API.

Calls ``evaluate_candidate(candidate, *, config=...)``. Does not guess
``evaluate_eligibility`` / ``evaluate``. A residual z-score is never eligibility.
"""

from __future__ import annotations

from typing import Any, Mapping

from northstar_research_loop.contracts import DiagnosticBundle, EligibilityDecision


def _codes(native: Any) -> tuple[str, ...]:
    raw = getattr(native, "reason_codes", ()) or ()
    out: list[str] = []
    for item in raw:
        out.append(item.value if hasattr(item, "value") else str(item))
    return tuple(out)


class Stage2EligibilityAdapter:
    def __init__(self) -> None:
        try:
            from northstar_mean_reversion import evaluate_candidate
            from northstar_mean_reversion.types import MeanReversionEligibilityConfig
            from northstar_mean_reversion.universe import EconomicCandidate
        except ImportError:
            self.evaluate_candidate = None
            self.EconomicCandidate = None
            self.MeanReversionEligibilityConfig = None
            self.source_package = None
        else:
            self.evaluate_candidate = evaluate_candidate
            self.EconomicCandidate = EconomicCandidate
            self.MeanReversionEligibilityConfig = MeanReversionEligibilityConfig
            self.source_package = "northstar_mean_reversion"

    def evaluate(
        self, diagnostics: DiagnosticBundle, evidence: Mapping[str, Any]
    ) -> EligibilityDecision:
        zscore = evidence.get("zscore")
        candidate = evidence.get("mean_reversion_candidate")
        config = evidence.get("mean_reversion_config")

        if self.evaluate_candidate is None:
            return EligibilityDecision(
                eligible=False,
                family="mean_reversion",
                reason_codes=("elig.stage2_unavailable_fail_closed",),
                source_package=None,
                zscore_after_eligibility=None,
            )

        if candidate is None:
            reasons = ["elig.missing_economic_candidate_fail_closed"]
            if zscore is not None:
                reasons.append("elig.zscore_ignored_before_eligibility")
            if not diagnostics.usable:
                reasons.append("elig.diagnostics_unusable")
            if not diagnostics.required_property_present:
                reasons.append("elig.required_property_absent")
            return EligibilityDecision(
                eligible=False,
                family="mean_reversion",
                reason_codes=tuple(reasons),
                source_package=self.source_package,
                zscore_after_eligibility=None,
            )

        if self.EconomicCandidate is not None and not isinstance(candidate, self.EconomicCandidate):
            return EligibilityDecision(
                eligible=False,
                family="mean_reversion",
                reason_codes=("elig.candidate_not_economic_candidate",),
                source_package=self.source_package,
                zscore_after_eligibility=None,
            )

        native = self.evaluate_candidate(candidate, config=config)
        payload = native.to_dict() if hasattr(native, "to_dict") else {}
        return EligibilityDecision(
            eligible=bool(native.eligible),
            family="mean_reversion",
            reason_codes=_codes(native) or (("elig.ok",) if native.eligible else ("elig.ineligible",)),
            source_package=self.source_package,
            evidence={
                "native_status": getattr(native, "status", None),
                "native": payload,
                "zscore_is_not_eligibility": True,
            },
            zscore_after_eligibility=None,
        )
