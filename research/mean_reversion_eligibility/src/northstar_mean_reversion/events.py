"""Deterministic event / fundamental-divergence veto flags.

Callers supply these flags. This module does not scrape news, call an LLM,
or infer corporate actions from prices.
"""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class EventVetoFlags:
    earnings: bool = False
    merger_or_acquisition: bool = False
    delisting: bool = False
    dividend_cut: bool = False
    accounting_restatement: bool = False
    credit_event: bool = False
    fundamental_divergence: bool = False
    other: bool = False
    notes: tuple[str, ...] = ()

    def active_event_names(self) -> tuple[str, ...]:
        names = []
        for item in fields(self):
            if item.name == "notes":
                continue
            if bool(getattr(self, item.name)):
                names.append(item.name)
        return tuple(names)

    def to_dict(self) -> dict[str, bool | tuple[str, ...]]:
        payload = {item.name: getattr(self, item.name) for item in fields(self)}
        return payload
