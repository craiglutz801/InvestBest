"""Discover in-flight Chan stage packages without duplicating them."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

# Candidate import names. Updated as later draft PRs land; unknown names are
# skipped. Stage 6 must not vendor copies of these modules.
STAGE_CANDIDATES: dict[int, tuple[str, ...]] = {
    1: ("northstar_diagnostics",),
    2: (
        "northstar_mean_reversion",
        "northstar_mr_eligibility",
        "northstar_eligibility",
        "northstar_stage2",
    ),
    3: (
        "northstar_trend",
        "northstar_trend_carry",
        "northstar_carry",
        "northstar_stage3",
    ),
    4: (
        "northstar_edge_health",
        "northstar_health",
        "northstar_stage4",
    ),
    5: (
        "northstar_promotion",
        "northstar_anti_overfit",
        "northstar_evaluation",
        "northstar_stage5",
    ),
}


@dataclass(frozen=True)
class DiscoveredModule:
    stage: int
    module_name: str
    version: str | None
    available: bool
    adapter_mode: str  # native | synthetic_fail_closed
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "module_name": self.module_name,
            "version": self.version,
            "available": self.available,
            "adapter_mode": self.adapter_mode,
            "notes": list(self.notes),
        }


def _try_import(name: str) -> Any | None:
    try:
        return importlib.import_module(name)
    except Exception:
        return None


def discover_stage(stage: int) -> DiscoveredModule:
    names = STAGE_CANDIDATES.get(stage, ())
    for name in names:
        module = _try_import(name)
        if module is None:
            continue
        version = getattr(module, "__version__", None)
        return DiscoveredModule(
            stage=stage,
            module_name=name,
            version=str(version) if version is not None else None,
            available=True,
            adapter_mode="native",
            notes=("Imported native Chan module; Stage 6 wraps contracts rather than reimplementing.",),
        )
    expected = ", ".join(names) if names else "(none configured)"
    return DiscoveredModule(
        stage=stage,
        module_name="",
        version=None,
        available=False,
        adapter_mode="synthetic_fail_closed",
        notes=(
            f"No native Stage {stage} package importable (tried: {expected}).",
            "Pipeline consumes explicit evidence records and fails closed if they are missing.",
        ),
    )


def discover_all() -> dict[int, DiscoveredModule]:
    return {stage: discover_stage(stage) for stage in sorted(STAGE_CANDIDATES)}


def native_module(stage: int) -> Any | None:
    found = discover_stage(stage)
    if not found.available:
        return None
    return _try_import(found.module_name)
