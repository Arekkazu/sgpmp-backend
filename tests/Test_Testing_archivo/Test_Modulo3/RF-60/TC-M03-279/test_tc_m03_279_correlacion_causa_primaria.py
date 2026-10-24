"""
TC-M03-279 (RF-60 CA-12/CA-16/E9/Restricción 10, CU-09) - Correlación y causa
primaria.

HALLAZGO PRINCIPAL (invalida (a) tal como la ficha la plantea): no existe
ninguna jerarquía que resuelva condiciones CONCURRENTES a una sola causa
primaria. `_generar_alertas_tecnicas()` (dentro de
`recibir_heartbeat_use_case.py`) evalúa batería y señal en bloques `if`
INDEPENDIENTES (no `if/elif`): si un mismo heartbeat trae batería baja Y
señal degradada a la vez, el código genera DOS alertas separadas
(`BATERIA_BAJA` y `SEÑAL_DEGRADADA`), no UNA sola con la causa "ganadora"
según ninguna jerarquía. No hay ningún campo `datos_diagnostico` ni ninguna
noción de "causa secundaria" en la entidad `Alerta` -- cada condición
detectada es una fila de alerta independiente, con su propio `tipo_variable`
y severidad, sin relación entre sí más allá de compartir `id_dispositivo_ioit`
y `fecha_evento`.

Además, "batería crítica + pérdida de conectividad" (el primer escenario de
(a)) describe una combinación que el código no puede producir en el mismo
punto de evaluación: las alertas de batería solo se generan cuando SÍ llega
un heartbeat (`_generar_alertas_tecnicas`, dentro de
`recibir_heartbeat_use_case.py`), mientras que `FALLO_CONECTIVIDAD` solo lo
genera la tarea periódica cuando NO llega ningún heartbeat
(`evaluar_estado_dispositivos_use_case.py`). Son dos use cases distintos, con
disparadores mutuamente excluyentes por construcción (uno necesita un
heartbeat reciente, el otro necesita la ausencia de uno) -- no hay ningún
punto del código donde ambas señales lleguen juntas para que una jerarquía
tenga algo que resolver.

(b) CONFIRMADO (ya anticipado en el triage inicial del lote): cero código
para `FALLO_MASIVO`, "jerarquía" o correlación entre dispositivos de la misma
unidad productiva (búsqueda exhaustiva, incluyendo `procesar_evento_alerta_dto.py`
que solo tiene un campo `correlacion_variables` sin uso real detectado). N
dispositivos cayendo en la misma ventana generan N alertas `FALLO_CONECTIVIDAD`
completamente independientes, nunca una alerta unificada.

Cómo correrlo (desde la raíz del repo; stub de fcntl en Windows):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_279_correlacion_causa_primaria.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-279.html --self-contained-html
"""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import (
    RecibirHeartbeatUseCase,
)
from src.telemetry.infrastructure.dto.heartbeat_dto import HeartbeatDTO

REPO_ROOT = Path(__file__).resolve().parents[5]
T0 = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)


def _use_case_con_dobles(estado_existente):
    db = MagicMock()
    dispositivo_port = MagicMock()
    dispositivo_port.validar_dispositivo_heartbeat.return_value = MagicMock(es_activo=True, id_infraestructura=5)
    heartbeat_repo = MagicMock()
    heartbeat_repo.guardar.side_effect = lambda hb: replace(hb, id_heartbeat=1)
    estado_repo = MagicMock()
    estado_repo.obtener_por_dispositivo.return_value = estado_existente
    alerta_repo = MagicMock()
    uc = RecibirHeartbeatUseCase(
        db=db, dispositivo_port=dispositivo_port, heartbeat_repo=heartbeat_repo,
        estado_repo=estado_repo, transicion_repo=MagicMock(), periodo_repo=MagicMock(),
        alerta_repo=alerta_repo, historico_alerta_repo=MagicMock(),
    )
    return uc, alerta_repo


