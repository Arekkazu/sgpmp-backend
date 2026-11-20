"""
TC-M07-G023 (RF-96 Precondiciones, 5.5, RNF-96.2, RNF-96.3, CU-11) -
"Invocación exclusiva, gobierno del contrato y rendimiento." Agrupa
TC-96-068 a TC-96-072.

Construido 2026-11-18 contra el código real.

HALLAZGO (matiza la ficha, no es una brecha de seguridad): las
Precondiciones dicen "Invocación exclusivamente desde RF-97; los Mappers
no se ejecutan de forma independiente." El código real tiene una SEGUNDA
ruta interna legítima: `gestionar_anexos_use_case.py::validar_con_datos_de_prueba()`
(RF-AE02 5.10) invoca `mapear_compras()`/`mapear_comprobantes()`
directamente con datos sintéticos fijos, como autoprueba ANTES de poner
el anexo en revisión -- no es una brecha (no hay ningún endpoint HTTP que
exponga los Mappers al exterior, ninguna llamada externa es posible), pero
contradice la letra de "exclusivamente desde RF-97".

Código bajo prueba:
    src/accounting_integration/infrastructure/routers/*.py (ausencia de exposición directa)
    src/accounting_integration/application/use_cases/contratos/gestionar_anexos_use_case.py
    src/accounting_integration/domain/entities/contrato.py (motivo_bloqueo_activacion)

NO VERIFICABLE AQUÍ: el límite de 5 segundos en volumen normal (2.000
facturas, RF-97) depende de BD viva y del resto de la cadena de RF-97 --
este TC solo mide el tiempo del Mapper puro en memoria, de forma
informativa, no como aserción dura del RNF-96.2 completo.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m07_g023_invocacion_exclusiva_y_gobierno.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M07-G023.html --self-contained-html
"""
from __future__ import annotations

import datetime
import time
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.accounting_integration.domain.entities.contrato import AnexoMapeo, VersionContrato, motivo_bloqueo_activacion
from src.accounting_integration.domain.services.aaef import CostoFactura, mapear_compras

D = Decimal
REPO_ROOT = Path(__file__).resolve().parents[5]
ROUTERS_DIR = REPO_ROOT / 'src/accounting_integration/infrastructure/routers'


class TestSubCasoNingunRouterExponeLosMappersDirectamenteConfirmadoCorrecto:
    def test_ningun_router_de_m07_importa_mapear_compras_ni_mapear_comprobantes(self):
        for archivo in ROUTERS_DIR.glob('*.py'):
            texto = archivo.read_text(encoding='utf-8')
            assert 'mapear_compras' not in texto and 'mapear_comprobantes' not in texto


class TestSubCasoExisteUnaSegundaRutaInternaLegitimaHallazgo:
    def test_rf98_invoca_los_mappers_directamente_para_autoprobar_el_anexo(self):
        archivo = REPO_ROOT / (
            'src/accounting_integration/application/use_cases/contratos/gestionar_anexos_use_case.py')
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO: validar_con_datos_de_prueba() (RF-AE02 5.10) invoca mapear_compras() y "
            "mapear_comprobantes() directamente con datos sinteticos fijos, sin pasar por "
            "RF-97 -- contradice la letra de las Precondiciones de RF-96 ('invocacion "
            "exclusivamente desde RF-97'). No es una brecha de seguridad (es un autoprueba "
            "interna del anexo antes de pasar a revision, sin ningun endpoint HTTP que la "
            "exponga), pero el RF deberia reconocer esta segunda via legitima."
        ) if 'mapear_compras(' in texto and 'mapear_comprobantes(' in texto else None


class TestSubCasoGobiernoDelAnexoConfirmadoCorrecto:
    def test_un_anexo_borrador_bloquea_la_activacion_del_contrato(self):
        contrato = VersionContrato(1, "2.2", "MINOR", datetime.date(2026, 12, 1), 1, ["COMPRAS"])
        anexo_borrador = AnexoMapeo(1, "ANEXO-X", "1.0", "s3://x", "a" * 64, estado="BORRADOR")
        motivo = motivo_bloqueo_activacion(contrato, anexo_borrador, es_produccion=False)
        assert motivo is not None

    def test_un_anexo_aprobado_no_bloquea_la_activacion(self):
        contrato = VersionContrato(1, "2.2", "MINOR", datetime.date(2026, 12, 1), 1, ["COMPRAS"])
        anexo_aprobado = AnexoMapeo(1, "ANEXO-X", "1.0", "s3://x", "a" * 64, estado="APROBADO")
        motivo = motivo_bloqueo_activacion(contrato, anexo_aprobado, es_produccion=False)
        assert motivo is None

    def test_sin_mapeadores_validos_tambien_bloquea_la_activacion(self):
        contrato = VersionContrato(1, "2.2", "MINOR", datetime.date(2026, 12, 1), 1, [])
        anexo_aprobado = AnexoMapeo(1, "ANEXO-X", "1.0", "s3://x", "a" * 64, estado="APROBADO")
        motivo = motivo_bloqueo_activacion(contrato, anexo_aprobado, es_produccion=False)
        assert motivo is not None


class TestSubCasoRendimientoDelMapperPuroInformativoNoEsElRnfCompleto:
    def test_1000_costos_se_transforman_en_un_tiempo_razonable_del_mapper_puro(self):
        """Informativo: mide solo el Mapper en memoria (sin BD, sin red, sin el resto de la
        cadena de RF-97) -- no es una medicion del RNF-96.2 completo, solo confirma que no
        hay un comportamiento cuadratico patologico en mapear_compras()."""
        costos = [CostoFactura(i, f"90077757{i % 9}", "Proveedor", "CP", str(1000 + i),
                               datetime.date(2026, 10, 1), None, "ALIMENTO", D("1000.00"), "158405", f"activo-{i}")
                  for i in range(1000)]
        inicio = time.perf_counter()
        documentos = mapear_compras(costos)
        duracion = time.perf_counter() - inicio
        assert len(documentos) == 1000  # cada factura_numero es distinta -> un documento por costo
        assert duracion < 2.0  # informativo: muy por debajo del presupuesto de 5s de RF-97 completo
