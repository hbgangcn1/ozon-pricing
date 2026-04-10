from io import BytesIO

import openpyxl

from api.dependencies import get_current_user_id
from api.main import app
from database import AsyncSessionLocal
from db.products import get_product_by_name


def _user_override(user_id):
    app.dependency_overrides[get_current_user_id] = lambda: user_id


def _clear_overrides():
    app.dependency_overrides.clear()


def _build_product_workbook(row_count):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["name", "weight_g", "length_cm", "width_cm", "height_cm"])

    for index in range(1, row_count + 1):
        sheet.append(
            [
                f"Imported Product {index}",
                100 + index,
                10,
                5,
                3,
            ]
        )

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


class TestProductImportTruncation:
    async def test_preview_returns_all_rows_from_uploaded_excel(
        self, client, test_user
    ):
        user_id = test_user["id"]
        _user_override(user_id)
        try:
            workbook = _build_product_workbook(12)

            response = await client.post(
                "/api/products/import/preview",
                files={
                    "file": (
                        "products.xlsx",
                        workbook.getvalue(),
                        "application/vnd.openxmlformats-officedocument"
                        ".spreadsheetml.sheet",
                    )
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["preview_rows"]) == 12
            assert data["preview_rows"][10]["name"] == "Imported Product 11"
            assert data["preview_rows"][11]["name"] == "Imported Product 12"
        finally:
            _clear_overrides()

    async def test_confirm_import_processes_all_rows_from_preview_payload(
        self, client, test_user
    ):
        user_id = test_user["id"]
        _user_override(user_id)
        try:
            workbook = _build_product_workbook(12)
            preview_response = await client.post(
                "/api/products/import/preview",
                files={
                    "file": (
                        "products.xlsx",
                        workbook.getvalue(),
                        "application/vnd.openxmlformats-officedocument"
                        ".spreadsheetml.sheet",
                    )
                },
            )
            assert preview_response.status_code == 200
            preview_data = preview_response.json()
            assert len(preview_data["preview_rows"]) == 12

            confirm_response = await client.post(
                "/api/products/import/confirm",
                json={
                    "rows": preview_data["preview_rows"],
                    "column_mapping": {
                        "name": "name",
                        "weight_g": "weight_g",
                        "length_cm": "length_cm",
                        "width_cm": "width_cm",
                        "height_cm": "height_cm",
                    },
                    "conflict_action": "skip",
                },
            )

            assert confirm_response.status_code == 200
            confirm_data = confirm_response.json()
            assert confirm_data["imported"] == 12
            assert confirm_data["skipped"] == 0
            assert confirm_data["errors"] == []

            async with AsyncSessionLocal() as session:
                for index in range(1, 13):
                    product = await get_product_by_name(
                        session, user_id, f"Imported Product {index}"
                    )
                    assert product is not None
        finally:
            _clear_overrides()
