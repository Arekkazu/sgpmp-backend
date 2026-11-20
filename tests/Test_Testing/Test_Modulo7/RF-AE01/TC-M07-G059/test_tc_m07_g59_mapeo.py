# | Fecha      | Nombre     | Que se hizo |
# |------------|------------|-------------|
# | 2026-11-18 | HulkyZeus  | TC-M07-G059 (RF-AE01 / RF-AE02): pytest de los subcasos G1.5 a G1.8 sobre el nucleo AAEF (sin BD ni red). |
"""TC-M07-G059 — subcasos de RF-AE02 que se verifican contra el codigo (sin BD, sin red).

    G1.5  Cada campo del esquema de AgroFusion esta mapeado y aparece en el Anexo.
    G1.6  Documento 02 desde COMPRA_PROVEEDOR y desde SERVICIO_TERCERO.
    G1.7  Documento 06 desde el comprobante NIC 41.
    G1.8  El hash SHA-256 del Anexo es reproducible.

Se ejecuta desde la raiz de sgpmp-backend (lo lanza ejecutar_tc_m07_g59.py):

    python -m pytest tests/Test_Testing/Test_Modulo7/RF-AE01/TC-M07-G059/test_tc_m07_g59_mapeo.py
"""
import hashlib
import json
import re
from datetime import date
from decimal import Decimal as D
from pathlib import Path

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
from src.accounting_integration.domain.services.esquema_agrofusion import AccountingConsultResponse

RAIZ = Path(__file__).resolve().parents[5]  # sgpmp-backend
ANEXO = RAIZ / "docs" / "integracion" / "anexo_aaef_v3.0.md"

TITULAR = Titular("901444215", "QA-M07 Titular Gateway S.A.S.")
SISTEMA = SistemaOrigen("SGPMP", "SIGAB", "TEST")
DESDE, HASTA = date(2026, 10, 1), date(2026, 10, 31)


def _costo(i, subtipo, monto, prefijo="CP", numero="1187"):
    return CostoFactura(i, "800555111", "Agroinsumos del Huila SAS", prefijo, numero, date(2026, 10, 4),
                        date(2026, 11, 3), subtipo, D(monto), "51350501", "BOV-001")


def _comprobante():
    return ComprobanteNic41("NIC-901444215-202610-VARIACION_VR_TB-1", "VARIACION_VR_TB", "Bovinos", date(2026, 10, 31),
                            [{"cuenta_debito": "15120501", "cuenta_credito": "42950501", "valor": "1200000.55"},
                             {"cuenta_debito": "53150501", "cuenta_credito": "15120501", "valor": "300000"}])


def _envelope():
    compras = mapear_compras([_costo(11, "ALIMENTO", "380000"), _costo(12, "VETERINARIO", "210000", "VP", "342")])
    comprobantes = mapear_comprobantes([_comprobante()], TITULAR)
    return construir_envelope(TITULAR, DESDE, HASTA, SISTEMA, "contador@gmail.com", date(2026, 11, 18), compras, comprobantes)


# --- G1.5 ---------------------------------------------------------------------------------------

def _campos_esquema():
    """(ruta, requerido) de cada campo del esquema JSON de AgroFusion, incluidos los anidados."""
    esquema = AccountingConsultResponse.model_json_schema()
    defs = esquema.get("$defs", {})

    def resolver(nodo):
        if "$ref" in nodo:
            return defs[nodo["$ref"].split("/")[-1]]
        for alt in nodo.get("anyOf", []):
            if alt.get("type") != "null":
                return resolver(alt)
        return nodo

    def recorrer(nodo, ruta):
        nodo = resolver(nodo)
        if nodo.get("type") == "array":
            nodo = resolver(nodo.get("items", {}))
            ruta += "[]"
        for nombre, sub in nodo.get("properties", {}).items():
            requerido = nombre in nodo.get("required", [])
            yield f"{ruta}.{nombre}" if ruta else nombre, requerido
            yield from recorrer(sub, f"{ruta}.{nombre}" if ruta else nombre)

    return list(recorrer(esquema, ""))


