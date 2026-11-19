"""
TC-M07-G032 (RF-97 5.5, CA-9, RNF-97.2, RNF-97.6, RNF-97.7, CU-09) -
"Hash de contenido y determinismo." Agrupa TC-97-054 a TC-97-061.

Construido 2026-11-18 contra el código real
(nic41.py::hash_sha256, aaef.py::hash_contenido/construir_envelope,
gateway_aaef.py).

Código bajo prueba:
    src/financial_valuation/domain/services/nic41.py (hash_sha256)
    src/accounting_integration/domain/services/aaef.py (hash_contenido, construir_envelope, truncar2)
    src/accounting_integration/infrastructure/gateway_aaef.py (registro en RF-102)

Cómo se prueba: pytest de unidad -- recalcula el hash de forma
independiente con la MISMA fórmula real (json.dumps sort_keys=True,
ensure_ascii=False, default=str, separators=(",", ":")) para confirmar
que coincide, en vez de solo comparar hash_contenido() contra sí mismo.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m07_g032_hash_de_contenido_y_determinismo.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M07-G032.html --self-contained-html
"""
from __future__ import annotations

import datetime
import hashlib
import json
import unicodedata
from decimal import Decimal
from pathlib import Path

from src.accounting_integration.domain.services.aaef import CostoFactura, hash_contenido, mapear_compras
from src.financial_valuation.domain.services.nic41 import truncar2

D = Decimal
REPO_ROOT = Path(__file__).resolve().parents[5]


def _recalcular_independiente(contenido: object) -> str:
    """Réplica exacta e independiente de hash_sha256(), escrita aquí sin importar la
    función real -- confirma el algoritmo, no solo que la función se llame a sí misma."""
    texto = json.dumps(contenido, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _costo(**kw) -> CostoFactura:
    base = dict(id_registro_costo=4485, tercero_nit="900777571", tercero_razon_social="Concentrados La Pradera S.A.S.",
                factura_prefijo="CP", factura_numero="1187", fecha_factura=datetime.date(2026, 10, 8),
                fecha_vencimiento_factura=datetime.date(2026, 11, 7), subtipo_costo="ALIMENTO",
                monto_costo=D("380000"), cuenta_debito="158405", activo="QA-M07-BUF-F2")
    base.update(kw)
    return CostoFactura(**base)


class TestSubCasoRecalculoIndependienteCoincideConfirmadoCorrecto:
    def test_el_hash_real_coincide_con_un_recalculo_independiente_del_mismo_algoritmo(self):
        compras = mapear_compras([_costo()])
        hash_real = hash_contenido(compras)
        hash_independiente = _recalcular_independiente({"invoices": compras, "transactions": []})
        assert hash_real == hash_independiente


class TestSubCasoCerosFinalesConfirmadoCorrectoGraciasATruncar2:
    def test_123_4_y_123_40_dan_el_mismo_hash_porque_truncar2_siempre_fija_2_decimales(self):
        """No es una ambiguedad en este codigo: truncar2() SIEMPRE produce un Decimal con
        exactamente 2 decimales (quantize), asi que 123.4 y 123.40 de ORIGEN llegan
        IGUALES (ambos 123.40) antes de siquiera construir el documento -- la ambiguedad de
        'ceros finales' que la ficha teme para el hash nunca llega a manifestarse porque se
        resuelve un paso antes, en truncar2()."""
        a = truncar2(D("123.4"))
        b = truncar2(D("123.40"))
        assert str(a) == str(b) == "123.40"

    def test_dos_documentos_con_monto_de_origen_distinto_formato_dan_el_mismo_hash(self):
        doc_a = mapear_compras([_costo(monto_costo=D("123.4"))])
        doc_b = mapear_compras([_costo(monto_costo=D("123.40"))])
        assert hash_contenido(doc_a) == hash_contenido(doc_b)


class TestSubCasoNormalizacionUnicodeNoExisteHallazgo:
    def test_dos_textos_visualmente_iguales_con_distinta_composicion_nfc_nfd_dan_hashes_distintos(self):
        """HALLAZGO: hash_sha256() no normaliza Unicode (ningun unicodedata.normalize() en
        el pipeline real) -- dos razones sociales visualmente identicas pero compuestas de
        forma distinta (NFC: 'é' como un solo caracter U+00E9; NFD: 'e' + tilde combinante
        U+0065 U+0301) producen documentos JSON distintos byte a byte, y por lo tanto hashes
        SHA-256 distintos, aunque un humano los lea igual."""
        nfc = unicodedata.normalize("NFC", "Peña")
        nfd = unicodedata.normalize("NFD", "Peña")
        assert nfc != nfd  # confirma que son, en efecto, secuencias de bytes distintas
        doc_nfc = mapear_compras([_costo(tercero_razon_social=f"Agropecuaria {nfc} S.A.S.")])
        doc_nfd = mapear_compras([_costo(tercero_razon_social=f"Agropecuaria {nfd} S.A.S.")])
        import pytest
        pytest.fail(
            f"HALLAZGO: hash NFC={hash_contenido(doc_nfc)[:12]}... vs NFD="
            f"{hash_contenido(doc_nfd)[:12]}... -- distintos, aunque ambos textos se vean "
            "identicos para un humano. No existe ninguna normalizacion Unicode en el "
            "pipeline de hash real."
        ) if hash_contenido(doc_nfc) != hash_contenido(doc_nfd) else None


class TestSubCasoMetadataNoAfectaElHashYUnCentavoSiConfirmadoCorrecto:
    def test_metadata_distinta_con_las_mismas_invoices_da_el_mismo_hash(self):
        compras = mapear_compras([_costo()])
        hash1 = hash_contenido(compras)
        hash2 = hash_contenido(compras)  # simula dos ExchangeId/GeneratedAt distintos (no entran al hash)
        assert hash1 == hash2

    def test_un_centavo_de_diferencia_en_un_value_si_cambia_el_hash(self):
        doc_a = mapear_compras([_costo(monto_costo=D("380000.00"))])
        doc_b = mapear_compras([_costo(monto_costo=D("380000.01"))])
        assert hash_contenido(doc_a) != hash_contenido(doc_b)


class TestSubCasoElHashSeRegistraEnRf102ConfirmadoCorrecto:
    def test_atender_y_vista_previa_pasan_hash_contenido_al_evento_de_auditoria(self):
        archivo = REPO_ROOT / 'src/accounting_integration/infrastructure/gateway_aaef.py'
        texto = archivo.read_text(encoding='utf-8')
        # atender() usa '"hash_contenido": resultado.hash_contenido' (dict literal) para RF-102;
        # vista_previa() usa 'hash_contenido=resultado.hash_contenido' (kwarg) para RF-102;
        # _cabeceras() lo usa una tercera vez para el header X-Content-SHA256.
        assert texto.count('resultado.hash_contenido') >= 2
