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

REEJECUTADO 2026-10-30 CONTRA CÓDIGO POST-MERGE (origin/test, merges
`5217e98b` 2026-10-29 + `d5d1488e` 2026-10-30). El hallazgo raíz se
mantiene en su forma estricta (no existe un endpoint que orqueste un
*reentrenamiento* de extremo a extremo), pero la premisa de que "RFC-009
no está implementada en absoluto" queda PARCIALMENTE INVERTIDA: el
merge del 2026-10-29 (ya presente, nunca revisado hasta ahora para
RF-71) trajo `src/shared/tipo_modelo.py` (RFC-009, autoría de los
commits `21e161c2`/`32229040`, "RF-15 v1.1"/"RF-20"), que SÍ implementa
el concepto central de "tres paradigmas" que pedía la ficha -- solo que
con nombres distintos a los que ésta anticipaba.

HALLAZGO RAÍZ, VIGENTE PERO MÁS PRECISO: no existe
`POST /api/v1/m04/retrainings` ni `/model-versions` -- `main.py` solo
registra `version_modelo_router` bajo el prefijo real
`/prediccion/modelos`. Pero a diferencia de la ronda anterior, ese router
SÍ es alcanzable por HTTP para el tramo de REGISTRO (no de orquestación):
expone `POST /prediccion/modelos` (registrar una versión ya entrenada,
multipart/form-data), 2×`GET` (listar/detalle) y `PATCH`
(activar/transicionar). Lo que sigue sin existir es el disparo/monitoreo
asíncrono de un *proceso de entrenamiento* (no hay `id_proceso` que
consultar, ni cancelación, ni reanudación -- eso se confirma TC a TC en
G113-G117/G122).

HALLAZGO INVERTIDO (taxonomía RFC-009): el enumerado de `tipo_modelo`
real (`TIPOS_MODELO` en `src/shared/tipo_modelo.py`) SÍ tiene 6 valores
-- `MODELO_AVES`, `MODELO_PORCINOS`, `MODELO_ACUICULTURA`,
`MODELO_ESPECIES_MEDIANAS`, `MODELO_ESPECIES_GRANDES`,
`MODELO_RIESGO_CONTAGIO` -- organizados en exactamente 3 paradigmas
(`POBLACIONAL`/`INDIVIDUAL`/`META`, vía `PARADIGMA_POR_TIPO_MODELO` y
`es_poblacional()`). La vieja constante `_TIPOS_VALIDOS` (4 valores,
clasificados por tamaño del animal) YA NO EXISTE en
`registrar_version_modelo_use_case.py` -- fue reemplazada por este
import: `from src.shared.tipo_modelo import COMPONENTES_POBLACIONAL,
TIPOS_MODELO, es_poblacional`. Los modelos `POBLACIONAL` (AVES/PORCINOS/
ACUICULTURA) ahora exigen un campo `componente` obligatorio
(`DETECTOR`/`SEGUIMIENTO`/`METRICAS`/`ANOMALIAS`, validado por
`_validar_componente()`), que es, en esencia, el mismo rol que la ficha
le pedía a `modo_generacion`/`CALIBRACION_EN_SITIO` -- organizar la
versión por "modo"/parte -- solo que resuelto para el problema de
reentrenamiento POBLACIONAL por componente, no para el de disparo de
reentrenamiento en sí.

HALLAZGOS QUE SE MANTIENEN VIGENTES, SIN CAMBIO, TRAS VERIFICAR CONTRA
EL CÓDIGO ACTUAL:
  - `modo_generacion` (el campo específico que la ficha pide para
    distinguir REENTRENAMIENTO de CALIBRACION_EN_SITIO): 0 coincidencias
    reales en `src/` ni en el DDL baseline. Sigue sin existir como campo
    de ningún DTO ni columna.
  - `CALIBRACION_EN_SITIO`: 0 coincidencias como valor reconocido en
    ningún punto del sistema (confirmado también contra
    `sp_iniciar_ciclo_reentrenamiento`, que solo acepta
    PROGRAMADO/MANUAL/DEGRADACION, ver G106/G115/G122).
  - `calibration_readiness`: 0 coincidencias (no existe ningún endpoint
    de verificación previa de auditorías, ver G123).
  - La dependencia que la ficha declara en "RF-24" para habilitar
    `CALIBRACION_EN_SITIO` ("las tres auditorías de M09") sigue sin
    corresponder a nada real: el RF-24 real
    (`src/configuration/domain/entities/calibracion.py`, sin cambios en
    este pull) es calibración de GANANCIA/OFFSET de un sensor individual
    -- sin ningún concepto de "auditoría" ni "72 horas de datos limpios".
  - `score_anomalia`: SÍ existe en el código real, pero NO en el
    contrato de RF-71/RF-69 que esta ficha evalúa -- vive en
    `src/prediction/domain/entities/riesgo_contagio.py` (RF-68, modelo
    de riesgo de contagio, un concepto distinto). No se incorporó a
    `VersionModelo` ni a `_METRICAS_REQUERIDAS` (ver G109).

