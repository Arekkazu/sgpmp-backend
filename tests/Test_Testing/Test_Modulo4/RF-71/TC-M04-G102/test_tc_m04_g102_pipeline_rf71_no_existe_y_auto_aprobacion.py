"""
TC-M04-G102 (RF-71 Fases 1-7/CA-3/RNF-12, CU-01) - "Pipeline completo de
extremo a extremo con trigger MANUAL (camino feliz)." Caso base del grupo
RF-71 (TC-01): prerrequisito declarado para TC-M04-G110/G111/G112, que
inspeccionan la salida que este produce.

Código bajo prueba: main.py (routers de M04 realmente registrados),
alembic/baseline/esquema_baseline.sql (infraestructura SQL de RF-71), y
src/prediction/application/use_cases/versiones_modelo/
registrar_version_modelo_use_case.py + domain/entities/version_modelo.py
(el único punto de contacto HTTP real con lo que la ficha llama "RF-71").

HALLAZGO PRINCIPAL, RAÍZ PARA TODO EL GRUPO RF-71 (G102-G123): el pipeline
de reentrenamiento que la ficha asume -- `POST /api/v1/m04/retraining`,
`GET /api/v1/m04/retraining/{id_proceso}`, `GET /api/v1/m04/retraining/
{id_proceso}/resources`, `POST .../cancel`, `POST .../resume`, `PUT
/api/v1/config/m04/retraining` -- **no existe en ningún lugar alcanzable
por HTTP**. `main.py` registra exactamente 7 routers de M04
(`patologia_m04`, `motor_ia`, `historial_diagnostico`, `version_modelo`,
`ota`, `retroalimentacion_clinica`, `auditoria_m04`); ninguno expone una
sola ruta de "retraining"/"reentrenamiento". Un grep exhaustivo de
"reentrenamiento"/"retraining"/"dataset_hash"/"drift" en todo `src/`
confirma cero use cases, cero routers y cero DTOs para esta
funcionalidad.

La infraestructura de RF-71 SÍ existe, pero únicamente a nivel de base de
datos: `alembic/baseline/esquema_baseline.sql` define el tipo
`enum_estado_proceso_reentrenamiento`, la tabla `modulo4.ciclos_entrenamientos`
(con columnas `dataset_hash`, `id_proceso_rf71`, `trigger_reentrenamiento`,
etc., exactamente como las describe la ficha) y el procedimiento
`modulo4.sp_iniciar_ciclo_reentrenamiento`. Pero un grep exhaustivo sobre
`src/` confirma que **ningún archivo Python invoca jamás ese
procedimiento ni consulta esa tabla** -- es infraestructura SQL huérfana,
diseñada pero nunca conectada a la capa de aplicación (mismo patrón que
`sp_corregir_vinculacion` en RF-61/TC-M03-G152, pero aquí ni siquiera hay
un endpoint Python que lo intente).

El único punto de contacto real y alcanzable por HTTP con "lo que entrega
RF-71" es `POST /api/v1/m04/models` (RF-69, `registrar_version_modelo_use_case.py`).
Su propio router lo documenta: "El endpoint POST (registro) no usa RBAC;
está protegido por X-RF71-Internal-Key" -- es decir, está diseñado para
ser invocado por un PROCESO EXTERNO (presumiblemente la "RF-71" real,
fuera de este backend), nunca por un usuario autenticado con rol
Administrador/Veterinario como asume (e) de esta ficha.

HALLAZGO ADICIONAL, CONTRADICCIÓN DE COMPORTAMIENTO (invalida (d) incluso
en sus propios términos): la instrucción explícita de (d) es "verificar
que el estado entregado es EN_VALIDACION y nunca APROBADO" -- pero
`RegistrarVersionModeloUseCase.execute()` llama inmediatamente a
`entidad.validar_y_asignar_estado()` (`version_modelo.py:99-115`), que
asigna **APROBADO automáticamente, en el mismo registro**, si
`f1_score_global >= 0.80` Y `recall_clase_riesgo_alto >= 0.85` -- sin
ninguna revisión humana. El estado inicial es EN_VALIDACION solo
transitoriamente (dura el tiempo de dos inserciones de historial dentro
de la misma transacción); el estado que realmente queda persistido puede
ser APROBADO, exactamente lo que (d) pide verificar que NUNCA ocurra.

(a)/(b)/(c)/(f) -- NO EJECUTABLES: no existe ningún endpoint que inicie
    un proceso de reentrenamiento, así que no hay "las 7 fases" que
    recorrer, ni REENTRENAMIENTO_INICIADO que registrar (ver también
    TC-M04-G120 para el catálogo de auditoría real de M04, que no
    incluye ningún evento REENTRENAMIENTO_*), ni trazabilidad end-to-end
    que verificar más allá del único tramo real (registro → RF-69).
(d) "la salida incluye ... estado COMPLETADO ... y la nueva versión en
    RF-69 con estado EN_VALIDACION" -- HALLAZGO: el registro de ejecución
    con estado COMPLETADO no existe (no hay tabla de ejecuciones
    alcanzable); y la versión en RF-69 puede llegar APROBADA de
    inmediato, no EN_VALIDACION, contradiciendo la instrucción explícita
    de la propia ficha.
(e) "Repetir con un Veterinario como iniciador: también autorizado" -- NO
    EVALUABLE: no hay ningún "iniciador" posible vía API de usuario; el
    único endpoint relacionado se autentica con una clave interna
    compartida, no con la identidad de un usuario con rol.

Cómo se prueba: grep exhaustivo sobre src/ y el DDL baseline + inspección
directa de `VersionModelo.validar_y_asignar_estado()` con un caso que
cumple ambos umbrales, demostrando que APROBADO es alcanzable sin
intervención humana.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m04_g102_pipeline_rf71_no_existe_y_auto_aprobacion.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G102.html --self-contained-html
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from src.prediction.domain.entities.version_modelo import VersionModelo

REPO_ROOT = Path(__file__).resolve().parents[5]
DDL = (REPO_ROOT / 'alembic/baseline/esquema_baseline.sql').read_text(encoding='utf-8', errors='ignore')


def _grep_src(termino: str) -> list[str]:
    return [
        str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
        if termino in p.read_text(encoding='utf-8', errors='ignore')
    ]


class TestHallazgoRaizNoExisteEndpointDeRetraining:
    def test_main_no_registra_ningun_router_de_retraining(self):
        texto_main = (REPO_ROOT / 'main.py').read_text(encoding='utf-8')
        rutas_m04 = [l for l in texto_main.splitlines() if 'include_router' in l and (
            'patologia_m04' in l or 'motor_ia' in l or 'historial_diagnostico' in l or
            'version_modelo' in l or 'ota_router' in l or 'retroalimentacion_clinica' in l or
            'auditoria_m04' in l
        )]
        assert len(rutas_m04) == 7
        pytest.fail(
            f"HALLAZGO RAIZ: main.py registra exactamente estos 7 routers de M04: "
            f"{[l.strip() for l in rutas_m04]!r} -- ninguno expone '/retraining' ni "
            f"'/reentrenamiento'. POST /api/v1/m04/retraining y los otros 5 endpoints que esta "
            f"ficha asume no existen en ningun lugar alcanzable por HTTP."
        )

    @pytest.mark.parametrize('termino', ['reentrenamiento', 'retraining', 'dataset_hash', 'drift'])
    def test_termino_del_pipeline_no_aparece_en_ningun_use_case_ni_router(self, termino):
        archivos_relevantes = [
            a for a in _grep_src(termino)
            if '/application/use_cases/' in a.replace('\\', '/') or '/infrastructure/routers/' in a.replace('\\', '/')
            or '/infrastructure/dto/' in a.replace('\\', '/')
        ]
        pytest.fail(
            f"HALLAZGO RAIZ: '{termino}' no aparece en ningun caso de uso, router ni DTO de "
            f"src/ (coincidencias en esas carpetas: {archivos_relevantes or 'ninguna'})."
        ) if not archivos_relevantes else None


class TestHallazgoInfraestructuraSqlHuerfana:
    def test_existe_la_tabla_y_el_procedimiento_en_el_ddl(self):
        assert 'CREATE TABLE modulo4.ciclos_entrenamientos' in DDL or 'ciclos_entrenamientos' in DDL
        assert 'CREATE PROCEDURE modulo4.sp_iniciar_ciclo_reentrenamiento' in DDL

    def test_ningun_archivo_python_invoca_el_procedimiento_ni_consulta_la_tabla(self):
        archivos = _grep_src('sp_iniciar_ciclo_reentrenamiento') + _grep_src('ciclos_entrenamientos')
        pytest.fail(
            f"HALLAZGO: la tabla modulo4.ciclos_entrenamientos y el procedimiento "
            f"sp_iniciar_ciclo_reentrenamiento existen en el DDL baseline (diseñados con las "
            f"columnas exactas que la ficha describe: dataset_hash, id_proceso_rf71, "
            f"trigger_reentrenamiento), pero ningun archivo de src/ los menciona (encontrados: "
            f"{archivos or 'ninguno'}) -- es infraestructura SQL huerfana, nunca conectada a la "
            f"aplicacion."
        ) if not archivos else None


class TestHallazgoDAutoAprobacionSinRevisionHumana:
    def test_el_endpoint_de_registro_no_usa_rbac_sino_clave_interna(self):
        archivo = REPO_ROOT / 'src/prediction/infrastructure/routers/version_modelo_router.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'X-RF71-Internal-Key' in texto
        pytest.fail(
            "HALLAZGO (e): el propio router documenta 'El endpoint POST (registro) no usa RBAC; "
            "esta protegido por X-RF71-Internal-Key' -- no hay ningun 'iniciador' con rol "
            "Administrador o Veterinario posible via API de usuario para este flujo."
        )

    def test_validar_y_asignar_estado_puede_producir_aprobado_sin_intervencion_humana(self):
        """Reproduce exactamente la contradiccion de (d): un modelo que
        cumple ambos umbrales queda APROBADO de inmediato, en el mismo
        registro, sin ningun paso de revision humana."""
        modelo = VersionModelo.crear(
            tipo_modelo='ESPECIES_MEDIANAS', formato_artefacto='ONNX', ruta_artefacto='/tmp/x.onnx',
            tamanio_artefacto_bytes=100, hash_artefacto_sha256='a' * 64, dataset_entrenamiento_hash='b' * 64,
            id_proceso_rf71=__import__('uuid').uuid4(), f1_score=Decimal('0.85'),
            recall_clase_riesgo_alto=Decimal('0.90'), precision_modelo=Decimal('0.85'),
            accuracy=Decimal('0.85'), roc_auc_score=Decimal('0.90'),
            recall_por_clase={}, matriz_confusion={}, compatibilidad_variables=[],
            fecha_entrenamiento=datetime(2026, 10, 20, tzinfo=timezone.utc),
        )
        assert modelo.estado_version == 'EN_VALIDACION'

        modelo.validar_y_asignar_estado()

        assert modelo.estado_version == 'APROBADO'
        pytest.fail(
            "HALLAZGO (d): con f1_score_global=0.85 y recall_clase_riesgo_alto=0.90 (ambos por "
            "encima de los umbrales 0.80/0.85), validar_y_asignar_estado() deja el modelo en "
            "APROBADO en el mismo registro, sin ninguna intervencion humana -- exactamente el "
            "resultado que la ficha pide verificar que NUNCA ocurre ('el estado entregado es "
            "EN_VALIDACION y nunca APROBADO')."
        )
