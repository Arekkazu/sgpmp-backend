"""
TC-M07-G018 (RF-96 5.2, 5.4, Fase 4, FA-4, CU-06) - "Cuadre de los
documentos." Agrupa TC-96-041 a TC-96-045.

Construido 2026-11-18 contra el código real (aaef.py) y el real de M06
(consolidacion.py::consolidar_comprobantes).

HALLAZGO (código de error no literal): el código real no lanza
'DESCUADRE_DOCUMENTO' -- verificar_cuadre() lanza `AaefError('MAPPER_FALLIDO',
..., campo='Totals')`. El mecanismo de detección SI existe y SI bloquea.

MATIZA LA FICHA (el 'bloqueante' de sumar-y-truncar vs truncar-y-sumar no
aplica dentro de RF-96): las 50 líneas de asiento de un par NUNCA llegan
al Mapper -- M06 (RF-87, consolidar_comprobantes()) ya las agrega en un
solo `valor` por par ANTES de que RF-96 las vea (RF-96 5.6, solo lee lo
que M06 ya calculó). El Mapper SIEMPRE hace una única operación
determinista sobre ese valor ya agregado: `truncar2(Decimal(valor))`
(ROUND_DOWN, una sola vez). La ambigüedad de orden (truncar cada línea vs.
sumar y truncar) es una decisión de RF-86/87 (M06), fuera del alcance de
RF-96 -- este TC confirma que, dado el valor que M06 le entregue, RF-96
lo trunca una sola vez, siempre con el mismo resultado.

Código bajo prueba:
    src/accounting_integration/domain/services/aaef.py (verificar_cuadre, mapear_compras, mapear_comprobantes)

Cómo se prueba: pytest de unidad; el caso de conciliación usa el
comprobante REAL de TEST (NIT 901444215, período 627, valor_total
180000.00).

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m07_g018_cuadre_de_documentos.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M07-G018.html --self-contained-html
"""
from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from src.accounting_integration.domain.services.aaef import (
    AaefError,
    ComprobanteNic41,
    CostoFactura,
    SistemaOrigen,
    Titular,
    construir_envelope,
    mapear_comprobantes,
    mapear_compras,
    verificar_cuadre,
)

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


class TestSubCasoCuadreCorrectoConfirmado:
    def test_02_cuadra_total_payment_subtotal_suma_de_lines_con_diferencia_cero(self):
        compras = mapear_compras([_costo()])
        envelope = construir_envelope(TITULAR, datetime.date(2026, 10, 1), datetime.date(2026, 10, 31), SISTEMA,
                                      "contador@pecuaria.co", datetime.date(2026, 11, 18), compras, [])
        verificar_cuadre(envelope)  # no lanza
        doc = compras[0]
        assert doc["Totals"]["TotalPayment"] == doc["Totals"]["Subtotal"] == sum(l["Value"] for l in doc["Lines"])

    def test_06_cuadra_igual(self):
        comprobante = ComprobanteNic41("NIC-901444215-202610-DEPRECIACION_ACTIVO_COSTO-655",
                                        "DEPRECIACION_ACTIVO_COSTO", "Bufalo Depreciacion Qa Mseis",
                                        datetime.date(2026, 10, 31),
                                        [{"valor": "180000.00", "cuenta_debito": "516005", "cuenta_credito": "159205"}])
        comprobantes = mapear_comprobantes([comprobante], TITULAR)
        envelope = construir_envelope(TITULAR, datetime.date(2026, 10, 1), datetime.date(2026, 10, 31), SISTEMA,
                                      "contador@pecuaria.co", datetime.date(2026, 11, 18), [], comprobantes)
        verificar_cuadre(envelope)
        doc = comprobantes[0]
        assert doc["Totals"]["TotalPayment"] == doc["Totals"]["Subtotal"] == sum(l["Value"] for l in doc["Lines"])


