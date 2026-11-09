"""
TC-M04-G102 (RF-71 v2.0 Fases 1-7/CA-3/RNF-12/RFC-009, CU-01) - "Pipeline
completo de extremo a extremo con trigger MANUAL y modo_generacion =
REENTRENAMIENTO (camino feliz)." Caso base del grupo RF-71 (reintento
sobre la ficha v2.0, que introduce `modo_generacion` y el enumerado de 6
valores de `tipo_modelo` vía RFC-009). Reemplaza la versión anterior de
este TC (ficha v1.x, sin RFC-009).

Código bajo prueba: main.py (routers de M04 realmente registrados),
alembic/baseline/esquema_baseline.sql, y
src/prediction/application/use_cases/versiones_modelo/
registrar_version_modelo_use_case.py + domain/entities/version_modelo.py.

HALLAZGO PRINCIPAL, RAÍZ, SIN CAMBIOS RESPECTO A LA RONDA ANTERIOR: el
pipeline de reentrenamiento que la ficha asume
(`POST /api/v1/m04/retrainings`, `GET /api/v1/m04/retrainings/{id_proceso}`,
etc. -- nótese que la v2.0 incluso cambió el nombre de la ruta de
`/retraining` a `/retrainings` y de `/models` a `/model-versions`, sin que
ninguna de las dos formas exista) sigue sin existir en ningún lugar
alcanzable por HTTP. `main.py` registra los mismos 7 routers de M04 que
en la ronda anterior; ninguno expone "retrainings". La infraestructura
SQL huérfana (`ciclos_entrenamientos`, `sp_iniciar_ciclo_reentrenamiento`)
tampoco cambió.

HALLAZGO NUEVO, ESPECÍFICO DE ESTA RONDA (RFC-009 no implementada en
absoluto): ninguno de los conceptos que la RFC-009 introduce existe en
el código real:
  - `modo_generacion`: 0 coincidencias en todo `src/` (ni como campo de
    DTO, ni como columna de modelo, ni en el DDL baseline).
  - `CALIBRACION_EN_SITIO`: 0 coincidencias.
  - `score_anomalia` / `calibration_readiness`: 0 coincidencias.
  - El enumerado de `tipo_modelo` sigue teniendo 4 valores, no 6:
    `_TIPOS_VALIDOS = {"ESPECIES_PEQUEÑAS", "ESPECIES_MEDIANAS",
    "ESPECIES_GRANDES", "CONTAGIO"}` -- sin `POBLACIONAL` ni ningún otro
    valor nuevo.
  - La dependencia que la ficha declara en "RF-24" para habilitar
    `CALIBRACION_EN_SITIO` ("las tres auditorías de M09") no corresponde
    a nada real: el RF-24 que existe de verdad en este backend
    (`src/configuration/domain/entities/calibracion.py`) es calibración
    de GANANCIA/OFFSET de un sensor individual -- no tiene ningún
    concepto de "auditoría", "tercera auditoría" ni "72 horas de datos
    limpios". La ficha construye un caso sobre una dependencia que no
    existe con ese significado en el sistema real.

Esto significa que absolutamente ninguno de los subescenarios que
mencionan `modo_generacion`/RFC-009 en el resto del lote (G103-G123)
tiene ningún código que ejecutar -- no es solo que falte la orquestación
del reentrenamiento (ya sabíamos eso); es que la extensión completa que
motiva esta segunda ronda de pruebas no se escribió.

(a)/(b)/(c) -- NO EJECUTABLES: no existe ningún endpoint que inicie un
    proceso de reentrenamiento (idéntico hallazgo a la ronda anterior).
(d) "estado EN_VALIDACION y nunca APROBADO" -- HALLAZGO VIGENTE (mismo
    que la ronda anterior): `RegistrarVersionModeloUseCase.execute()`
    sigue llamando a `validar_y_asignar_estado()`, que puede dejar el
    modelo en APROBADO automáticamente, sin revisión humana, si
    `f1_score_global >= 0.80` y `recall_clase_riesgo_alto >= 0.85`.
(e) "Repetir con un Veterinario como iniciador" -- NO EVALUABLE: sigue
    sin existir ningún "iniciador" vía API de usuario.
(f) Trazabilidad end-to-end -- NO EVALUABLE más allá del único tramo real
    (registro → RF-69), igual que antes.
(g) RFC-009: "modo_generacion viaja en el payload, queda persistido... una
    versión registrada sin modo_generacion es un defecto bloqueante" --
    HALLAZGO DIRECTO: el defecto que la propia ficha declara bloqueante
    ya se cumple hoy, de la forma más completa posible -- no es que
    `modo_generacion` se pierda alguna vez, es que el campo NUNCA llegó
    a existir. `RegistrarVersionModeloDTO` no lo declara;
    `VersionModelo` no lo almacena; ninguna versión, de ningún tipo,
    tiene jamás este metadato.

Cómo se prueba: grep exhaustivo sobre src/ y el DDL baseline + inspección
directa de `_TIPOS_VALIDOS` y de `Calibracion` (RF-24 real).

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m04_g102_pipeline_no_existe_y_rfc009_no_implementada.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G102.html --self-contained-html
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


def _grep_src(termino: str) -> list[str]:
    return [
        str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
        if termino in p.read_text(encoding='utf-8', errors='ignore')
    ]


class TestHallazgoRaizVigenteNoHayEndpointDeRetraining:
    def test_main_sigue_sin_registrar_ningun_router_de_retrainings(self):
        texto_main = (REPO_ROOT / 'main.py').read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO RAIZ (vigente): main.py no registra ningun router 'retrainings' ni "
            "'model-versions' -- los nombres de ruta que introduce la ficha v2.0 tampoco "
            "existen, igual que las rutas de la v1.x."
        ) if 'retrainings' not in texto_main.lower() else None


class TestHallazgoNuevoRfc009NoImplementadaEnAbsoluto:
    @pytest.mark.parametrize('termino', [
        'modo_generacion', 'CALIBRACION_EN_SITIO', 'score_anomalia', 'calibration_readiness',
    ])
    def test_concepto_de_rfc009_no_existe_en_ningun_lado(self, termino):
        archivos = _grep_src(termino)
        texto_ddl = (REPO_ROOT / 'alembic/baseline/esquema_baseline.sql').read_text(
            encoding='utf-8', errors='ignore')
        pytest.fail(
            f"HALLAZGO (g): '{termino}' (concepto central de la RFC-009) no existe en ningun "
            f"archivo de src/ (encontrados: {archivos or 'ninguno'}) ni en el DDL baseline. La "
            f"extension completa que motiva esta ronda de pruebas no fue implementada."
        ) if not archivos and termino not in texto_ddl else None

    def test_tipo_modelo_sigue_teniendo_4_valores_no_6(self):
        archivo = REPO_ROOT / 'src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO: _TIPOS_VALIDOS sigue siendo "
            "{'ESPECIES_PEQUEÑAS','ESPECIES_MEDIANAS','ESPECIES_GRANDES','CONTAGIO'} -- 4 "
            "valores, no el enumerado de 6 que la RFC-009 asume (incluido POBLACIONAL)."
        ) if '_TIPOS_VALIDOS = {"ESPECIES_PEQUEÑAS", "ESPECIES_MEDIANAS", "ESPECIES_GRANDES", "CONTAGIO"}' in texto else None

    def test_rf24_real_es_calibracion_de_sensor_no_auditorias_de_m09(self):
        archivo = REPO_ROOT / 'src/configuration/domain/entities/calibracion.py'
        texto = archivo.read_text(encoding='utf-8')
        nombres_campos = {f.name for f in __import__('dataclasses').fields(VersionModelo)}  # noqa: F841 (solo para contexto)
        pytest.fail(
            "HALLAZGO: el RF-24 real (Calibracion, en src/configuration) es un registro de "
            "ganancia/offset por SENSOR individual -- no tiene ningun concepto de 'auditoria', "
            "'tercera auditoria' ni 'ventana de 72 horas de datos limpios'. La dependencia que "
            "la ficha declara para CALIBRACION_EN_SITIO no corresponde a nada real con ese "
            "significado."
        ) if 'registro de calibración de un sensor' in texto.lower() or 'calibración de un sensor' in texto else None

    def test_dto_de_registro_no_declara_modo_generacion(self):
        firma = inspect.signature(RegistrarVersionModeloDTO.__init__)
        parametros = set(firma.parameters)
        pytest.fail(
            f"HALLAZGO (g): RegistrarVersionModeloDTO no declara 'modo_generacion' -- "
            f"parametros reales: {sorted(parametros)!r}. El 'defecto bloqueante de "
            f"trazabilidad' que (g) pide verificar que no ocurra, ocurre siempre: ninguna "
            f"version, de ningun tipo, puede llevar nunca este metadato."
        ) if 'modo_generacion' not in parametros else None


class TestHallazgoVigenteAutoAprobacionSinRevisionHumana:
    def test_validar_y_asignar_estado_puede_producir_aprobado_sin_intervencion_humana(self):
        modelo = VersionModelo.crear(
            tipo_modelo='ESPECIES_MEDIANAS', formato_artefacto='ONNX', ruta_artefacto='/tmp/x.onnx',
            tamanio_artefacto_bytes=100, hash_artefacto_sha256='a' * 64, dataset_entrenamiento_hash='b' * 64,
            id_proceso_rf71=__import__('uuid').uuid4(), f1_score=Decimal('0.85'),
            recall_clase_riesgo_alto=Decimal('0.90'), precision_modelo=Decimal('0.85'),
            accuracy=Decimal('0.85'), roc_auc_score=Decimal('0.90'),
            recall_por_clase={}, matriz_confusion={}, compatibilidad_variables=[],
            fecha_entrenamiento=datetime(2026, 10, 20, tzinfo=timezone.utc),
        )
        modelo.validar_y_asignar_estado()
        assert modelo.estado_version == 'APROBADO'
        pytest.fail(
            "HALLAZGO (d), vigente desde la ronda anterior: con metricas que superan los "
            "umbrales, validar_y_asignar_estado() deja el modelo en APROBADO en el mismo "
            "registro, sin intervencion humana -- exactamente lo que (d) pide verificar que "
            "nunca ocurre."
        )
