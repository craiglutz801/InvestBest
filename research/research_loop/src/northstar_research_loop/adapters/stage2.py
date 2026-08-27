"""Stage 2 eligibility adapter.

Does not reimplement CADF/Johansen eligibility math. Wraps a native Stage 2
module when importable; otherwise consumes an explicit EligibilityDecision
(fail closed if missing).
"""

from __future__ import annotations

from typing import Any, Mapping

from northstar_research_loop.adapters.discovery import native_module
from northstar_research_loop.contracts import DiagnosticBundle, EligibilityDecision


def _from_native(payload: Any, source: str) -> EligibilityDecision:
    if isinstance(payload, EligibilityDecision):
        return payload
    if isinstance(payload, Mapping):
        return EligibilityDecision(
            eligible=bool(payload.get("eligible")),
            family=str(payload.get("family") or "mean_reversion"),
            reason_codes=tuple(payload.get("reason_codes") or ()),
            source_package=source,
            evidence=dict(payload.get("evidence") or {}),
            zscore_after_eligibility=payload.get("zscore_after_eligibility"),
        )
    eligible = bool(getattr(payload, "eligible", False))
    return EligibilityDecision(
        eligible=eligible,
        family=str(getattr(payload, "family", "mean_reversion")),
        reason_codes=tuple(getattr(payload, "reason_codes", ()) or ()),
        source_package=source,
        evidence=dict(getattr(payload, "evidence", {}) or {}),
        zscore_after_eligibility=getattr(payload, "zscore_after_eligibility", None),
    )


class Stage2EligibilityAdapter:
    def __init__(self) -> None:
        self.module = native_module(2)

    def evaluate(
        self, diagnostics: DiagnosticBundle, evidence: Mapping[str, Any]
    ) -> EligibilityDecision:
        explicit = evidence.get("eligibility")
        native = self.module
        if native is not None:
            for attr in ("evaluate_eligibility", "eligibility_decision", "evaluate"):
                fn = getattr(native, attr, None)
                if callable(fn):
                    return _from_native(fn(diagnostics, evidence), native.__name__)

        if isinstance(explicit, EligibilityDecision):
            return explicit
        if isinstance(explicit, Mapping):
            return _from_native(explicit, native.__name__ if native else "explicit_evidence")

        # Fail closed: cannot invent eligibility. A residual z-score is not enough.
        zscore = evidence.get("zscore")
        reasons = ["elig.missing_stage2_fail_closed"]
        if zscore is not None:
            reasons.append("elig.zscore_ignored_before_eligibility")
        if not diagnostics.usable:
            reasons.append("elig.diagnostics_unusable")
        if not diagnostics.required_property_present:
            reasons.append("elig.required_property_absent")
        return EligibilityDecision(
            eligible=False,
            family=str(evidence.get("family") or "mean_reversion"),
            reason_codes=tuple(reasons),
            source_package=native.__name__ if native else None,
            zscore_after_eligibility=None,
        )
