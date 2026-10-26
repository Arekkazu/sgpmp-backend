"""
TC-M03-G144 (RF-60 CA-3/CA-7/CA-8/E6/Fase 5, CU-07) - "Ciclo de vida
manual y recuperación."

Código bajo prueba:
    src/telemetry/application/use_cases/infraestructura/aplicar_mantenimiento_dispositivo_use_case.py
    src/telemetry/infrastructure/dto/aplicar_mantenimiento_dto.py
    src/telemetry/infrastructure/routers/infraestructura_iot_router.py
    src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py

(a) CA-7: Admin/Ingeniero marca EN_MANTENIMIENTO desde CUALQUIER estado --
    CONFIRMADO CORRECTO: la transición es genérica (solo valida
    `estado_anterior != nuevo_estado`), sin restricción de origen; el
    DTO acota `nuevo_estado` a exactamente {EN_MANTENIMIENTO, ACTIVO}.
(b) CA-8: desde EN_MANTENIMIENTO, confirma resolución -> ACTIVO con
    "cierre del incidente" -- PARCIALMENTE CONFIRMADO, CON HALLAZGO: la
    transición a ACTIVO sí ocurre y se audita (`TRANSICION_MANTENIMIENTO_MANUAL`),
    pero `AplicarMantenimientoDispositivoUseCase` nunca recibe ni invoca
    ningún `alerta_repo` -- no hay "cierre de incidente" alguno: ninguna
    alerta técnica activa se resuelve automáticamente al salir de
    mantenimiento.
(c) CA-3/E6: INACTIVO + heartbeat válido -> ACTIVO, cierre de la alerta
    activa y fin del periodo de inactividad -- PARCIALMENTE CONFIRMADO,
    MISMO HALLAZGO: `recibir_heartbeat_use_case.py` SÍ cierra el periodo
    de inactividad (`periodo.cerrar(ahora)`) al reconectar, pero nunca
    toca `alerta_repo` en esa misma ruta -- la alerta activa asociada
    sigue sin resolverse, exactamente el mismo vacío que (b).
(d) Productor/Veterinario -> 403 -- CONFIRMADO CORRECTO: el endpoint
    real (`PATCH /iot/dispositivos/{id}/mantenimiento`) usa
    `require_permission(35, 3)`, documentado explícitamente como "solo
    Admin, Ing" en el propio router.

Cómo se prueba: pytest a nivel de caso de uso para (a)/(b)/(c) +
`TestClient` con `monkeypatch` de `rbac.tiene_permiso` para (d).

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g144_ciclo_de_vida_manual_sin_cierre_de_alerta.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G144.html --self-contained-html
"""
from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.telemetry.application.use_cases.infraestructura.aplicar_mantenimiento_dispositivo_use_case import (
    AplicarMantenimientoDispositivoUseCase,
)
from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import (
    RecibirHeartbeatUseCase,
)
from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT
from src.telemetry.infrastructure.dto.aplicar_mantenimiento_dto import AplicarMantenimientoDTO
from src.telemetry.infrastructure.dto.heartbeat_dto import HeartbeatDTO

AHORA = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)


def _estado(estado_actual):
    return EstadoDispositivoIoT(
        id_estado_dispositivo_iot=1, id_dispositivo_iot=144, estado_actual=estado_actual,
        fecha_ultimo_contacto=AHORA, id_ultimo_heartbeat=1, tiempo_sin_contacto=0,
        causa_primaria=None, causas_secundarias=None, fecha_ultima_actualizacion=AHORA, id_usuario=None,
    )


class TestSubCasoACualquierEstadoHaciaMantenimientoConfirmadoCorrecto:
    @pytest.mark.parametrize('estado_origen', ['ACTIVO', 'SIN_SEÑAL', 'BUFFER_ACTIVO', 'INACTIVO'])
    def test_transicion_a_mantenimiento_funciona_desde_cualquier_estado(self, estado_origen):
        estado_repo = MagicMock()
        estado_repo.obtener_por_dispositivo.return_value = _estado(estado_origen)
        uc = AplicarMantenimientoDispositivoUseCase(db=MagicMock(), estado_repo=estado_repo, auditoria_repo=None)
        dto = AplicarMantenimientoDTO(nuevo_estado='EN_MANTENIMIENTO', motivo='Revisión programada')
        resultado = uc.execute(id_dispositivo_iot=144, dto=dto, id_usuario=1, nombre_usuario='Ingeniero')
        assert resultado.estado_actual == 'EN_MANTENIMIENTO'


