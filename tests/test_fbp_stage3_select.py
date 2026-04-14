import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pricing.fbp_stage3_select import (  # noqa: E402
    compute_temp_abcde_groups,
    select_best_price_stage3,
    select_best_speed_stage3,
)


def _log(name, min_days, max_days):
    return {"name": name, "min_days": min_days, "max_days": max_days}


def _candidate(name, min_days, max_days, cost):
    return (_log(name, min_days, max_days), cost)


def test_standard_grouping():
    logs = [
        _log("L1", 3, 5),
        _log("L2", 2, 4),
        _log("L3", 7, 10),
        _log("L4", 5, 8),
        _log("L5", 0, 0),
    ]

    assert compute_temp_abcde_groups(logs) == {
        "L1": "A",
        "L2": "A",
        "L3": "D",
        "L4": "D",
        "L5": "E",
    }


def test_all_same_times():
    logs = [_log("L1", 5, 7), _log("L2", 5, 7), _log("L3", 5, 7)]

    assert compute_temp_abcde_groups(logs) == {"L1": "A", "L2": "A", "L3": "A"}


def test_single_logistics():
    assert compute_temp_abcde_groups([_log("L1", 4, 6)]) == {"L1": "A"}


def test_all_zero_times():
    logs = [_log("L1", 0, 0), _log("L2", 0, 0), _log("L3", 0, 0)]

    assert compute_temp_abcde_groups(logs) == {"L1": "E", "L2": "E", "L3": "E"}


def test_mixed_valid_invalid():
    logs = [
        _log("L1", 3, 5),
        _log("L2", None, 4),
        _log("L3", 2, 3),
        _log("L4", 0, 0),
    ]

    assert compute_temp_abcde_groups(logs) == {
        "L1": "D",
        "L2": "E",
        "L3": "A",
        "L4": "E",
    }


def test_empty_list():
    assert compute_temp_abcde_groups([]) == {}


def test_two_logistics_grouping():
    logs = [_log("L1", 2, 4), _log("L2", 6, 8)]

    assert compute_temp_abcde_groups(logs) == {"L1": "A", "L2": "D"}


def test_pick_lowest_cost_in_best_group():
    candidates = [
        _candidate("A1", 3, 5, 20),
        _candidate("A2", 2, 4, 10),
        _candidate("B1", 7, 9, 1),
    ]
    temp_groups = {"A1": "A", "A2": "A", "B1": "B"}

    assert select_best_speed_stage3(candidates, temp_groups) == candidates[1]


def test_fallback_to_b_when_no_a():
    candidates = [
        _candidate("B1", 3, 5, 30),
        _candidate("B2", 4, 6, 10),
        _candidate("D1", 7, 9, 1),
    ]
    temp_groups = {"B1": "B", "B2": "B", "D1": "D"}

    assert select_best_speed_stage3(candidates, temp_groups) == candidates[1]


def test_fallback_cascade():
    candidates = [_candidate("D1", 7, 9, 30), _candidate("D2", 8, 10, 5)]
    temp_groups = {"D1": "D", "D2": "D"}

    assert select_best_speed_stage3(candidates, temp_groups) == candidates[1]


def test_tiebreak_by_avg_time():
    candidates = [_candidate("A1", 4, 8, 10), _candidate("A2", 2, 4, 10)]
    temp_groups = {"A1": "A", "A2": "A"}

    assert select_best_speed_stage3(candidates, temp_groups) == candidates[1]


def test_empty_candidates_speed():
    assert select_best_speed_stage3([], {}) == (None, None)


def test_all_e_group():
    candidates = [
        _candidate("E1", 0, 0, 9),
        _candidate("E2", None, None, 4),
        _candidate("E3", 0, None, 1),
    ]
    temp_groups = {"E1": "E", "E2": "E", "E3": "E"}

    assert select_best_speed_stage3(candidates, temp_groups) == candidates[2]


def test_pick_lowest_cost():
    candidates = [
        _candidate("L1", 5, 7, 12),
        _candidate("L2", 3, 6, 4),
        _candidate("L3", 1, 2, 9),
    ]

    assert select_best_price_stage3(candidates) == candidates[1]


def test_tiebreak_by_avg_time_price():
    candidates = [_candidate("L1", 6, 8, 10), _candidate("L2", 2, 4, 10)]

    assert select_best_price_stage3(candidates) == candidates[1]


def test_empty_candidates_price():
    assert select_best_price_stage3([]) == (None, None)


def test_none_min_max_treated_as_zero():
    candidates = [_candidate("L1", None, None, 1), _candidate("L2", 2, 3, 2)]

    assert select_best_price_stage3(candidates) == candidates[0]


def test_speed_prefers_a_over_cheaper_lower_group():
    candidates = [_candidate("A1", 3, 5, 50), _candidate("D1", 8, 10, 1)]
    temp_groups = {"A1": "A", "D1": "D"}

    assert select_best_speed_stage3(candidates, temp_groups) == candidates[0]


def test_price_ignores_grouping_and_uses_cost_only():
    candidates = [
        _candidate("A1", 3, 5, 8),
        _candidate("E1", 0, 0, 2),
        _candidate("D1", 7, 9, 5),
    ]

    assert select_best_price_stage3(candidates) == candidates[1]