(a)/(b)/(c) -- NO EJECUTABLES: sigue sin existir ningún endpoint que
    DISPARE un proceso de reentrenamiento (solo existe el REGISTRO de un
    modelo ya entrenado externamente).
(d) "estado EN_VALIDACION y nunca APROBADO" -- HALLAZGO VIGENTE, CON
    MECANISMO ACTUALIZADO: `VersionModelo.validar_y_asignar_estado()`
    ahora se bifurca por paradigma -- para `POBLACIONAL` exige
    `metricas_poblacionales['calibracion_completada'] is True`; para
    `INDIVIDUAL`/`META` sigue exigiendo `f1_score >= 0.80` y
    `recall_clase_riesgo_alto >= 0.85` -- pero en AMBAS ramas, si se
    cumple la condición, el modelo queda `APROBADO` en el mismo método,
    sin ninguna intervención humana. El hallazgo de fondo (auto-
    aprobación sin revisión) no cambió, solo el criterio que la activa.
(e) "Repetir con un Veterinario como iniciador" -- NO EVALUABLE: sigue
    sin existir ningún "iniciador" vía API de usuario (el endpoint real
    se autentica con `X-RF71-Internal-Key`, no con RBAC de usuario, ver
    G119).
(f) Trazabilidad end-to-end -- NO EVALUABLE más allá del único tramo real
    (registro → RF-69), igual que antes.
(g) RFC-009: "modo_generacion viaja en el payload, queda persistido... una
    versión registrada sin modo_generacion es un defecto bloqueante" --
    HALLAZGO DIRECTO, VIGENTE: el defecto que la propia ficha declara
    bloqueante se sigue cumpliendo, de la forma más completa posible --
    el campo nunca llegó a existir. `RegistrarVersionModeloDTO` no lo
    declara (aunque SÍ declara `componente`, el análogo para
    POBLACIONAL); `VersionModelo` no lo almacena; ninguna versión, de
    ningún tipo, tiene jamás este metadato específico.

Cómo se prueba: grep exhaustivo sobre src/ y el DDL baseline + inspección
directa de `TIPOS_MODELO`/`es_poblacional`/`COMPONENTES_POBLACIONAL` (en
`src/shared/tipo_modelo.py`) y de `Calibracion` (RF-24 real).

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
from src.shared.tipo_modelo import COMPONENTES_POBLACIONAL, TIPOS_MODELO, es_poblacional

REPO_ROOT = Path(__file__).resolve().parents[5]


def _grep_src(termino: str) -> list[str]:
    return [
        str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
        if termino in p.read_text(encoding='utf-8', errors='ignore')
    ]


class TestHallazgoRaizMatizadoRegistroSiEsAlcanzablePeroNoElDisparo:
    def test_main_sigue_sin_registrar_ningun_router_de_retrainings(self):
        texto_main = (REPO_ROOT / 'main.py').read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO RAIZ (vigente en su forma estricta): main.py no registra ningun router "
            "'retrainings' ni 'model-versions' -- los nombres de ruta que la ficha v2.0 asume "
            "tampoco existen."
        ) if 'retrainings' not in texto_main.lower() else None

    def test_pero_si_registra_version_modelo_router_para_el_tramo_de_registro(self):
        texto_main = (REPO_ROOT / 'main.py').read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO INVERTIDO DE ALCANCE: main.py SI registra 'version_modelo_router' "
            "(prefijo real /prediccion/modelos) -- a diferencia de 'no existe en ningun lugar "
            "alcanzable por HTTP', el tramo de REGISTRO de una version ya entrenada SI es "
            "alcanzable (POST/GET/PATCH). Lo que sigue sin existir es el DISPARO/monitoreo "
            "asincrono de un proceso de entrenamiento en si (ver G113-G117/G122)."
        ) if 'version_modelo_router' in texto_main else None


