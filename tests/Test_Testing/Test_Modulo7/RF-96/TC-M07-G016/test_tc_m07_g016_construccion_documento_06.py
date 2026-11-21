"""
TC-M07-G016 (RF-96 5.4, CA-4, CU-04) - "Construcción del documento 06 por
el Mapper de Comprobante NIC 41." Agrupa TC-96-026 a TC-96-034.

Construido 2026-11-18 contra el código real (mapear_comprobantes(),
aaef.py). Dato real confirmado en vivo en TEST (NIT 901444215, período
627): comprobante NIC-901444215-202610-DEPRECIACION_ACTIVO_COSTO-655,
especie "Bufalo Depreciacion Qa Mseis", 1 línea (par único), valor
180000.00. El DBA no pudo armar un comprobante con 2 pares de cuentas
(requiere activos a valor razonable con movimiento de precio real) -- el
caso de CA-4 con 2 pares se construye como fixture sintética a partir de
la MISMA estructura real (mismo codigo/especie, un segundo par agregado),
no inventada desde cero.

ARREGLADO 2026-11-19/20 (TC-M07-G016, Arekkazu, PR #1190/#1202, merge de
origin/dev 2026-11-20): el hallazgo original de este TC ("el código real
rechaza un neto negativo igual que cero, sin invertir débito/crédito") ya
se corrigió. Ahora `valor < 0` invierte `cuenta_debito`/`cuenta_credito` y
entrega `Value` siempre positivo (CA-4: "el sentido lo dan las cuentas");
solo `valor == 0` (ya no `<= 0`) sigue siendo `MAPPER_FALLIDO`.

Código bajo prueba:
    src/accounting_integration/domain/services/aaef.py (mapear_comprobantes)

Cómo se prueba: pytest de unidad invocando mapear_comprobantes()
directamente con fixtures basadas en datos reales de TEST.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m07_g016_construccion_documento_06.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M07-G016.html --self-contained-html
"""
from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from src.accounting_integration.domain.services.aaef import AaefError, ComprobanteNic41, Titular, mapear_comprobantes

D = Decimal
TITULAR = Titular(nit="901444215", razon_social="Hacienda Qa Mseis S.A.S.")


def _comprobante_real_un_par() -> ComprobanteNic41:
    """Réplica exacta del comprobante real de TEST (período 627)."""
    return ComprobanteNic41(
        codigo="NIC-901444215-202610-DEPRECIACION_ACTIVO_COSTO-655",
        tipo_hecho="DEPRECIACION_ACTIVO_COSTO", especie="Bufalo Depreciacion Qa Mseis",
        fecha_comprobante=datetime.date(2026, 10, 31),
        lineas=[{"valor": "180000.00", "cuenta_debito": "516005", "cuenta_credito": "159205"}],
    )


def _comprobante_sintetico_dos_pares() -> ComprobanteNic41:
    """CA-4 literal: mismo codigo/especie reales, con un segundo par agregado para cubrir
    el caso de 2 pares que el DBA no pudo generar con datos reales todavía."""
    c = _comprobante_real_un_par()
    return ComprobanteNic41(c.codigo, c.tipo_hecho, c.especie, c.fecha_comprobante,
                            c.lineas + [{"valor": "25000.00", "cuenta_debito": "150405", "cuenta_credito": "280505"}])


class TestSubCasoCA1ConDatosRealesDeTestUnParConfirmadoCorrecto:
    def test_el_comprobante_real_produce_un_documento_con_una_linea(self):
        doc = mapear_comprobantes([_comprobante_real_un_par()], TITULAR)[0]
        assert len(doc["Lines"]) == 1
        assert doc["Lines"][0]["accounting_account"] == ["516005", "159205"]
        assert doc["Lines"][0]["Value"] == D("180000.00")

    def test_documentid_prefix_y_serial_salen_del_codigo_real(self):
        doc = mapear_comprobantes([_comprobante_real_un_par()], TITULAR)[0]
        assert doc["Header"]["DocumentId"] == "NIC-901444215-202610-DEPRECIACION_ACTIVO_COSTO-655"
        assert doc["Header"]["Prefix"] == "NIC"
        assert doc["Header"]["Serial"] == "202610-DEPRECIACION_ACTIVO_COSTO-655"

    def test_fechas_issue_due_updated_son_el_ultimo_dia_del_periodo(self):
        doc = mapear_comprobantes([_comprobante_real_un_par()], TITULAR)[0]
        assert doc["Header"]["IssueDate"] == doc["Header"]["DueDate"] == doc["Header"]["UpdatedAt"] == "2026-10-31"

    def test_thirdparty_es_el_propio_titular(self):
        doc = mapear_comprobantes([_comprobante_real_un_par()], TITULAR)[0]
        assert doc["ThirdParty"] == {"NIT": "901444215", "Name": "Hacienda Qa Mseis S.A.S."}


