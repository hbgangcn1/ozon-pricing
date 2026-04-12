# pyright: reportPrivateUsage=false
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pricing.calculate_pricing import (  # noqa: E402
    _calc_stats,
    _compute_stats_savings,
    _extract_savings,
)


def _log(min_days, max_days, name="test-logistics"):
    return {
        "name": name,
        "min_days": min_days,
        "max_days": max_days,
    }


def test_calc_stats_includes_best_in_average_pool():
    candidates = [
        (_log(6, 8, "candidate-1"), 130.0),
        (_log(8, 10, "candidate-2"), 160.0),
    ]

    stats = _calc_stats(candidates, _log(2, 4, "best"), 100.0)

    assert stats is not None
    assert stats["avg_cost"] == pytest.approx((100.0 + 130.0 + 160.0) / 3)
    assert stats["avg_time"] == pytest.approx((3.0 + 7.0 + 9.0) / 3)


def test_calc_stats_single_candidate_matching_best_produces_zero_saved_values():
    candidates = [(_log(4, 6, "candidate"), 100.0)]

    stats = _calc_stats(candidates, _log(4, 6, "best"), 100.0)

    assert stats is not None
    assert stats["avg_cost"] == pytest.approx(100.0)
    assert stats["avg_time"] == pytest.approx(5.0)
    assert stats["cost_saving"] == pytest.approx(0.0)
    assert stats["time_saving"] == pytest.approx(0.0)


def test_calc_stats_returns_none_when_no_candidates_exist():
    assert _calc_stats([], _log(3, 5, "best"), 88.0) is None



def test_calc_stats_cost_saving_uses_average_based_percentage_formula():
    candidates = [(_log(5, 7, "candidate"), 140.0)]

    stats = _calc_stats(candidates, _log(3, 5, "best"), 100.0)

    expected_avg_cost = (100.0 + 140.0) / 2
    expected_cost_saving = (expected_avg_cost - 100.0) / expected_avg_cost * 100
    assert stats is not None
    assert stats["cost_saving"] == pytest.approx(expected_cost_saving)


def test_calc_stats_time_saving_equals_average_time_minus_best_time():
    candidates = [(_log(8, 10, "candidate"), 120.0)]

    stats = _calc_stats(candidates, _log(2, 4, "best"), 100.0)

    expected_avg_time = (3.0 + 9.0) / 2
    assert stats is not None
    assert stats["avg_time"] == pytest.approx(expected_avg_time)
    assert stats["time_saving"] == pytest.approx(expected_avg_time - 3.0)


def test_extract_savings_returns_average_and_saved_tuple_values():
    stats = {
        "avg_cost": 135.0,
        "avg_time": 7.5,
        "cost_saving": 11.11,
        "time_saving": 2.5,
    }

    result = _extract_savings(stats, _log(4, 6, "best"), 120.0)

    assert result == pytest.approx((135.0, 7.5, 15.0, 2.5))


def test_compute_stats_savings_returns_combined_land_and_air_metrics():
    land_candidates = [(_log(8, 10, "land-candidate"), 14.0)]
    air_candidates = [
        (_log(4, 6, "air-candidate-1"), 22.0),
        (_log(6, 8, "air-candidate-2"), 26.0),
    ]

    result = _compute_stats_savings(
        land_candidates,
        _log(4, 6, "land-best"),
        10.0,
        air_candidates,
        _log(2, 4, "air-best"),
        20.0,
    )

    (
        land_stats,
        air_stats,
        avg_land_cost,
        avg_land_days,
        saved_land_cost,
        saved_land_days,
        avg_air_cost,
        avg_air_days,
        saved_air_cost,
        saved_air_days,
    ) = result

    assert land_stats is not None
    assert land_stats["avg_cost"] == pytest.approx(12.0)
    assert land_stats["avg_time"] == pytest.approx(7.0)
    assert avg_land_cost == pytest.approx(12.0)
    assert avg_land_days == pytest.approx(7.0)
    assert saved_land_cost == pytest.approx(2.0)
    assert saved_land_days == pytest.approx(2.0)

    assert air_stats is not None
    assert air_stats["avg_cost"] == pytest.approx((20.0 + 22.0 + 26.0) / 3)
    assert air_stats["avg_time"] == pytest.approx((3.0 + 5.0 + 7.0) / 3)
    assert avg_air_cost == pytest.approx((20.0 + 22.0 + 26.0) / 3)
    assert avg_air_days == pytest.approx((3.0 + 5.0 + 7.0) / 3)
    assert saved_air_cost == pytest.approx(((20.0 + 22.0 + 26.0) / 3) - 20.0)
    assert saved_air_days == pytest.approx(((3.0 + 5.0 + 7.0) / 3) - 3.0)