class TestSubCasoBSinCierreDeIncidenteAlSalirDeMantenimiento:
    def test_aplicar_mantenimiento_no_recibe_ningun_alerta_repo(self):
        firma = inspect.signature(AplicarMantenimientoDispositivoUseCase.__init__)
        parametros = set(firma.parameters)
        pytest.fail(
            f"HALLAZGO (b): AplicarMantenimientoDispositivoUseCase.__init__{tuple(parametros)!r} "
            f"no recibe ningun parametro de alertas -- al volver a ACTIVO no se cierra ninguna "
            f"alerta tecnica activa, por lo que no hay 'cierre de incidente' real."
        ) if 'alerta_repo' not in parametros else None


class TestSubCasoCReconexionCierraPeriodoPeroNoLaAlerta:
    def test_inactivo_mas_heartbeat_cierra_periodo_pero_nunca_toca_alerta_repo(self):
        dispositivo_port = MagicMock()
        dispositivo_port.validar_dispositivo_heartbeat.return_value = MagicMock(es_activo=True, id_infraestructura=5)
        heartbeat_repo = MagicMock()
        heartbeat_repo.guardar.side_effect = lambda hb: replace(hb, id_heartbeat=1)
        estado_repo = MagicMock()
        estado = _estado('INACTIVO')
        estado.fecha_ultimo_contacto = AHORA - timedelta(hours=30)
        estado_repo.obtener_por_dispositivo.return_value = estado
        periodo_repo = MagicMock()
        periodo_abierto = MagicMock()
        periodo_repo.obtener_abierto_por_dispositivo.return_value = periodo_abierto
        alerta_repo = MagicMock()
        uc = RecibirHeartbeatUseCase(
            db=MagicMock(), dispositivo_port=dispositivo_port, heartbeat_repo=heartbeat_repo,
            estado_repo=estado_repo, transicion_repo=MagicMock(), periodo_repo=periodo_repo,
            alerta_repo=alerta_repo, historico_alerta_repo=MagicMock(),
        )
        dto = HeartbeatDTO(
            tipo_mensaje='PERIODICO', nivel_bateria_pct=Decimal('80'), estado_local_buffer='I',
            datos_pendientes_buffer=0, fecha_registro=AHORA,
        )
        uc.execute(dto, device_id=144, access_key='k')
        assert estado.estado_actual == 'ACTIVO'
        periodo_abierto.cerrar.assert_called_once()
        pytest.fail(
            "HALLAZGO (c): el periodo de inactividad SI se cierra al reconectar, pero "
            "alerta_repo.guardar/actualizar_estado nunca se invoca en esta ruta -- la alerta "
            "tecnica activa asociada al dispositivo sigue ACTIVA tras la reconexion, sin "
            "ningun cierre automatico."
        ) if alerta_repo.guardar.call_count == 0 and alerta_repo.actualizar_estado.call_count == 0 else None


class TestSubCasoDRbacConfirmadoCorrecto:
    def test_productor_recibe_403_al_intentar_mantenimiento(self, monkeypatch):
        from fastapi import Request
        from fastapi.responses import JSONResponse

        from src.identity_access.domain.entities.cuenta import Cuenta
        from src.identity_access.infrastructure.dependencies import get_current_user
        from src.shared import rbac
        from src.shared.database import get_db
        from src.shared.errors import AuthorizationError
        from src.telemetry.infrastructure.routers import infraestructura_iot_router as router_module

        monkeypatch.setattr(rbac, 'tiene_permiso', lambda *_args, **_kwargs: False)

        app = FastAPI()
        app.include_router(router_module.router)

        @app.exception_handler(AuthorizationError)
        async def _handler(_request: Request, exc: AuthorizationError):
            return JSONResponse(status_code=403, content={"code": exc.code, "message": exc.message})

        app.dependency_overrides[get_db] = lambda: MagicMock()
        app.dependency_overrides[get_current_user] = lambda: MagicMock(
            id_usuario=1, id_rol=3, id_estado_cuenta=Cuenta.ESTADO_ACTIVO,
        )  # rol Productor, cuenta activa
        with TestClient(app, raise_server_exceptions=False) as client:
            respuesta = client.patch(
                '/iot/dispositivos/144/mantenimiento',
                json={'nuevo_estado': 'EN_MANTENIMIENTO', 'motivo': 'intento no autorizado'},
            )
        assert respuesta.status_code == 403
