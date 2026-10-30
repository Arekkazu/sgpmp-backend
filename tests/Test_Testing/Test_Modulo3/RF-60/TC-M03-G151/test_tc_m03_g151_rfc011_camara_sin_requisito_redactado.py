"""
TC-M03-G151 (RF-60 v1.3/RFC-011 v1.1, CU-18) - "Categoría CAMARA y
estado_calibración."

REEJECUCIÓN 2026-10-29 TRAS MERGE DE `origin/test` (811 commits reales) --
ver [[feedback_verify_against_live_before_local_code]]. El HALLAZGO
PRINCIPAL de la ronda anterior ("CAMARA/CAMARA_VISION/estado_calibracion
tienen CERO coincidencias, confirma el BLOQUEO que la propia ficha
declara") queda COMPLETAMENTE INVERTIDO. Esto ya se había anticipado
contra el `openapi.json` en vivo de TEST (ver
[[feedback_verify_against_live_before_local_code]], que documentó un
módulo completo de visión/cámara: `EstadoCalibracionCamara`,
`CalibrarVisionDTO`, `/iot/telemetria/vision`); ahora se confirma
directamente contra el código fuente real tras el merge.

HALLAZGO PRINCIPAL ACTUALIZADO: `TipoDispositivoIot`
(`src/configuration/domain/entities/tipo_dispositivo_iot.py`) declara
literalmente `CATEGORIA_CAMARA = "CAMARA"` junto a `CATEGORIA_SENSOR =
"SENSOR"`, con el comentario explícito "RF-21 v2.0 (RFC-011): la
categoría es del tipo, no del dispositivo" -- exactamente el concepto
que la ficha pedía y que la ronda anterior no encontró. Existe además un
módulo completo de visión bajo `src/telemetry/.../vision` y `.../ingesta/
ingerir_observaciones_vision_use_case.py`, con `estado_calibracion` como
campo real en varias entidades/DTOs/modelos (`calidad_vision.py`,
`observacion_vision.py`, `observacion_vision_model.py`, etc.) -- 20
archivos de `src/` mencionan `CAMARA`.

(a) Intervalo de heartbeat propio de CAMARA -- HALLAZGO INVERTIDO: SÍ
    existe un intervalo propio para cámaras. Confirmado también en
    TC-M03-G133 reejecutado: `ParametrosHeartbeatMLOpsAdapter.
    obtener_comunicacion()` usa `INTERVALO_CAMARA` (clave
    `intervalo_heartbeat_camara`, límites 30-600s) como un intervalo
    SEPARADO del catálogo `INTERVALOS_TIPO` para el resto de categorías,
    condicionado exactamente por `dispositivo['categoria'] == 'CAMARA'`.
(b) Cámara sin señal -> algoritmo general -- SIGUE SIN SER UN HALLAZGO
    NUEVO: el algoritmo de estado (`evaluar_transicion`) sigue sin
    distinguir categorías explícitamente -- la diferenciación por CAMARA
    ocurre en la capa de parámetros (umbral_activo), no en el algoritmo
    de 4 pasos en sí.
(c) Cámara con señal pero sin detección válida -> estado_calibracion --
    HALLAZGO INVERTIDO: `estado_calibracion` SÍ existe como concepto
    real en el módulo de visión.
(d) Diferenciación en RF-59 -- NO REEVALUADO EN DETALLE esta ronda (fuera
    del alcance inmediato de RF-60); dado que (c) se invirtió, esta
    conclusión derivada tampoco puede darse por válida sin revisar RF-59
    directamente -- queda como hallazgo pendiente de otra ronda.

Cómo se prueba: grep exhaustivo contra el código real tras el merge +
inspección directa de `TipoDispositivoIot` y de
`ParametrosHeartbeatMLOpsAdapter.obtener_comunicacion()`.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m03_g151_rfc011_camara_sin_requisito_redactado.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G151.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]


def _grep(termino: str, carpetas: tuple[str, ...]) -> list[str]:
    archivos: list[str] = []
    for carpeta in carpetas:
        base = REPO_ROOT / carpeta
        if not base.exists():
            continue
        for p in base.rglob('*.py'):
            if termino in p.read_text(encoding='utf-8', errors='ignore'):
                archivos.append(str(p.relative_to(REPO_ROOT)))
        for p in base.rglob('*.sql'):
            if termino in p.read_text(encoding='utf-8', errors='ignore'):
                archivos.append(str(p.relative_to(REPO_ROOT)))
    return archivos


class TestElBloqueoDeclaradoPorLaFichaQuedaInvertidoTrasElMerge:
    @pytest.mark.parametrize('termino', ['CAMARA', 'estado_calibracion'])
    def test_termino_del_rfc011_si_existe_en_codigo_tras_el_merge(self, termino):
        archivos = _grep(termino, ('src', 'alembic'))
        pytest.fail(
            f"HALLAZGO INVERTIDO: '{termino}' SI aparece en {len(archivos)} archivo(s) de src/ "
            f"o alembic/ tras el merge de origin/test -- la ronda anterior (codigo stale) "
            f"afirmo que tenia CERO coincidencias en todo el repositorio."
        ) if archivos else None

    def test_tipo_dispositivo_iot_si_declara_categoria_camara(self):
        archivo = REPO_ROOT / 'src/configuration/domain/entities/tipo_dispositivo_iot.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (a) INVERTIDO: TipoDispositivoIot SI declara "
            "CATEGORIA_CAMARA = \"CAMARA\" junto a CATEGORIA_SENSOR -- 'RF-21 v2.0 (RFC-011): "
            "la categoria es del tipo, no del dispositivo', exactamente el concepto que la "
            "ficha pedia."
        ) if 'CATEGORIA_CAMARA = "CAMARA"' in texto else None

    def test_el_adaptador_de_parametros_si_usa_un_intervalo_propio_para_camara(self):
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/adapters/parametros_heartbeat_mlops_adapter.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (a) INVERTIDO: ParametrosHeartbeatMLOpsAdapter.obtener_comunicacion() SI "
            "usa INTERVALO_CAMARA como clave separada cuando dispositivo['categoria']=='CAMARA' "
            "-- confirma que SI existe un intervalo de heartbeat propio para camaras."
        ) if "dispositivo['categoria'] == 'CAMARA'" in texto else None

    def test_el_algoritmo_de_estado_sigue_sin_distinguir_categoria_explicitamente(self):
        archivo = REPO_ROOT / 'src/telemetry/domain/entities/estado_dispositivo_iot.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'CAMARA' not in texto
        assert 'categoria' not in texto.lower()
