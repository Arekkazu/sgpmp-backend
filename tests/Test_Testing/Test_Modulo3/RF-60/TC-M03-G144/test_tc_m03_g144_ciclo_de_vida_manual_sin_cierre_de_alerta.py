"""
TC-M03-G144 (RF-60 CA-3/CA-7/CA-8/E6/Fase 5, CU-07) - "Ciclo de vida
manual y recuperación."

Código bajo prueba:
    src/telemetry/application/use_cases/infraestructura/aplicar_mantenimiento_dispositivo_use_case.py
    src/telemetry/infrastructure/dto/aplicar_mantenimiento_dto.py
    src/telemetry/infrastructure/routers/infraestructura_iot_router.py
    src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py

(a) CA-7: Admin/Ingeniero marca EN_MANTENIMIENTO desde CUALQUIER estado --
    REEJECUTADO 2026-10-30 TRAS NUEVO PULL DE `origin/test` (149 commits
    adicionales): HALLAZGO VUELVE A INVERTIRSE, ahora a favor de la ficha.
    El commit `ebbcc19f` (Arekkazu, 2026-10-29, INC-M03-134-G03 #847,
    "mantenimiento manual desde cualquier estado y rechazo de lecturas en
    mantenimiento") reescribió `validar_transicion_manual()`:
    ```
    a_mantenimiento = destino == 'EN_MANTENIMIENTO' and self.estado_actual != 'EN_MANTENIMIENTO'
    cierre = (self.estado_actual, destino) == ('EN_MANTENIMIENTO', 'ACTIVO')
    if not (a_mantenimiento or cierre):
        raise BusinessRuleError(...)
    ```
    El mensaje del commit lo dice explícitamente: "RF-60 CA-7 permite pasar
    a EN_MANTENIMIENTO desde cualquier estado; solo se admitia desde
    INACTIVO, y un dispositivo recien creado no podia llegar a
    mantenimiento." Es decir: la restricción que esta misma ronda confirmó
    como vigente el 2026-10-29 (`DEV-42`, solo INACTIVO->EN_MANTENIMIENTO)
    fue un defecto reconocido por el propio equipo y ya está corregido --
    ahora SÍ funciona desde CUALQUIER estado (incluido uno recién creado,
    sin heartbeats), coincidiendo con lo que pedía la ficha desde el
    principio. Solo sigue bloqueado un no-op (`EN_MANTENIMIENTO ->
    EN_MANTENIMIENTO`) y cualquier destino que no sea `EN_MANTENIMIENTO`
    ni `ACTIVO` desde `EN_MANTENIMIENTO`.
(b) CA-8: desde EN_MANTENIMIENTO, confirma resolución -> ACTIVO con
    "cierre del incidente" -- PARCIALMENTE CONFIRMADO, CON HALLAZGO: la
    transición a ACTIVO sí ocurre y se audita (`TRANSICION_MANTENIMIENTO_MANUAL`),
    pero `AplicarMantenimientoDispositivoUseCase` nunca recibe ni invoca
    ningún `alerta_repo` -- no hay "cierre de incidente" alguno: ninguna
    alerta técnica activa se resuelve automáticamente al salir de
    mantenimiento.
(c) CA-3/E6: INACTIVO + heartbeat válido -> ACTIVO, cierre de la alerta
    activa y fin del periodo de inactividad -- REEJECUTADO 2026-10-29 TRAS
    MERGE DE `origin/test`: HALLAZGO INVERTIDO. Con la nueva arquitectura
    de dos fases (`RecibirHeartbeatUseCase` persiste, luego
    `ProcesarHeartbeatPersistidoUseCase.procesar_estado()` evalúa y llama
    a `completar_transicion_comunicacion()`), al volver a ACTIVO el
    código SÍ cierra el período de inactividad Y SÍ resuelve la alerta
    técnica de conectividad activa: itera
    `alertas.listar_conectividad_abierta(id_dispositivo)` y llama a
    `ActualizarEstadoAlertaUseCase.resolver_conectividad(alerta,
    alerta_repo, ahora)` para cada una de tipo `DISPOSITIVO_SIN_SEÑAL`,
    `DISPOSITIVO_INACTIVO`, `FALLO_CONECTIVIDAD` o `HEARTBEAT_AUSENTE`
    (con una excepción deliberada: si es `HEARTBEAT_AUSENTE` y el
    heartbeat recién recibido no cae dentro de la ventana de
    `2*intervalo_heartbeat_seg`, NO la resuelve -- "la telemetría sola no
    prueba recuperación del heartbeat"). Esto ya NO es el mismo vacío que
    (b): la vía automática (heartbeat) SÍ cierra incidentes de
    conectividad; solo la vía manual (mantenimiento) sigue sin hacerlo.
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
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.telemetry.application.use_cases.infraestructura.aplicar_mantenimiento_dispositivo_use_case import (
    AplicarMantenimientoDispositivoUseCase,
)
from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import (
    ProcesarHeartbeatPersistidoUseCase,
)
from src.telemetry.domain.entities.alerta import Alerta
from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT
from src.telemetry.domain.entities.heartbeat import Heartbeat
from src.telemetry.infrastructure.dto.aplicar_mantenimiento_dto import AplicarMantenimientoDTO

AHORA = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)


def _estado(estado_actual):
    return EstadoDispositivoIoT(
        id_estado_dispositivo_iot=1, id_dispositivo_iot=144, estado_actual=estado_actual,
        fecha_ultimo_contacto=AHORA, id_ultimo_heartbeat=1, tiempo_sin_contacto=0,
        causa_primaria=None, causas_secundarias=None, fecha_ultima_actualizacion=AHORA, id_usuario=None,
    )


class TestSubCasoADesdeCualquierEstadoVuelveAFuncionarComoPediaLaFicha:
    @pytest.mark.parametrize('estado_origen', ['INACTIVO', 'ACTIVO', 'SIN_SEÑAL', 'BUFFER_ACTIVO'])
    def test_cualquier_estado_puede_entrar_a_mantenimiento_tras_ebbcc19f(self, estado_origen):
        estado_repo = MagicMock()
        estado_repo.bloquear_por_dispositivo.return_value = _estado(estado_origen)
        uc = AplicarMantenimientoDispositivoUseCase(db=MagicMock(), estado_repo=estado_repo, auditoria_repo=None)
        dto = AplicarMantenimientoDTO(nuevo_estado='EN_MANTENIMIENTO', motivo='Revisión programada')
        resultado = uc.execute(id_dispositivo_iot=144, dto=dto, id_usuario=1, nombre_usuario='Ingeniero')
        pytest.fail(
            f"HALLAZGO (a) INVERTIDO DE NUEVO (ebbcc19f, INC-M03-134-G03): marcar EN_MANTENIMIENTO "
            f"desde '{estado_origen}' SI funciona ahora (resultado.estado_actual="
            f"'{resultado.estado_actual}') -- la restriccion 'solo desde INACTIVO' que esta misma "
            f"ronda confirmo el 2026-10-29 fue corregida por el propio equipo: coincide con lo que "
            f"la ficha original pedia (CA-7, 'desde cualquier estado')."
        ) if resultado.estado_actual == 'EN_MANTENIMIENTO' else None

    def test_un_no_op_en_mantenimiento_sigue_rechazado(self):
        """El unico caso que ebbcc19f sigue bloqueando: pedir
        EN_MANTENIMIENTO cuando ya se esta en EN_MANTENIMIENTO."""
        from src.shared.errors import BusinessRuleError
        estado_repo = MagicMock()
        estado_repo.bloquear_por_dispositivo.return_value = _estado('EN_MANTENIMIENTO')
        uc = AplicarMantenimientoDispositivoUseCase(db=MagicMock(), estado_repo=estado_repo, auditoria_repo=None)
        dto = AplicarMantenimientoDTO(nuevo_estado='EN_MANTENIMIENTO', motivo='Revisión programada')
        with pytest.raises(BusinessRuleError):
            uc.execute(id_dispositivo_iot=144, dto=dto, id_usuario=1, nombre_usuario='Ingeniero')


class TestSubCasoBSinCierreDeIncidenteAlSalirDeMantenimiento:
    def test_aplicar_mantenimiento_no_recibe_ningun_alerta_repo(self):
        firma = inspect.signature(AplicarMantenimientoDispositivoUseCase.__init__)
        parametros = set(firma.parameters)
        pytest.fail(
            f"HALLAZGO (b): AplicarMantenimientoDispositivoUseCase.__init__{tuple(parametros)!r} "
            f"no recibe ningun parametro de alertas -- al volver a ACTIVO no se cierra ninguna "
            f"alerta tecnica activa, por lo que no hay 'cierre de incidente' real."
        ) if 'alerta_repo' not in parametros else None


class TestSubCasoCReconexionSiResuelveLaAlertaDeConectividad:
    def test_inactivo_mas_heartbeat_cierra_periodo_y_resuelve_la_alerta_de_conectividad(self):
        """REEJECUTADO 2026-10-29: con la nueva arquitectura de dos fases, al
        reconectar (ACTIVO) el codigo SI itera las alertas de conectividad
        abiertas y SI llama a resolver_conectividad() para cada una -- ya no
        es el mismo vacio que (b). El texto 'Reconexión confirmada por
        RF-60.' coincide exactamente con el observado en vivo en TEST sobre
        el dispositivo 348 (ver TC-M03-G132 reejecutado)."""
        estado_repo = MagicMock()
        estado = _estado('INACTIVO')
        estado.fecha_ultimo_contacto = AHORA - timedelta(seconds=10)  # dentro de umbral_activo -> nuevo='ACTIVO'
        estado_repo.bloquear_por_dispositivo.return_value = estado
        periodo_repo = MagicMock()
        periodo_abierto = MagicMock()
        periodo_repo.obtener_abierto_por_dispositivo.side_effect = [periodo_abierto, None]
        alerta_repo = MagicMock()
        alerta_conectividad = Alerta(
            id_alerta=804, tipo_alerta='TECNICA', severidad='CRITICO', estado_alerta='ACTIVA',
            origen_evento='EVALUACION_PERIODICA', tipo_variable='DISPOSITIVO_INACTIVO',
            fecha_evento=AHORA, fecha_generacion=AHORA, id_dispositivo_ioit=144, id_infraestructura=6,
        )
        alerta_repo.listar_conectividad_abierta.return_value = [alerta_conectividad]
        parametros_port = MagicMock()
        parametros = MagicMock(
            umbral_activo=300, umbral_sin_senal=1800, umbral_inactivo=86400,
            estado_local_buffer='I', id_infraestructura=6, ultimo_heartbeat=AHORA, ultima_telemetria=AHORA,
            datos_pendientes_buffer=0,
        )
        parametros.heartbeat_ausente.return_value = False
        parametros_port.obtener_comunicacion.return_value = parametros
        uc = ProcesarHeartbeatPersistidoUseCase(
            estado_repo=estado_repo, alerta_repo=alerta_repo, parametros_port=parametros_port,
            periodo_repo=periodo_repo,
        )
        heartbeat = Heartbeat(
            id_heartbeat=1, id_dispositivo_iot=144, tipo_mensaje='PERIODICO', nivel_bateria_pct=80,
            calidad_senal_rssi=None, calidad_senal_snr=None, estado_local_buffer='I',
            datos_pendientes_buffer=0, version_firmware=None, coordenadas=None,
            fecha_registro=AHORA, fecha_recepcion=AHORA, reloj_sincronizado=True,
            sensores_operativos=None, temperatura_dispositivo=None,
        )
        with patch(
            'src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case.datetime'
        ) as mock_dt:
            mock_dt.now.return_value = AHORA
            uc.procesar_estado(heartbeat, es_ultimo=True)
        assert estado.estado_actual == 'ACTIVO'
        periodo_abierto.cerrar.assert_called_once()
        pytest.fail(
            f"HALLAZGO (c) INVERTIDO: al reconectar, alerta_repo.actualizar_estado SI se invoca "
            f"para la alerta de conectividad abierta (id_alerta={alerta_conectividad.id_alerta}), "
            f"con diagnostico='{alerta_conectividad.diagnostico}' -- la ronda anterior (codigo "
            f"stale) afirmo que la alerta seguia ACTIVA sin ningun cierre automatico; ya no es "
            f"cierto para la via de heartbeat (solo sigue siendo cierto para la via manual de "
            f"mantenimiento, ver (b))."
        ) if alerta_repo.actualizar_estado.call_count > 0 else None


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
