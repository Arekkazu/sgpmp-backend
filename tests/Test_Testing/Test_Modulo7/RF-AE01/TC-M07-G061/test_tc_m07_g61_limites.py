# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-19 | usuario-git | TC-M07-G061 (RF-AE01 / RF-AE02): pytest de valores limite G3.1 a G3.6 sobre el nucleo AAEF (sin BD ni red). |
# | 2026-11-19 | usuario-git | TC-M07-G061: G3.5 agrega la comprobacion de 0.0049 (valido en M06, el Mapper lo trunca a 0.00). |
"""TC-M07-G061 — valores limite de la consulta AAEF y del Anexo, verificados contra el codigo (sin BD, sin red).

    G3.1  Rango de un solo dia: alineado (periodo de un dia) valido; no alineado -> RANGO_NO_ALINEADO con rango sugerido.
    G3.2  Rango cerrado sin hechos: envelope valido, invoices [] y summary en 0.
    G3.3  Respuesta de 20 MB exactos pasa y de 20 MB + 1 byte -> TAMANO_EXCEDIDO.
    G3.4  accounting_account con 0, 1, 2 y 3 elementos: solo 1 en el tipo 02 y 2 en el tipo 06.
    G3.5  monto_costo con 0, 0.01 y 100.999 (se trunca a 2 decimales; 0 no genera documento valido).
    G3.6  Value de una linea del tipo 06 con 0, 0.01 y suma del par de cuentas (debe ser > 0).

Se ejecuta desde la raiz de sgpmp-backend (lo lanza ejecutar_tc_m07_g61.py):

    python -m pytest tests/Test_Testing/Test_Modulo7/RF-AE01/TC-M07-G061/test_tc_m07_g61_limites.py
"""
import json
from datetime import date
from decimal import Decimal as D

import pytest

from src.accounting_integration.application.use_cases.contratos import gestionar_anexos_use_case as anexos
from src.accounting_integration.application.use_cases.exportacion.consultar_aaef_use_case import (
    ConsultarAaefUseCase,
    SolicitudAaef,
)
from src.accounting_integration.domain.entities.contrato import VersionContrato
from src.accounting_integration.domain.services.aaef import (
    AaefError,
    ComprobanteNic41,
    CostoFactura,
    Periodo,
    SistemaOrigen,
    Titular,
    construir_envelope,
    controlar_tamano,
    mapear_comprobantes,
    mapear_compras,
    serializar,
    validar_rango,
    verificar_cuadre,
)
from src.accounting_integration.domain.services.esquema_agrofusion import AccountingConsultResponse
from src.accounting_integration.infrastructure import configuracion
from src.shared.errors import BusinessRuleError

LIMITE = 20 * 1024 * 1024
TITULAR = Titular("901444215", "QA-M07 Titular Gateway S.A.S.")
SISTEMA = SistemaOrigen("SGPMP", "SIGAB", "TEST")
OCT = Periodo(date(2026, 10, 1), date(2026, 10, 31), "CERRADO")
SEP = Periodo(date(2026, 9, 1), date(2026, 9, 30), "CERRADO")


def _costo(monto, i=11, cuenta="51350501"):
    return CostoFactura(i, "800555111", "Agroinsumos del Huila SAS", "CP", f"11{i}", date(2026, 10, 4),
                        date(2026, 11, 3), "ALIMENTO", D(str(monto)), cuenta, "BOV-001")


def _comprobante(*valores, debito="15120501", credito="42950501"):
    return ComprobanteNic41("NIC-901444215-202610-VARIACION_VR_TB-1", "VARIACION_VR_TB", "Bovinos", date(2026, 10, 31),
                            [{"cuenta_debito": debito, "cuenta_credito": credito, "valor": str(v)} for v in valores])


def _envelope(compras=(), comprobantes=()):
    return construir_envelope(TITULAR, date(2026, 10, 1), date(2026, 10, 31), SISTEMA, "contador@gmail.com",
                              date(2026, 11, 19), list(compras), list(comprobantes))


# --- G3.1 ---------------------------------------------------------------------------------------

def test_g3_1_dia_alineado_a_un_periodo_de_un_dia_es_valido():
    dia = Periodo(date(2026, 10, 5), date(2026, 10, 5), "CERRADO")
    assert validar_rango([dia], date(2026, 10, 5), date(2026, 10, 5)) == [dia]


