# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-96/RF-97: pruebas del núcleo AAEF (sin BD) |
# | 2026-11-14 | Arekkazu | M07 RF-97: el ExchangeId cumple el patrón de SIGCON |
# | 2026-11-19 | Leandro | INC-M07-378-G61 RF-AE02: verificar importes mínimos y truncamiento de los tipos 02 y 06. |
"""Pruebas del núcleo AAEF: rango, Mappers, envelope, hash y esquema de AgroFusion."""
import json
import re
from dataclasses import replace
from datetime import date
from decimal import Decimal as D

import pytest

from src.accounting_integration.domain.services.aaef import (
    AaefError,
    ComprobanteNic41,
    CostoFactura,
    Periodo,
    SistemaOrigen,
    Titular,
    construir_envelope,
    controlar_tamano,
    hash_contenido,
    mapear_comprobantes,
    mapear_compras,
    serializar,
    validar_rango,
    verificar_cuadre,
)
from src.accounting_integration.domain.services.esquema_agrofusion import AccountingConsultResponse

TITULAR = Titular("900123456", "Hacienda La Esperanza SAS")
SISTEMA = SistemaOrigen("SGPMP", "SIGAB", "TEST")
SEPT = Periodo(date(2026, 9, 1), date(2026, 9, 30), "CERRADO")
OCT = Periodo(date(2026, 10, 1), date(2026, 10, 31), "CERRADO")
NOV = Periodo(date(2026, 11, 1), date(2026, 11, 30), "ABIERTO")


def _costo(i, monto, activo="BOV-001", prefijo="FE", numero="88231", cuenta="51350501"):
    return CostoFactura(i, "800555111", "Agroinsumos del Huila SAS", prefijo, numero, date(2026, 10, 4),
                        date(2026, 11, 3), "ALIMENTO", D(monto), cuenta, activo)


def _comprobante():
    return ComprobanteNic41("NIC-900123456-202610-VARIACION_VR_TB-1", "VARIACION_VR_TB", "Bovinos", date(2026, 10, 31),
                            [{"cuenta_debito": "15120501", "cuenta_credito": "42950501", "valor": "1200000.555"},
                             {"cuenta_debito": "53150501", "cuenta_credito": "15120501", "valor": "300000"}])


def test_rango_alineado_devuelve_los_periodos_cerrados():
    assert validar_rango([OCT, SEPT, NOV], date(2026, 9, 1), date(2026, 10, 31)) == [SEPT, OCT]


def test_rango_no_alineado_sugiere_el_rango_valido_mas_cercano():
    with pytest.raises(AaefError) as e:
        validar_rango([SEPT, OCT, NOV], date(2026, 10, 5), date(2026, 10, 31))
    assert e.value.codigo == "RANGO_NO_ALINEADO"
    assert "2026-10-01 a 2026-10-31" in e.value.mensaje


def test_periodo_abierto_en_el_rango_se_rechaza_con_su_mes():
    with pytest.raises(AaefError) as e:
        validar_rango([SEPT, OCT, NOV], date(2026, 10, 1), date(2026, 11, 30))
    assert e.value.codigo == "PERIODO_NO_CERRADO" and "2026-11" in e.value.mensaje


def test_factura_repartida_es_un_solo_02_con_una_linea_por_activo():
    docs = mapear_compras([_costo(12, "300000.009", "BOV-002"), _costo(11, "700000", "BOV-001")])
    assert len(docs) == 1
    doc = docs[0]
    assert doc["Header"]["DocumentId"] == "COS-11-20261004"
    assert (doc["Header"]["Prefix"], doc["Header"]["Serial"], doc["Header"]["Type"]["Code"]) == ("FE", "88231", "02")
    assert doc["ThirdParty"]["NIT"] == "800555111"
    assert [ln["Value"] for ln in doc["Lines"]] == [D("700000.00"), D("300000.00")]  # truncado, sin redondeo
    assert all(len(ln["accounting_account"]) == 1 for ln in doc["Lines"])
    assert doc["Totals"]["Subtotal"] == doc["Totals"]["TotalPayment"] == doc["Totals"]["OutstandingBalance"] == D("1000000.00")


def test_factura_sin_prefijo_sale_con_prefijo_vacio():
    assert mapear_compras([_costo(5, "10", prefijo=None)])[0]["Header"]["Prefix"] == ""


@pytest.mark.parametrize("monto", ["0", "0.0049", "-0.01"])
def test_compras_rechaza_linea_no_positiva_tras_truncar(monto):
    # La otra línea es válida y deja la factura con un total positivo.
    with pytest.raises(AaefError) as error:
        mapear_compras([_costo(11, "5"), _costo(12, monto)])
    assert (error.value.codigo, error.value.campo, error.value.detalle["mapper"]) == (
        "MAPPER_FALLIDO", "Value", "COMPRAS",
    )


