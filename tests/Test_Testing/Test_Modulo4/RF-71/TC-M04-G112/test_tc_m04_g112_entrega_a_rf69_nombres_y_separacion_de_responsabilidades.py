"""
TC-M04-G112 (RF-71 Fase 6/Restricciones 3 y 4/CA-3/CA-4/CA-5, CU-09) -
"Entrega a RF-69 y separación estricta de responsabilidades." Grupo
existente de RF-71.

RELACIÓN CON TC-M04-G102/G109 (hallazgos ya establecidos): el estado
inicial EN_VALIDACION puede transicionar a APROBADO automáticamente en el
mismo registro (G102); `detalle_validacion` contiene una comparación
contra umbral (G109(e)). Este TC confirma, además, los nombres de campo
reales y el aislamiento correcto de la producción.

(a) Campos obligatorios: `hash_artefacto_modelo`, métricas completas,
    `id_proceso_rf71` -- HALLAZGO DE NOMBRE: el campo real es
    `hash_artefacto_sha256`, no `hash_artefacto_modelo` (mismo patrón de
    discrepancia de nombres que TC-M04-G109(d) para las métricas);
    `id_proceso_rf71` sí coincide exactamente.
(b) CA-4/Restricción 3: estado inicial EN_VALIDACION; RF-71 NO asigna ni
    modifica estados; intentar enviar estado APROBADO/RECHAZADO ->
    rechazado -- CONFIRMADO CORRECTO EN SENTIDO ESTRECHO: `RegistrarVersionModeloDTO`
    no declara ningún campo `estado`/`estado_version` -- no hay ningún
    vector para "enviarlo" porque el campo no existe en el contrato. Pero
    en sentido amplio sigue vigente el hallazgo de TC-M04-G102: el propio
    backend (no el llamador) asigna APROBADO automáticamente nada más
    registrar, sin intervención humana -- la letra de (b) se cumple, su
    espíritu no.
(c) Sin juicios ni comparaciones contra umbrales -- HALLAZGO (ya
    documentado en TC-M04-G109(e)): `detalle_validacion` sí contiene una
    comparación textual contra el umbral.
(d) CA-5/Restricción 4: el modelo entregado no reemplaza al activo; tras
    una ejecución completa, el modelo en producción sigue siendo el
    anterior -- CONFIRMADO CORRECTO: `VersionModelo.crear()` siempre
    construye con `esta_produccion=False`; solo `activar()` (un caso de
    uso DISTINTO, `activar_version_modelo_use_case.py`, que exige estado
    APROBADO + notas de validación clínica) puede ponerlo en producción.
    El registro nunca reemplaza nada por sí mismo.
(e) RF-69 no disponible -> reintento sin reentrenar desde cero -- NO
    EVALUABLE: no existe ningún "RF-71" que pueda reintentar (ver G102);
    `POST /api/v1/m04/models` ES RF-69 mismo, por lo que "RF-69 no
    disponible" equivale a que este mismo endpoint esté caído -- no hay
    ningún mecanismo de cola/reintento del lado del backend para su
    propia indisponibilidad.

Cómo se prueba: inspección directa del DTO real y de `VersionModelo.crear()`/
`activar()`.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m04_g112_entrega_a_rf69_nombres_y_separacion_de_responsabilidades.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G112.html --self-contained-html
"""
from __future__ import annotations

import inspect
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from src.prediction.domain.entities.version_modelo import VersionModelo
from src.prediction.infrastructure.dto.registrar_version_modelo_dto import RegistrarVersionModeloDTO

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestSubCasoANombreDeCampoHashNoCoincide:
    def test_el_campo_real_es_hash_artefacto_sha256_no_hash_artefacto_modelo(self):
        firma = inspect.signature(RegistrarVersionModeloDTO.__init__)
        parametros = set(firma.parameters)
        pytest.fail(
            f"HALLAZGO (a): el DTO real declara {sorted(parametros)!r} -- el campo es "
            f"'hash_artefacto_sha256', no 'hash_artefacto_modelo' como nombra esta ficha. "
            f"id_proceso_rf71 si coincide exactamente."
        ) if 'hash_artefacto_sha256' in parametros and 'hash_artefacto_modelo' not in parametros else None


class TestSubCasoBNoHayCampoEstadoEnElDto:
    def test_el_dto_no_declara_ningun_campo_de_estado(self):
        firma = inspect.signature(RegistrarVersionModeloDTO.__init__)
        parametros = set(firma.parameters)
        assert 'estado' not in parametros and 'estado_version' not in parametros


class TestSubCasoDRegistroNuncaReemplazaAlModeloActivo:
    def test_crear_siempre_deja_esta_produccion_en_false(self):
        modelo = VersionModelo.crear(
            tipo_modelo='ESPECIES_MEDIANAS', formato_artefacto='ONNX', ruta_artefacto='/tmp/x.onnx',
            tamanio_artefacto_bytes=10, hash_artefacto_sha256='a' * 64, dataset_entrenamiento_hash='b' * 64,
            id_proceso_rf71=__import__('uuid').uuid4(), f1_score=Decimal('0.90'),
            recall_clase_riesgo_alto=Decimal('0.90'), precision_modelo=Decimal('0.90'),
            accuracy=Decimal('0.90'), roc_auc_score=Decimal('0.90'),
            recall_por_clase={}, matriz_confusion={}, compatibilidad_variables=[],
            fecha_entrenamiento=datetime(2026, 10, 20, tzinfo=timezone.utc),
        )
        modelo.validar_y_asignar_estado()
        assert modelo.estado_version == 'APROBADO'
        assert modelo.esta_produccion is False

    def test_activar_exige_notas_de_validacion_clinica_antes_de_produccion(self):
        archivo = REPO_ROOT / 'src/prediction/domain/entities/version_modelo.py'
        texto = archivo.read_text(encoding='utf-8')
        bloque_activar = texto.split('def activar(')[1].split('def deprecar(')[0]
        assert 'notas_validacion' in bloque_activar
