"""
TC-M04-G109 (RF-71 v2.0 Fases 4-5/Restricciones 3 y 12/CA-11/RFC-009,
CU-06) - "Entrenamiento y contrato de métricas, diferenciado por
tipo_modelo." Reintento sobre la ficha v2.0 (añade el subescenario (d)
sobre POBLACIONAL y la exigencia de incorporar score_anomalia a la
nomenclatura unificada).

REEJECUTADO 2026-10-30 CONTRA CÓDIGO POST-MERGE. RELACIÓN CON TC-M04-G102
(hallazgo raíz, actualizado): `tipo_modelo` SÍ incluye el paradigma
POBLACIONAL ahora (ver G102) -- el hallazgo (d) de esta ficha queda
CASI TOTALMENTE INVERTIDO como consecuencia directa.

Código bajo prueba:
    src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py

HALLAZGO (d) INVERTIDO: `execute()` se bifurca explícitamente por
paradigma ANTES de validar métricas --
`if es_poblacional(dto.tipo_modelo): metricas_poblacionales =
self._validar_metricas_poblacionales(...); metricas =
dict.fromkeys(_METRICAS_REQUERIDAS)` (las 7 claves supervisadas quedan
en `None`, explícitamente "no aplicables") `else: componente,
metricas_poblacionales = None, None`. Existe un método DEDICADO,
`_validar_metricas_poblacionales()`, con su propio contrato de 3 claves:
`calibracion_completada` (bool) + `tasa_falsos_positivos_rutina` +
`tasa_deteccion_eventos_clinicos` (`_TASAS_POBLACIONALES`). Esto es,
literalmente, lo que (d) pedía verificar que NO existiera: un conjunto de
métricas propio para POBLACIONAL, con los campos supervisados viajando
de forma explícita como no aplicables (`None`), en vez de forzar el
contrato de 7 claves.

(a) Formato ONNX/TF SavedModel -- CONFIRMADO CORRECTO (sin cambios).
(b) Incompatibilidad de algoritmo -- NO APLICA: no existe concepto de
    "algoritmo" en el contrato de RF-69 (sin cambios).
(c) CA-11, métricas para clases 0,1,2,3 -- VIGENTE PARA LA RAMA
    SUPERVISADA: `_validar_metricas()` solo valida que las claves
    existan y estén en rango [0,1], nunca su contenido semántico por
    clase (sin cambios respecto a la ronda anterior).
(d) Conjunto de métricas para POBLACIONAL -- HALLAZGO INVERTIDO: ver
    arriba -- el contrato real SÍ tiene una variante dedicada para
    POBLACIONAL.
(e) Restricción 12, nomenclatura unificada + incorporar score_anomalia --
    HALLAZGO VIGENTE para `accuracy` sin calificador (sigue siendo clave
    literal de `_METRICAS_REQUERIDAS`); PERO MATIZADO para
    score_anomalia: el campo SÍ existe en el código real
    (`riesgo_contagio.py`, RF-68), solo que NO se incorporó al contrato
    de métricas de RF-69/RF-71 -- las tasas poblacionales usan su propia
    nomenclatura (`tasa_falsos_positivos_rutina`/
    `tasa_deteccion_eventos_clinicos`), no `score_anomalia`.
(f) Restricción 3, sin juicios ni comparaciones -- HALLAZGO VIGENTE:
    `detalle_validacion` sigue conteniendo comparaciones textuales contra
    umbral, también en la rama POBLACIONAL nueva
    (`"calibracion_completada=false: la calibración en sitio no está
    COMPLETADA"`).

Cómo se prueba: inspección directa de `_METRICAS_REQUERIDAS`,
`_TASAS_POBLACIONALES` y `_validar_metricas_poblacionales()`, más
llamadas reales a ambos validadores (supervisado y poblacional).

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


def _use_case():
    return RegistrarVersionModeloUseCase(
        db=MagicMock(), repo=MagicMock(), auditoria_repo=MagicMock(), variable_port=MagicMock(),
        aviso_port=MagicMock(),
    )


class TestSubCasoDPoblacionalSiTieneSuPropioContratoDeMetricas:
    def test_validar_metricas_poblacionales_existe_y_exige_su_propio_contrato(self):
        uc = _use_case()
        with pytest.raises(BusinessRuleError) as exc_info:
            uc._validar_metricas_poblacionales({})
        pytest.fail(
            f"HALLAZGO (d) INVERTIDO: _validar_metricas_poblacionales({{}}) falla con codigo "
            f"'{exc_info.value.code}' porque faltan SUS PROPIAS claves "
            f"(calibracion_completada/tasa_falsos_positivos_rutina/tasa_deteccion_eventos_"
            f"clinicos) -- es un metodo DEDICADO, distinto de _validar_metricas() (el "
            f"supervisado de 7 claves). La ronda anterior afirmo que 'no existe ninguna "
            f"variante para tipos sin etiquetas'; si existe."
        ) if exc_info.value.code == 'METRICAS_INCOMPLETAS' else None

    def test_validar_metricas_poblacionales_acepta_el_contrato_correcto(self):
        uc = _use_case()
        resultado = uc._validar_metricas_poblacionales({
            'calibracion_completada': True,
            'tasa_falsos_positivos_rutina': 0.05,
            'tasa_deteccion_eventos_clinicos': 0.92,
        })
        assert resultado['calibracion_completada'] is True

    def test_la_rama_supervisada_recibe_las_7_claves_en_none_para_poblacional(self):
        """Confirma el mecanismo exacto que (d) pedia: dict.fromkeys(_METRICAS_REQUERIDAS)
        deja las 7 claves supervisadas en None (explicitamente no aplicables) para
        POBLACIONAL, en vez de forzar su contrato o simplemente omitirlas."""
        archivo = REPO_ROOT / 'src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (d) INVERTIDO, MECANISMO CONFIRMADO: 'metricas = "
            "dict.fromkeys(_METRICAS_REQUERIDAS)' aparece en el flujo POBLACIONAL de execute() "
            "-- las 7 claves supervisadas SI viajan explicitamente como None/no-aplicables para "
            "POBLACIONAL, exactamente como (d) pedia verificar que ocurriera."
        ) if 'metricas = dict.fromkeys(_METRICAS_REQUERIDAS)' in texto else None

    def test_score_anomalia_no_existe_en_version_modelo_ni_en_el_contrato_de_rf71(self):
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