class TestHallazgoInvertidoTaxonomiaRfc009SiExisteConOtrosNombres:
    def test_tipos_modelo_real_tiene_6_valores_no_4(self):
        pytest.fail(
            f"HALLAZGO INVERTIDO: TIPOS_MODELO (src/shared/tipo_modelo.py) SI tiene 6 valores "
            f"-- {sorted(TIPOS_MODELO)!r} -- organizados en 3 paradigmas via "
            f"PARADIGMA_POR_TIPO_MODELO. La vieja _TIPOS_VALIDOS de 4 valores "
            f"(ESPECIES_PEQUEÑAS/MEDIANAS/GRANDES/CONTAGIO) ya no existe en "
            f"registrar_version_modelo_use_case.py."
        ) if len(TIPOS_MODELO) == 6 else None

    def test_es_poblacional_y_componentes_poblacional_si_existen(self):
        pytest.fail(
            f"HALLAZGO INVERTIDO: el paradigma POBLACIONAL SI existe (es_poblacional('MODELO_AVES')"
            f"={es_poblacional('MODELO_AVES')!r}), con 4 componentes obligatorios "
            f"{sorted(COMPONENTES_POBLACIONAL)!r} -- el concepto de 'tipos que se versionan de "
            f"forma distinta' que pide la RFC-009 si se implemento, aunque no con los nombres "
            f"literales que la ficha anticipaba (POBLACIONAL/INDIVIDUAL/META, no 'modo_generacion')."
        ) if COMPONENTES_POBLACIONAL else None

    def test_dto_de_registro_si_declara_componente_el_analogo_de_modo_generacion(self):
        firma = inspect.signature(RegistrarVersionModeloDTO.__init__)
        parametros = set(firma.parameters)
        pytest.fail(
            f"HALLAZGO INVERTIDO DE ALCANCE: RegistrarVersionModeloDTO SI declara 'componente' "
            f"(obligatorio para POBLACIONAL) -- parametros reales: {sorted(parametros)!r}. No es "
            f"'modo_generacion', pero cumple un rol de encuadre similar para el caso POBLACIONAL."
        ) if 'componente' in parametros else None


class TestHallazgoVigenteRfc009DeReentrenamientoNoImplementada:
    @pytest.mark.parametrize('termino', [
        'modo_generacion', 'CALIBRACION_EN_SITIO', 'calibration_readiness',
    ])
    def test_concepto_de_reentrenamiento_rfc009_no_existe_en_ningun_lado(self, termino):
        archivos = _grep_src(termino)
        texto_ddl = (REPO_ROOT / 'alembic/baseline/esquema_baseline.sql').read_text(
            encoding='utf-8', errors='ignore')
        pytest.fail(
            f"HALLAZGO VIGENTE: '{termino}' (especifico del disparo de reentrenamiento/"
            f"calibracion-en-sitio de la RFC-009) sigue sin existir en ningun archivo de src/ "
            f"(encontrados: {archivos or 'ninguno'}) ni en el DDL baseline."
        ) if not archivos and termino not in texto_ddl else None

    def test_score_anomalia_existe_pero_en_otro_rf_no_en_el_contrato_de_rf71(self):
        archivos_prediction_version = _grep_src('score_anomalia')
        pytest.fail(
            f"MATIZ: 'score_anomalia' SI existe en el codigo real ({archivos_prediction_version}), "
            f"pero en riesgo_contagio.py (RF-68), no en VersionModelo/_METRICAS_REQUERIDAS "
            f"(RF-69/RF-71, ver G109). No se incorporo al contrato de metricas que evalua esta "
            f"ficha."
        ) if any('version_modelo' not in a and 'registrar_version_modelo' not in a for a in archivos_prediction_version) else None

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
    def test_validar_y_asignar_estado_puede_producir_aprobado_sin_intervencion_humana_individual(self):
        modelo = VersionModelo.crear(
            tipo_modelo='MODELO_ESPECIES_MEDIANAS', formato_artefacto='ONNX', ruta_artefacto='/tmp/x.onnx',
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
            "HALLAZGO (d), VIGENTE CON MECANISMO ACTUALIZADO: para un modelo INDIVIDUAL con "
            "metricas que superan los umbrales, validar_y_asignar_estado() lo deja en APROBADO "
            "en el mismo registro, sin intervencion humana -- exactamente lo que (d) pide "
            "verificar que nunca ocurre."
        )

    def test_validar_y_asignar_estado_tambien_auto_aprueba_poblacional_por_calibracion_completada(self):
        """HALLAZGO NUEVO: la rama POBLACIONAL (RFC-009) tiene su propio
        criterio de auto-aprobacion (calibracion_completada=True), pero
        sigue siendo auto-aprobacion sin revision humana -- el defecto de
        (d) se extiende tambien a la rama nueva."""
        modelo = VersionModelo.crear(
            tipo_modelo='MODELO_AVES', formato_artefacto='ONNX', ruta_artefacto='/tmp/x.onnx',
            tamanio_artefacto_bytes=100, hash_artefacto_sha256='a' * 64, dataset_entrenamiento_hash='b' * 64,
            id_proceso_rf71=__import__('uuid').uuid4(), f1_score=None,
            recall_clase_riesgo_alto=None, precision_modelo=None,
            accuracy=None, roc_auc_score=None,
            recall_por_clase={}, matriz_confusion={}, compatibilidad_variables=[],
            fecha_entrenamiento=datetime(2026, 10, 20, tzinfo=timezone.utc),
            componente='DETECTOR', metricas_poblacionales={'calibracion_completada': True},
        )
        modelo.validar_y_asignar_estado()
        pytest.fail(
            f"HALLAZGO NUEVO: con calibracion_completada=True, un modelo POBLACIONAL tambien "
            f"queda '{modelo.estado_version}' sin intervencion humana -- la auto-aprobacion de "
            f"(d) no se corrigio, solo se extendio con un segundo criterio automatico."
        ) if modelo.estado_version == 'APROBADO' else None
