"""Tests for add_unselected() reason text by priority_type."""

from pricing.select_best import add_unselected


def _log(name, min_days=5, max_days=10, priority_group="C"):
    return {
        "name": name,
        "min_days": min_days,
        "max_days": max_days,
        "priority_group": priority_group,
    }


class TestAddUnselectedPriceReason:
    """低价优先 (default) should show cost comparison."""

    def test_cost_reason_without_best(self):
        candidates = [(_log("Slow"), 20.0)]
        fl = []
        add_unselected(candidates, fl)
        assert len(fl) == 1
        assert fl[0]["reason"] == "未被选中，物流成本 ¥20.00"

    def test_cost_reason_with_best(self):
        best = (_log("Fast", min_days=2, max_days=4), 10.0)
        loser = (_log("Slow"), 20.0)
        candidates = [best, loser]
        fl = []
        add_unselected(candidates, fl, global_best=best)
        assert len(fl) == 1
        assert "物流成本 ¥20.00" in fl[0]["reason"]
        assert "已选更优方案：Fast ¥10.00" in fl[0]["reason"]

    def test_cost_reason_explicit_price_priority(self):
        best = (_log("Fast"), 10.0)
        loser = (_log("Slow"), 20.0)
        fl = []
        add_unselected([best, loser], fl, global_best=best, priority_type="低价优先")
        assert "物流成本" in fl[0]["reason"]
        assert "时效" not in fl[0]["reason"]


class TestAddUnselectedSpeedReason:
    """速度优先 should show delivery-time comparison."""

    def test_speed_reason_without_best(self):
        candidates = [(_log("Slow", min_days=8, max_days=12), 20.0)]
        fl = []
        add_unselected(candidates, fl, priority_type="速度优先")
        assert len(fl) == 1
        assert fl[0]["reason"] == "未被选中，时效 8-12天"

    def test_speed_reason_with_best(self):
        best = (_log("Fast", min_days=2, max_days=4, priority_group="A"), 15.0)
        loser = (_log("Slow", min_days=8, max_days=12, priority_group="C"), 10.0)
        candidates = [best, loser]
        fl = []
        add_unselected(candidates, fl, global_best=best, priority_type="速度优先")
        assert len(fl) == 1
        r = fl[0]["reason"]
        assert "时效 8-12天" in r
        assert "已选更快方案：Fast 2-4天" in r

    def test_speed_reason_no_cost_info(self):
        """Speed priority reason must NOT contain cost info."""
        best = (_log("Fast", min_days=2, max_days=4), 15.0)
        loser = (_log("Slow", min_days=8, max_days=12), 10.0)
        fl = []
        add_unselected([best, loser], fl, global_best=best, priority_type="速度优先")
        assert "¥" not in fl[0]["reason"]
        assert "物流成本" not in fl[0]["reason"]

    def test_speed_reason_still_prefixed_unselected(self):
        """Frontend checks '未被选中' prefix — must be preserved."""
        fl = []
        add_unselected([(_log("X", 5, 10), 20.0)], fl, priority_type="速度优先")
        assert fl[0]["reason"].startswith("未被选中")


class TestAddUnselectedEdgeCases:
    """Edge cases that apply regardless of priority_type."""

    def test_empty_candidates(self):
        fl = []
        add_unselected([], fl, priority_type="速度优先")
        assert fl == []

    def test_best_is_skipped(self):
        best = (_log("Best"), 10.0)
        fl = []
        add_unselected([best], fl, global_best=best, priority_type="速度优先")
        assert fl == []

    def test_already_filtered_is_skipped(self):
        fl = [{"name": "Dup", "reason": "过滤"}]
        add_unselected([(_log("Dup"), 20.0)], fl, priority_type="速度优先")
        assert len(fl) == 1

    def test_multiple_losers(self):
        best = (_log("Best", 1, 3, "A"), 10.0)
        c1 = (_log("L1", 5, 10, "C"), 20.0)
        c2 = (_log("L2", 8, 14, "D"), 25.0)
        fl = []
        add_unselected([best, c1, c2], fl, global_best=best, priority_type="速度优先")
        assert len(fl) == 2
        names = {item["name"] for item in fl}
        assert names == {"L1", "L2"}
        for item in fl:
            assert "时效" in item["reason"]
            assert "已选更快方案：Best 1-3天" in item["reason"]
