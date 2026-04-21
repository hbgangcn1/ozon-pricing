from db.products import add_product, get_products_by_names


async def test_get_products_by_names_empty_returns_empty_dict(db_session, test_user):
    result = await get_products_by_names(db_session, test_user["id"], [])
    assert result == {}


async def test_get_products_by_names_returns_multiple_matches(db_session, test_user):
    await add_product(db_session, test_user["id"], {"name": "Batch Product 1"})
    await add_product(db_session, test_user["id"], {"name": "Batch Product 2"})

    result = await get_products_by_names(
        db_session,
        test_user["id"],
        ["Batch Product 1", "Batch Product 2", "Missing Product"],
    )

    assert set(result) == {"Batch Product 1", "Batch Product 2"}
    assert result["Batch Product 1"]["name"] == "Batch Product 1"
    assert result["Batch Product 2"]["name"] == "Batch Product 2"
