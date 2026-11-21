# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-18 | usuario-git | TC-M07-G060 (RF-AE02): pytest de G2.6 (valores fijos) y G2.7 (controles que bloquean EN_REVISION). |
"""TC-M07-G060 — subcasos de RF-AE02 que se verifican contra el codigo (sin BD, sin red).

    G2.6  Valores fijos del Anexo: StandardVersion "1.0", fechas AAAA-MM-DD, transactions [], Status ACTIVE.
    G2.7  Forzar cada falla (estructura, cobertura, cuadre de documento, cuadre de summary, cuentas, fecha):
          cada una debe bloquear el paso a EN_REVISION (FA-2) y dejar el Anexo en BORRADOR.

Se ejecuta desde la raiz de sgpmp-backend (lo lanza ejecutar_tc_m07_g60.py):

    python -m pytest tests/Test_Testing/Test_Modulo7/RF-AE01/TC-M07-G060/test_tc_m07_g60_validacion_anexo.py
"""
import json
import re
from datetime import date
from decimal import Decimal as D

import pytest

from src.accounting_integration.application.use_cases.contratos import gestionar_anexos_use_case as uc
from src.accounting_integration.domain.entities.contrato import AnexoMapeo
from src.accounting_integration.domain.services.aaef import (
    ComprobanteNic41,
    CostoFactura,
    SistemaOrigen,
    Titular,
    construir_envelope,
    mapear_comprobantes,
    mapear_compras,
    serializar,
)
from src.shared.errors import BusinessRuleError

JUSTIFICACION = "TC-M07-G060: aprobacion interna del mapeo para la prueba de QA."

FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TITULAR = Titular("901444215", "QA-M07 Titular Gateway S.A.S.")


def _envelope():
    compra = CostoFactura(11, "800555111", "Agroinsumos del Huila SAS", "CP", "1187", date(2026, 10, 4), date(2026, 11, 3),
                          "ALIMENTO", D("380000"), "51350501", "BOV-001")
    comprobante = ComprobanteNic41("NIC-901444215-202610-VARIACION_VR_TB-1", "VARIACION_VR_TB", "Bovinos", date(2026, 10, 31),
                                   [{"cuenta_debito": "15120501", "cuenta_credito": "42950501", "valor": "1200000.55"}])
    return construir_envelope(TITULAR, date(2026, 10, 1), date(2026, 10, 31), SistemaOrigen("SGPMP", "SIGAB", "TEST"),
                              "contador@gmail.com", date(2026, 11, 18), mapear_compras([compra]),
                              mapear_comprobantes([comprobante], TITULAR))


# --- G2.6 ---------------------------------------------------------------------------------------

def test_g2_6_valores_fijos_del_anexo():
    sal = json.loads(serializar(_envelope()))
    assert sal["metadata"]["StandardVersion"] == "1.0"
    assert sal["transactions"] == []
    assert sal["summary"]["TotalTransactions"] == 0
    fechas = [sal["metadata"]["GeneratedAt"], sal["metadata"]["RequestedPeriod"]["From"], sal["metadata"]["RequestedPeriod"]["To"]]
    for doc in sal["invoices"]:
        fechas += [doc["Header"][c] for c in ("IssueDate", "DueDate", "UpdatedAt")]
        assert doc["Header"]["Status"] == "ACTIVE", doc["Header"]["DocumentId"]
    assert {d["Header"]["Type"]["Code"] for d in sal["invoices"]} == {"02", "06"}  # se revisaron ambos tipos
    malas = [f for f in fechas if not FECHA.match(str(f))]
    assert not malas, f"Fechas fuera de AAAA-MM-DD: {malas}"


# --- G2.7 ---------------------------------------------------------------------------------------

def _estructura(e):  # falta un campo requerido del esquema de AgroFusion
    del e["metadata"]["SourceSystem"]["SystemNIT"]


def _cobertura(e):  # un documento sin una seccion completa
    del e["invoices"][0]["Lines"]


def _cuadre_documento(e):
    e["invoices"][0]["Totals"]["TotalPayment"] += D("1.00")


def _cuadre_summary(e):
    e["summary"]["TotalNet"] += D("1.00")


def _cuentas(e):
    e["invoices"][0]["Lines"][0]["accounting_account"] = []


def _fecha(e):
    e["invoices"][0]["Header"]["IssueDate"] = "04/10/2026"


FALLAS = {"estructura": _estructura, "cobertura": _cobertura, "cuadre_documento": _cuadre_documento,
          "cuadre_summary": _cuadre_summary, "cuentas": _cuentas, "formato_fecha": _fecha}


class _Contratos:
    def __init__(self):
        self.anexo = AnexoMapeo(1, "ANEXO-AAEF-QA", "9.9", "docs/qa.md", "0" * 64)
        self.guardados = 0

    def obtener_anexo(self, _id):
        return self.anexo

    def guardar_anexo(self, anexo):
        self.guardados += 1
        return anexo


class _Auditoria:
    def __init__(self):
        self.eventos = []

    def registrar(self, evento):
        self.eventos.append(evento.tipo_evento)


class _Db:
    commits = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


def test_g2_7_linea_base_sin_fallas_pasa_a_revision():
    contratos, auditoria = _Contratos(), _Auditoria()
    uc.GestionarAnexosUseCase(contratos, auditoria, _Db()).enviar_a_revision(1, 1, JUSTIFICACION)
    assert contratos.anexo.estado == "EN_REVISION" and auditoria.eventos == ["ANEXO_EN_REVISION"]


@pytest.mark.parametrize("falla", sorted(FALLAS))
def test_g2_7_cada_falla_bloquea_el_paso_a_en_revision(falla, monkeypatch):
    original = uc.construir_envelope

    def con_falla(*args, **kwargs):
        envelope = original(*args, **kwargs)
        FALLAS[falla](envelope)
        return envelope

    monkeypatch.setattr(uc, "construir_envelope", con_falla)
    contratos, auditoria = _Contratos(), _Auditoria()
    caso = uc.GestionarAnexosUseCase(contratos, auditoria, _Db())
    with pytest.raises(BusinessRuleError) as exc:
        caso.enviar_a_revision(1, 1, JUSTIFICACION)
    assert exc.value.code == "ANEXO_VALIDACION_FALLIDA"
    assert contratos.anexo.estado == "BORRADOR" and contratos.guardados == 0, "el Anexo no debe avanzar"
    assert auditoria.eventos == ["ANEXO_VALIDACION_FALLIDA"]
