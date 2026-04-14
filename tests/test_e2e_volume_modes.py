from pathlib import Path
import time
from uuid import uuid4

import httpx
import pytest

BASE_URL = "http://localhost:8003"
XLSX_PATH = Path(
    r"C:\Users\hbgan\OneDrive\Robert\learn\logistics\xlsx\FBP_List_of_services_7_04_26_1775544198.xlsx"
)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = 'q]j@tFp:q>EUC;9"'
TIMEOUT = 120.0
RETRYABLE_EXCEPTIONS = (httpx.ConnectError, httpx.ReadTimeout)


@pytest.fixture(scope="module")
def admin_token() -> str:
    """登录一次，复用 admin token（含限流重试）。"""
    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as client:
        for attempt in range(10):
            try:
                response = client.post(
                    "/api/auth/login",
                    json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
                )
                if response.status_code == 429:
                    time.sleep(min(5 * (attempt + 1), 30))
                    continue
                assert response.status_code == 200, response.text
                data = response.json()
                assert data["user"]["role"] == "admin"
                return data["access_token"]
            except RETRYABLE_EXCEPTIONS:
                if attempt >= 9:
                    raise
                time.sleep(2)
    raise AssertionError("admin login should return a token")


@pytest.fixture(scope="module", autouse=True)
def preserve_pool(admin_token: str):
    """测试前备份物流池数据，测试后通过 xlsx 重新导入恢复。

    防止 _clear_pool 调用导致生产数据永久丢失。
    """
    transport = _RateLimitTransport()
    headers = {"Authorization": f"Bearer {admin_token}"}
    with httpx.Client(
        base_url=BASE_URL,
        timeout=TIMEOUT,
        headers=headers,
        transport=transport,
    ) as client:
        resp = client.get("/api/logistics-pool", params={"limit": 1000})
        had_data = resp.status_code == 200 and resp.json().get("items")

        yield

        client.delete("/api/logistics-pool/all")
        if had_data and XLSX_PATH.exists():
            with XLSX_PATH.open("rb") as fh:
                files = {
                    "file": (
                        XLSX_PATH.name,
                        fh,
                        "application/vnd.openxmlformats-"
                        "officedocument.spreadsheetml.sheet",
                    )
                }
                client.post("/api/logistics-pool/import", files=files)


class _RateLimitTransport(httpx.HTTPTransport):
    def handle_request(self, request):
        response = super().handle_request(request)
        for attempt in range(10):
            if response.status_code != 429:
                return response
            time.sleep(min(5 * (attempt + 1), 30))
            response = super().handle_request(request)
        return response


