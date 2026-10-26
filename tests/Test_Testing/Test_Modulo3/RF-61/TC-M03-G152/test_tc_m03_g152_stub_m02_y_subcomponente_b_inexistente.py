"""
TC-M03-G152 (RF-61 v1.2 CA-5/CA-11/E4/E6/E7/Restricciones 4 y 10/Fase B3,
CU-09) - "Vinculación retrospectiva de datos de buffer."

Código bajo prueba:
    src/telemetry/application/use_cases/infraestructura/vincular_lectura_activo_use_case.py
    src/telemetry/infrastructure/adapters/activo_biologico_stub_adapter.py
    src/telemetry/domain/entities/vinculacion_lectura.py
    src/telemetry/infrastructure/models/vinculacion_lectura_model.py

HALLAZGO PRINCIPAL, RAÍZ PARA TODO RF-61: la única implementación real de
`ActivoBiologicoDependencyPort` es `ActivoBiologicoStubAdapter`, cuyo
método `obtener_activos_en_momento()` hace literalmente `return []`
siempre. Toda lectura vinculada hoy en el sistema real queda
SIN_VINCULAR, siempre -- no por ningún caso límite, sino porque el punto
de integración con M02 nunca fue implementado.

Segundo hallazgo: no existe ningún "Subcomponente B" de resolución
retrospectiva de buffer. `VincularLecturaActivoUseCase` se invoca siempre
en tiempo real, nunca como proceso batch/asíncrono. No existe
`POST /api/v1/links/batch-resolve`. El campo `fecha_fin_vinculacion` se
declara pero NINGÚN archivo le asigna jamás un valor distinto de `None`.

Tercer hallazgo: el catálogo real de `estado_vinculacion` es
`VINCULADA|SIN_VINCULAR|AMBIGUA|CORREGIDA` -- 4 valores, NUNCA
`CONFIRMADA`, `PENDIENTE_REVISION` ni `SUPERADA`.

(a) Fronteras fecha_inicio/fecha_fin -- HALLAZGO: inevaluable en la
    práctica porque el stub siempre devuelve lista vacía y
    fecha_fin_vinculacion nunca toma un valor real.
(b) "NO se usa timestamp de sincronización" -- CONFIRMADO PARCIALMENTE:
    el caso de uso sí pasa timestamp_captura, pero el puerto real lo
    ignora por completo.
(c) E4 fecha de baja -- HALLAZGO: no existe ningún concepto de "fecha de
    baja" en el puerto ni en el stub.
(d) Proceso asíncrono, PENDIENTE_REVISION -- HALLAZGO: no existe.
(e) Restricción 10 vía Fase B3, multi-animal -> AMBIGUA -- PARCIALMENTE
    CONFIRMADO Y MATIZADO: la regla de ambigüedad existe y está
    correctamente implementada, pero es código muerto: nunca puede
    ejecutarse en producción porque el stub jamás devuelve más de 0
    elementos.

Cómo se prueba: inspección directa del stub + pytest con un puerto doble
que SÍ simula 0/1/N activos.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g152_stub_m02_y_subcomponente_b_inexistente.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G152.html --self-contained-html
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.telemetry.application.use_cases.infraestructura.vincular_lectura_activo_use_case import (
    VincularLecturaActivoUseCase,
)
from src.telemetry.infrastructure.adapters.activo_biologico_stub_adapter import ActivoBiologicoStubAdapter

REPO_ROOT = Path(__file__).resolve().parents[5]
AHORA = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)


def _grep(termino: str) -> list[str]:
    return [
        str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src' / 'telemetry').rglob('*.py')
        if termino in p.read_text(encoding='utf-8', errors='ignore')
    ]


class TestSubCasoRaizElStubSiempreDevuelveSinVincular:
    def test_stub_devuelve_lista_vacia_sin_importar_el_timestamp(self):
        stub = ActivoBiologicoStubAdapter()
        resultado_a = stub.obtener_activos_en_momento(id_infraestructura=1, timestamp=AHORA)
        resultado_b = stub.obtener_activos_en_momento(id_infraestructura=999, timestamp=datetime(2000, 1, 1, tzinfo=timezone.utc))
        pytest.fail(
            f"HALLAZGO RAIZ: ActivoBiologicoStubAdapter.obtener_activos_en_momento() devuelve "
            f"{resultado_a!r} y {resultado_b!r} -- siempre lista vacia, sin importar "
            f"id_infraestructura ni timestamp."
        ) if resultado_a == [] and resultado_b == [] else None

    def test_use_case_con_el_puerto_real_siempre_produce_sin_vincular(self):
        vinculacion_repo = MagicMock()
        vinculacion_repo.guardar.side_effect = lambda v: v
        uc = VincularLecturaActivoUseCase(
            db=MagicMock(), vinculacion_repo=vinculacion_repo, activo_port=ActivoBiologicoStubAdapter(),
        )
        resultado = uc.execute(id_telemetria=152, id_infraestructura=1, timestamp_captura=AHORA)
        assert resultado.estado_vinculacion == 'SIN_VINCULAR'
        assert resultado.id_activo_biologico is None


class TestSubCasoANoExisteSubcomponenteBRetrospectivo:
    def test_no_existe_endpoint_batch_resolve(self):
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/routers/vinculacion_router.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (a)/(d): no existe ningun endpoint 'batch-resolve' ni ninguna ruta de "
            "resolucion masiva en vinculacion_router.py."
        ) if 'batch' not in texto.lower() else None

    def test_fecha_fin_vinculacion_nunca_se_asigna_un_valor_real(self):
        archivos_con_asignacion = [
            arch for arch in _grep('fecha_fin_vinculacion')
            if 'fecha_fin_vinculacion =' in (REPO_ROOT / arch).read_text(encoding='utf-8', errors='ignore')
            and 'fecha_fin_vinculacion = None' not in (REPO_ROOT / arch).read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (a): ningun archivo de src/telemetry/ asigna un valor distinto de None a "
            f"fecha_fin_vinculacion. Archivos con alguna asignacion no-None: "
            f"{archivos_con_asignacion or 'ninguno'}."
        ) if not archivos_con_asignacion else None

    def test_no_existe_proceso_asincrono_ni_estado_pendiente_revision(self):
        archivos_celery = _grep('celery') + _grep('asyncio.create_task') + _grep('background')
        archivos_pendiente = _grep('PENDIENTE_REVISION')
        archivos_confirmada = _grep('CONFIRMADA')
        pytest.fail(
            f"HALLAZGO (d): no hay ningun proceso asincrono/background job "
            f"({archivos_celery or 'ninguno'}), y los estados 'PENDIENTE_REVISION' "
            f"({archivos_pendiente or 'ninguno'}) y 'CONFIRMADA' ({archivos_confirmada or 'ninguno'}) "
            f"no existen en src/telemetry/."
        ) if not archivos_pendiente and not archivos_confirmada else None


class TestSubCasoEReglaDeAmbiguedadExisteYaEsAlcanzable:
    def test_con_dos_activos_simulados_la_regla_de_ambiguedad_si_funciona(self):
        activo_1 = MagicMock(id_activo_biologico=1, modelo_manejo='INDIVIDUAL')
        activo_2 = MagicMock(id_activo_biologico=2, modelo_manejo='INDIVIDUAL')
        activo_port_doble = MagicMock()
        activo_port_doble.obtener_activos_en_momento.return_value = [activo_1, activo_2]
        vinculacion_repo = MagicMock()
        vinculacion_repo.guardar.side_effect = lambda v: v
        uc = VincularLecturaActivoUseCase(
            db=MagicMock(), vinculacion_repo=vinculacion_repo, activo_port=activo_port_doble,
        )
        resultado = uc.execute(id_telemetria=152, id_infraestructura=1, timestamp_captura=AHORA)
        assert resultado.estado_vinculacion == 'AMBIGUA'
        assert resultado.id_activo_biologico is None

    def test_pero_el_adaptador_real_jamas_puede_producir_ese_escenario(self):
        pytest.fail(
            "HALLAZGO (e), matiz: la regla de ambiguedad esta bien implementada en codigo, pero "
            "es inalcanzable en el sistema real porque el unico ActivoBiologicoDependencyPort "
            "real (el stub) nunca devuelve mas de 0 elementos."
        )
