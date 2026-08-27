# NorthstarAlpha Stage 3 — Multi-Speed Trend + Futures Carry

Research / shadow-testing evidence only.

This package implements **Stage 3** of `docs/NorthstarAlpha_Chan_Integration_Roadmap.md`.
It is a pure Python library. It does **not** place orders, mutate paper positions,
call a broker, enable live shorting/leverage/futures execution, or change
InvestBest / NorthstarAlpha buy/sell thresholds.

Active application code remains `apps/web` (Next.js paper-trading MVP). Stage 3
lives here — not inside `hourlyMarketAgent` — so it can be developed in parallel
with mean reversion (Stage 2) and paper-safety work.

## Why this home?

- The production app is TypeScript. Time-series momentum, vol scaling, and
  listed-contract carry are easier to test deterministically in a small Python
  research package with numpy.
- `apps/ml-service` is a scoring stub that may later be called from the hourly
  agent. Putting trend/carry there would make accidental trade-path coupling easy.
- `research/` is already the isolated research surface. Stage 1 diagnostics
  (`research/statistical_diagnostics`) is a **parallel draft**; this package
  branches from `main` and does **not** hard-require Stage 1.

## Install (research environment)

```bash
python3 -m pip install -e "research/trend_carry[test]"
python3 -m pytest research/trend_carry
```

## Dependencies

| Package | Why |
|---|---|
| `numpy` | Returns, realized vol, ensemble math, synthetic fixtures |
| `pytest` (optional extra) | Deterministic unit tests |

**Not required:** paid futures/market-data vendors, broker SDKs, pandas,
statsmodels, `northstar-diagnostics`.

Optional extra `stage1` installs `northstar-diagnostics` when that draft package
is available. `research_edge_to_friction` delegates to Stage 1 EFR if importable,
otherwise uses a local fallback with the same friction component names
(including `futures_roll` as **execution** roll cost only). Bid/ask are
recommended for that estimate. The front/deferred price gap is carry
(`curve_gap` / `roll_gap`), not a cost, and is never copied into Stage 1
`futures_roll`.

## Public API

| Function | Role |
|---|---|
| `evaluate_asset_trend` | Multi-speed TSMOM ensemble (1m/3m/6m/12m defaults) |
| `evaluate_cross_asset_trend` | Cross-symbol research snapshot + diagnostic weights |
| `evaluate_trend_health` | Horizon agreement, persistence, whipsaw, vol shock, breadth |
| `neighboring_parameter_plateau` | Neighborhood / plateau robustness; never picks a lookback |
| `refuse_performance_sweep_selection` | Explicit refusal to promote a sweep argmax |
| `evaluate_carry` | Contango/backwardation roll yield; `curve_gap` is carry, not friction |
| `build_research_continuous_series` | PIT back-adjusted series (**not** executable P&L) |
| `executable_contract_state` | Listed-contract identity, curve gap, execution roll friction if known |
| `research_edge_to_friction` | EFR hook (Stage 1 if present, else local); does not treat curve gap as cost |

Ensemble method is always `equal_weight_capped_horizons`.
`selected_lookback` is always `None`.

## Safety boundary

- No broker / order API (enforced by `tests/test_isolation.py`).
- No import from `hourlyMarketAgent` or buy/sell/short rule files.
- Current momentum strategy `lookback_days=126` is not modified.
- Diagnostics do not authorize RiskGovernor changes.

See `docs/trend_carry.md` for provider fields needed later and for what these
calculations can and cannot establish.
