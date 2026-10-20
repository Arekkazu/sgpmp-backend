"""
TC-M03-G152 (RF-61 v1.2 CA-5/CA-11/E4/E6/E7/Restricciones 4 y 10/Fase B3,
CU-09) - "Vinculación retrospectiva de datos de buffer." Grupo existente de
RF-61 (dependiente, según la propia ficha, de un traslado previo).

Código bajo prueba:
    src/telemetry/application/use_cases/infraestructura/vincular_lectura_activo_use_case.py
    src/telemetry/infrastructure/adapters/activo_biologico_stub_adapter.py
    src/telemetry/domain/entities/vinculacion_lectura.py
    src/telemetry/infrastructure/models/vinculacion_lectura_model.py

HALLAZGO PRINCIPAL, RAÍZ PARA TODO RF-61 (G152-G159): la única
implementación real de `ActivoBiologicoDependencyPort` (el puerto hacia
M02) es `ActivoBiologicoStubAdapter`, cuyo propio docstring dice "Stub de
M02 hasta que el módulo de activos biológicos esté disponible. Retorna
lista vacía → las vinculaciones quedan en estado SIN_VINCULAR." Su único
método, `obtener_activos_en_momento()`, hace literalmente `return []`
siempre, sin excepción, sin importar `id_infraestructura` ni `timestamp`.
Esto significa que **toda lectura vinculada hoy en el sistema real queda
SIN_VINCULAR, siempre** -- no por ningún caso límite de fecha, baja o
ambigüedad, sino porque el punto de integración con M02 nunca fue
implementado. Mismo patrón exacto que `IotStubAdapter` (TC-M03-G148).

Segundo hallazgo, igual de estructural: no existe ningún "Subcomponente B"
de resolución retrospectiva de buffer. `VincularLecturaActivoUseCase` (el
único caso de uso que crea vinculaciones) se invoca, según su propio
docstring, "desde IngerirTelemetriaUseCase después del commit de la
telemetría" -- es decir, SIEMPRE en tiempo real, nunca como un proceso
batch/asíncrono sobre un lote histórico de buffer. No existe
`POST /api/v1/links/batch-resolve` en `vinculacion_router.py` (los 4 únicos
endpoints son GET lista, GET detalle, PATCH resolver, POST corregir). El
campo `fecha_fin_vinculacion` se declara, se lee y se reenvía sin cambios
en `corregir_vinculacion_use_case.py`, pero NINGÚN archivo de
`src/telemetry/` le asigna jamás un valor distinto de `None` -- por lo que
la condición de frontera que pide (a) (`fecha_fin IS NULL OR fecha_fin >
timestamp_captura`) nunca puede evaluar la rama "fecha_fin con valor real",
porque esa columna está permanentemente NULL para toda vinculación jamás
creada por este código.

Tercer hallazgo: el catálogo real de `estado_vinculacion` (confirmado en el
comentario del propio modelo, `vinculacion_lectura_model.py:30`) es
`VINCULADA|SIN_VINCULAR|AMBIGUA|CORREGIDA` -- 4 valores, NUNCA
`CONFIRMADA`, `PENDIENTE_REVISION` ni `SUPERADA` (estos tres nombres
existen en el código, pero en dominios completamente distintos:
`SUPERADA` es de `asociacion_sensor_activo` en M02/biological_assets y de
`TelemetriaCalidad` en RF-56 -- no de `VinculacionLectura`/RF-61).

(a) CA-5/Restricción 4, fronteras de fecha_inicio/fecha_fin -- HALLAZGO:
    inevaluable en la práctica porque (1) el stub siempre devuelve lista
    vacía antes de que cualquier comparación de fechas pueda importar, y
    (2) `fecha_fin_vinculacion` nunca toma un valor real en ningún punto
    del código, por lo que la rama "igual a fecha_fin" de la Restricción 4
    nunca puede alcanzarse.
(b) "NO se usa timestamp de sincronización" -- CONFIRMADO PARCIALMENTE:
    `VincularLecturaActivoUseCase.execute()` sí pasa `timestamp_captura`
    (no la hora de sincronización) al puerto -- correcto en diseño -- pero
    el puerto real (el stub) ignora ese parámetro por completo, así que el
    comportamiento correcto en el caso de uso es clínicamente irrelevante
    hoy: cualquier timestamp produce el mismo resultado (SIN_VINCULAR).
(c) E4 lectura posterior/anterior a fecha de baja -- HALLAZGO: no hay
    ningún concepto de "fecha de baja" en `ActivoBiologicoDependencyPort`
    ni en el stub; no puede evaluarse.
(d) CA-11/E6/E7 proceso asíncrono, priorización, resumen CONFIRMADA/
    AMBIGUA/SIN_VINCULAR, PENDIENTE_REVISION -- HALLAZGO: no existe ningún
    proceso asíncrono/batch, ni los estados CONFIRMADA ni
    PENDIENTE_REVISION en el dominio de vinculación de lecturas.
(e) Restricción 10 vía Fase B3, multi-animal -> AMBIGUA -- PARCIALMENTE
    CONFIRMADO Y MATIZADO: la regla de ambigüedad (`len(activos) > 1` ->
    `AMBIGUA`) SÍ existe y está correctamente implementada en
    `VincularLecturaActivoUseCase` -- pero es, hoy, código MUERTO: nunca
    puede ejecutarse en producción porque el stub jamás devuelve más de 0
    elementos. La regla existe; su activación no.

Cómo se prueba: inspección directa del stub + pytest a nivel de caso de uso
con un puerto doble que SÍ simula 0/1/N activos (para distinguir "la regla
no existe" de "la regla existe pero está inalcanzable hoy") + grep
exhaustivo de rutas batch/asíncronas.

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
    """Hallazgo raiz: el puerto hacia M02 es un stub que siempre devuelve []."""

    def test_stub_devuelve_lista_vacia_sin_importar_el_timestamp(self):
        stub = ActivoBiologicoStubAdapter()
        resultado_a = stub.obtener_activos_en_momento(id_infraestructura=1, timestamp=AHORA)
        resultado_b = stub.obtener_activos_en_momento(id_infraestructura=999, timestamp=datetime(2000, 1, 1, tzinfo=timezone.utc))
        pytest.fail(
            f"HALLAZGO RAIZ: ActivoBiologicoStubAdapter.obtener_activos_en_momento() devuelve "
            f"{resultado_a!r} y {resultado_b!r} -- siempre lista vacia, sin importar "
            f"id_infraestructura ni timestamp. Su docstring lo confirma: 'Stub de M02 ... retorna "
            f"lista vacia -> las vinculaciones quedan en SIN_VINCULAR'. Es la UNICA implementacion "
            f"real de ActivoBiologicoDependencyPort en todo el repositorio."
        ) if resultado_a == [] and resultado_b == [] else None

    def test_use_case_con_el_puerto_real_siempre_produce_sin_vincular(self):
        """Con el adaptador REAL (no un mock), confirma end-to-end que
        cualquier lectura queda SIN_VINCULAR hoy, sea cual sea su contenido."""
        vinculacion_repo = MagicMock()
        vinculacion_repo.guardar.side_effect = lambda v: v
        uc = VincularLecturaActivoUseCase(
            db=MagicMock(), vinculacion_repo=vinculacion_repo, activo_port=ActivoBiologicoStubAdapter(),
        )
        resultado = uc.execute(id_telemetria=152, id_infraestructura=1, timestamp_captura=AHORA)
        assert resultado.estado_vinculacion == 'SIN_VINCULAR'
        assert resultado.id_activo_biologico is None


class TestSubCasoANoExisteSubcomponenteBRetrospectivo:
    """(a)/(d): no hay proceso batch/asincrono ni comparacion de intervalos
    fecha_inicio/fecha_fin -- fecha_fin_vinculacion nunca se asigna."""

    def test_no_existe_endpoint_batch_resolve(self):
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/routers/vinculacion_router.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (a)/(d): no existe ningun endpoint 'batch-resolve' ni ninguna ruta de "
            "resolucion masiva en vinculacion_router.py -- los 4 unicos endpoints son GET lista, "
            "GET detalle, PATCH resolver (una lectura AMBIGUA a la vez) y POST corregir (una "
            "lectura a la vez). No hay ningun mecanismo para resolver un lote de buffer completo."
        ) if 'batch' not in texto.lower() else None

    def test_fecha_fin_vinculacion_nunca_se_asigna_un_valor_real(self):
        archivos_con_asignacion = [
            arch for arch in _grep('fecha_fin_vinculacion')
            if 'fecha_fin_vinculacion =' in (REPO_ROOT / arch).read_text(encoding='utf-8', errors='ignore')
            and 'fecha_fin_vinculacion = None' not in (REPO_ROOT / arch).read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (a): ningun archivo de src/telemetry/ asigna un valor distinto de None a "
            f"fecha_fin_vinculacion (se declara, se lee y se reenvia sin cambios, pero nunca se "
            f"'cierra' un periodo de vinculacion). Archivos que la mencionan con alguna asignacion "
            f"no-None: {archivos_con_asignacion or 'ninguno'}. La condicion de frontera de la "
            f"Restriccion 4 ('igual a fecha_fin') nunca es alcanzable porque esa columna es "
            f"permanentemente NULL."
        ) if not archivos_con_asignacion else None

    def test_no_existe_proceso_asincrono_ni_estado_pendiente_revision(self):
        archivos_celery = _grep('celery') + _grep('asyncio.create_task') + _grep('background')
        archivos_pendiente = _grep('PENDIENTE_REVISION')
        archivos_confirmada = _grep('CONFIRMADA')
        pytest.fail(
            f"HALLAZGO (d): no hay ningun proceso asincrono/background job asociado a vinculacion "
            f"({archivos_celery or 'ninguno'}), y los estados 'PENDIENTE_REVISION' "
            f"({archivos_pendiente or 'ninguno'}) y 'CONFIRMADA' ({archivos_confirmada or 'ninguno'}) "
            f"no existen en src/telemetry/ -- el catalogo real de estado_vinculacion, confirmado en "
            f"el comentario del propio modelo (vinculacion_lectura_model.py:30), es "
            f"'VINCULADA|SIN_VINCULAR|AMBIGUA|CORREGIDA', 4 valores, nunca 5."
        ) if not archivos_pendiente and not archivos_confirmada else None


class TestSubCasoEReglaDeAmbiguedadExisteYaEsAlcanzable:
    """(e): distingue 'la regla no existe' de 'la regla existe pero esta
    inalcanzable hoy por culpa del stub' -- usando un doble de prueba que SI
    simula 2 activos, en lugar del stub real."""

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
            "HALLAZGO (e), matiz: el test anterior prueba que la regla de ambiguedad de la "
            "Restriccion 10 esta bien implementada EN CODIGO -- pero esa rama es inalcanzable en "
            "el sistema real, porque el unico ActivoBiologicoDependencyPort que existe de verdad "
            "(ActivoBiologicoStubAdapter) nunca devuelve mas de 0 elementos. La regla existe; su "
            "activacion, hoy, no."
        )