class TestGrupoACondicionesConcurrentesGeneranAlertasSeparadasNoUnaJerarquia:

    def test_bateria_baja_y_senal_degradada_simultaneas_generan_2_alertas_independientes(self):
        from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT

        estado = EstadoDispositivoIoT(
            id_estado_dispositivo_iot=1, id_dispositivo_iot=1, estado_actual='ACTIVO',
            fecha_ultimo_contacto=T0, id_ultimo_heartbeat=1, tiempo_sin_contacto=0,
            causa_primaria=None, causas_secundarias=None, fecha_ultima_actualizacion=T0, id_usuario=None,
        )
        uc, alerta_repo = _use_case_con_dobles(estado)
        dto = HeartbeatDTO(
            tipo_mensaje='PERIODICO', fecha_registro=T0,
            nivel_bateria_pct=Decimal('20'),       # <=30 -> BATERIA_BAJA
            calidad_senal_rssi=Decimal('-110'),    # <-100 -> SEÑAL_DEGRADADA
        )
        uc.execute(dto, device_id=1, access_key='k')

        causas_generadas = [c.args[0].tipo_variable for c in alerta_repo.guardar.call_args_list]
        pytest.fail(
            f"HALLAZGO (a): con bateria_baja Y senal_degradada en el MISMO heartbeat, se generaron "
            f"{len(causas_generadas)} alertas independientes ({causas_generadas}), no UNA sola "
            f"resuelta por jerarquia (la ficha esperaba que ganara BATERIA_BAJA). No existe ningun "
            f"mecanismo que fusione o priorice condiciones concurrentes -- cada una genera su propia "
            f"fila de alerta, sin 'causa secundaria' ni 'datos_diagnostico'."
        ) if len(causas_generadas) > 1 else None

    def test_bateria_critica_y_senal_degradada_tambien_generan_2_alertas(self):
        from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT

        estado = EstadoDispositivoIoT(
            id_estado_dispositivo_iot=1, id_dispositivo_iot=1, estado_actual='ACTIVO',
            fecha_ultimo_contacto=T0, id_ultimo_heartbeat=1, tiempo_sin_contacto=0,
            causa_primaria=None, causas_secundarias=None, fecha_ultima_actualizacion=T0, id_usuario=None,
        )
        uc, alerta_repo = _use_case_con_dobles(estado)
        dto = HeartbeatDTO(
            tipo_mensaje='PERIODICO', fecha_registro=T0,
            nivel_bateria_pct=Decimal('5'),        # <=10 -> BATERIA_CRITICA
            calidad_senal_rssi=Decimal('-110'),    # <-100 -> SEÑAL_DEGRADADA
        )
        uc.execute(dto, device_id=1, access_key='k')
        assert alerta_repo.guardar.call_count == 2, (
            'se esperaban 2 alertas independientes (BATERIA_CRITICA y SEÑAL_DEGRADADA), confirmando '
            'que no hay jerarquia que descarte la secundaria'
        )

    def test_bateria_critica_y_fallo_conectividad_son_use_cases_mutuamente_excluyentes(self):
        """Confirma por que el primer escenario de (a) no es representable: las alertas de bateria
        solo nacen de un heartbeat RECIBIDO; FALLO_CONECTIVIDAD solo nace de la AUSENCIA de
        heartbeats. No hay un punto de codigo donde ambas señales coexistan."""
        heartbeat_file = REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py'
        job_file = REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py'
        assert 'BATERIA_CRITICA' in heartbeat_file.read_text(encoding='utf-8')
        assert 'BATERIA_CRITICA' not in job_file.read_text(encoding='utf-8')
        assert 'FALLO_CONECTIVIDAD' in job_file.read_text(encoding='utf-8')
        assert 'FALLO_CONECTIVIDAD' not in heartbeat_file.read_text(encoding='utf-8') or (
            heartbeat_file.read_text(encoding='utf-8').count('FALLO_CONECTIVIDAD') == 0
        )


class TestGrupoBSinFalloMasivoNiAgrupacionPorUnidadProductiva:

    def test_no_existe_codigo_de_fallo_masivo_ni_jerarquia_de_correlacion(self):
        archivos_con_fallo_masivo = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src' / 'telemetry').rglob('*.py')
            if re.search(r'FALLO_MASIVO|FALLO_INFRAESTRUCTURA_COMPARTIDA.*agrup|incidente.*unificado', p.read_text(encoding='utf-8', errors='ignore'), re.I)
        ]
        pytest.fail(
            f"HALLAZGO (b): no existe codigo para FALLO_MASIVO ni agrupacion de alertas por unidad "
            f"productiva en src/telemetry (encontrado: {archivos_con_fallo_masivo or 'ninguno'}). "
            f"N dispositivos de la misma unidad cayendo en la misma ventana generarian N alertas "
            f"FALLO_CONECTIVIDAD independientes, nunca una sola unificada con causa_primaria="
            f"FALLO_INFRAESTRUCTURA_COMPARTIDA."
        ) if not archivos_con_fallo_masivo else None

    def test_fallo_infraestructura_compartida_existe_solo_como_valor_de_enum_sin_logica(self):
        """FALLO_INFRAESTRUCTURA_COMPARTIDA SI es un valor valido del enum_causa_inactividad (ver
        anotaciones/modulo_3/implementacion_dev_m03_rf60_rf62.md), pero ningun caso de uso lo asigna."""
        archivos = [
            REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py',
            REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py',
        ]
        asignaciones = [a.name for a in archivos if 'FALLO_INFRAESTRUCTURA_COMPARTIDA' in a.read_text(encoding='utf-8')]
        assert asignaciones == [], f'se esperaba que ningun caso de uso asignara esta causa; se encontro en: {asignaciones}'