@pytest.fixture
def api_client(admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    transport = _RateLimitTransport()
    with httpx.Client(
        base_url=BASE_URL,
        timeout=TIMEOUT,
        headers=headers,
        transport=transport,
    ) as client:
        yield client


def _unique_name(prefix: str) -> str:
    return f"{prefix} {uuid4().hex[:8]}"


def _assert_ok(response: httpx.Response, expected_status: int) -> dict:
    assert response.status_code == expected_status, response.text
    return response.json()


def _clear_pool(client: httpx.Client) -> None:
    response = client.delete("/api/logistics-pool/all")
    assert response.status_code == 200, response.text


def _import_pool(client: httpx.Client) -> list[dict]:
    with XLSX_PATH.open("rb") as handle:
        files = {
            "file": (
                XLSX_PATH.name,
                handle,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        }
        import_response = client.post("/api/logistics-pool/import", files=files)
    import_data = _assert_ok(import_response, 200)
    assert import_data["imported"] > 0
    pool_response = client.get("/api/logistics-pool", params={"limit": 1000})
    pool_data = _assert_ok(pool_response, 200)
    items = pool_data["items"]
    assert items, "物流池导入后应存在数据"
    return items


def _delete_logistics_if_exists(client: httpx.Client, logistics_id: int | None) -> None:
    if logistics_id is None:
        return
    response = client.delete(f"/api/logistics/{logistics_id}")
    assert response.status_code == 200, response.text


def _create_logistics_rule(client: httpx.Client, payload: dict) -> dict:
    response = client.post("/api/logistics", json=payload)
    return _assert_ok(response, 201)


def _calculate_fast(client: httpx.Client, product_data: dict) -> dict:
    response = client.post(
        "/api/pricing/calculate",
        json={"mode": "fast", "product_data": product_data},
    )
    return _assert_ok(response, 200)


def _deactivate_all_logistics(client: httpx.Client) -> list[int]:
    resp = client.get("/api/logistics", params={"limit": 1000})
    data = _assert_ok(resp, 200)
    items = data["items"]
    deactivated_ids = []
    for item in items:
        if item.get("is_active"):
            client.put(
                f"/api/logistics/{item['id']}",
                json={"is_active": 0},
            )
            deactivated_ids.append(item["id"])
    return deactivated_ids


def _reactivate_logistics(client: httpx.Client, ids: list[int]) -> None:
    for lid in ids:
        client.put(f"/api/logistics/{lid}", json={"is_active": 1})


def test_fbp_xlsx_import_populates_volume_modes_in_pool(api_client: httpx.Client):
    """6.1 导入 FBP xlsx 后，物流池应包含完整体积模式字段。"""
    try:
        _clear_pool(api_client)
        items = _import_pool(api_client)

        none_items = [item for item in items if item["volume_mode"] == "none"]
        sum_items = [item for item in items if item["volume_mode"] == "sum_of_sides"]
        max_items = [
            item for item in items if item["volume_mode"] == "max_actual_vs_volume"
        ]

        # 中文注释：验证三种目标体积模式都已真实导入。
        assert none_items, "应导入 physical weight -> none 的记录"
        assert sum_items, "应导入 sum_of_sides 的记录"
        assert max_items, "应导入 max_actual_vs_volume 的记录"

        thresholds = {item["sum_of_sides_threshold"] for item in sum_items}
        assert 75 in thresholds or 90 in thresholds

        sample = next(
            item for item in sum_items if item["sum_of_sides_threshold"] in {75, 90}
        )
        assert sample["sum_of_sides_threshold"] > 0
        assert sample["volume_coefficient"] == pytest.approx(6000.0)
    finally:
        _clear_pool(api_client)


def test_add_pool_record_to_my_logistics_transfers_volume_fields(
    api_client: httpx.Client,
):
    """6.2 从物流池添加到我的物流后，应保留 sum_of_sides 字段。"""
    created_logistics_id = None
    try:
        _clear_pool(api_client)
        items = _import_pool(api_client)
        pool_item = next(
            item for item in items if item["volume_mode"] == "sum_of_sides"
        )

        add_response = api_client.post(
            f"/api/logistics-pool/{pool_item['id']}/add-to-my-logistics"
        )
        add_data = _assert_ok(add_response, 200)
        created_logistics_id = add_data["id"]

        logistics_response = api_client.get("/api/logistics", params={"limit": 1000})
        logistics_data = _assert_ok(logistics_response, 200)
        logistics_items = logistics_data["items"]
        created_item = next(
            item for item in logistics_items if item["id"] == created_logistics_id
        )

        # 中文注释：验证从 pool 复制到用户物流后的核心字段完全一致。
        assert created_item["volume_mode"] == "sum_of_sides"
        assert (
            created_item["sum_of_sides_threshold"]
            == pool_item["sum_of_sides_threshold"]
        )
        assert created_item["volume_coefficient"] == pytest.approx(
            pool_item["volume_coefficient"]
        )
    finally:
        _delete_logistics_if_exists(api_client, created_logistics_id)
        _clear_pool(api_client)


def test_pricing_calculation_uses_sum_of_sides_threshold(api_client: httpx.Client):
    """6.3 sum_of_sides 模式下，超阈值与未超阈值应产生不同物流成本。"""
    logistics_id = None
    deactivated_ids: list[int] = []
    rule_name = _unique_name("E2E test sum_of_sides")
    payload = {
        "name": rule_name,
        "type": "land",
        "delivery_method": "door",
        "fee_mode": "per_kg",
        "first_fee": 0.1,
        "first_weight_g": 1000,
        "continue_fee": 0.1,
        "continue_unit": "1000",
        "min_days": 1,
        "max_days": 1,
        "volume_mode": "sum_of_sides",
        "sum_of_sides_threshold": 80,
        "volume_coefficient": 6000,
        "min_weight": 0,
        "max_weight": 50000,
        "is_active": 1,
        "fulfillment_type": "fbp",
        "destination": "RU",
        "price_min_cny": 0,
        "price_limit_cny": 100000,
    }

    try:
        deactivated_ids = _deactivate_all_logistics(api_client)
        created = _create_logistics_rule(api_client, payload)
        logistics_id = created["id"]

        exceed_result = _calculate_fast(
            api_client,
            {
                "name": "E2E Volume Test",
                "weight_g": 500,
                "length_cm": 30,
                "width_cm": 30,
                "height_cm": 30,
                "unit_price": 50,
                "commission_rate": 5,
                "target_profit_margin": 20,
            },
        )
        below_result = _calculate_fast(
            api_client,
            {
                "name": "E2E Volume Test Small",
                "weight_g": 500,
                "length_cm": 10,
                "width_cm": 10,
                "height_cm": 10,
                "unit_price": 50,
                "commission_rate": 5,
                "target_profit_margin": 20,
            },
        )

        exceed_item = exceed_result["price_priority"]["land"]
        below_item = below_result["price_priority"]["land"]

        assert exceed_item["is_available"] is True
        assert below_item["is_available"] is True
        assert exceed_item["logistics_name"] == rule_name
        assert below_item["logistics_name"] == rule_name
        assert exceed_item["logistics_cost"] == pytest.approx(0.5, abs=1e-6)
        assert below_item["logistics_cost"] == pytest.approx(0.1, abs=1e-6)
        assert exceed_item["logistics_cost"] > below_item["logistics_cost"]
    finally:
        _delete_logistics_if_exists(api_client, logistics_id)
        _reactivate_logistics(api_client, deactivated_ids)


def test_pricing_calculation_uses_longest_side_threshold(api_client: httpx.Client):
    """6.4 longest_side 模式下，超阈值与未超阈值应产生不同物流成本。"""
    logistics_id = None
    deactivated_ids: list[int] = []
    rule_name = _unique_name("E2E test longest_side")
    payload = {
        "name": rule_name,
        "type": "land",
        "delivery_method": "door",
        "fee_mode": "per_kg",
        "first_fee": 0.1,
        "first_weight_g": 1000,
        "continue_fee": 0.1,
        "continue_unit": "1000",
        "min_days": 1,
        "max_days": 1,
        "volume_mode": "longest_side",
        "longest_side_threshold": 40,
        "volume_coefficient": 6000,
        "min_weight": 0,
        "max_weight": 50000,
        "is_active": 1,
        "fulfillment_type": "fbp",
        "destination": "RU",
        "price_min_cny": 0,
        "price_limit_cny": 100000,
    }

    try:
        deactivated_ids = _deactivate_all_logistics(api_client)
        created = _create_logistics_rule(api_client, payload)
        logistics_id = created["id"]

        exceed_result = _calculate_fast(
            api_client,
            {
                "name": "E2E Longest Test",
                "weight_g": 500,
                "length_cm": 50,
                "width_cm": 20,
                "height_cm": 20,
                "unit_price": 50,
                "commission_rate": 5,
                "target_profit_margin": 20,
            },
        )
        below_result = _calculate_fast(
            api_client,
            {
                "name": "E2E Longest Test Small",
                "weight_g": 500,
                "length_cm": 30,
                "width_cm": 20,
                "height_cm": 20,
                "unit_price": 50,
                "commission_rate": 5,
                "target_profit_margin": 20,
            },
        )

        exceed_item = exceed_result["price_priority"]["land"]
        below_item = below_result["price_priority"]["land"]

        assert exceed_item["is_available"] is True
        assert below_item["is_available"] is True
        assert exceed_item["logistics_name"] == rule_name
        assert below_item["logistics_name"] == rule_name
        assert exceed_item["logistics_cost"] == pytest.approx(0.4, abs=1e-6)
        assert below_item["logistics_cost"] == pytest.approx(0.1, abs=1e-6)
        assert exceed_item["logistics_cost"] > below_item["logistics_cost"]
    finally:
        _delete_logistics_if_exists(api_client, logistics_id)
        _reactivate_logistics(api_client, deactivated_ids)
