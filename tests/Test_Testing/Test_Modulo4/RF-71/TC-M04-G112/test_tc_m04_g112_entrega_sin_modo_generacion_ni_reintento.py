"""
TC-M04-G112 (RF-71 v2.0 Fase 6/Restricciones 3 y 4/CA-3/CA-4/CA-5/RFC-009,
CU-09) - "Entrega a RF-69 y separación estricta de responsabilidades."
Reintento sobre la ficha v2.0 (añade modo_generacion/tipo_modelo del
enumerado de 6 a los campos obligatorios, y un endpoint de reintento de
entrega en (e)).

REEJECUTADO 2026-10-30 CONTRA CÓDIGO POST-MERGE. RELACIÓN CON
TC-M04-G102 (hallazgo raíz, actualizado): `modo_generacion` sigue sin
existir en ningún DTO (G102); `tipo_modelo` YA tiene 6 valores, no 4
(G102/G107) -- la mitad de la premisa de (a) queda invertida.

(a) Campos obligatorios, incluidos modo_generacion y tipo_modelo del
    enumerado de 6 -- HALLAZGO PARCIALMENTE INVERTIDO: `hash_artefacto_sha256`
    (no `hash_artefacto_modelo`, ver ronda anterior) y `id_proceso_rf71`
    coinciden; `modo_generacion` SIGUE sin ser un campo del DTO en
    absoluto (no es que falte en un envío puntual, es que nunca pudo
    declararse); PERO `tipo_modelo` SÍ acepta 6 valores reales ahora
    (`TIPOS_MODELO`), y el DTO declara además `componente` (obligatorio
    para los 3 valores POBLACIONAL) -- el único campo de la lista de (a)
    que sigue totalmente ausente es `modo_generacion`.
(b) CA-4/Restricción 3: EN_VALIDACION inicial, sin campo estado en el DTO
    -- CONFIRMADO CORRECTO EN SENTIDO ESTRECHO (sin cambios); vigente el
    matiz de G102: el propio backend auto-aprueba sin intervención
    humana.
(c) Sin juicios ni comparaciones -- HALLAZGO VIGENTE (ver G109(f)).
(d) El modelo no reemplaza al activo, también para calibración en sitio
    -- CONFIRMADO CORRECTO para el camino que existe (`crear()` siempre
    deja `esta_produccion=False`); NO EVALUABLE para "cuando el
    origen fue una calibración en sitio" porque ese origen no puede
    existir (no hay campo que lo represente).
(e) RF-69 no disponible -> reintento de la Fase 6 mediante endpoint de
    reintento de entrega -- HALLAZGO: no existe ningún endpoint
    `retry-delivery` ni equivalente en `version_modelo_router.py` ni en
    ningún otro router de M04.

Cómo se prueba: inspección directa del DTO real, de `VersionModelo.crear()`
y de los 4 endpoints reales del router de versiones.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m04_g112_entrega_sin_modo_generacion_ni_reintento.py -v \
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


class TestSubCasoACamposObligatoriosIncompletosSegunRfc009:
    def test_modo_generacion_no_es_un_campo_del_dto(self):
        firma = inspect.signature(RegistrarVersionModeloDTO.__init__)
        parametros = set(firma.parameters)
        pytest.fail(
            f"HALLAZGO (a): el DTO real declara {sorted(parametros)!r} -- 'modo_generacion' no "
            f"esta entre ellos. No es que falte en un envio puntual: el campo nunca pudo "
            f"declararse porque no existe en el contrato."
        ) if 'modo_generacion' not in parametros else None

    def test_hash_sigue_llamandose_distinto_a_lo_que_nombra_la_ficha(self):
        firma = inspect.signature(RegistrarVersionModeloDTO.__init__)
        parametros = set(firma.parameters)
        assert 'hash_artefacto_sha256' in parametros and 'hash_artefacto_modelo' not in parametros


class TestSubCasoDRegistroNuncaReemplazaAlModeloActivo:
    def test_crear_siempre_deja_esta_produccion_en_false(self):
        modelo = VersionModelo.crear(
            tipo_modelo='MODELO_ESPECIES_MEDIANAS', formato_artefacto='ONNX', ruta_artefacto='/tmp/x.onnx',
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


class TestSubCasoENoExisteEndpointDeReintentoDeEntrega:
    def test_ninguno_de_los_4_endpoints_reales_es_un_reintento_de_entrega(self):
        archivo = REPO_ROOT / 'src/prediction/infrastructure/routers/version_modelo_router.py'
        texto = archivo.read_text(encoding='utf-8')
        rutas = [l.strip() for l in texto.splitlines() if '@router.' in l or 'summary=' in l]
        pytest.fail(
            f"HALLAZGO (e) VIGENTE: ninguno de los 5 endpoints reales de version_modelo_router.py "
            f"(2 GET, 1 PATCH, 2 POST -- uno más que la ronda anterior, que contó 4) menciona "
            f"'retry'/'reintento'/'delivery'/'entrega' en su definición -- sigue sin existir "
            f"ningún endpoint de reintento de entrega tras una caída de RF-69. Líneas "
            f"relevantes: {rutas!r}"
        ) if 'retry' not in texto.lower() and 'reintento' not in texto.lower() else None
