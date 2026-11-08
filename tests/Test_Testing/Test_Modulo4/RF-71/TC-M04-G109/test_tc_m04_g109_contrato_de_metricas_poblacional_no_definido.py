"""
TC-M04-G109 (RF-71 v2.0 Fases 4-5/Restricciones 3 y 12/CA-11/RFC-009,
CU-06) - "Entrenamiento y contrato de métricas, diferenciado por
tipo_modelo." Reintento sobre la ficha v2.0 (añade el subescenario (d)
sobre POBLACIONAL y la exigencia de incorporar score_anomalia a la
nomenclatura unificada).

RELACIÓN CON TC-M04-G102 (hallazgo raíz): `tipo_modelo` sigue sin incluir
POBLACIONAL (G102); el contrato de métricas real asume siempre un
clasificador supervisado.

Código bajo prueba:
    src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py

HALLAZGO (d), vigente y agravado por la RFC-009: `_METRICAS_REQUERIDAS`
exige SIEMPRE las 7 claves (`f1_score_global`, `recall_clase_riesgo_alto`,
`precision_global`, `accuracy`, `roc_auc_score`, `recall_por_clase`,
`matriz_confusion`) sin ninguna rama por `tipo_modelo` -- no hay ningún
mecanismo para que estos campos "viajen explícitamente como no
aplicables" para un modelo sin etiquetas, como pide (d): si
`tipo_modelo` pudiera ser POBLACIONAL, el registro fallaría con
`METRICAS_INCOMPLETAS` en cualquier caso, porque el contrato exige las 7
claves sin excepción. No existe ningún campo `score_anomalia` en
`_METRICAS_REQUERIDAS` ni en `VersionModelo`.

(a) Formato ONNX/TF SavedModel -- CONFIRMADO CORRECTO (sin cambios, ver
    ronda anterior).
(b) Incompatibilidad de algoritmo -- NO APLICA: no existe concepto de
    "algoritmo" en el contrato de RF-69.
(c) CA-11, métricas para clases 0,1,2,3 -- PARCIALMENTE CONFIRMADO, CON
    HALLAZGO VIGENTE: solo se valida que las claves existan, nunca su
    contenido (ver ronda anterior, sin cambios).
(d) Conjunto de métricas para POBLACIONAL -- HALLAZGO: ver arriba --
    el contrato real no tiene ninguna variante para tipos sin etiquetas.
(e) Restricción 12, nomenclatura unificada + incorporar score_anomalia --
    HALLAZGO VIGENTE (`accuracy` sin calificador, ver ronda anterior) MÁS
    HALLAZGO NUEVO: `score_anomalia` no existe en ningún lado, por lo que
    no puede estar "incorporado a la nomenclatura unificada" porque la
    nomenclatura unificada real no tiene ningún campo para indicadores
    poblacionales.
(f) Restricción 3, sin juicios ni comparaciones -- HALLAZGO VIGENTE:
    `detalle_validacion` sigue conteniendo una comparación textual contra
    umbral (ver ronda anterior, sin cambios).

Cómo se prueba: inspección directa de `_METRICAS_REQUERIDAS` y de
`VersionModelo`, más una llamada real a `_validar_metricas()` omitiendo
las métricas supervisadas para simular un intento de registro
POBLACIONAL.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m04_g109_contrato_de_metricas_poblacional_no_definido.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G109.html --self-contained-html
"""
from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.prediction.application.use_cases.versiones_modelo.registrar_version_modelo_use_case import (
    RegistrarVersionModeloUseCase,
)
from src.prediction.domain.entities.version_modelo import VersionModelo
from src.shared.errors import BusinessRuleError

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestSubCasoDPoblacionalFallaElContratoSupervisadoSiempre:
    def test_metricas_requeridas_no_tiene_rama_por_tipo_modelo(self):
        uc = RegistrarVersionModeloUseCase(
            db=MagicMock(), repo=MagicMock(), auditoria_repo=MagicMock(), variable_port=MagicMock(),
        )
        metricas_sin_las_supervisadas = {}  # simula un modelo sin etiquetas, sin metricas de clase
        with pytest.raises(BusinessRuleError) as exc_info:
            uc._validar_metricas(metricas_sin_las_supervisadas)
        pytest.fail(
            f"HALLAZGO (d): _validar_metricas({{}}) (simulando un registro POBLACIONAL sin "
            f"metricas de clasificacion) falla con codigo '{exc_info.value.code}' -- el "
            f"contrato real exige las 7 claves supervisadas SIEMPRE, sin ninguna rama para "
            f"tipos sin etiquetas. No hay forma de que estos campos 'viajen como no "
            f"aplicables': el registro simplemente se rechaza por completo."
        ) if exc_info.value.code == 'METRICAS_INCOMPLETAS' else None

    def test_score_anomalia_no_existe_en_version_modelo(self):
        nombres_campos = {f.name for f in fields(VersionModelo)}
        assert 'score_anomalia' not in nombres_campos


class TestSubCasoENomenclaturaSigueViolandoSuPropiaRestriccion:
    def test_accuracy_sin_calificador_sigue_siendo_exigido(self):
        archivo = REPO_ROOT / 'src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (e), vigente: _METRICAS_REQUERIDAS sigue exigiendo literalmente la clave "
            "'accuracy' -- la variante 'sin calificador' que la Restriccion 12 prohibe."
        ) if '"accuracy"' in texto else None
