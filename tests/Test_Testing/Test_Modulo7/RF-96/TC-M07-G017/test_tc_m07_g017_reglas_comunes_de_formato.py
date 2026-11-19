"""
TC-M07-G017 (RF-96 5.2, CA-5, CU-05) - "Reglas comunes de formato."
Agrupa TC-96-035 a TC-96-040.

Construido 2026-11-18 contra el código real (aaef.py) y datos reales de
TEST (NIT 901444215, período 627).

Código bajo prueba:
    src/accounting_integration/domain/services/aaef.py
    src/accounting_integration/domain/services/esquema_agrofusion.py (AccountingConsultResponse)
    src/financial_valuation/domain/services/nic41.py (truncar2)

Cómo se prueba: pytest de unidad; la validación de esquema completo usa el
modelo Pydantic real que valida AgroFusión (réplica exacta, ver su
docstring).

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m07_g017_reglas_comunes_de_formato.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M07-G017.html --self-contained-html
"""
from __future__ import annotations

import datetime
import json
from decimal import Decimal

from src.accounting_integration.domain.services.aaef import (
    CostoFactura,
    SistemaOrigen,
    Titular,
    construir_envelope,
    mapear_compras,
    serializar,
)
from src.accounting_integration.domain.services.esquema_agrofusion import AccountingConsultResponse
from src.financial_valuation.domain.services.nic41 import truncar2

D = Decimal
SISTEMA = SistemaOrigen(system_id="SGPMP", system_name="SIGAB", environment="TEST")
TITULAR = Titular("901444215", "Hacienda Qa Mseis S.A.S.")


def _costo(**kw) -> CostoFactura:
    base = dict(id_registro_costo=4485, tercero_nit="900777571", tercero_razon_social="Concentrados La Pradera S.A.S.",
                factura_prefijo="CP", factura_numero="1187", fecha_factura=datetime.date(2026, 10, 8),
                fecha_vencimiento_factura=datetime.date(2026, 11, 7), subtipo_costo="ALIMENTO",
                monto_costo=D("380000"), cuenta_debito="158405", activo="QA-M07-BUF-F2")
    base.update(kw)
    return CostoFactura(**base)


class TestSubCasoCamposComunesDeFormatoConfirmadosCorrectos:
    def test_status_siempre_es_active(self):
        doc = mapear_compras([_costo()])[0]
        assert doc["Header"]["Status"] == "ACTIVE"

    def test_las_fechas_son_strings_yyyy_mm_dd_sin_hora(self):
        doc = mapear_compras([_costo()])[0]
        for campo in ("IssueDate", "DueDate", "UpdatedAt"):
            valor = doc["Header"][campo]
            assert isinstance(valor, str)
            datetime.date.fromisoformat(valor)  # lanza si no es YYYY-MM-DD exacto
            assert len(valor) == 10

    def test_taxes_vacio_y_totales_de_impuestos_retenciones_descuentos_en_cero(self):
        doc = mapear_compras([_costo()])[0]
        assert doc["Lines"][0]["Taxes"] == []
        assert doc["Totals"]["TotalVAT"] == doc["Totals"]["TotalWithholdings"] == doc["Totals"]["TotalDiscounts"] == 0


class TestSubCasoTruncadoA2DecimalesSinRedondeoConfirmadoCorrecto:
    def test_123_999_trunca_a_123_99_no_a_124_00(self):
        assert truncar2(D("123.999")) == D("123.99")

    def test_123_455_trunca_a_123_45_confirma_que_no_es_redondeo(self):
        assert truncar2(D("123.455")) == D("123.45")

    def test_0_009_trunca_a_0_00(self):
        assert truncar2(D("0.009")) == D("0.00")

    def test_el_monto_de_un_costo_real_con_mas_de_2_decimales_se_trunca_en_el_mapper(self):
        doc = mapear_compras([_costo(monto_costo=D("380000.999"))])[0]
        assert doc["Lines"][0]["Value"] == D("380000.99")


class TestSubCasoZonaHorariaNoAplicaEnEstaCapaDocumentacion:
    def test_costofactura_solo_recibe_date_nunca_datetime_con_hora(self):
        """No es un defecto en RF-96/Mapper: CostoFactura.fecha_factura es `date`, sin hora
        ni zona horaria -- el salto de día cerca de las 7-8 p. m. hora de Colombia (si
        ocurre) tendría que originarse en M06 al resolver esa fecha, nunca en el Mapper,
        que no recibe ningún datetime con tz. No hay forma de reproducir el escenario de la
        ficha en esta capa con una fixture (sería forzar un tipo que la función no acepta)."""
        import typing
        from src.accounting_integration.domain.services import aaef
        tipos = typing.get_type_hints(aaef.CostoFactura)
        assert tipos['fecha_factura'] is datetime.date


class TestSubCasoValidacionCompletaContraElEsquemaDeAgrofusion:
    def test_el_envelope_real_de_un_periodo_valida_completo_contra_el_esquema(self):
        """Usa el mismo modelo Pydantic que valida AgroFusión (esquema_agrofusion.py) sobre
        un envelope construido con el Mapper real y datos reales de TEST."""
        compras = mapear_compras([_costo()])
        envelope = construir_envelope(TITULAR, datetime.date(2026, 10, 1), datetime.date(2026, 10, 31), SISTEMA,
                                      "contador@pecuaria.co", datetime.date(2026, 11, 18), compras, [])
        cuerpo = serializar(envelope)
        validado = AccountingConsultResponse.model_validate_json(cuerpo)
        assert len(validado.invoices) == 1
        assert validado.invoices[0].Header.DocumentId == "COS-4485-20261008"

    def test_el_json_serializado_es_utf8_valido_con_tildes_y_enes(self):
        compras = mapear_compras([_costo(activo="QA-M07-BUF-F2")])
        envelope = construir_envelope(TITULAR, datetime.date(2026, 10, 1), datetime.date(2026, 10, 31), SISTEMA,
                                      "contador@pecuaria.co", datetime.date(2026, 11, 18), compras, [])
        cuerpo = serializar(envelope)
        decodificado = json.loads(cuerpo.decode("utf-8"))
        assert decodificado["invoices"][0]["Lines"][0]["Description"] == "Activo biológico QA-M07-BUF-F2"
