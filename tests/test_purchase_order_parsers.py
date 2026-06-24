import sys
from types import SimpleNamespace

try:
    import pdfplumber  # noqa: F401
except ModuleNotFoundError:
    sys.modules["pdfplumber"] = SimpleNamespace(PDF=object)

from app.parsers.purchase_orders import _parse_danec, _parse_favorita


def test_favorita_uses_each_filename_only_as_a_confirmable_hint():
    text = """
    CORPORACION FAVORITA C.A.
    https://cfavorita.ec/b2b/pedidos.do?pedidoId=55555555
    """

    first = _parse_favorita(text, "OC 123456 - JUN.pdf")[0]
    second = _parse_favorita(text, "OC 987654 - JUL.pdf")[0]

    assert first["order_number"] == "123456"
    assert second["order_number"] == "987654"
    assert first["order_number_source"] == "filename"
    assert first["external_reference"] == "PEDIDO PORTAL 55555555"


def test_favorita_does_not_invent_an_order_number():
    order = _parse_favorita("CORPORACION FAVORITA C.A.", "pedido.pdf")[0]

    assert order["order_number"] == ""
    assert order["order_number_source"] == "missing"


def test_danec_extracts_each_order_number_from_its_header():
    text = """
    INDUSTRIAL DANEC S A
    ORDEN DE COMPRA2 7N0º09999 OB ENS101
    """

    order = _parse_danec(text)[0]

    assert order["order_number"] == "27009999"
    assert order["order_number_source"] == "document"
