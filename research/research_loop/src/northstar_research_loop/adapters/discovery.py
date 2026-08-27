"""Exact Chan Stage 1–5 import names. No alias guessing.

Primary integration is explicit typed calls in adapters/stageN.py.
Discovery only answers “is the canonical package importable?”
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

# Canonical import names from draft PRs #4, #11, #10, #13, #14.
NATIVE_MODULES: dict[int, str] = {
    1: "northstar_diagnostics",
    2: "northstar_mean_reversion",
    3: "northstar_trend_carry",
    4: "northstar_edge_health",
    5: "northstar_promotion",
}

REQUIRED_NATIVE_STAGES: tuple[int, ...] = (1, 2, 3, 4, 5)


@dataclass(frozen=True)
class DiscoveredModule:
    stage: int
    module_name: str
    version: str | None
    available: bool
    adapter_mode: str  # native | missing
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


class NativeStageMissingError(RuntimeError):
    """Raised when a required Chan package is not importable."""


def _try_import(name: str) -> Any | None:
    try:
        return importlib.import_module(name)
    except Exception:
        return None


def discover_stage(stage: int) -> DiscoveredModule:
    name = NATIVE_MODULES.get(stage)
    if not name:
        return DiscoveredModule(
            stage=stage,
            module_name="",
            version=None,
            available=False,
            adapter_mode="missing",
            notes=(f"No canonical Stage {stage} import is configured.",),
        )
    module = _try_import(name)
    if module is None:
        return DiscoveredModule(
            stage=stage,
            module_name=name,
            version=None,
            available=False,
            adapter_mode="missing",
            notes=(
                f"Canonical package {name!r} is not importable.",
                "Install the matching research/* package; do not use synthetic_fail_closed as a silent pass.",
            ),
        )
    version = getattr(module, "__version__", None)
    return DiscoveredModule(
        stage=stage,
        module_name=name,
        version=str(version) if version is not None else None,
        available=True,
        adapter_mode="native",
        notes=(f"Imported {name}; Stage 6 adapters call its typed public API.",),
    )


def discover_all() -> dict[int, DiscoveredModule]:
    return {stage: discover_stage(stage) for stage in sorted(NATIVE_MODULES)}


def native_module(stage: int) -> Any | None:
    found = discover_stage(stage)
    if not found.available:
        return None
    return _try_import(found.module_name)


def require_native_stages(stages: tuple[int, ...] = REQUIRED_NATIVE_STAGES) -> dict[int, DiscoveredModule]:
    """Fail loudly if any required stage would fall back to a synthetic path."""

    snapshot = {stage: discover_stage(stage) for stage in stages}
    missing = [stage for stage, item in snapshot.items() if not item.available or item.adapter_mode != "native"]
    if missing:
        detail = ", ".join(
            f"{stage}:{snapshot[stage].module_name or 'unset'}" for stage in missing
        )
        raise NativeStageMissingError(
            "Required Chan stages are not natively importable: "
            f"{detail}. Refusing synthetic_fail_closed fallback."
        )
    return snapshot
