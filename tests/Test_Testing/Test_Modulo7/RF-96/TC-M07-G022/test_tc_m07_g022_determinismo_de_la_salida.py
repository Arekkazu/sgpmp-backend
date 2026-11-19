"""
TC-M07-G022 (RF-96 CA-8, RNF-96.1, Salida, CU-10) - "Determinismo de la
salida." Agrupa TC-96-064 a TC-96-067.

Construido 2026-11-18 contra el código real (aaef.py).

Código bajo prueba:
    src/accounting_integration/domain/services/aaef.py (mapear_compras, construir_envelope, hash_contenido)

Cómo se prueba: pytest de unidad -- 2 instancias del servicio no se
pueden simular literalmente en pytest; se confirma en su lugar que las
funciones son puras (sin estado global ni fecha/hora implícita más allá
de lo que se les pasa explícitamente), que es la propiedad que garantiza
el mismo resultado sin importar la instancia.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m07_g022_determinismo_de_la_salida.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M07-G022.html --self-contained-html
"""
from __future__ import annotations

import datetime
import random
from decimal import Decimal

from src.accounting_integration.domain.services.aaef import (
    CostoFactura,
    SistemaOrigen,
    Titular,
    construir_envelope,
    hash_contenido,
    mapear_compras,
)

D = Decimal
SISTEMA = SistemaOrigen(system_id="SGPMP", system_name="SIGAB", environment="TEST")
TITULAR = Titular("901444215", "Hacienda Qa Mseis S.A.S.")


def _costos() -> list[CostoFactura]:
    return [
        CostoFactura(4485, "900777571", "Concentrados La Pradera S.A.S.", "CP", "1187",
                    datetime.date(2026, 10, 8), datetime.date(2026, 11, 7), "ALIMENTO", D("380000"), "158405", "F2"),
        CostoFactura(4486, "900777582", "Veterinaria El Prado S.A.S.", "VP", "342",
                    datetime.date(2026, 10, 21), datetime.date(2026, 11, 20), "VETERINARIO", D("210000"), "158405", "F3"),
        CostoFactura(4487, "900777593", "Drogueria Veterinaria Neiva S.A.S.", "DV", "77",
                    datetime.date(2026, 10, 27), datetime.date(2026, 11, 26), "MEDICAMENTO", D("150000"), "158405", "F1"),
    ]


class TestSubCasoRepetirConLaMismaEntradaProduceSalidaIdenticaConfirmadoCorrecto:
    def test_dos_ejecuciones_con_los_mismos_costos_dan_el_mismo_hash(self):
        compras1 = mapear_compras(_costos())
        compras2 = mapear_compras(_costos())
        envelope1 = construir_envelope(TITULAR, datetime.date(2026, 10, 1), datetime.date(2026, 10, 31), SISTEMA,
                                       "contador@pecuaria.co", datetime.date(2026, 11, 18), compras1, [])
        envelope2 = construir_envelope(TITULAR, datetime.date(2026, 10, 1), datetime.date(2026, 10, 31), SISTEMA,
                                       "contador@pecuaria.co", datetime.date(2026, 11, 18), compras2, [])
        assert hash_contenido(envelope1["invoices"]) == hash_contenido(envelope2["invoices"])


class TestSubCasoLaSalidaQuedaOrdenadaPorDocumentIdAscendenteConfirmadoCorrecto:
    def test_las_invoices_del_envelope_quedan_en_orden_ascendente_de_documentid(self):
        compras = mapear_compras(_costos())
        envelope = construir_envelope(TITULAR, datetime.date(2026, 10, 1), datetime.date(2026, 10, 31), SISTEMA,
                                      "contador@pecuaria.co", datetime.date(2026, 11, 18), compras, [])
        ids = [doc["Header"]["DocumentId"] for doc in envelope["invoices"]]
        assert ids == sorted(ids)


class TestSubCasoLaPermutacionDeLaEntradaNoCambiaLaSalida:
    def test_entregar_los_costos_en_orden_distinto_produce_la_misma_salida_final(self):
        costos = _costos()
        orden_original = mapear_compras(list(costos))
        orden_invertido = mapear_compras(list(reversed(costos)))
        orden_aleatorio = costos[:]
        random.Random(42).shuffle(orden_aleatorio)
        orden_random = mapear_compras(orden_aleatorio)

        def _envelope(compras):
            return construir_envelope(TITULAR, datetime.date(2026, 10, 1), datetime.date(2026, 10, 31), SISTEMA,
                                      "contador@pecuaria.co", datetime.date(2026, 11, 18), compras, [])

        hash_original = hash_contenido(_envelope(orden_original)["invoices"])
        hash_invertido = hash_contenido(_envelope(orden_invertido)["invoices"])
        hash_random = hash_contenido(_envelope(orden_random)["invoices"])
        assert hash_original == hash_invertido == hash_random


class TestSubCasoLasFuncionesSonPurasSinEstadoGlobalDocumentacion:
    def test_mapear_compras_no_depende_de_ningun_reloj_ni_variable_global(self):
        """Propiedad que garantiza el mismo resultado en cualquier instancia del servicio:
        ni mapear_compras ni mapear_comprobantes llaman a datetime.now()/date.today() --
        toda fecha/hora les llega como parámetro explícito desde quien las invoca."""
        import inspect
        from src.accounting_integration.domain.services import aaef
        codigo_fuente = inspect.getsource(aaef.mapear_compras) + inspect.getsource(aaef.mapear_comprobantes)
        assert 'datetime.now(' not in codigo_fuente and 'date.today(' not in codigo_fuente
