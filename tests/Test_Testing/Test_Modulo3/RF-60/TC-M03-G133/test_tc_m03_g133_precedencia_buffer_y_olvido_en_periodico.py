"""
TC-M03-G133 (RF-60 CA-2/CA-18/CA-21/PASO 2/E6, CU-04) - "Precedencia del
PASO 2 (buffer) sobre el PASO 3 (sin señal)."

REEJECUCIÓN 2026-10-30 TRAS NUEVO PULL DE `origin/test` (149 commits
adicionales sobre el merge del 2026-10-29) -- ver
[[feedback_verify_against_live_before_local_code]]. El hallazgo que esta
misma ronda había dejado "confirmado correcto" el 2026-10-29 vuelve a
cambiar de fondo por el commit `761faa8b` (Leandro, 2026-10-27,
INC-M03-127-G27, "conservar buffer activo hasta confirmar vaciado"),
fusionado a `test` recién el 2026-10-29/30.

HALLAZGO PRINCIPAL ACTUALIZADO: la precedencia del PASO 2 (buffer) ya NO
es solo "sobre el PASO 3 (sin señal)" -- ahora el buffer con datos
pendientes tiene precedencia INCLUSO SOBRE EL PASO 1 (contacto reciente
-> ACTIVO). `EstadoDispositivoIoT.evaluar_transicion()` ganó un parámetro
`datos_pendientes_buffer: int | None = None` y reordenó el algoritmo:
```
if datos_pendientes_buffer is None:
    buffer_activo = estado_local_buffer in ('A', 'L') or self.estado_actual == 'BUFFER_ACTIVO'
else:
    buffer_activo = datos_pendientes_buffer > 0 and (
        estado_local_buffer in ('A', 'L') or self.estado_actual == 'BUFFER_ACTIVO')
if buffer_activo:
    nuevo = 'BUFFER_ACTIVO'
elif tiempo_sin_contacto_seg <= umbral_activo:
    nuevo = 'ACTIVO'
...
```
Es decir: un heartbeat que llega puntualmente (`tiempo_sin_contacto_seg`
dentro del umbral_activo) YA NO fuerza `ACTIVO` si el dispositivo reporta
buffer con datos pendientes (`datos_pendientes_buffer > 0` y
`estado_local_buffer` en `('A','L')`) -- el estado se queda en
BUFFER_ACTIVO hasta que el propio dispositivo reporte el buffer vacío
(`datos_pendientes_buffer == 0`). También se agrega `'L'` (LLENO) como
código de buffer que cuenta igual que `'A'` (ACTIVO) -- antes solo `'A'`
activaba el paso 2.

Además, `ProcesarHeartbeatPersistidoUseCase.procesar_estado()` cambió SU
FUENTE: ya no llama `evaluar_transicion()` con `heartbeat.estado_local_buffer`
(el de ESTE heartbeat) sino con `parametros.estado_local_buffer` --
el mismo valor que resuelve `parametros_port.obtener_comunicacion()`, es
decir el MISMO camino que usa el job periódico
(`EvaluarEstadoDispositivosUseCase`). Esto elimina por diseño cualquier
posible divergencia entre "lo que ve el heartbeat en vivo" y "lo que ve
el job periódico" -- ambos pasan ahora por el mismo adaptador.

(a)/(b) CA-21/CA-18, heartbeat con estado_local_buffer='A' -> BUFFER_ACTIVO
    -- SIGUE CONFIRMADO CORRECTO, pero el mecanismo cambió de fuente (ver
    arriba: ahora vía `parametros.estado_local_buffer`, no
    `heartbeat.estado_local_buffer` directo).
(a-bis) HALLAZGO NUEVO: un heartbeat PUNTUAL (dentro del umbral_activo)
    con buffer declarado Y datos pendientes > 0 YA NO produce ACTIVO --
    produce BUFFER_ACTIVO. Esto invierte cualquier expectativa de que el
    "contacto reciente" (PASO 1) siempre gana.
(a-ter) HALLAZGO NUEVO: si `datos_pendientes_buffer == 0` (buffer ya
    vaciado), el mismo heartbeat puntual con `estado_local_buffer='A'` SÍ
    produce ACTIVO -- la letra del buffer sola ya no basta, se exige
    `datos_pendientes_buffer > 0` cuando ese dato es conocido.
(c) Alerta `BUFFER_PROLONGADO` al superar un umbral configurable --
    HALLAZGO VIGENTE (sin cambios): `BUFFER_PROLONGADO` sigue sin existir
    en ningún archivo de `src/telemetry/` tras este pull.
(d1) Heartbeat de reconexión con `datos_pendientes_buffer > 0` -> ACTIVO
    inmediato + registro de "inicio de sincronización" (E6) -- HALLAZGO
    VIGENTE Y AHORA MÁS CLARO: ya no solo falta el marcador de E6 --
    directamente YA NO hay "ACTIVO inmediato": con datos pendientes > 0 el
    nuevo algoritmo mantiene BUFFER_ACTIVO en vez de pasar a ACTIVO. La
    nota de transición en BD sigue siendo la genérica
    `'Transición automática de estado operativo'` (confirmado: la
    migración `c68227f60a01` no toca ese texto).
(d2) `datos_pendientes_buffer` decrece sin que el estado cambie --
    HALLAZGO INVERTIDO: ya NO es cierto. `datos_pendientes_buffer` es
    ahora el dato que decide si el PASO 2 se mantiene o se libera --
    cuando llega a 0, el algoritmo deja de forzar BUFFER_ACTIVO y
    reevalúa los pasos normales.
(e) Nodo con buffer ACTIVO declarado y silencio total de 8h -- HALLAZGO
    ACTUALIZADO (resuelve la pregunta original de la ficha): el job
    periódico (`EvaluarEstadoDispositivosUseCase`) también pasa ahora
    `datos_pendientes_buffer=parametros.datos_pendientes_buffer` a
    `evaluar_transicion()`. Mientras la ÚLTIMA fila de heartbeats
    conocida siga reportando `datos_pendientes_buffer > 0`, el PASO 2 SÍ
    enmascara la inactividad sin techo temporal (por diseño, según el
    propio mensaje del commit: "conservar buffer activo HASTA CONFIRMAR
    VACIADO") -- pero en cuanto esa última fila reporte
    `datos_pendientes_buffer = 0`, la máscara se levanta y el algoritmo
    vuelve a evaluar PASO 3/4 por tiempo. Ya no es un "olvido" accidental
    ni una ventana sin techo: es una espera acotada a que el dispositivo
    confirme el vaciado. No se verificó en vivo en esta sesión.

Cómo se prueba: inspección directa de
`estado_dispositivo_iot.py::evaluar_transicion()`,
`recibir_heartbeat_use_case.py` y
`evaluar_estado_dispositivos_use_case.py`, más pytest de unidad sobre la
nueva prioridad buffer-sobre-contacto-reciente.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g133_precedencia_buffer_y_olvido_en_periodico.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G133.html --self-contained-html
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import (
    ProcesarHeartbeatPersistidoUseCase,
)
from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT
from src.telemetry.domain.entities.heartbeat import Heartbeat

REPO_ROOT = Path(__file__).resolve().parents[5]
AHORA = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)


def _parametros(estado_local_buffer):
    p = MagicMock(
        umbral_activo=300, umbral_sin_senal=1800, umbral_inactivo=86400,
        estado_local_buffer=estado_local_buffer, id_infraestructura=6,
        ultimo_heartbeat=AHORA, ultima_telemetria=AHORA,
    )
    p.heartbeat_ausente.return_value = False
    return p


def _estado(estado_actual='ACTIVO', minutos_desde_contacto=18):
    return EstadoDispositivoIoT(
        id_estado_dispositivo_iot=1, id_dispositivo_iot=133, estado_actual=estado_actual,
        fecha_ultimo_contacto=AHORA - timedelta(minutes=minutos_desde_contacto), id_ultimo_heartbeat=1,
        tiempo_sin_contacto=0, causa_primaria=None, causas_secundarias=None,
        fecha_ultima_actualizacion=AHORA, id_usuario=None,
    )


def _heartbeat(estado_local_buffer='A', datos_pendientes_buffer=5):
    return Heartbeat(
        id_heartbeat=1, id_dispositivo_iot=133, tipo_mensaje='PERIODICO', nivel_bateria_pct=80,
        calidad_senal_rssi=None, calidad_senal_snr=None, estado_local_buffer=estado_local_buffer,
        datos_pendientes_buffer=datos_pendientes_buffer, version_firmware=None, coordenadas=None,
        fecha_registro=AHORA, fecha_recepcion=AHORA, reloj_sincronizado=True,
        sensores_operativos=None, temperatura_dispositivo=None,
    )


def _procesar(estado, estado_local_buffer, datos_pendientes_buffer):
    estado_repo = MagicMock()
    estado_repo.bloquear_por_dispositivo.return_value = estado
    parametros_port = MagicMock()
    parametros_port.obtener_comunicacion.return_value = _parametros(estado_local_buffer)
    parametros_port.obtener_comunicacion.return_value.datos_pendientes_buffer = datos_pendientes_buffer
    alerta_repo = MagicMock()
    alerta_repo.listar_conectividad_abierta.return_value = []
    periodo_repo = MagicMock()
    # Si no se fija None explicito, obtener_abierto_por_dispositivo() devuelve otro
    # MagicMock truthy en cada llamada y el `while` de completar_transicion_comunicacion
    # ('ACTIVO' -> cierra periodos abiertos en bucle) nunca termina.
    periodo_repo.obtener_abierto_por_dispositivo.return_value = None
    uc = ProcesarHeartbeatPersistidoUseCase(
        estado_repo=estado_repo, alerta_repo=alerta_repo, parametros_port=parametros_port,
        periodo_repo=periodo_repo,
    )
    heartbeat = _heartbeat(estado_local_buffer, datos_pendientes_buffer)
    with patch(
        'src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case.datetime'
    ) as mock_dt:
        mock_dt.now.return_value = AHORA
        uc.procesar_estado(heartbeat, es_ultimo=True)
    return estado


class TestSubCasoAyBBufferActivoConfirmadoCorrectoEnNuevaArquitectura:
    def test_heartbeat_con_buffer_a_produce_buffer_activo(self):
        estado = _estado(minutos_desde_contacto=18)
        estado = _procesar(estado, estado_local_buffer='A', datos_pendientes_buffer=5)
        assert estado.estado_actual == 'BUFFER_ACTIVO'


class TestSubCasoABisElBufferConPendientesGanaIncusoConContactoPuntual:
    def test_heartbeat_puntual_con_pendientes_mayor_a_cero_no_produce_activo(self):
        """HALLAZGO NUEVO (INC-M03-127-G27): tiempo_sin_contacto_seg=0 (muy
        dentro de umbral_activo=300) pero con buffer='A' y pendientes=5 ->
        el algoritmo ya NO prioriza el contacto reciente."""
        estado = _estado(minutos_desde_contacto=0)
        estado = _procesar(estado, estado_local_buffer='A', datos_pendientes_buffer=5)
        assert estado.estado_actual == 'BUFFER_ACTIVO', (
            "HALLAZGO NUEVO: el PASO 2 (buffer con pendientes>0) ahora tiene "
            "precedencia incluso sobre un heartbeat puntual (PASO 1)."
        )

    def test_heartbeat_puntual_con_buffer_lleno_l_tambien_produce_buffer_activo(self):
        """'L' (LLENO) ahora cuenta igual que 'A' (ACTIVO) para el PASO 2."""
        estado = _estado(minutos_desde_contacto=0)
        estado = _procesar(estado, estado_local_buffer='L', datos_pendientes_buffer=12)
        assert estado.estado_actual == 'BUFFER_ACTIVO', (
            "HALLAZGO NUEVO: 'L' (buffer lleno) activa el PASO 2 igual que 'A', "
            "algo que la ronda anterior no contemplaba (solo probaba 'A')."
        )

    def test_heartbeat_puntual_con_pendientes_en_cero_si_produce_activo(self):
        """Con datos_pendientes_buffer=0 (buffer ya vaciado), la letra 'A' sola
        ya no basta: el heartbeat puntual SÍ produce ACTIVO."""
        estado = _estado(minutos_desde_contacto=0)
        estado = _procesar(estado, estado_local_buffer='A', datos_pendientes_buffer=0)
        assert estado.estado_actual == 'ACTIVO', (
            "HALLAZGO NUEVO: datos_pendientes_buffer=0 libera el PASO 2 aunque "
            "estado_local_buffer siga en 'A' -- ya no es suficiente la sola letra."
        )


class TestSubCasoCBufferProlongadoSigueSinExistir:
    def test_no_existe_ninguna_alerta_de_buffer_prolongado(self):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src/telemetry').rglob('*.py')
            if 'BUFFER_PROLONGADO' in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (c) VIGENTE: 'BUFFER_PROLONGADO' sigue sin existir en ningun archivo de "
            f"src/telemetry/ tras el merge (encontrados: {archivos or 'ninguno'})."
        ) if not archivos else None


class TestSubCasoD1NotaDeTransicionSigueSiendoGenerica:
    def test_el_trigger_de_bd_usa_una_nota_generica_para_toda_transicion(self):
        ddl = (REPO_ROOT / 'alembic/baseline/esquema_baseline.sql').read_text(encoding='utf-8', errors='ignore')
        pytest.fail(
            "HALLAZGO (d1) VIGENTE, MECANISMO ACTUALIZADO: la nota de transicion la escribe "
            "ahora el trigger fn_log_transicion_dispositivo en BD, con el texto fijo "
            "'Transicion automatica de estado operativo' para TODA transicion -- sigue sin "
            "existir ningun marcador de 'inicio de sincronizacion' especifico para E6."
        ) if 'Transición automática de estado operativo' in ddl else None


class TestSubCasoEElJobPeriodicoYaNoOlvidaElBufferYRespetaLosPendientes:
    def test_el_adaptador_real_consulta_el_ultimo_buffer_declarado_en_bd(self):
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/adapters/parametros_heartbeat_mlops_adapter.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (e) INVERTIDO: ParametrosHeartbeatMLOpsAdapter.obtener_comunicacion() SI "
            "consulta en BD el ultimo estado_local_buffer declarado (subconsulta ORDER BY "
            "fecha_recepcion DESC LIMIT 1) -- la ronda anterior (codigo stale) afirmo que el job "
            "periodico siempre pasaba estado_local_buffer=None."
        ) if "ORDER BY h.fecha_recepcion DESC" in texto else None

    def test_el_adaptador_tambien_resuelve_datos_pendientes_buffer_desde_el_2026_10_27(self):
        """HALLAZGO NUEVO (INC-M03-127-G27, 761faa8b): el adaptador ahora
        trae tambien datos_pendientes_buffer del mismo ultimo heartbeat --
        sin este dato, evaluar_transicion() caeria al modo 'desconocido'
        (datos_pendientes_buffer=None), que solo mira la letra del buffer."""
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/adapters/parametros_heartbeat_mlops_adapter.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'datos_pendientes_buffer' in texto

    def test_evaluar_estado_dispositivos_use_case_ya_no_tiene_el_literal_buffer_none(self):
        archivo = REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'estado_local_buffer=None' not in texto

    def test_el_job_periodico_tambien_pasa_datos_pendientes_buffer_a_evaluar_transicion(self):
        """Confirma que el job periodico usa EXACTAMENTE el mismo criterio de
        vaciado que el heartbeat en vivo (mismo kwarg, mismo origen)."""
        archivo = REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'datos_pendientes_buffer=parametros.datos_pendientes_buffer' in texto


class TestSubCasoD2DatosPendientesBufferYaSiDecideElEstado:
    def test_datos_pendientes_buffer_es_parametro_real_de_evaluar_transicion(self):
        """HALLAZGO (d2) INVERTIDO: ya no es un campo que se persiste sin
        leerse -- es un kwarg real de evaluar_transicion() y decide si el
        PASO 2 se mantiene o se libera (ver TestSubCasoABis)."""
        import inspect
        firma = inspect.signature(EstadoDispositivoIoT.evaluar_transicion)
        pytest.fail(
            "HALLAZGO (d2) INVERTIDO: 'datos_pendientes_buffer' SI es un parametro real de "
            f"evaluar_transicion() -- firma real: {firma}."
        ) if 'datos_pendientes_buffer' in firma.parameters else None