@pytest.mark.parametrize("dia", [date(2026, 10, 1), date(2026, 10, 15), date(2026, 10, 31)])
def test_g3_1_dia_suelto_con_periodos_mensuales_no_esta_alineado(dia):
    with pytest.raises(AaefError) as exc:
        validar_rango([SEP, OCT], dia, dia)
    assert exc.value.codigo == "RANGO_NO_ALINEADO"
    assert "2026-10-01 a 2026-10-31" in exc.value.mensaje, "debe sugerir el rango valido"


# --- G3.2 / G3.3: caso de uso con una fuente simulada ---------------------------------------------

class _Fuente:
    def __init__(self, costos=(), comprobantes=()):
        self._costos, self._comprobantes = list(costos), list(comprobantes)

    def titular(self, nit):
        return TITULAR

    def fincas_titular(self, nit):
        return {1}

    def fincas_usuario(self, id_usuario):
        return {1}

    def periodos(self, nit):
        return [SEP, OCT]

    def lineas_sin_trazabilidad(self, nit, desde, hasta):
        return 0

    def costos_factura(self, nit, desde, hasta):
        return self._costos

    def comprobantes(self, nit, desde, hasta):
        return self._comprobantes


class _Contratos:
    def listar_contratos(self):
        return [VersionContrato(1, "3.0", "MAYOR", date(2026, 1, 1), 1, ["COMPRAS", "COMPROBANTE_NIC41"], estado="ACTIVO")]


def _caso(fuente, limite=LIMITE):
    return ConsultarAaefUseCase(fuente, _Contratos(), SISTEMA, limite, lambda: date(2026, 11, 19))


SOLICITUD = SolicitudAaef("901444215", date(2026, 10, 1), date(2026, 10, 31), 1, "contador@gmail.com")


def test_g3_2_rango_cerrado_sin_hechos_da_envelope_vacio_valido():
    r = _caso(_Fuente()).execute(SOLICITUD)
    cuerpo = json.loads(r.cuerpo)
    assert r.documentos == 0 and cuerpo["invoices"] == [] and cuerpo["transactions"] == []
    assert cuerpo["summary"]["TotalInvoices"] == 0 and cuerpo["summary"]["TotalDocuments"] == 0
    assert cuerpo["summary"]["TotalNet"] == 0 and cuerpo["summary"]["TotalGrossAmount"] == 0
    AccountingConsultResponse.model_validate(cuerpo)  # lo que valida AgroFusion


def test_g3_3_limite_configurado_es_20_mb():
    assert configuracion.LIMITE_BYTES == LIMITE


def test_g3_3_controlar_tamano_exacto_pasa_y_un_byte_mas_se_rechaza():
    controlar_tamano(b"x" * LIMITE, LIMITE)
    with pytest.raises(AaefError) as exc:
        controlar_tamano(b"x" * (LIMITE + 1), LIMITE)
    assert exc.value.codigo == "TAMANO_EXCEDIDO"


def test_g3_3_el_caso_de_uso_aplica_el_limite_sobre_el_cuerpo_real():
    fuente = _Fuente(costos=[_costo("380000")], comprobantes=[_comprobante("1200000.55")])
    tamano = len(_caso(fuente).execute(SOLICITUD).cuerpo)
    assert len(_caso(fuente, limite=tamano).execute(SOLICITUD).cuerpo) == tamano  # exacto: pasa
    with pytest.raises(BusinessRuleError) as exc:  # un byte menos de limite = cuerpo + 1 byte
        _caso(fuente, limite=tamano - 1).execute(SOLICITUD)
    assert exc.value.code == "TAMANO_EXCEDIDO" and exc.value.status_code == 422


# --- G3.4 ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("tipo,cantidad", [(t, n) for t in ("02", "06") for n in (0, 1, 2, 3)])
def test_g3_4_cuentas_por_linea_solo_valido_1_en_02_y_2_en_06(tipo, cantidad, monkeypatch):
    original = anexos.construir_envelope

    def con_cuentas(*args, **kwargs):
        envelope = original(*args, **kwargs)
        for doc in envelope["invoices"]:
            if doc["Header"]["Type"]["Code"] == tipo:
                for linea in doc["Lines"]:
                    linea["accounting_account"] = [str(10000000 + i) for i in range(cantidad)]
        return envelope

    monkeypatch.setattr(anexos, "construir_envelope", con_cuentas)
    valida = cantidad == (1 if tipo == "02" else 2)
    assert ("cuentas" in anexos.validar_con_datos_de_prueba()) is (not valida), \
        f"tipo {tipo} con {cantidad} cuenta(s): {'debia ser valido' if valida else 'debia rechazarse'}"


