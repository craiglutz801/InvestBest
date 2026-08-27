# Stage 2 mean-reversion eligibility — developer notes

**Status:** research/shadow-only (not wired to execution)  
**Code:** `research/mean_reversion_eligibility/`  
**Depends on:** Stage 1 `research/statistical_diagnostics/` (`northstar_diagnostics`)  
**Roadmap:** `docs/NorthstarAlpha_Chan_Integration_Roadmap.md` Stage 2

This document states what the eligibility engine **can** and **cannot** establish.
Nothing here may place an order, mutate a simulated position, or authorize live
trading. `EligibilityDecision.eligible` is formation evidence, not a signal.

## Formation vs entry timing

Stage 2 splits two questions that must not be collapsed:

1. **Formation / eligibility** — is this economically related pair/basket a
   statistically defensible mean-reversion *candidate* on a point-in-time window?
2. **Entry timing** — is the residual currently extended (z-score)? Applied only
   in `evaluate_shadow_entry`, and only if (1) already passed.

A collapsing security that is statistically distant from a historical mean is
still ineligible if cointegration, stationarity, half-life, cost, or veto gates
fail. Oversold is not mean reversion.

## Candidate universe interface

Callers supply `EconomicCandidate` groups with:

- symbols / price legs
- a declared `RelationshipKind` (share class, dual listing, sector peers, …)
- a non-empty economic `relationship_rationale`
- a requested `holding_horizon` (bars)

The engine does **not** discover a universe and does **not** accept LLM ticker
lists without that declaration. Broad universe search is out of scope.

## Gates (fail closed)

| Gate | Evidence | Can establish | Cannot establish |
|---|---|---|---|
| Economic universe | caller declaration | The group was asserted to be economically related | That the assertion is true in the real economy |
| Market data | Stage 1 PIT prep | The window is usable and future bars were excluded | That prices are the executable NBBO |
| Event / fundamental veto | caller flags | A supplied event/divergence flag blocked the candidate | Event detection from news, filings, or an LLM |
| Liquidity / shortability | caller snapshots | ADV/spread/shortable flags met config | Live locates, live borrow, or broker connectivity |
| CADF (pairs) | Stage 1 `cadf_cointegration` | Residual cointegration evidence at the configured p-value | A pairs trade after costs |
| Johansen (baskets) | Stage 1 `johansen_cointegration` | Trace-test rank ≥ configured minimum | Unique trading weights |
| Hedge ratio | OLS / Johansen vector | In-sample hedge weights and residual | Out-of-sample hedge stability by itself |
| Spread stationarity | Stage 1 ADF on residual | Unit-root rejection on the spread | Tradable edge |
| Hedge stability | rolling OLS beta relative std | Descriptive in-window hedge drift | Future stability |
| Spread-vol stability | rolling residual std CV | Descriptive vol instability | A vol-target sizing rule |
| Half-life vs horizon | Stage 1 AR(1) half-life | Time-scale compatibility with the requested hold | A holding-period recommendation if the DGP is not AR(1) |
| Structural-break veto | Stage 1 Chow/CUSUM | Instability evidence on the residual | The economic cause of the break |
| EFR / cost cushion | Stage 1 EFR | Gross edge / round-trip friction vs configured floor | That the numerator is a real edge |

Broken cointegration is flagged when CADF passes in the first half of the window
and fails in the second half (`BROKEN_COINTEGRATION`), in addition to full-sample
CADF / ADF / break gates.

## Reason codes

Every rejection carries one or more `EligibilityReasonCode` values (see
`reasons.py`). `status` is `eligible`, `ineligible`, or `insufficient_data`.
Entry timing uses `ENTRY_BLOCKED_NOT_ELIGIBLE` when formation failed, even if
`|z|` is large.

## Shadow signal

`evaluate_shadow_entry` may report `SHADOW_ENTRY_OBSERVED` with direction
`long_spread` / `short_spread`. That payload is explicitly
`is_production_signal=False` and is not imported by `hourlyMarketAgent`.

## What Stage 2 intentionally does not do

- Production signal activation
- LLM trade decisions or LLM universe discovery
- Broker / order API access
- Live locates or live shortability queries
- Live trading
- Changes to `hourlyMarketAgent`, buy/sell rules, or paper-safety gates
- Stage 3 trend / futures carry work
- Merge, deploy, or strategy promotion
