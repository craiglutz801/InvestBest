from __future__ import annotations

import numpy as np

from fixtures import iid_normal
from northstar_promotion.kelly import RiskCapBundle, kelly_ceiling
from northstar_promotion.quality import QualityCode, QualityLevel


def test_kelly_ceiling_shrinks_with_uncertainty():
    # Same mean/vol process; shorter sample ⇒ smaller t-stat ⇒ smaller ceiling.
    long_rets = iid_normal(400, mu=0.003, sigma=0.01, seed=4)
    short_rets = long_rets[:40]
    caps = RiskCapBundle(hard_leverage_cap=1000.0, risk_governor_cap=1000.0)
    long_k = kelly_ceiling(long_rets, fraction=0.25, caps=caps, min_obs=30)
    short_k = kelly_ceiling(short_rets, fraction=0.25, caps=caps, min_obs=30)
    assert long_k.is_usable and short_k.is_usable
    assert short_k.shrink_factor < long_k.shrink_factor
    assert short_k.shrunk_full_kelly < long_k.shrunk_full_kelly
    assert short_k.ceiling < long_k.ceiling
    assert long_k.role == "ceiling_not_target"
    assert short_k.role == "ceiling_not_target"


def test_kelly_never_exceeds_fractional_or_hard_caps():
    rets = iid_normal(200, mu=0.01, sigma=0.02, seed=8)
    caps = RiskCapBundle(
        vol_target=0.15,
        asset_vol=0.30,
        concentration_max_weight=0.10,
        drawdown_throttle=0.5,
        exposure_cap=0.20,
        liquidity_cap=0.25,
        risk_governor_cap=0.08,
        hard_leverage_cap=0.50,
    )
    result = kelly_ceiling(rets, fraction=0.25, caps=caps, min_obs=30)
    assert result.is_usable
    assert result.ceiling <= result.fractional_shrunk_kelly + 1e-12
    assert result.ceiling <= caps.hard_leverage_cap + 1e-12
    assert result.ceiling <= caps.concentration_max_weight + 1e-12
    assert result.ceiling <= caps.exposure_cap + 1e-12
    assert result.ceiling <= caps.liquidity_cap + 1e-12
    assert result.ceiling <= caps.risk_governor_cap + 1e-12
    assert result.ceiling <= (caps.vol_target / caps.asset_vol) + 1e-12
    # Drawdown throttle is applied after the min().
    assert result.ceiling <= 0.08 * 0.5 + 1e-12
    assert result.full_kelly > result.fractional_shrunk_kelly
    assert result.ceiling < result.full_kelly


def test_full_kelly_rejected():
    rets = iid_normal(80, 0.005, 0.01, seed=1)
    result = kelly_ceiling(rets, fraction=1.0, min_obs=30)
    assert not result.is_usable
    assert result.ceiling == 0.0
    assert any(f.code == QualityCode.FULL_KELLY_REJECTED for f in result.quality_flags)


def test_kelly_subordinate_to_risk_governor_even_if_fractional_is_large():
    rets = iid_normal(300, mu=0.02, sigma=0.02, seed=2)
    caps = RiskCapBundle(risk_governor_cap=0.03, hard_leverage_cap=1.0)
    result = kelly_ceiling(rets, fraction=0.5, caps=caps, min_obs=30)
    assert result.is_usable
    assert result.fractional_shrunk_kelly > 0.03
    assert abs(result.ceiling - 0.03) < 1e-12


def test_missing_risk_governor_is_warned_not_unlimited_in_docs():
    rets = iid_normal(80, 0.004, 0.01, seed=6)
    result = kelly_ceiling(rets, fraction=0.25, caps=RiskCapBundle(hard_leverage_cap=0.2), min_obs=30)
    assert result.is_usable
    assert any(f.code == QualityCode.RISK_GOVERNOR_CAP_NOT_SUPPLIED for f in result.quality_flags)
    assert result.ceiling <= 0.2 + 1e-12


def test_non_positive_edge_ceiling_is_zero():
    rets = iid_normal(80, mu=-0.002, sigma=0.01, seed=12)
    result = kelly_ceiling(rets, fraction=0.25, min_obs=30)
    assert result.ceiling == 0.0
    assert any(f.level is QualityLevel.FAIL for f in result.quality_flags)


def test_kelly_invalid_inputs_fail_closed():
    result = kelly_ceiling([0.01, np.nan], fraction=0.25, min_obs=2)
    assert not result.is_usable
    assert result.ceiling == 0.0
    short = kelly_ceiling([0.01] * 10, fraction=0.25, min_obs=30)
    assert not short.is_usable
