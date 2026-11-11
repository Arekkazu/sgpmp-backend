"""
TC-M03-G133 (RF-60 CA-2/CA-18/CA-21/PASO 2/E6, CU-04) - "Precedencia del
PASO 2 (buffer) sobre el PASO 3 (sin señal)."

Código bajo prueba:
    src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py
    src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py

(a)/(b) CA-21/CA-18, heartbeat con estado_local_buffer='A' -> BUFFER_ACTIVO
    -- CONFIRMADO CORRECTO: el Paso 5 de `recibir_heartbeat_use_case.py`
    fija `nuevo_estado = 'BUFFER_ACTIVO'` siempre que `dto.estado_local_buffer
    == 'A'`, sin alerta de inactividad.
(c) Alerta `BUFFER_PROLONGADO` al superar un umbral configurable --
    HALLAZGO: `BUFFER_PROLONGADO`/`umbral_buffer_prolongado` no existen
    en ningún archivo de `src/telemetry/` -- no hay ninguna alerta de
    buffer prolongado implementada.
(d1) Heartbeat de reconexión con `datos_pendientes_buffer > 0` ->
    ACTIVO inmediato + registro de "inicio de sincronización" (E6) --
    PARCIALMENTE CONFIRMADO, CON HALLAZGO: la transición a ACTIVO
    inmediato sí ocurre (el Paso 5 fija ACTIVO cuando
    `estado_local_buffer != 'A'`, sin mirar `datos_pendientes_buffer`);
    pero no existe ningún evento ni registro de "inicio de
    sincronización" -- la única nota que se guarda es el genérico
    "Transición por recepción de heartbeat.", igual para cualquier
    transición.
(d2) `datos_pendientes_buffer` decrece sin que el estado cambie --
    CONFIRMADO POR DISEÑO (sin hallazgo adicional a lo ya conocido): el
    campo se persiste en cada heartbeat pero nunca se evalúa en la
    lógica de transición (mismo patrón write-only ya documentado para
    otros campos de este módulo).
(e) Nodo con buffer ACTIVO declarado y silencio total de 8 h: ¿el PASO 2
    enmascara indefinidamente, sin techo temporal? -- HALLAZGO QUE
    REFUTA LA PREMISA DE LA FICHA, POR UN MOTIVO NO INTENCIONAL: el job
    periódico (`evaluar_estado_dispositivos_use_case.py`) llama a
    `evaluar_transicion()` con `estado_local_buffer=None` SIEMPRE
    (comentario propio del código: "sin heartbeat reciente → no
    conocemos buffer") -- nunca propaga el último valor de buffer
    declarado por el dispositivo. Esto significa que un nodo en
    BUFFER_ACTIVO que deja de enviar heartbeats por completo SÍ
    transiciona a SIN_SEÑAL/INACTIVO según el timeline normal, porque el
    job periódico "olvida" que el buffer estaba activo. No está
    enmascarado para siempre -- pero no por una regla deliberada de
    "techo temporal del PASO 2" (que no existe), sino porque el estado
    de buffer es efímero: solo se conoce mientras llegan heartbeats, y
    se pierde apenas dejan de llegar.

Cómo se prueba: pytest a nivel de caso de uso con `MagicMock`, siguiendo
el patrón de reloj fijo de la ronda anterior.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g133_precedencia_buffer_y_olvido_en_periodico.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G133.html --self-contained-html
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case import (
    EvaluarEstadoDispositivosUseCase,
)
from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import (
    RecibirHeartbeatUseCase,
)
from src.telemetry.domain.entities.estado_dispositivo_iot import (
    UMBRAL_INACTIVO_SEG, EstadoDispositivoIoT,
)
from src.telemetry.infrastructure.dto.heartbeat_dto import HeartbeatDTO

REPO_ROOT = Path(__file__).resolve().parents[5]
AHORA = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)


def _heartbeat_use_case():
    dispositivo_port = MagicMock()
    dispositivo_port.validar_dispositivo_heartbeat.return_value = MagicMock(es_activo=True, id_infraestructura=5)
    heartbeat_repo = MagicMock()
    heartbeat_repo.guardar.side_effect = lambda hb: replace(hb, id_heartbeat=1)
    estado_repo = MagicMock()
    periodo_repo = MagicMock()
    periodo_repo.obtener_abierto_por_dispositivo.return_value = None
    alerta_repo = MagicMock()
    uc = RecibirHeartbeatUseCase(
        db=MagicMock(), dispositivo_port=dispositivo_port, heartbeat_repo=heartbeat_repo,
        estado_repo=estado_repo, transicion_repo=MagicMock(), periodo_repo=periodo_repo,
        alerta_repo=alerta_repo, historico_alerta_repo=MagicMock(),
    )
    return uc, estado_repo, periodo_repo


class TestSubCasoAyBBufferActivoConfirmadoCorrecto:
    def test_estado_local_buffer_a_produce_buffer_activo(self):
        uc, estado_repo, _ = _heartbeat_use_case()
        estado = EstadoDispositivoIoT(
            id_estado_dispositivo_iot=1, id_dispositivo_iot=133, estado_actual='ACTIVO',
            fecha_ultimo_contacto=AHORA - timedelta(minutes=18), id_ultimo_heartbeat=1, tiempo_sin_contacto=0,
            causa_primaria=None, causas_secundarias=None, fecha_ultima_actualizacion=AHORA, id_usuario=None,
        )
        estado_repo.obtener_por_dispositivo.return_value = estado
        dto = HeartbeatDTO(
            tipo_mensaje='PERIODICO', nivel_bateria_pct=Decimal('80'), estado_local_buffer='A',
            datos_pendientes_buffer=5, fecha_registro=AHORA,
        )
        uc.execute(dto, device_id=133, access_key='k')
        assert estado.estado_actual == 'BUFFER_ACTIVO'


class TestSubCasoCBufferProlongadoNoExiste:
    def test_no_existe_ninguna_alerta_de_buffer_prolongado(self):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src/telemetry').rglob('*.py')
            if 'BUFFER_PROLONGADO' in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (c): 'BUFFER_PROLONGADO' no existe en ningun archivo de src/telemetry/ "
            f"(encontrados: {archivos or 'ninguno'})."
        ) if not archivos else None


class TestSubCasoD1SinRegistroDeInicioDeSincronizacion:
    def test_reconexion_con_datos_pendientes_no_genera_ningun_evento_de_sincronizacion(self):
        uc, estado_repo, periodo_repo = _heartbeat_use_case()
        estado = EstadoDispositivoIoT(
            id_estado_dispositivo_iot=1, id_dispositivo_iot=133, estado_actual='INACTIVO',
            fecha_ultimo_contacto=AHORA - timedelta(hours=30), id_ultimo_heartbeat=1, tiempo_sin_contacto=0,
            causa_primaria='FALLO_CONECTIVIDAD', causas_secundarias=None, fecha_ultima_actualizacion=AHORA, id_usuario=None,
        )
        estado_repo.obtener_por_dispositivo.return_value = estado
        periodo_repo.obtener_abierto_por_dispositivo.return_value = MagicMock()
        dto = HeartbeatDTO(
            tipo_mensaje='PERIODICO', nivel_bateria_pct=Decimal('80'), estado_local_buffer='I',
            datos_pendientes_buffer=200, fecha_registro=AHORA,
        )
        uc.execute(dto, device_id=133, access_key='k')
        assert estado.estado_actual == 'ACTIVO'
        llamada_transicion = uc.transicion_repo.registrar.call_args.args[0]
        pytest.fail(
            f"HALLAZGO (d1): la transicion a ACTIVO inmediato SI ocurre, pero la nota registrada "
            f"es '{llamada_transicion.notas}' -- el mismo texto generico para cualquier "
            f"transicion. No existe ningun evento o campo que marque el 'inicio de "
            f"sincronizacion' que pide E6."
        ) if llamada_transicion.notas == 'Transición por recepción de heartbeat.' else None


class TestSubCasoERefutaElEnmascaramientoIndefinidoPorOlvidoDelBuffer:
    def test_el_job_periodico_nunca_propaga_el_ultimo_buffer_declarado(self):
        archivo = REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        assert "estado_local_buffer=None" in texto

    def test_silencio_de_8h_con_buffer_activo_declarado_transiciona_igual_a_sin_senal(self):
        db = MagicMock()
        estado_repo = MagicMock()
        estado = EstadoDispositivoIoT(
            id_estado_dispositivo_iot=1, id_dispositivo_iot=133, estado_actual='BUFFER_ACTIVO',
            fecha_ultimo_contacto=AHORA - timedelta(hours=8), id_ultimo_heartbeat=1, tiempo_sin_contacto=0,
            causa_primaria=None, causas_secundarias=None, fecha_ultima_actualizacion=AHORA, id_usuario=None,
        )
        estado_repo.listar_activos.return_value = [estado]
        periodo_repo = MagicMock()
        periodo_repo.obtener_abierto_por_dispositivo.return_value = None
        uc = EvaluarEstadoDispositivosUseCase(
            db=db, estado_repo=estado_repo, transicion_repo=MagicMock(), periodo_repo=periodo_repo,
            alerta_repo=MagicMock(), historico_alerta_repo=MagicMock(),
        )
        with patch(
            'src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case.datetime'
        ) as mock_dt:
            mock_dt.now.return_value = AHORA
            uc.execute()
        pytest.fail(
            f"HALLAZGO (e), refuta la premisa de enmascaramiento indefinido: tras 8h de silencio "
            f"total con BUFFER_ACTIVO como ultimo estado conocido, el dispositivo transiciono a "
            f"'{estado.estado_actual}' (8h < 24h de UMBRAL_INACTIVO, por eso SIN_SEÑAL, no "
            f"INACTIVO) -- el job periodico SI saca al dispositivo de BUFFER_ACTIVO, porque "
            f"evalua con estado_local_buffer=None siempre. No queda enmascarado para siempre, "
            f"pero no por una regla deliberada de techo temporal -- es un efecto colateral de "
            f"que el buffer declarado se olvida en cuanto dejan de llegar heartbeats."
        ) if estado.estado_actual == 'SIN_SEÑAL' else None