def _existe(dato, ruta):
    partes = ruta.replace("[]", "").split(".")
    nodos = [dato]
    for p in partes:
        siguiente = []
        for n in nodos:
            if isinstance(n, list):
                n = n[0] if n else {}
            if isinstance(n, dict) and p in n:
                siguiente.append(n[p])
        if not siguiente:
            return False
        nodos = siguiente
    return True


def test_g1_5_todo_campo_requerido_del_esquema_esta_mapeado_y_en_el_anexo():
    sal = json.loads(serializar(_envelope()))
    AccountingConsultResponse(**sal)  # lo que valida AgroFusion: si falla, AgroFusion responde 502
    campos = _campos_esquema()
    requeridos = [r for r, req in campos if req]
    sin_mapear = [r for r in requeridos if not _existe(sal, r)]
    assert not sin_mapear, f"Campos requeridos del esquema que el envelope no trae: {sin_mapear}"
    anexo = ANEXO.read_text(encoding="utf-8")
    fuera_del_anexo = [r for r in requeridos if not re.search(rf"\b{re.escape(r.split('.')[-1])}\b", anexo)]
    assert not fuera_del_anexo, f"Campos del esquema que el Anexo no menciona: {fuera_del_anexo}"
    opcionales_sin_mapear = sorted(r for r, req in campos if not req and not _existe(sal, r))
    print("CAMPOS_REQUERIDOS", len(requeridos))
    print("OPCIONALES_NO_MAPEADOS", opcionales_sin_mapear)


# --- G1.6 ---------------------------------------------------------------------------------------

def test_g1_6_documento_02_desde_compra_proveedor_y_servicio_tercero():
    # El Mapper recibe CostoFactura; el origen (COMPRA_PROVEEDOR / SERVICIO_TERCERO) solo decide que costo entra.
    # Se prueban dos subtipos: un insumo comprado (ALIMENTO) y un servicio de tercero (VETERINARIO).
    for subtipo, id_costo in (("ALIMENTO", 21), ("VETERINARIO", 22)):
        (doc,) = mapear_compras([_costo(id_costo, subtipo, "420000.999")])
        assert doc["Header"]["Type"] == {"Code": "02", "Name": "Factura de compra"}
        assert doc["Header"]["DocumentId"] == f"COS-{id_costo}-20261004"
        t = doc["Totals"]
        assert (t["TotalVAT"], t["TotalWithholdings"], t["TotalDiscounts"]) == (D(0), D(0), D(0))
        assert len(doc["Lines"]) == 1 and doc["Lines"][0]["Taxes"] == []
        assert doc["Lines"][0]["Value"] == D("420000.99")  # trunca, no redondea
        assert len(doc["Lines"][0]["accounting_account"]) == 1


# --- G1.7 ---------------------------------------------------------------------------------------

def test_g1_7_documento_06_desde_el_comprobante_nic41():
    (doc,) = mapear_comprobantes([_comprobante()], TITULAR)
    assert doc["Header"]["Type"] == {"Code": "06", "Name": "Comprobante contable NIC 41"}
    assert doc["Header"]["DocumentId"] == "NIC-901444215-202610-VARIACION_VR_TB-1"
    assert doc["Header"]["Prefix"] == "NIC" and doc["Header"]["Serial"] == "202610-VARIACION_VR_TB-1"
    assert doc["Header"]["IssueDate"] == doc["Header"]["DueDate"] == doc["Header"]["UpdatedAt"] == "2026-10-31"
    assert all(len(ln["accounting_account"]) == 2 for ln in doc["Lines"])
    assert doc["Totals"]["OutstandingBalance"] == D(0)


# --- G1.8 ---------------------------------------------------------------------------------------

def test_g1_8_hash_del_anexo_reproducible_y_en_formato_rf98():
    h1 = hashlib.sha256(ANEXO.read_bytes()).hexdigest()
    h2 = hashlib.sha256(ANEXO.read_bytes()).hexdigest()
    assert h1 == h2
    assert re.fullmatch(r"[0-9a-f]{64}", h1)  # formato que acepta POST /integracion/anexos (HASH_DOCUMENTO_INVALIDO si no)
    print("SHA256_ANEXO", h1)
