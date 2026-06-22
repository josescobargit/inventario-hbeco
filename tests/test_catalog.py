from backend.app.services.catalog import (
    clean_catalog_code,
    is_product_sku,
    units_per_case_for_product,
)


def test_units_per_case_for_sachets():
    assert units_per_case_for_product("AR005", "SHAMPOO ANA REGENEXT RISTRA 18 ML.") == 288
    assert units_per_case_for_product("AR006", "ACONDICIONADOR ANA REGENEXT SACHET 18 ML.") == 288


def test_units_per_case_for_packs():
    assert units_per_case_for_product("AE003", "PACK SH + AC ANA ELIXIR ROMERO 370 ML.") == 6
    assert units_per_case_for_product("AR012", "PACK SH+AC REGENEXT ARGAN") == 6


def test_units_per_case_default():
    assert units_per_case_for_product("AE001", "SHAMPOO ANA ELIXIR ROMERO 370 ML.") == 12


def test_sku_detection():
    assert is_product_sku("AE001")
    assert is_product_sku("ACP001")
    assert not is_product_sku("Listado de productos")


def test_catalog_code_cleanup():
    assert clean_catalog_code("7862133169275.0") == "7862133169275"
