"""
TC-M03-G149 (RF-60 CA-15/Fase 9/Salida 7/E1, CU-15) - "Completitud de la
bitácora de auditoría (RF-63)."

REEJECUCIÓN 2026-10-29 TRAS MERGE DE `origin/test` (811 commits reales,
autoría Leandro DEV-47 2026-10-22) -- ver
[[feedback_verify_against_live_before_local_code]]. El HALLAZGO PRINCIPAL
de la ronda anterior ("CERO de los 7 tipos de evento existen tal cual")
queda CASI TOTALMENTE INVERTIDO: 6 de los 7 SÍ existen, generados desde
un módulo dedicado (`src/telemetry/infrastructure/repositories/
evidencia_fuentes_iot.py`, "Proyecciones auditables, sin copiar payloads
ni modificar las fuentes") invocado por el worker post-commit
(`postcommit_worker.py`, etapas `RF60_TRANSICIONES` ->
`auditar_transicion`, `HEARTBEAT_AUDITORIA` -> `auditar_heartbeat`) -- NO
por un `auditoria_repo` inyectado en `RecibirHeartbeatUseCase` o
`EvaluarEstadoDispositivosUseCase` (eso sigue sin existir, ver (a)/(c)
abajo: el mecanismo es correcto, solo que vive en otra capa).

HALLAZGO PRINCIPAL ACTUALIZADO (b): catálogo real confirmado en
`evidencia_fuentes_iot.py::auditar_transicion()`/`auditar_heartbeat()`:
`HEARTBEAT_RECIBIDO`, `ESTADO_CAMBIADO` (genérico, catch-all),
`DISPOSITIVO_SIN_SEÑAL`, `DISPOSITIVO_INACTIVO`, `MANTENIMIENTO_INICIADO`,
`MANTENIMIENTO_COMPLETADO`, `DISPOSITIVO_RECONECTADO` -- 6 de los 7
nombres de la Fase 9/Salida 7 existen literalmente (`MANTENIMIENTO_
INICIADO`/`MANTENIMIENTO_COMPLETADO` SÍ se distinguen ahora, al revés de
lo que encontró la ronda anterior sobre
`TRANSICION_MANTENIMIENTO_MANUAL`). Solo `ALERTA_TECNICA_GENERADA` sigue
sin existir -- no hay ninguna función `auditar_alerta` en el módulo de
evidencia, y las alertas técnicas de RF-60 no generan ningún evento de
auditoría propio.

**Hallazgo nuevo, relevante también para TC-M03-G132 reejecutado**: el
comentario de `auditar_transicion()` confirma explícitamente el misterio
de los registros duplicados observado en vivo en TEST ("Dos triggers
existentes pueden materializar la misma transición con now()") -- el
propio equipo de desarrollo reconoce el defecto de doble-trigger y
agrega una deduplicación defensiva aquí (consulta por
`accion_detallada['transicion']` antes de insertar), pero NO corrige la
causa raíz en `historico_transiciones_dispositivos`, que sigue
recibiendo las dos filas duplicadas (confirmado en vivo en TEST para el
dispositivo 348).

(a) CA-15, traza por el único evento real -- HALLAZGO ACTUALIZADO: ya no
    es solo `TRANSICION_MANTENIMIENTO_MANUAL` -- ahora hay 6 tipos reales
    (ver arriba). `RecibirHeartbeatUseCase`/`EvaluarEstadoDispositivosUseCase`
    siguen sin recibir `auditoria_repo` por constructor (CONFIRMADO
    VIGENTE), pero la auditoría de heartbeat/transición SÍ ocurre, vía el
    worker post-commit y `evidencia_fuentes_iot.py`.
(b) catálogo de 6+1 tipos -- HALLAZGO INVERTIDO: 6 de 7 existen con esos
    nombres (o un equivalente directo), solo `ALERTA_TECNICA_GENERADA`
    sigue sin existir.
(c) "traza continua sin saltos" -- HALLAZGO PARCIALMENTE INVERTIDO: la
    traza de heartbeat/transición de estado SÍ es prácticamente continua
    ahora (6 de 7 tipos); el salto real que queda es la ausencia total de
    auditoría de alertas técnicas.
(d) "los campos de diagnóstico no contienen credenciales" -- SIGUE
    CONFIRMADO: ninguno de los `detalle={...}` de `evidencia_fuentes_iot.py`
    incluye credenciales ni tokens.

Cómo se prueba: grep exhaustivo contra el código real tras el merge +
confirmación directa de la ausencia de `auditoria_repo` en los
constructores de `RecibirHeartbeatUseCase`/`EvaluarEstadoDispositivosUseCase`,
y de la ausencia de `ALERTA_TECNICA_GENERADA`/`auditar_alerta`.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m03_g149_completitud_bitacora_auditoria.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G149.html --self-contained-html
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case import (
    EvaluarEstadoDispositivosUseCase,
)
from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import (
    RecibirHeartbeatUseCase,
)

REPO_ROOT = Path(__file__).resolve().parents[5]
ARCHIVO_EVIDENCIA = REPO_ROOT / 'src/telemetry/infrastructure/repositories/evidencia_fuentes_iot.py'
_CATALOGO_FASE9_CON_EQUIVALENTE_REAL = (
    'HEARTBEAT_RECIBIDO', 'ESTADO_CAMBIADO', 'DISPOSITIVO_RECONECTADO',
    'MANTENIMIENTO_INICIADO', 'MANTENIMIENTO_COMPLETADO',
)


class TestSubCasoBCatalogoDeSieteTiposDeEventoCasiCompleto:
    @pytest.mark.parametrize('tipo_evento', _CATALOGO_FASE9_CON_EQUIVALENTE_REAL)
    def test_tipo_de_evento_si_existe_tras_el_merge(self, tipo_evento):
        texto = ARCHIVO_EVIDENCIA.read_text(encoding='utf-8')
        pytest.fail(
            f"HALLAZGO (b) INVERTIDO: '{tipo_evento}' SI existe en evidencia_fuentes_iot.py "
            f"tras el merge de origin/test -- la ronda anterior (codigo stale) afirmo que CERO "
            f"de los 7 tipos existian."
        ) if tipo_evento in texto else None

    def test_alerta_tecnica_generada_sigue_sin_existir(self):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src' / 'telemetry').rglob('*.py')
            if 'ALERTA_TECNICA_GENERADA' in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (b) VIGENTE: 'ALERTA_TECNICA_GENERADA' sigue sin existir en ningun "
            f"archivo de src/telemetry/ (encontrados: {archivos or 'ninguno'}) -- es el unico "
            f"de los 7 tipos de la Fase 9 que sigue ausente tras el merge."
        ) if not archivos else None

    def test_mantenimiento_iniciado_y_completado_ahora_si_se_distinguen(self):
        texto = ARCHIVO_EVIDENCIA.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (b) INVERTIDO: MANTENIMIENTO_INICIADO y MANTENIMIENTO_COMPLETADO ahora SI "
            "se distinguen como tipos de evento separados (segun estado_anterior/estado_nuevo) "
            "-- la ronda anterior encontro un unico tipo generico "
            "'TRANSICION_MANTENIMIENTO_MANUAL' que no los distinguia."
        ) if "'MANTENIMIENTO_INICIADO'" in texto and "'MANTENIMIENTO_COMPLETADO'" in texto else None


class TestHallazgoNuevoDuplicacionDeTransicionesReconocidaPorElEquipo:
    def test_el_comentario_del_codigo_reconoce_los_dos_triggers_duplicados(self):
        """Confirma en codigo el misterio observado en vivo en TEST
        (TC-M03-G132 reejecutado): dos filas de historial para la misma
        transicion, con distinto texto de nota, milisegundos aparte."""
        texto = ARCHIVO_EVIDENCIA.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO NUEVO: el propio codigo reconoce ('Dos triggers existentes pueden "
            "materializar la misma transicion con now()') que historico_transiciones_dispositivos "
            "recibe filas duplicadas para la misma transicion -- la deduplicacion aqui solo "
            "evita contarla dos veces en la bitacora de auditoria RF-63, NO corrige la causa "
            "raiz en la tabla de historial, que sigue duplicada."
        ) if 'Dos triggers existentes pueden materializar' in texto else None


class TestSubCasoARecibirHeartbeatNoAuditaDirectamentePeroElWorkerSi:
    def test_recibir_heartbeat_use_case_sigue_sin_recibir_auditoria_repo_directo(self):
        firma = inspect.signature(RecibirHeartbeatUseCase.__init__)
        nombres_parametros = set(firma.parameters.keys())
        pytest.fail(
            f"HALLAZGO (a) VIGENTE EN ESTE PUNTO (pero ver arriba, el mecanismo real vive en "
            f"el worker post-commit): RecibirHeartbeatUseCase.__init__ sigue sin declarar "
            f"ningun parametro de auditoria -- parametros reales: "
            f"{sorted(nombres_parametros)!r}."
        ) if not any('auditoria' in p.lower() for p in nombres_parametros) else None

    def test_evaluar_estado_dispositivos_use_case_tampoco_recibe_auditoria_directo(self):
        firma = inspect.signature(EvaluarEstadoDispositivosUseCase.__init__)
        nombres_parametros = set(firma.parameters.keys())
        pytest.fail(
            f"HALLAZGO (a) VIGENTE EN ESTE PUNTO: EvaluarEstadoDispositivosUseCase.__init__ "
            f"tampoco declara ningun parametro de auditoria -- parametros reales: "
            f"{sorted(nombres_parametros)!r}."
        ) if not any('auditoria' in p.lower() for p in nombres_parametros) else None

    def test_pero_el_worker_postcommit_si_invoca_la_auditoria_real(self):
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/workers/postcommit_worker.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (a) ACTUALIZADO: el worker post-commit SI invoca 'auditar_heartbeat' y "
            "'auditar_transicion' como etapas RF60_TRANSICIONES/HEARTBEAT_AUDITORIA -- la "
            "auditoria real ocurre, solo que fuera de RecibirHeartbeatUseCase/"
            "EvaluarEstadoDispositivosUseCase."
        ) if 'auditar_heartbeat' in texto and 'auditar_transicion' in texto else None
