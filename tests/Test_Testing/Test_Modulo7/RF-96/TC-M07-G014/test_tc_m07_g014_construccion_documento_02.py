"""
TC-M07-G014 (RF-96 5.3, CA-1, CU-03) - "Construcción del documento 02 por
el Mapper de Compras." Agrupa TC-96-013 a TC-96-020.

Construido 2026-11-18 contra el código real (mapear_compras(), aaef.py).
El caso base usa datos REALES de TEST (NIT 901444215, período 627,
octubre 2026 -- confirmados en vivo con el Contador el 2026-11-17/18) y el
caso literal de la ficha (factura FE-88231 / proveedor 800555111) como
fixture sintética porque ese ejemplo exacto no existe en TEST.

Dato real (vista-previa, período 627): documento COS-4485-20261008,
Prefix=CP, Serial=1187, proveedor 900777571 "Concentrados La Pradera
S.A.S.", 1 línea ALIMENTO, accounting_account=['158405'],
OutstandingBalance=Subtotal=380000.0. Confirma CA-1 campo a campo con un
NIT/factura reales distintos del ejemplo de la ficha.

Código bajo prueba:
    src/accounting_integration/domain/services/aaef.py (mapear_compras)

Cómo se prueba: pytest de unidad invocando mapear_compras() directamente
(función pura, sin BD) con fixtures que replican tanto el caso real de
TEST como el caso literal CA-1.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m07_g014_construccion_documento_02.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M07-G014.html --self-contained-html
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from src.accounting_integration.domain.services.aaef import CostoFactura, mapear_compras

D = Decimal


def _costo(**kw) -> CostoFactura:
    base = dict(id_registro_costo=1, tercero_nit="900777571", tercero_razon_social="Concentrados La Pradera S.A.S.",
                factura_prefijo="CP", factura_numero="1187", fecha_factura=datetime.date(2026, 10, 8),
                fecha_vencimiento_factura=datetime.date(2026, 11, 7), subtipo_costo="ALIMENTO",
                monto_costo=D("380000"), cuenta_debito="158405", activo="QA-M07-BUF-F2")
    base.update(kw)
    return CostoFactura(**base)


class TestSubCasoCA1LiteralDeLaFichaConfirmadoCorrecto:
    def test_factura_fe_88231_del_proveedor_800555111(self):
        """Caso literal de CA-1 (fixture sintética: ese NIT/factura exactos no existen en
        TEST, pero el mecanismo ya se confirmó con datos reales equivalentes abajo)."""
        costo = _costo(id_registro_costo=943, tercero_nit="800555111", tercero_razon_social="Proveedor CA-1 S.A.S.",
                       factura_prefijo="FE", factura_numero="88231")
        documentos = mapear_compras([costo])
        assert len(documentos) == 1
        doc = documentos[0]
        assert doc["Header"]["Prefix"] == "FE"
        assert doc["Header"]["Serial"] == "88231"
        assert doc["ThirdParty"]["NIT"] == "800555111"
        assert len(doc["Lines"][0]["accounting_account"]) == 1


class TestSubCasoCA1ConDatosRealesDeTestConfirmadoCorrecto:
    def test_la_factura_real_cos_4485_cuadra_campo_a_campo(self):
        """Replica exacta del documento real devuelto por vista-previa en TEST (período 627,
        NIT 901444215, 2026-11-17/18) -- confirma que mapear_compras() produce lo mismo que
        la API viva con la misma entrada."""
        costo = _costo(id_registro_costo=4485)
        doc = mapear_compras([costo])[0]
        assert doc["Header"]["DocumentId"] == "COS-4485-20261008"
        assert doc["Header"]["IssueDate"] == "2026-10-08"
        assert doc["Header"]["UpdatedAt"] == "2026-10-08"
        assert doc["Totals"]["Subtotal"] == D("380000")
        assert doc["Totals"]["OutstandingBalance"] == doc["Totals"]["Subtotal"]


class TestSubCasoDocumentIdConFechasDeUnSoloDigitoConfirmadoCorrecto:
    def test_documentid_usa_el_id_de_costo_y_la_fecha_con_ceros_a_la_izquierda(self):
        costo = _costo(id_registro_costo=123, fecha_factura=datetime.date(2026, 1, 5))
        doc = mapear_compras([costo])[0]
        assert doc["Header"]["DocumentId"] == "COS-123-20260105"

    def test_29_de_febrero_bisiesto(self):
        costo = _costo(id_registro_costo=55, fecha_factura=datetime.date(2028, 2, 29))
        doc = mapear_compras([costo])[0]
        assert doc["Header"]["DocumentId"] == "COS-55-20280229"


class TestSubCasoCreditoYContadoConfirmadoCorrecto:
    def test_factura_a_credito_usa_la_fecha_de_vencimiento_real(self):
        costo = _costo(fecha_vencimiento_factura=datetime.date(2026, 11, 7))
        doc = mapear_compras([costo])[0]
        assert doc["Header"]["DueDate"] == "2026-11-07"

    def test_factura_de_contado_sin_fecha_de_vencimiento_usa_la_fecha_de_la_factura(self):
        """El RF no define cómo se marca 'de contado' en RF-90; el código real resuelve
        fecha_vencimiento_factura=None -> DueDate=IssueDate, que es la única señal
        disponible en el dataclass CostoFactura."""
        costo = _costo(fecha_vencimiento_factura=None)
        doc = mapear_compras([costo])[0]
        assert doc["Header"]["DueDate"] == doc["Header"]["IssueDate"]


class TestSubCasoThirdPartyYLineaUnicaConfirmadoCorrecto:
    def test_thirdparty_nit_y_name_vienen_del_tercero_proveedor(self):
        doc = mapear_compras([_costo()])[0]
        assert doc["ThirdParty"] == {"NIT": "900777571", "Name": "Concentrados La Pradera S.A.S."}

    def test_una_linea_unica_con_code_linetype_quantity_1_y_value_igual_a_unitprice(self):
        doc = mapear_compras([_costo(monto_costo=D("1234567.8999"))])[0]
        linea = doc["Lines"][0]
        assert linea["Code"] == linea["LineType"] == "ALIMENTO"
        assert linea["Quantity"] == D(1)
        assert linea["UnitPrice"] == linea["Value"]
        assert linea["Value"] == D("1234567.89")  # truncado a 2 decimales, ver TC-M07-G017

    def test_description_incluye_el_identificador_legible_del_activo(self):
        """CONFIRMADO: Description es 'Activo biológico {activo}', nunca un '#id' crudo."""
        doc = mapear_compras([_costo(activo="QA-M07-BUF-F2")])[0]
        assert doc["Lines"][0]["Description"] == "Activo biológico QA-M07-BUF-F2"


class TestSubCasoAccountingAccountDeUnSoloElementoYOutstandingBalanceConfirmadoCorrecto:
    def test_accounting_account_tiene_exactamente_un_elemento_la_cuenta_debito(self):
        doc = mapear_compras([_costo(cuenta_debito="158405")])[0]
        assert doc["Lines"][0]["accounting_account"] == ["158405"]

    def test_outstanding_balance_es_igual_al_subtotal_incluso_de_contado(self):
        """CONFIRMADO: incluso una factura 'de contado' queda con OutstandingBalance =
        Subtotal -- el pago se registra en SIGCON, no en la exportación (RF-96 5.3)."""
        doc = mapear_compras([_costo(fecha_vencimiento_factura=None)])[0]
        assert doc["Totals"]["OutstandingBalance"] == doc["Totals"]["Subtotal"]
