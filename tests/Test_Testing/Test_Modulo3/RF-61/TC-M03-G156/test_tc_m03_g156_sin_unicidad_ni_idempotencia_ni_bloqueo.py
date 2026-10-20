"""
TC-M03-G156 (RF-61 v1.2 Restricciones 1 y 2/Subcomponente C/Fases A5 y B3,
CU-13) - "Unicidad, idempotencia y concurrencia de la vinculación." Grupo
existente de RF-61 (TC-M03-G25).

Código bajo prueba:
    src/telemetry/application/use_cases/infraestructura/vincular_lectura_activo_use_case.py
    src/telemetry/application/use_cases/infraestructura/resolver_vinculacion_use_case.py
    src/telemetry/infrastructure/models/vinculacion_lectura_model.py
    src/telemetry/infrastructure/repositories/vinculacion_lectura_repository.py

HALLAZGO PRINCIPAL: ninguno de los 3 mecanismos que (a)/(b)/(c) asumen
existe en el código real:
  1. `VinculacionLecturaModel.id_telemetria` NO tiene `unique=True` ni
     ninguna restricción de unicidad a nivel de BD (confirmado leyendo la
     definición completa de la columna).
  2. `VincularLecturaActivoUseCase.execute()` NUNCA consulta si ya existe
     una vinculación para el mismo `id_telemetria` antes de llamar a
     `vinculacion_repo.guardar()` -- inserta sin condición, siempre.
  3. `obtener_por_id()`/`actualizar()` en el repositorio no usan
     `with_for_update()` (SELECT ... FOR UPDATE) ni ninguna columna de
     bloqueo optimista (`version_id` o similar) -- la verificación de
     `estado_vinculacion != 'AMBIGUA'` en `VinculacionLectura.resolver()`
     ocurre en memoria, sobre una fila leída sin bloqueo.

(a) Restricción 2, una sola vinculación vigente por lectura -- HALLAZGO:
    no hay ninguna restricción de unicidad en BD sobre `id_telemetria`; dos
    llamadas a `VincularLecturaActivoUseCase.execute()` con el mismo
    `id_telemetria` crean DOS filas en `vinculaciones_lecturas`, ambas
    "vigentes" (ninguna se marca como superada), sin ningún rechazo.
(b) Reenvío de RF-53 (idempotencia) -- HALLAZGO: confirmado por el mismo
    código que (a) -- no hay ninguna verificación de "ya procesado" antes
    de insertar; un reenvío produce una vinculación duplicada, no un no-op.
(c) Dos resoluciones concurrentes de la misma AMBIGUA -- HALLAZGO
    (ventana de carrera, TOCTOU): `ResolverVinculacionUseCase.execute()`
    lee la fila con `obtener_por_id()` SIN `FOR UPDATE`, valida en memoria
    (`VinculacionLectura.resolver()`) y recién después escribe con
    `actualizar()`. Dos transacciones concurrentes pueden leer la misma
    fila AMBIGUA antes de que cualquiera escriba, pasar ambas la
    validación en memoria, y ambas ejecutar `actualizar()` -- la última
    en comitear gana silenciosamente, sin ningún rechazo explícito a la
    perdedora (la ficha exige que la perdedora reciba un rechazo explícito,
    no que simplemente sea sobrescrita sin aviso).
(d) Traslado de M02 durante vinculación masiva -- NO APLICA: no existe
    ninguna "vinculación masiva" (confirmado en TC-M03-G152).
(e) Reprocesar un lote ya vinculado -- NO APLICA, mismo motivo que (d); en
    la parte que sí aplica (reenvío de una única lectura) ya cubierto por
    (b): sí duplica.

Cómo se prueba: pytest con doble de prueba del repositorio, reproduciendo
(a)/(b) con dos llamadas `execute()` sobre el mismo `id_telemetria`, e
inspección directa del código de `obtener_por_id()`/`actualizar()` para
(c) (una carrera real de hilos no es necesaria para demostrar la ausencia
estructural del bloqueo).

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g156_sin_unicidad_ni_idempotencia_ni_bloqueo.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G156.html --self-contained-html
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.telemetry.application.use_cases.infraestructura.vincular_lectura_activo_use_case import (
    VincularLecturaActivoUseCase,
)

REPO_ROOT = Path(__file__).resolve().parents[5]
AHORA = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)


class TestSubCasoAyBSinUnicidadNiIdempotencia:
    def test_columna_id_telemetria_no_tiene_restriccion_de_unicidad(self):
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/models/vinculacion_lectura_model.py'
        texto = archivo.read_text(encoding='utf-8')
        linea_id_telemetria = next(l for l in texto.splitlines() if 'id_telemetria: Mapped[int]' in l)
        pytest.fail(
            f"HALLAZGO (a): la columna id_telemetria no declara unique=True ni ninguna "
            f"restriccion de unicidad -- definicion real: {linea_id_telemetria.strip()!r}. Nada "
            f"en BD impide mas de una fila 'vigente' para la misma lectura."
        ) if 'unique' not in linea_id_telemetria else None

    def test_dos_llamadas_con_el_mismo_id_telemetria_crean_dos_filas(self):
        """Reproduce (a)/(b): ni el reenvio de RF-53 ni una segunda
        vinculacion por error se deduplican -- execute() siempre inserta."""
        vinculacion_repo = MagicMock()
        guardadas = []
        vinculacion_repo.guardar.side_effect = lambda v: (guardadas.append(v), v)[1]
        activo_port = MagicMock()
        activo_port.obtener_activos_en_momento.return_value = []
        uc = VincularLecturaActivoUseCase(db=MagicMock(), vinculacion_repo=vinculacion_repo, activo_port=activo_port)

        uc.execute(id_telemetria=156, id_infraestructura=1, timestamp_captura=AHORA)
        uc.execute(id_telemetria=156, id_infraestructura=1, timestamp_captura=AHORA)  # reenvio simulado

        assert vinculacion_repo.guardar.call_count == 2
        pytest.fail(
            f"HALLAZGO (a)/(b): dos llamadas a execute() con el mismo id_telemetria=156 (un "
            f"reenvio del mismo evento de RF-53, o un error de doble-envio) produjeron "
            f"{len(guardadas)} filas guardadas -- ninguna verificacion previa de 'ya existe una "
            f"vinculacion para esta lectura' impidio la segunda insercion. No hay idempotencia."
        )


class TestSubCasoCCarreraSinBloqueoTocTou:
    def test_obtener_por_id_no_usa_select_for_update(self):
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/repositories/vinculacion_lectura_repository.py'
        texto = archivo.read_text(encoding='utf-8')
        bloque_obtener = texto.split('def obtener_por_id(')[1].split('def actualizar(')[0]
        pytest.fail(
            "HALLAZGO (c): obtener_por_id() usa db.get(VinculacionLecturaModel, ...) sin "
            "with_for_update() -- lee la fila sin bloqueo. La validacion de "
            "'estado_vinculacion != AMBIGUA' en VinculacionLectura.resolver() ocurre en memoria, "
            "sobre esa lectura sin bloqueo, antes de escribir con actualizar(). Dos resoluciones "
            "concurrentes sobre la misma vinculacion AMBIGUA pueden ambas pasar la validacion "
            "antes de que cualquiera escriba -- la segunda en comitear sobrescribe a la primera "
            "sin ningun rechazo explicito, en lugar del 'solo una prevalece, la otra recibe un "
            "rechazo explicito' que pide la ficha."
        ) if 'with_for_update' not in bloque_obtener else None

    def test_no_existe_ninguna_columna_de_bloqueo_optimista(self):
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/models/vinculacion_lectura_model.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'version_id' not in texto and '__mapper_args__' not in texto