@pytest.mark.parametrize(("monto", "esperado"), [("0.01", "0.01"), ("100.999", "100.99")])
def test_compras_conserva_importes_positivos_truncados(monto, esperado):
    [factura] = mapear_compras([_costo(5, monto)])
    [linea] = factura["Lines"]
    assert linea["Value"] == linea["UnitPrice"] == D(esperado)
    assert factura["Totals"]["Subtotal"] == factura["Totals"]["TotalPayment"] == D(esperado)


def test_costo_sin_cuenta_detiene_la_transformacion():
    with pytest.raises(AaefError) as e:
        mapear_compras([_costo(5, "10", cuenta=None)])
    assert e.value.codigo == "MAPPER_FALLIDO" and e.value.campo == "accounting_account"


def test_comprobante_06_una_linea_por_par_de_cuentas_con_dos_cuentas():
    doc = mapear_comprobantes([_comprobante()], TITULAR)[0]
    assert doc["Header"]["Type"]["Code"] == "06" and doc["Header"]["Serial"] == "202610-VARIACION_VR_TB-1"
    assert doc["ThirdParty"] == {"NIT": "900123456", "Name": "Hacienda La Esperanza SAS"}
    assert [ln["accounting_account"] for ln in doc["Lines"]] == [["15120501", "42950501"], ["53150501", "15120501"]]
    assert doc["Totals"]["Subtotal"] == D("1500000.55") and doc["Totals"]["OutstandingBalance"] == 0


def test_comprobante_06_conserva_el_minimo_positivo():
    original = _comprobante()
    linea = original.lineas[0]
    with pytest.raises(AaefError) as error:
        mapear_comprobantes([replace(original, lineas=[{**linea, "valor": "0.0049"}])], TITULAR)
    assert (error.value.codigo, error.value.campo) == ("MAPPER_FALLIDO", "Value")
    [comprobante] = mapear_comprobantes([replace(original, lineas=[{**linea, "valor": "0.01"}])], TITULAR)
    assert comprobante["Lines"][0]["Value"] == D("0.01")


def _envelope(compras, comprobantes=()):
    return construir_envelope(TITULAR, date(2026, 10, 1), date(2026, 10, 31), SISTEMA, "contador@finca.co",
                              date(2026, 11, 6), mapear_compras(compras), mapear_comprobantes(comprobantes, TITULAR))


def test_envelope_cumple_el_esquema_de_agrofusion_y_cuadra():
    env = _envelope([_costo(11, "700000"), _costo(20, "50", numero="9")], [_comprobante()])
    verificar_cuadre(env)
    validado = AccountingConsultResponse.model_validate(json.loads(serializar(env)))
    assert validado.metadata.StandardVersion == "1.0" and validado.metadata.SourceSystem.SystemNIT == "900123456"
    assert validado.summary.TotalInvoices == validado.summary.TotalDocuments == 3
    assert validado.summary.TotalTransactions == 0 and validado.transactions == []
    assert [d.Header.DocumentId for d in validado.invoices] == sorted(d.Header.DocumentId for d in validado.invoices)
    assert {d.Header.Type.Code for d in validado.invoices} <= {"02", "06"}


def test_exchange_id_cumple_sigcon_antes_y_despues_del_cambio_de_agrofusion():
    patron_sigcon = r"AF-(?:[A-Z]+-)?\d{4}-\d{2}-\d{4,}"  # AaefMetadataDTO de SIGCON
    exchange_id = _envelope([])["metadata"]["ExchangeId"]
    *inicio, _ = exchange_id.split("-")  # AgroFusion reemplaza el último segmento por 7 dígitos
    for valor in (exchange_id, "-".join([*inicio, "0001234"])):
        assert re.fullmatch(patron_sigcon, valor), valor
    assert exchange_id.startswith("AF-SIGAB-2026-10-") and len(exchange_id) <= 64


def test_hash_de_contenido_es_estable_aunque_cambien_metadatos():
    a, b = _envelope([_costo(11, "700000")]), _envelope([_costo(11, "700000")])
    assert hash_contenido(a["invoices"]) == hash_contenido(b["invoices"])
    assert hash_contenido(a["invoices"]) != hash_contenido(_envelope([_costo(11, "700001")])["invoices"])


def test_rango_sin_datos_da_envelope_valido_vacio():
    env = _envelope([])
    AccountingConsultResponse.model_validate(json.loads(serializar(env)))
    assert env["invoices"] == [] and env["summary"]["TotalGrossAmount"] == 0


def test_tamano_excedido():
    with pytest.raises(AaefError) as e:
        controlar_tamano(b"x" * 11, 10)
    assert e.value.codigo == "TAMANO_EXCEDIDO"
