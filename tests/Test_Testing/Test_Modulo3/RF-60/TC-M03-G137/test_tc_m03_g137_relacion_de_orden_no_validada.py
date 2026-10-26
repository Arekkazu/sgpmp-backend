"""
TC-M03-G137 (RF-60 CA-19/Restricción 12/Precondición 3, CU-12) -
"Validación de la relación de orden entre parámetros temporales."

Código bajo prueba:
    src/configuration/application/use_cases/configuracion/actualizar_configuracion_use_case.py
    src/configuration/infrastructure/dto/actualizar_configuracion_dto.py
    src/configuration/infrastructure/routers/configuracion_global_router.py

HALLAZGO PRINCIPAL: el endpoint real de actualización de parámetros
(`PATCH /configuracion/parametros/{id}`, no `PUT /api/v1/config/thresholds`
como nombra la ficha) solo acepta dos campos:
`frecuencia_muestreo` y `heartbeat`. No existe ningún campo `margen` en
el contrato, y no existe NINGUNA validación de relación de orden entre
ellos (HB <= FM/2, margen >= max(HB, FM*0.5), FM >= 2*HB) -- cada valor
se valida de forma aislada (solo por su propio rango, vía los value
objects `FrecuenciaMuestreo`/`Heartbeat`), nunca en conjunto. Esto es
consistente con el hallazgo ya establecido de que RF-60 ni siquiera lee
estos campos para calcular sus umbrales (los umbrales son constantes
fijas, ver TC-M03-G132) -- la Restricción 12 que esta ficha pide
verificar protege un cálculo que el sistema real no hace.

(a) Rechazo con mensaje que identifique la restricción violada (HB=8/
    FM=10, margen=2 con HB=5/FM=10, FM=5 con HB=5) -- HALLAZGO: no hay
    ningún campo `margen`, y no existe ninguna validación cruzada
    HB-vs-FM -- cualquier combinación de `frecuencia_muestreo`/`heartbeat`
    que pase la validación individual de cada value object se acepta,
    sin importar la relación entre ambos.
(b) Configuraciones válidas en el límite exacto, con recálculo y
    previsualización de umbral_sin_senal/umbral_inactivo -- NO
    EVALUABLE: no existe ninguna "previsualización de umbral" -- RF-60
    nunca deriva sus umbrales de estos campos.
(c) Parametrización por tipo de dispositivo y por variable -- HALLAZGO:
    `ConfiguracionGlobal` es una entidad única y global (confirmado en
    rondas anteriores) -- no existe ninguna configuración por
    combinación dispositivo-variable.
(d) FM=5 con HB=5 debe ser RECHAZADO porque viola HB<=FM/2 -- HALLAZGO:
    como no existe ninguna validación de relación de orden, esta
    combinación (y cualquier otra) se aceptaría sin rechazo -- no por
    una inconsistencia entre la Precondición 3 y la Restricción 12 (que
    sigue siendo un punto válido a escalar sobre el documento del RF),
    sino porque ninguna de las dos reglas está implementada.

Cómo se prueba: inspección directa de `ActualizarConfiguracionDTO` y del
cuerpo de `ActualizarConfiguracionUseCase.execute()`.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g137_relacion_de_orden_no_validada.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G137.html --self-contained-html
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from src.configuration.application.use_cases.configuracion.actualizar_configuracion_use_case import (
    ActualizarConfiguracionUseCase,
)
from src.configuration.infrastructure.dto.actualizar_configuracion_dto import ActualizarConfiguracionDTO

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestSubCasoAyDNoHayValidacionDeRelacionDeOrden:
    def test_el_dto_no_tiene_campo_margen(self):
        campos = set(ActualizarConfiguracionDTO.model_fields.keys()) if hasattr(
            ActualizarConfiguracionDTO, 'model_fields') else set(inspect.signature(
                ActualizarConfiguracionDTO.__init__).parameters)
        pytest.fail(
            f"HALLAZGO (a): ActualizarConfiguracionDTO declara {sorted(campos)!r} -- no hay "
            f"ningun campo 'margen'."
        ) if 'margen' not in campos else None

    def test_el_use_case_no_valida_relacion_entre_frecuencia_y_heartbeat(self):
        archivo = REPO_ROOT / 'src/configuration/application/use_cases/configuracion/actualizar_configuracion_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (a)/(d): execute() nunca compara dto.frecuencia_muestreo contra "
            "dto.heartbeat -- cada uno se envuelve en su propio value object "
            "(FrecuenciaMuestreo/Heartbeat) sin ninguna validacion cruzada. Una combinacion "
            "FM=5/HB=5 (que (d) pide verificar que se rechace) se aceptaria igual que "
            "cualquier otra."
        ) if 'dto.frecuencia_muestreo < ' not in texto and 'dto.heartbeat <' not in texto and 'margen' not in texto else None


class TestSubCasoCConfiguracionEsUnicaYGlobal:
    def test_no_existe_parametrizacion_por_dispositivo_ni_variable(self):
        archivo = REPO_ROOT / 'src/configuration/application/use_cases/configuracion/actualizar_configuracion_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        firma = inspect.signature(ActualizarConfiguracionUseCase.execute)
        parametros = set(firma.parameters)
        pytest.fail(
            f"HALLAZGO (c): execute({sorted(parametros)!r}) no recibe ningun id_dispositivo ni "
            f"id_variable -- ConfiguracionGlobal es una entidad unica identificada solo por "
            f"id_configuracion_global."
        ) if 'id_dispositivo' not in parametros and 'id_variable' not in parametros else None

    def test_el_path_real_no_es_put_config_thresholds(self):
        archivo = REPO_ROOT / 'src/configuration/infrastructure/routers/configuracion_global_router.py'
        texto = archivo.read_text(encoding='utf-8')
        assert '/configuracion/parametros' in texto