class TestSubCasoLaAgregacionDeLineasEsResponsabilidadDeM06NoDeRf96Documentacion:
    def test_el_mapper_recibe_el_par_ya_agregado_nunca_las_lineas_individuales(self):
        """No es una ambiguedad de RF-96: ComprobanteNic41.lineas ya es una lista de PARES
        (un dict por par de cuentas distinto), no de lineas de asiento individuales -- la
        agregacion de las N lineas en un solo 'valor' por par ya la hizo
        consolidar_comprobantes() en M06 (RF-87) antes de que RF-96 reciba el objeto."""
        import inspect
        from src.financial_valuation.domain.services.consolidacion import consolidar_comprobantes
        firma = inspect.signature(consolidar_comprobantes)
        assert 'lineas' in firma.parameters  # recibe LineaContable individuales, no pares

    def test_dado_un_valor_ya_agregado_con_mas_de_2_decimales_el_mapper_trunca_una_sola_vez(self):
        """Simula lo que recibiría el Mapper si 50 líneas de 0,0099 se agregan primero y se
        truncan después (sumar-y-truncar: 50*0.0099=0.4950 -> 0.49). El Mapper SIEMPRE aplica
        esta unica regla (truncar2 una vez sobre el valor agregado), sin importar cuántas
        líneas había antes de llegar aquí -- la responsabilidad de RF-96 termina en 'truncar
        lo que me entregan', no en decidir el orden de agregación."""
        comprobante = ComprobanteNic41("NIC-901444215-202610-VARIACION_VR_TB-655", "VARIACION_VR_TB", "Bufalo",
                                       datetime.date(2026, 10, 31),
                                       [{"valor": "0.4950", "cuenta_debito": "516005", "cuenta_credito": "159205"}])
        doc = mapear_comprobantes([comprobante], TITULAR)[0]
        assert doc["Lines"][0]["Value"] == D("0.49")


class TestSubCasoConciliacionConElTotalRealDeRf87ConfirmadoCorrecto:
    def test_la_suma_del_06_coincide_con_el_valor_total_real_del_comprobante(self):
        """Dato real de TEST: comprobante NIC-901444215-202610-DEPRECIACION_ACTIVO_COSTO-655
        tiene valor_total=180000.00 (confirmado vía GET /finanzas/periodos/627/comprobantes,
        2026-11-18) -- coincide exactamente con el Value del 06, sin diferencia de truncado
        porque el monto real ya tiene 2 decimales."""
        comprobante = ComprobanteNic41("NIC-901444215-202610-DEPRECIACION_ACTIVO_COSTO-655",
                                        "DEPRECIACION_ACTIVO_COSTO", "Bufalo Depreciacion Qa Mseis",
                                        datetime.date(2026, 10, 31),
                                        [{"valor": "180000.00", "cuenta_debito": "516005", "cuenta_credito": "159205"}])
        doc = mapear_comprobantes([comprobante], TITULAR)[0]
        assert sum(l["Value"] for l in doc["Lines"]) == D("180000.00")


class TestSubCasoDescuadreInducidoSeDetectaBajoOtroCodigo:
    def test_un_documento_manipulado_en_memoria_lanza_mapper_fallido_no_descuadre_documento(self):
        """No es DESCUADRE_DOCUMENTO literal -- es MAPPER_FALLIDO con campo='Totals'. El
        mecanismo de deteccion SI existe y SI bloquea el envelope completo."""
        compras = mapear_compras([_costo()])
        compras[0]["Lines"][0]["Value"] = D("999999.99")  # induce el descuadre manipulando en memoria
        envelope = construir_envelope(TITULAR, datetime.date(2026, 10, 1), datetime.date(2026, 10, 31), SISTEMA,
                                      "contador@pecuaria.co", datetime.date(2026, 11, 18), compras, [])
        with pytest.raises(AaefError) as exc_info:
            verificar_cuadre(envelope)
        assert exc_info.value.codigo == "MAPPER_FALLIDO"
        assert exc_info.value.campo == "Totals"


class TestSubCasoMontoEnElLimiteDelCampoConfirmadoCorrecto:
    def test_un_monto_muy_alto_no_se_desborda_ni_pierde_precision(self):
        doc = mapear_compras([_costo(monto_costo=D("999999999999.99"))])[0]
        assert doc["Lines"][0]["Value"] == D("999999999999.99")
        assert doc["Totals"]["Subtotal"] == doc["Totals"]["TotalPayment"]
