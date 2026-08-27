"""Stage 1 adapter — wraps northstar_diagnostics.DiagnosticResult / EFR.

Does not reimplement ADF/CADF/Johansen/half-life/Hurst/VR/breaks.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from northstar_research_loop.adapters.discovery import native_module
from northstar_research_loop.contracts import DiagnosticBundle

FRAGILE_EFR_DEFAULT = 2.5


def _flag_codes(result: Any) -> tuple[str, ...]:
    flags = getattr(result, "quality_flags", ()) or ()
    codes: list[str] = []
    for flag in flags:
        code = getattr(flag, "code", None)
        if code:
            codes.append(str(code))
        elif isinstance(flag, Mapping) and flag.get("code"):
            codes.append(str(flag["code"]))
    return tuple(codes)


def _is_usable(result: Any) -> bool:
    if hasattr(result, "is_usable"):
        return bool(result.is_usable)
    flags = getattr(result, "quality_flags", ()) or ()
    for flag in flags:
        level = getattr(flag, "level", None)
        value = getattr(level, "value", level)
        if str(value).lower() == "fail":
            return False
    return True


def wrap_diagnostic_results(
    results: Sequence[Any],
    *,
    required_ids: Sequence[str] = ("cadf", "efr"),
    fragile_below: float = FRAGILE_EFR_DEFAULT,
    source_package: str | None = "northstar_diagnostics",
) -> DiagnosticBundle:
    if not results:
        return DiagnosticBundle(
            usable=False,
            required_property_present=False,
            reason_codes=("diag.missing_results",),
            diagnostic_ids=(),
            efr=None,
            efr_fragile=True,
            break_detected=False,
            source_package=source_package,
        )

    ids: list[str] = []
    reasons: list[str] = []
    stats: dict[str, Any] = {}
    usable = True
    efr: float | None = None
    efr_fragile = True
    break_detected = False
    required_property_present = False

    for result in results:
        diagnostic_id = str(getattr(result, "diagnostic_id", "") or "")
        ids.append(diagnostic_id)
        item_usable = _is_usable(result)
        if not item_usable:
            usable = False
            reasons.extend(f"diag.{diagnostic_id}.{code}" for code in _flag_codes(result) or ("unusable",))
        statistics = dict(getattr(result, "statistics", {}) or {})
        stats[diagnostic_id] = statistics
        interpretation = str(getattr(result, "interpretation", "") or "")
        details = dict(getattr(result, "details", {}) or {})
        pvalue = getattr(result, "pvalue", None)

        if diagnostic_id == "efr":
            raw = statistics.get("efr")
            efr = float(raw) if raw is not None else None
            efr_fragile = bool(
                efr is None or efr < float(statistics.get("fragile_below", fragile_below))
            ) or "fragile" in interpretation
            if efr_fragile:
                reasons.append("diag.efr_fragile")
        if diagnostic_id in {"cadf", "adf"} and item_usable and pvalue is not None:
            if float(pvalue) < 0.05:
                required_property_present = True
        if diagnostic_id == "half_life" and item_usable:
            half = statistics.get("half_life")
            stats["half_life"] = half
        if details.get("break_detected") is True or statistics.get("break_detected") is True:
            break_detected = True
            reasons.append("diag.structural_break")
        if "break" in diagnostic_id and item_usable:
            if details.get("break_detected") is True:
                break_detected = True

    missing_required = [rid for rid in required_ids if rid not in ids]
    if missing_required:
        usable = False
        reasons.append("diag.missing_required:" + ",".join(missing_required))

    if not reasons and usable and required_property_present and not efr_fragile and not break_detected:
        reasons = ("diag.ok",)

    return DiagnosticBundle(
        usable=usable,
        required_property_present=required_property_present,
        reason_codes=tuple(dict.fromkeys(reasons)),
        diagnostic_ids=tuple(ids),
        efr=efr,
        efr_fragile=bool(efr_fragile),
        break_detected=break_detected,
        statistics=stats,
        source_package=source_package,
    )


class Stage1DiagnosticsAdapter:
    def __init__(self) -> None:
        self.module = native_module(1)

    @property
    def source_package(self) -> str | None:
        return "northstar_diagnostics" if self.module is not None else None

    def evaluate(self, evidence: Mapping[str, Any]) -> DiagnosticBundle:
        precomputed = evidence.get("diagnostic_results")
        if precomputed:
            return wrap_diagnostic_results(
                list(precomputed),
                required_ids=tuple(evidence.get("required_ids") or ("cadf", "efr")),
                fragile_below=float(evidence.get("fragile_below") or FRAGILE_EFR_DEFAULT),
                source_package=self.source_package or "synthetic_fail_closed",
            )

        bundle = evidence.get("diagnostic_bundle")
        if isinstance(bundle, DiagnosticBundle):
            return bundle

        if self.module is None:
            return DiagnosticBundle(
                usable=False,
                required_property_present=False,
                reason_codes=("diag.stage1_unavailable_fail_closed",),
                diagnostic_ids=(),
                efr=None,
                efr_fragile=True,
                break_detected=False,
                source_package=None,
            )

        return self._compute_from_series(evidence)

    def _compute_from_series(self, evidence: Mapping[str, Any]) -> DiagnosticBundle:
        assert self.module is not None
        y = evidence.get("y")
        x = evidence.get("x")
        expected_gross_edge = evidence.get("expected_gross_edge")
        friction_dict = dict(evidence.get("friction") or {})
        as_of = evidence.get("as_of")
        results: list[Any] = []

        # Residual cointegration (CADF) is the mean-reversion formation test.
        # Do not run half-life on raw I(1) legs — that would fail-closed a valid pair.
        if y is not None and x is not None:
            results.append(self.module.cadf_cointegration(y, x, as_of=as_of))
        elif y is not None:
            results.append(self.module.adf_stationarity(y, as_of=as_of))

        if expected_gross_edge is not None:
            friction_cls = self.module.FrictionInputs
            allowed = friction_cls().as_dict()
            friction = friction_cls(
                **{k: float(v) for k, v in friction_dict.items() if k in allowed}
            )
            results.append(
                self.module.edge_to_friction_ratio(
                    float(expected_gross_edge),
                    friction,
                    fragile_below=float(evidence.get("fragile_below") or FRAGILE_EFR_DEFAULT),
                    as_of=as_of,
                )
            )

        break_flag = evidence.get("break_detected")
        if break_flag is True and y is not None:
            results.append(
                self.module.detect_structural_break(y, method="chow_ols", as_of=as_of)
            )

        if not results:
            return DiagnosticBundle(
                usable=False,
                required_property_present=False,
                reason_codes=("diag.insufficient_inputs_fail_closed",),
                diagnostic_ids=(),
                efr=None,
                efr_fragile=True,
                break_detected=bool(break_flag),
                source_package=self.source_package,
            )
        bundle = wrap_diagnostic_results(
            results,
            required_ids=tuple(evidence.get("required_ids") or ("cadf", "efr")),
            fragile_below=float(evidence.get("fragile_below") or FRAGILE_EFR_DEFAULT),
            source_package=self.source_package,
        )
        if break_flag is True:
            return DiagnosticBundle(
                usable=bundle.usable,
                required_property_present=bundle.required_property_present,
                reason_codes=tuple(dict.fromkeys((*bundle.reason_codes, "diag.structural_break"))),
                diagnostic_ids=bundle.diagnostic_ids,
                efr=bundle.efr,
                efr_fragile=bundle.efr_fragile,
                break_detected=True,
                statistics=bundle.statistics,
                source_package=bundle.source_package,
            )
        return bundle