def test_g3_4_mapper_rechaza_una_cuenta_vacia_o_no_numerica():
    for cuenta in (None, "", "51A50501"):
        with pytest.raises(AaefError) as exc:
            mapear_compras([_costo("1000", cuenta=cuenta)])
        assert exc.value.codigo == "MAPPER_FALLIDO"
    with pytest.raises(AaefError):
        mapear_comprobantes([_comprobante("1000", credito=None)], TITULAR)


# --- G3.5 ---------------------------------------------------------------------------------------

def test_g3_5_monto_0_01_es_valido():
    (doc,) = mapear_compras([_costo("0.01")])
    assert doc["Lines"][0]["Value"] == D("0.01") and doc["Totals"]["TotalPayment"] == D("0.01")
    AccountingConsultResponse.model_validate(json.loads(serializar(_envelope(compras=[doc]))))


def test_g3_5_monto_100_999_se_trunca_a_2_decimales():
    (doc,) = mapear_compras([_costo("100.999")])
    assert doc["Lines"][0]["Value"] == D("100.99") and doc["Totals"]["Subtotal"] == D("100.99")


def test_g3_5_monto_0_no_genera_un_documento_valido():
    """Esperado: el pipeline (Mapper, cuadre o esquema de AgroFusion) rechaza un documento con monto 0."""
    try:
        docs = mapear_compras([_costo("0")])
        envelope = _envelope(compras=docs)
        verificar_cuadre(envelope)
        AccountingConsultResponse.model_validate(json.loads(serializar(envelope)))
    except Exception:  # noqa: BLE001 — cualquier rechazo del pipeline es lo esperado
        return
    pytest.fail("un costo con monto 0 produjo un documento 02 que supera Mapper, cuadre y esquema de AgroFusion")


def test_g3_5_monto_menor_a_un_centavo_no_produce_una_linea_en_cero():
    """0.0049 si entra por la API de costos (CostoDTO exige monto_costo > 0 con hasta 4 decimales) pero el Mapper
    lo trunca a 0.00. Esperado (misma regla que el 0): el pipeline no deja pasar un documento 02 con valor 0.00."""
    docs = mapear_compras([_costo("0.0049")])
    valor = docs[0]["Lines"][0]["Value"] if docs else None
    try:
        envelope = _envelope(compras=docs)
        verificar_cuadre(envelope)
        AccountingConsultResponse.model_validate(json.loads(serializar(envelope)))
    except Exception:  # noqa: BLE001 — cualquier rechazo del pipeline es lo esperado
        return
    pytest.fail(f"un costo de 0.0049 (valido en M06) produjo un documento 02 con Value={valor} que supera "
                "Mapper, cuadre y esquema de AgroFusion")


# --- G3.6 ---------------------------------------------------------------------------------------

def test_g3_6_valor_de_linea_0_se_rechaza():
    with pytest.raises(AaefError) as exc:
        mapear_comprobantes([_comprobante("0")], TITULAR)
    assert exc.value.codigo == "MAPPER_FALLIDO" and exc.value.campo == "Value"


def test_g3_6_valor_de_linea_menor_a_un_centavo_se_rechaza_porque_se_trunca_a_0():
    with pytest.raises(AaefError) as exc:
        mapear_comprobantes([_comprobante("0.009")], TITULAR)
    assert exc.value.codigo == "MAPPER_FALLIDO"


def test_g3_6_valor_de_linea_0_01_se_acepta_y_la_suma_del_par_cuadra():
    (solo,) = mapear_comprobantes([_comprobante("0.01")], TITULAR)
    assert solo["Lines"][0]["Value"] == D("0.01") and solo["Totals"]["Subtotal"] == D("0.01")
    (par,) = mapear_comprobantes([_comprobante("0.01", "0.01")], TITULAR)
    assert par["Totals"]["Subtotal"] == D("0.02") == par["Totals"]["TotalPayment"]
    verificar_cuadre(_envelope(comprobantes=[par]))
