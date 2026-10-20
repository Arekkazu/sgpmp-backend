"""
TC-M04-G109 (RF-71 Fases 4-5/Restricciones 3 y 12/CA-11, CU-06) -
"Entrenamiento y cálculo de métricas." Grupo existente de RF-71.

RELACIÓN CON TC-M04-G102 (hallazgo raíz): no existe ningún endpoint de
entrenamiento (confirmado en G102); "el entrenamiento se ejecuta con el
algoritmo especificado" no es evaluable porque no hay ningún "algoritmo
especificado" -- RF-69 solo recibe el artefacto YA entrenado. Pero el
CONTRATO de métricas que RF-69 exige al recibirlo SÍ es código real y
verificable, y aquí aparecen dos hallazgos genuinos de nomenclatura e
interpretación.

Código bajo prueba:
    src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py
    src/prediction/domain/entities/version_modelo.py

HALLAZGO (d), Restricción 12 invertida: la ficha exige "nomenclatura
unificada (f1_score_global, recall_clase_riesgo_alto, precision_global,
accuracy); ningún campo de salida usa variantes como 'precision' o
'accuracy' SIN CALIFICADOR". Pero `_METRICAS_REQUERIDAS` en el código
real exige literalmente la clave `"accuracy"` -- exactamente la variante
"sin calificador" que la Restricción 12 dice que NUNCA debe aparecer. El
contrato real contradice su propia restricción nombrada.

HALLAZGO (e), Restricción 3 violada: la ficha exige que "la salida NO
contiene juicios, interpretaciones ni comparaciones contra umbrales".
Pero `VersionModelo.validar_y_asignar_estado()` escribe en
`detalle_validacion` (un campo que SÍ se persiste y se expone, ver
`_snapshot()`) un mensaje como `"f1_score_global=0.75 < umbral requerido
0.80"` -- una comparación textual explícita contra un umbral, exactamente
lo que la Restricción 3 prohíbe.

(a) Formato ONNX/TF SavedModel -- CONFIRMADO (sin hallazgo):
    `_detectar_formato()` distingue correctamente por magic bytes
    (`\\x08` ONNX, `\\x0a` TF SavedModel) y rechaza cualquier otro valor.
(b) Incompatibilidad de algoritmo -> REENTRENAMIENTO_FALLIDO -- NO
    APLICA: no existe ningún concepto de "algoritmo" en el contrato de
    RF-69; el artefacto llega ya entrenado.
(c) CA-11, métricas para clases 0,1,2,3 en TODA ejecución --
    PARCIALMENTE CONFIRMADO, CON HALLAZGO: `_METRICAS_REQUERIDAS` exige
    que `recall_por_clase` y `matriz_confusion` existan como claves, pero
    `_validar_metricas()` nunca valida su CONTENIDO -- no verifica que
    `recall_por_clase` tenga entradas para las clases 0, 1, 2 y 3; un
    `recall_por_clase={}` vacío pasa la validación sin error.
(d) Restricción 12, nomenclatura unificada -- HALLAZGO: ver arriba.
(e) Restricción 3, sin juicios ni comparaciones -- HALLAZGO: ver arriba.

Cómo se prueba: inspección directa de `_METRICAS_REQUERIDAS` y
`validar_y_asignar_estado()`, más una llamada real a
`_validar_metricas()`/`validar_y_asignar_estado()` con datos sintéticos.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m04_g109_contrato_de_metricas_y_nomenclatura.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G109.html --self-contained-html
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.prediction.application.use_cases.versiones_modelo.registrar_version_modelo_use_case import (
    RegistrarVersionModeloUseCase,
)
from src.prediction.domain.entities.version_modelo import VersionModelo

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestSubCasoAFormatoConfirmadoCorrecto:
    @pytest.mark.parametrize('magic, esperado', [(b'\x08\x01', 'ONNX'), (b'\x0a\x01', 'TENSORFLOW_SAVED_MODEL')])
    def test_deteccion_de_formato_por_magic_bytes(self, magic, esperado):
        uc = RegistrarVersionModeloUseCase(
            db=MagicMock(), repo=MagicMock(), auditoria_repo=MagicMock(), variable_port=MagicMock(),
        )
        assert uc._detectar_formato(magic) == esperado


class TestSubCasoCContenidoDeMetricasPorClaseNuncaSeValida:
    def test_recall_por_clase_vacio_pasa_la_validacion_sin_error(self):
        uc = RegistrarVersionModeloUseCase(
            db=MagicMock(), repo=MagicMock(), auditoria_repo=MagicMock(), variable_port=MagicMock(),
        )
        metricas = {
            "f1_score_global": "0.9", "recall_clase_riesgo_alto": "0.9", "precision_global": "0.9",
            "accuracy": "0.9", "roc_auc_score": "0.9", "recall_por_clase": {}, "matriz_confusion": {},
        }
        resultado = uc._validar_metricas(metricas)
        pytest.fail(
            f"HALLAZGO (c): _validar_metricas() acepto recall_por_clase={{}} (vacio, sin ninguna "
            f"de las 4 clases 0/1/2/3 que CA-11 exige) sin lanzar ningun error -- "
            f"resultado={resultado['recall_por_clase']!r}. Solo se verifica que la CLAVE exista, "
            f"nunca su contenido."
        ) if resultado['recall_por_clase'] == {} else None


class TestSubCasoDNomenclaturaUnificadaViolaSuPropiaRestriccion:
    def test_accuracy_sin_calificador_es_exigido_literalmente(self):
        archivo = REPO_ROOT / 'src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (d): _METRICAS_REQUERIDAS exige literalmente la clave 'accuracy' -- "
            "exactamente la variante 'sin calificador' que la Restriccion 12 (citada por esta "
            "ficha) dice que nunca debe usarse. El contrato real contradice la restriccion que "
            "el mismo RF declara."
        ) if '"accuracy"' in texto else None


class TestSubCasoEDetalleValidacionEsUnaComparacionContraUmbral:
    def test_detalle_validacion_contiene_una_comparacion_textual_contra_el_umbral(self):
        modelo = VersionModelo.crear(
            tipo_modelo='ESPECIES_MEDIANAS', formato_artefacto='ONNX', ruta_artefacto='/tmp/x.onnx',
            tamanio_artefacto_bytes=10, hash_artefacto_sha256='a' * 64, dataset_entrenamiento_hash='b' * 64,
            id_proceso_rf71=__import__('uuid').uuid4(), f1_score=Decimal('0.75'),
            recall_clase_riesgo_alto=Decimal('0.90'), precision_modelo=Decimal('0.75'),
            accuracy=Decimal('0.75'), roc_auc_score=Decimal('0.75'),
            recall_por_clase={}, matriz_confusion={}, compatibilidad_variables=[],
            fecha_entrenamiento=datetime(2026, 10, 20, tzinfo=timezone.utc),
        )
        modelo.validar_y_asignar_estado()
        assert modelo.estado_version == 'RECHAZADO'
        pytest.fail(
            f"HALLAZGO (e): detalle_validacion='{modelo.detalle_validacion}' es una comparacion "
            f"textual explicita contra un umbral numerico, persistida y expuesta via _snapshot() "
            f"-- exactamente lo que la Restriccion 3 ('la salida NO contiene juicios, "
            f"interpretaciones ni comparaciones contra umbrales') prohibe."
        )
