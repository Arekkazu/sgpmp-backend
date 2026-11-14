"""
TC-M04-G111 (RF-71 v2.0 Fase 4/Restricción 15/CA-19, CU-08) -
"Compatibilidad del modelo con el motor de inferencia." Reintento sobre
la ficha v2.0 (añade (e) correspondencia con el enumerado de 6 valores, y
(g) corrige la fuente de evidencia hacia el proceso de RF-71 en vez del
endpoint de RF-69).

REEJECUTADO 2026-10-30 CONTRA CÓDIGO POST-MERGE. RELACIÓN CON TC-M04-G102
(hallazgo raíz, actualizado): `tipo_modelo` YA TIENE 6 valores, no 4
(confirmado en G102/G107) -- esto invierte la premisa de (e), aunque no
su conclusión práctica (ver abajo).

Código bajo prueba:
    src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py
    (método `_validar_variables`)

HALLAZGO PRINCIPAL, VIGENTE: la única validación de compatibilidad que
existe (`_validar_variables()`) comprueba ÚNICAMENTE que cada id de
`compatibilidad_variables` exista y esté activo en el catálogo I3P-1. No
valida orden, tipo, dimensionalidad, ni correspondencia con `tipo_modelo`.

(a) Formato del artefacto -- CONFIRMADO CORRECTO (sin cambios).
(b)/(c)/(d) -- HALLAZGO VIGENTE: solo se verifica existencia de IDs, sin
    orden, tipo ni dimensionalidad.
(e) Correspondencia con tipo_modelo, incluidos los 2 valores nuevos del
    enumerado de 6 -- HALLAZGO VIGENTE EN SU CONCLUSIÓN, PREMISA
    CORREGIDA: el enumerado real SÍ tiene 6 valores ahora (confirmado en
    G102/G107, con nombres distintos a los que (e) anticipaba), así que
    los "2 valores nuevos" SÍ son entradas posibles del sistema -- pero
    `_validar_variables()` sigue sin recibir `tipo_modelo` en absoluto,
    así que sigue sin poder verificar correspondencia con NINGÚN valor
    del enumerado, ni con los 4 originales ni con los 2/6 reales.
(f) Modelo compatible -> envío procede -- CONFIRMADO CORRECTO PERO
    TRIVIAL (sin cambios).
(g) La validación ocurre antes de la entrega; la evidencia se toma del
    PROCESO DE RF-71 (no del endpoint de RF-69) -- NO EVALUABLE EN LA
    FORMA PEDIDA: no existe ningún "proceso de RF-71" observable del que
    tomar evidencia (confirmado en G102) -- la única validación real
    ocurre DENTRO del propio endpoint de RF-69 (`_validar_variables()`
    se ejecuta en `RegistrarVersionModeloUseCase.execute()`), no antes de
    invocarlo desde un proceso externo. La corrección de ruta que (g)
    introduce no cambia esta conclusión: ambas fuentes de evidencia
    (proceso de RF-71 o endpoint de RF-69) remiten, en la práctica, al
    mismo código, porque RF-71 no tiene su propia validación separada.

Cómo se prueba: inspección directa de la firma y el cuerpo de
`_validar_variables()`.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m04_g111_compatibilidad_solo_verifica_existencia.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G111.html --self-contained-html
"""
from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.prediction.application.use_cases.versiones_modelo.registrar_version_modelo_use_case import (
    RegistrarVersionModeloUseCase,
)

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestValidarVariablesSoloVerificaExistenciaYActividad:
    def test_la_firma_no_recibe_tipo_modelo(self):
        firma = inspect.signature(RegistrarVersionModeloUseCase._validar_variables)
        parametros = set(firma.parameters)
        pytest.fail(
            f"HALLAZGO (e) VIGENTE (premisa de 6 valores confirmada en G102/G107): "
            f"_validar_variables{tuple(parametros)!r} no recibe tipo_modelo -- no puede "
            f"verificar correspondencia con ningun valor del enumerado real de 6."
        ) if 'tipo_modelo' not in parametros else None

    def test_activos_pasa_la_validacion_sin_importar_el_orden_enviado(self):
        uc = RegistrarVersionModeloUseCase(
            db=MagicMock(), repo=MagicMock(), auditoria_repo=MagicMock(), variable_port=MagicMock(),
            aviso_port=MagicMock(),
        )
        uc._variable_port.obtener_ids_activos.return_value = [3, 1, 2]
        uc._validar_variables([1, 2, 3])
        uc._validar_variables([3, 2, 1])
        pytest.fail(
            "HALLAZGO (c): _validar_variables([1,2,3]) y _validar_variables([3,2,1]) pasan "
            "identicamente -- el orden de las variables nunca se verifica."
        )

    def test_no_hay_parseo_de_dimensionalidad_del_artefacto(self):
        archivo = REPO_ROOT / 'src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (d): no hay ninguna libreria de parseo de ONNX/TensorFlow importada en "
            "este archivo -- _detectar_formato() solo lee el primer byte."
        ) if 'import onnx' not in texto and 'import tensorflow' not in texto else None


class TestSubCasoGLaValidacionOcurreDentroDelEndpointDeRf69:
    def test_validar_variables_se_ejecuta_dentro_de_execute_de_registrar_version(self):
        archivo = REPO_ROOT / 'src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        bloque_execute = texto.split('def execute(')[1].split('def _verificar_clave_interna(')[0]
        pytest.fail(
            "HALLAZGO (g): self._validar_variables(...) se invoca dentro del propio metodo "
            "execute() de RegistrarVersionModeloUseCase (el endpoint de RF-69), no en un "
            "proceso externo de RF-71 que la preceda -- no existe tal proceso (G102). La "
            "distincion entre 'evidencia de RF-71' y 'evidencia de RF-69' que (g) introduce no "
            "aplica: ambas remiten al mismo codigo."
        ) if 'self._validar_variables(' in bloque_execute else None
