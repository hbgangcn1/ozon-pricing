# pyright: reportOptionalSubscript=false
import pytest
from db.priority_group import compute_priority_groups

_ = pytest


class TestComputePriorityGroups:
    """Unit tests for the pure priority group algorithm."""

    def test_empty_list_returns_empty(self):
        result = compute_priority_groups([])
        assert result == {}

    def test_all_invalid_get_group_e(self):
        """Logistics with missing/zero min_days or max_days -> group E."""
        items = [
            {"id": 1, "type": "land", "min_days": 0, "max_days": 10},
            {"id": 2, "type": "land", "min_days": 5, "max_days": None},
            {"id": 3, "type": "land", "min_days": None, "max_days": None},
        ]
        result = compute_priority_groups(items)
        assert result == {1: "E", 2: "E", 3: "E"}

    def test_single_valid_item_gets_group_a(self):
        """Single valid item: all 3 metrics == averages -> all <= -> group A."""
        items = [{"id": 1, "type": "air", "min_days": 5, "max_days": 10}]
        result = compute_priority_groups(items)
        assert result == {1: "A"}

    def test_mixed_valid_and_invalid(self):
        """Invalid items get E; valid items scored against valid-only avgs."""
        items = [
            {"id": 1, "type": "land", "min_days": 3, "max_days": 5},
            {"id": 2, "type": "land", "min_days": 0, "max_days": 10},
            {"id": 3, "type": "land", "min_days": 7, "max_days": 9},
        ]
        result = compute_priority_groups(items)
        assert result[2] == "E"
        # avg_min=5, avg_max=7, avg_avg=6
        # id=1: min=3<=5, max=5<=7, avg=4<=6 -> 3 -> A
        assert result[1] == "A"
        # id=3: min=7>5, max=9>7, avg=8>6 -> 0 -> D
        assert result[3] == "D"

    def test_types_calculated_independently(self):
        """Land and air logistics are scored separately."""
        items = [
            {"id": 1, "type": "land", "min_days": 10, "max_days": 20},
            {"id": 2, "type": "air", "min_days": 2, "max_days": 4},
        ]
        result = compute_priority_groups(items)
        # Each is the only item in its type -> equals average -> A
        assert result[1] == "A"
        assert result[2] == "A"

    def test_types_independent_scoring(self):
        """A slow land item is not penalized by fast air items."""
        items = [
            {"id": 1, "type": "land", "min_days": 10, "max_days": 20},
            {"id": 2, "type": "land", "min_days": 20, "max_days": 30},
            {"id": 3, "type": "air", "min_days": 1, "max_days": 2},
        ]
        result = compute_priority_groups(items)
        # land: avg_min=15, avg_max=25, avg_avg=20
        # id=1: 10<=15, 20<=25, 15<=20 -> A
        assert result[1] == "A"
        # id=2: 20>15, 30>25, 25>20 -> D
        assert result[2] == "D"
        # air: single item -> A
        assert result[3] == "A"

    def test_group_b_exact(self):
        """Construct a scenario where exactly 2 metrics pass -> B."""
        items = [
            {"id": 1, "type": "land", "min_days": 1, "max_days": 10},
            {"id": 2, "type": "land", "min_days": 3, "max_days": 6},
            {"id": 3, "type": "land", "min_days": 5, "max_days": 4},
            {"id": 4, "type": "land", "min_days": 7, "max_days": 8},
        ]
        result = compute_priority_groups(items)
        # avg_min=4, avg_max=7, avg_avg=5.5
        # id=1: min=1<=4, max=10>7, avg=5.5<=5.5 -> 2 -> B
        assert result[1] == "B"
        # id=2: min=3<=4, max=6<=7, avg=4.5<=5.5 -> 3 -> A
        assert result[2] == "A"
        # id=3: min=5>4, max=4<=7, avg=4.5<=5.5 -> 2 -> B
        assert result[3] == "B"
        # id=4: min=7>4, max=8>7, avg=7.5>5.5 -> 0 -> D
        assert result[4] == "D"

    def test_group_c_exact(self):
        """Construct a scenario where exactly 1 metric passes -> C."""
        items = [
            {"id": 1, "type": "air", "min_days": 2, "max_days": 3},
            {"id": 2, "type": "air", "min_days": 4, "max_days": 5},
            {"id": 3, "type": "air", "min_days": 3, "max_days": 8},
        ]
        result = compute_priority_groups(items)
        # avg_min=3, avg_max=5.33, avg_avg=4.17
        # id=1: min=2<=3, max=3<=5.33, avg=2.5<=4.17 -> 3 -> A
        assert result[1] == "A"
        # id=2: min=4>3, max=5<=5.33, avg=4.5>4.17 -> 1 -> C
        assert result[2] == "C"
        # id=3: min=3<=3, max=8>5.33, avg=5.5>4.17 -> 1 -> C
        assert result[3] == "C"

    def test_none_min_days_is_invalid(self):
        items = [{"id": 1, "type": "land", "min_days": None, "max_days": 5}]
        result = compute_priority_groups(items)
        assert result[1] == "E"

    def test_none_max_days_is_invalid(self):
        items = [{"id": 1, "type": "land", "min_days": 5, "max_days": None}]
        result = compute_priority_groups(items)
        assert result[1] == "E"

    def test_zero_min_days_is_invalid(self):
        items = [{"id": 1, "type": "land", "min_days": 0, "max_days": 5}]
        result = compute_priority_groups(items)
        assert result[1] == "E"

    def test_zero_max_days_is_invalid(self):
        items = [{"id": 1, "type": "land", "min_days": 5, "max_days": 0}]
        result = compute_priority_groups(items)
        assert result[1] == "E"

    def test_missing_type_defaults_to_land(self):
        items = [{"id": 1, "min_days": 5, "max_days": 10}]
        result = compute_priority_groups(items)
        assert result[1] == "A"
