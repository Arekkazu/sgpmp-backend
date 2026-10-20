"""
TC-M03-G142 (RF-60 CA-12/CA-16/E9/Restricción 10/Fase 6, CU-09) -
"Correlación y causa primaria." Consolida CP-ALE-06/07, misma agrupación
que TC-M03-279 (ya ejecutado: (a) invalidado -- no existe jerarquía de
causas concurrentes, cada condición genera una alerta independiente, y
batería/conectividad son disparadores mutuamente excluyentes por
construcción; (b) FALLO_MASIVO no existe en el código).

RELACIÓN CON TC-M03-279 (NO duplicar): (a) y (b) ya están confirmados ahí.
Este archivo cubre SOLO (a3) [CORREGIDO]: "batería crítica + señal
degradada con contacto vigente: el dispositivo permanece ACTIVO y por tanto
NO hay periodo de inactividad donde escribir causa_primaria. La aserción se
hace sobre datos_diagnostico de la alerta (Fase 6), no sobre causa_primaria."

HALLAZGO: la premisa corregida de (a3) tampoco se sostiene -- el campo
`datos_diagnostico` que propone como alternativa NO EXISTE en la entidad
`Alerta` (`alerta.py`, dataclass completa revisada campo por campo: no hay
ningún campo con ese nombre ni similar). Mismo patrón que TC-M03-276(b) ya
encontró para el payload de alertas hacia RF-57 (`datos_diagnostico`
esperado -> real: campo `diagnostico`, distinto, y tampoco existe en esta
entidad base). No hay NINGÚN lugar donde escribir el detalle de "batería
crítica + señal degradada concurrentes" -- ni `causa_primaria` (correcto,
no aplica aquí, el dispositivo sigue ACTIVO) ni `datos_diagnostico`
(porque no existe). Lo único que SÍ ocurre es lo ya confirmado por
TC-279(a): dos alertas independientes (`BATERIA_CRITICA` y
`SEÑAL_DEGRADADA`), sin ninguna relación entre sí.

Primera mitad de (a3) -- CONFIRMADA correcta: con contacto vigente (heartbeat
recién llegado), el dispositivo efectivamente permanece ACTIVO sin importar
las alertas técnicas generadas -- `_generar_alertas_tecnicas()` nunca toca
`estado.estado_actual`.

Cómo se prueba: pytest a nivel de caso de uso.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g142_datos_diagnostico_no_existe.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G142.html --self-contained-html
"""
from __future__ import annotations

from dataclasses import fields, replace
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import (
    RecibirHeartbeatUseCase,
)
from src.telemetry.domain.entities.alerta import Alerta
from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT
from src.telemetry.infrastructure.dto.heartbeat_dto import HeartbeatDTO

AHORA = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)


def _estado() -> EstadoDispositivoIoT:
    return EstadoDispositivoIoT(
        id_estado_dispositivo_iot=1, id_dispositivo_iot=142, estado_actual='ACTIVO',
        fecha_ultimo_contacto=AHORA, id_ultimo_heartbeat=1, tiempo_sin_contacto=0,
        causa_primaria=None, causas_secundarias=None, fecha_ultima_actualizacion=AHORA, id_usuario=None,
    )


def _heartbeat_bateria_critica_y_senal_degradada() -> HeartbeatDTO:
    return HeartbeatDTO(
        tipo_mensaje='PERIODICO',
        nivel_bateria_pct=Decimal('5'),       # <= 10 -> BATERIA_CRITICA
        calidad_senal_rssi=Decimal('-110'),   # < -100 -> SEÑAL_DEGRADADA
        estado_local_buffer='I', datos_pendientes_buffer=0, fecha_registro=AHORA,
    )


class TestSubCasoA3DatosDiagnosticoNoExiste:
    """(a3) [CORREGIDO]: la ficha pide afirmar sobre datos_diagnostico en vez de
    causa_primaria -- ese campo tampoco existe en la entidad Alerta."""

    def test_alerta_no_tiene_campo_datos_diagnostico(self):
        nombres_campos = {f.name for f in fields(Alerta)}
        assert 'datos_diagnostico' not in nombres_campos, (
            'Si esto aparece, la entidad Alerta ya tiene datos_diagnostico -- (a3) podria '
            'verificarse tal cual la ficha pide.'
        )
        pytest.fail(
            f"HALLAZGO (a3): la entidad Alerta no declara ningun campo 'datos_diagnostico' -- "
            f"campos reales: {sorted(nombres_campos)!r}. La asercion que propone (a3) como "
            f"alternativa a causa_primaria no tiene donde apoyarse: no existe ningun lugar que "
            f"registre el detalle de 'bateria critica + senal degradada concurrentes'. Mismo "
            f"patron que TC-M03-276(b) (el payload real usa nombres de campo distintos a los que "
            f"la ficha asume en varios puntos)."
        )

    def test_dispositivo_permanece_activo_con_bateria_critica_y_senal_degradada_concurrentes(self):
        """Primera mitad de (a3), CONFIRMADA: contacto vigente -> ACTIVO, sin importar
        las alertas tecnicas generadas en paralelo."""
        db = MagicMock()
        dispositivo_port = MagicMock()
        dispositivo_port.validar_dispositivo_heartbeat.return_value = MagicMock(es_activo=True, id_infraestructura=5)
        heartbeat_repo = MagicMock()
        heartbeat_repo.guardar.side_effect = lambda hb: replace(hb, id_heartbeat=1)
        estado = _estado()
        estado_repo = MagicMock()
        estado_repo.obtener_por_dispositivo.return_value = estado
        periodo_repo = MagicMock()
        periodo_repo.obtener_abierto_por_dispositivo.return_value = None
        alerta_repo = MagicMock()
        alerta_repo.guardar.side_effect = lambda a: replace(a, id_alerta=1)
        uc = RecibirHeartbeatUseCase(
            db=db, dispositivo_port=dispositivo_port, heartbeat_repo=heartbeat_repo,
            estado_repo=estado_repo, transicion_repo=MagicMock(), periodo_repo=periodo_repo,
            alerta_repo=alerta_repo, historico_alerta_repo=MagicMock(),
        )

        uc.execute(_heartbeat_bateria_critica_y_senal_degradada(), device_id=142, access_key='k')

        assert estado.estado_actual == 'ACTIVO'
        periodo_repo.abrir.assert_not_called()  # sin periodo de inactividad: confirma la premisa de (a3)
        tipos_generados = sorted(c.args[0].tipo_variable for c in alerta_repo.guardar.call_args_list)
        assert tipos_generados == ['BATERIA_CRITICA', 'SEÑAL_DEGRADADA'], (
            f'se generaron: {tipos_generados!r} -- dos alertas independientes, sin relacion entre '
            f'si (mismo hallazgo de TC-M03-279(a), reconfirmado aqui con el escenario exacto de (a3)).'
        )
