"""
TC-M04-G111 (RF-71 Fase 4/Restricción 15/CA-19, CU-08) - "Compatibilidad
del modelo con el motor de inferencia." Grupo existente de RF-71.

Código bajo prueba:
    src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py
    (método `_validar_variables`)

HALLAZGO PRINCIPAL: la única validación de compatibilidad que existe
(`_validar_variables()`) comprueba ÚNICAMENTE que cada id de
`compatibilidad_variables` exista y esté activo en el catálogo I3P-1
(`self._variable_port.obtener_ids_activos(ids)`). No valida NINGUNO de
los 5 criterios que pide esta ficha: ni el orden de las variables, ni su
tipo, ni la dimensionalidad de entrada/salida, ni la correspondencia con
`tipo_modelo`. Dos artefactos con las MISMAS variables en distinto orden,
o con tipos incompatibles, pasan esta validación exactamente igual que
uno perfectamente compatible.

(a) Formato del artefacto soportado -- CONFIRMADO CORRECTO (ya probado en
    TC-M04-G109(a)): `_detectar_formato()` sí distingue ONNX/TF
    SavedModel correctamente. Es el único de los 5 criterios de
    compatibilidad que sí se verifica, aunque por una función distinta
    a `_validar_variables`.
(b) Estructura de entrada (features esperadas) -- HALLAZGO: solo se
    verifica que los IDs existan y estén activos; no hay ninguna
    comprobación de que el CONJUNTO de features coincida con lo que el
    motor de inferencia espera para ese `tipo_modelo`.
(c) Orden y tipo de las variables -- HALLAZGO: `_validar_variables` no
    lee ningún tipo de dato de las variables, solo sus IDs; el orden de
    la lista `compatibilidad_variables` nunca se compara contra nada (se
    guarda tal cual se recibe).
(d) Dimensionalidad de entrada/salida -- HALLAZGO: no existe ningún
    parseo del artefacto ONNX/TF para extraer su esquema de entrada/
    salida; la detección de formato solo lee 1 byte (magic number), no
    el grafo completo del modelo.
(e) Correspondencia con tipo_modelo declarado -- HALLAZGO: `_validar_variables`
    no recibe `tipo_modelo` como parámetro en absoluto -- no puede cruzar
    las variables contra el tipo de modelo aunque quisiera.
(f)/(g) Modelo compatible -> envío procede; validación antes de la
    entrega -- CONFIRMADO CORRECTO PERO TRIVIAL: como la única validación
    real es "¿existen los IDs?", prácticamente cualquier conjunto de IDs
    activos "pasa" -- la validación sí ocurre antes de guardar el
    artefacto (orden correcto en el código), pero verifica mucho menos
    de lo que (g) asume.

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
            f"HALLAZGO (e): _validar_variables{tuple(parametros)!r} no recibe tipo_modelo -- no "
            f"puede verificar correspondencia entre las variables y el tipo de modelo declarado."
        ) if 'tipo_modelo' not in parametros else None

    def test_no_hay_verificacion_de_orden_ni_tipo_de_dato(self):
        archivo = REPO_ROOT / 'src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        bloque = texto.split('def _validar_variables(')[1].split('def _guardar_artefacto(')[0]
        pytest.fail(
            "HALLAZGO (c): el cuerpo de _validar_variables solo convierte los IDs a entero y los "
            "compara contra obtener_ids_activos() -- no hay ninguna comparacion de orden (la "
            "lista se usa como conjunto, no como secuencia) ni de tipo de dato de cada variable."
        ) if 'orden' not in bloque.lower() and 'tipo' not in bloque.lower() else None

    def test_activos_pasa_la_validacion_sin_importar_el_orden_enviado(self):
        uc = RegistrarVersionModeloUseCase(
            db=MagicMock(), repo=MagicMock(), auditoria_repo=MagicMock(), variable_port=MagicMock(),
        )
        uc._variable_port.obtener_ids_activos.return_value = [3, 1, 2]
        uc._validar_variables([1, 2, 3])  # orden distinto al devuelto por el puerto -- no falla
        uc._validar_variables([3, 2, 1])  # orden inverso -- tampoco falla
        pytest.fail(
            "HALLAZGO (c): _validar_variables([1,2,3]) y _validar_variables([3,2,1]) pasan "
            "identicamente -- el orden de las variables nunca se verifica."
        )

    def test_no_hay_parseo_de_dimensionalidad_del_artefacto(self):
        archivo = REPO_ROOT / 'src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (d): no hay ninguna libreria de parseo de ONNX/TensorFlow ('onnx', "
            "'tensorflow', 'onnxruntime') importada en este archivo -- _detectar_formato() solo "
            "lee el primer byte (magic number), nunca el grafo completo del modelo para extraer "
            "su dimensionalidad de entrada/salida."
        ) if 'import onnx' not in texto and 'import tensorflow' not in texto else None