class TestSubCasoCA4LiteralConDosParesSobreDatosRealesConfirmadoCorrecto:
    def test_dos_pares_producen_dos_lineas_cada_una_con_dos_elementos(self):
        doc = mapear_comprobantes([_comprobante_sintetico_dos_pares()], TITULAR)[0]
        assert len(doc["Lines"]) == 2
        for linea in doc["Lines"]:
            assert len(linea["accounting_account"]) == 2

    def test_el_orden_de_accounting_account_es_siempre_debito_credito(self):
        doc = mapear_comprobantes([_comprobante_sintetico_dos_pares()], TITULAR)[0]
        assert doc["Lines"][0]["accounting_account"] == ["516005", "159205"]
        assert doc["Lines"][1]["accounting_account"] == ["150405", "280505"]

    def test_outstanding_balance_es_siempre_cero(self):
        doc = mapear_comprobantes([_comprobante_sintetico_dos_pares()], TITULAR)[0]
        assert doc["Totals"]["OutstandingBalance"] == D(0)


class TestSubCasoUnDocumentoPorTitularTipoHechoYEspecie:
    def test_cuatro_comprobantes_distintos_producen_cuatro_documentos(self):
        """DocumentId = comprobante.codigo tal cual lo entrega M06/RF-87 (el Mapper NO lo
        reconstruye desde tipo_hecho/especie, solo lo transfiere) -- cada combinación real
        de titular×tipo_hecho×especie viene con su propio código ya armado por M06."""
        base = _comprobante_real_un_par()
        prefijo = "NIC-901444215-202610-"
        variantes = [
            ComprobanteNic41(prefijo + "DEPRECIACION_ACTIVO_COSTO-655", "DEPRECIACION_ACTIVO_COSTO", "Bufalo",
                             base.fecha_comprobante, base.lineas),
            ComprobanteNic41(prefijo + "VARIACION_VR_TB-655", "VARIACION_VR_TB", "Bufalo",
                             base.fecha_comprobante, base.lineas),
            ComprobanteNic41(prefijo + "DEPRECIACION_ACTIVO_COSTO-660", "DEPRECIACION_ACTIVO_COSTO", "Bovino",
                             base.fecha_comprobante, base.lineas),
            ComprobanteNic41(prefijo + "VARIACION_VR_TB-660", "VARIACION_VR_TB", "Bovino",
                             base.fecha_comprobante, base.lineas),
        ]
        documentos = mapear_comprobantes(variantes, TITULAR)
        assert len(documentos) == 4
        assert len({d["Header"]["DocumentId"] for d in documentos}) == 4


class TestSubCasoNetoCeroSeRechazaYNegativoSeInvierteArreglado:
    def test_neto_cero_se_rechaza_confirmado_correcto(self):
        """El rechazo de valor == 0 se mantuvo tal cual (el cambio del fix fue en <= 0 -> == 0)."""
        comprobante = _comprobante_real_un_par()
        comprobante.lineas[0]["valor"] = "0.00"
        with pytest.raises(AaefError) as exc_info:
            mapear_comprobantes([comprobante], TITULAR)
        assert exc_info.value.codigo == "MAPPER_FALLIDO"

    def test_neto_negativo_ahora_invierte_debito_y_credito_arreglado(self):
        """ARREGLADO (2026-11-19, TC-M07-G016/Arekkazu, PR #1190/#1202): un par con neto
        negativo (ej. una pérdida de valor razonable) ya NO se rechaza -- el Mapper invierte
        cuenta_debito/cuenta_credito y entrega Value positivo, exactamente lo que pide CA-4
        ('el sentido lo dan las cuentas')."""
        comprobante = _comprobante_real_un_par()
        comprobante.lineas[0]["valor"] = "-50000.00"  # ej. perdida de valor razonable
        doc = mapear_comprobantes([comprobante], TITULAR)[0]
        linea = doc["Lines"][0]
        assert linea["Value"] == D("50000.00")  # siempre positivo
        assert linea["accounting_account"] == ["159205", "516005"]  # invertido vs. el caso positivo (ver test de arriba)
