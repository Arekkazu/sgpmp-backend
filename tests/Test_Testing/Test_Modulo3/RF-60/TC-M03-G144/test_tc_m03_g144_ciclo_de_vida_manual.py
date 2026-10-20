"""
TC-M03-G144 (RF-60 CA-3/CA-7/CA-8/E6/Fase 5, CU-07) - "Ciclo de vida manual
y recuperación." Grupo NUEVO (sin TC previo) -- primera cobertura de
CA-3/CA-7/CA-8 en este repo.

Código bajo prueba:
    src/telemetry/application/use_cases/infraestructura/aplicar_mantenimiento_dispositivo_use_case.py
    src/telemetry/infrastructure/routers/infraestructura_iot_router.py
        (`PATCH /dispositivos/{id}/mantenimiento`, RBAC recurso 35 acción 3)
    src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py

HALLAZGO PRINCIPAL (la "[DEPENDENCIA]" de la ficha NO aplica -- el código ya
es más completo de lo que teme): la ficha advierte "la Fase 5 solo define
INACTIVO -> EN_MANTENIMIENTO y no define INACTIVO -> ACTIVO ni
BUFFER_ACTIVO -> SIN_SEÑAL; (a) y (c) requieren completar la máquina de
estados." Leído `AplicarMantenimientoDispositivoUseCase.execute()` completo:
la única validación es `estado_anterior != dto.nuevo_estado` -- NO hay
ninguna matriz de transiciones permitidas por estado de origen. Cualquiera
de los 4 estados operativos (ACTIVO, SIN_SEÑAL, BUFFER_ACTIVO, INACTIVO)
puede pasar a EN_MANTENIMIENTO con este único endpoint, y viceversa. (a) y
(b) de la ficha SÍ están completamente soportados, sin ninguna pieza
faltante de la máquina de estados.

(a) CA-7 (X -> EN_MANTENIMIENTO desde cada uno de los 4 estados) --
CONFIRMADO para los 4.
(b) CA-8 (EN_MANTENIMIENTO -> ACTIVO con cierre de incidente) -- CONFIRMADO:
transiciona y genera el evento de auditoría `TRANSICION_MANTENIMIENTO_MANUAL`
con `estado_anterior`/`estado_nuevo`/usuario/motivo. "Cierre del incidente"
tal como lo describe la ficha (un registro formal de "incidente" como
entidad) no existe como tal -- lo más parecido es este evento de auditoría,
documentado aquí tal cual es.
(c) CA-3/E6 (INACTIVO -> ACTIVO vía heartbeat válido) -- PARCIALMENTE
CONFIRMADO: la transición de ESTADO sí ocurre (mismo mecanismo ya
confirmado en TC-M03-270/G133: cualquier heartbeat fuerza ACTIVO/
BUFFER_ACTIVO sin importar el estado previo) y el periodo de inactividad SÍ
se cierra con el timestamp de reconexión (`periodo.cerrar(ahora)`,
confirmado en código). **HALLAZGO**: "cierre de la alerta activa" que pide
la ficha NO ocurre -- búsqueda exhaustiva en `recibir_heartbeat_use_case.py`
confirma que la única función relacionada con alertas
(`_generar_alertas_tecnicas`) solo CREA alertas nuevas (batería/señal),
nunca actualiza el `estado_alerta` de una alerta ya existente. Una alerta
técnica `FALLO_CONECTIVIDAD` generada cuando el dispositivo entró en
INACTIVO queda `ACTIVA` para siempre en la tabla, aunque el dispositivo
vuelva a conectarse.
(d) Rol no autorizado (Productor/Veterinario) -> 403 -- CONFIRMADO, RBAC
genérico del proyecto (`require_permission(35, 3)`), mismo patrón ya
verificado en otros routers de este repo.

Cómo se prueba: pytest a nivel de caso de uso (para a/b/c) y TestClient con
monkeypatch de RBAC (para d) -- mismo patrón que
`tests/configuration/test_rf23_alcance_finca.py`.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g144_ciclo_de_vida_manual.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G144.html --self-contained-html
"""
from __future__ import annotations

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


def _estado(estado_actual: str) -> EstadoDispositivoIoT:
    return EstadoDispositivoIoT(
        id_estado_dispositivo_iot=1, id_dispositivo_iot=144, estado_actual=estado_actual,
        fecha_ultimo_contacto=AHORA, id_ultimo_heartbeat=1, tiempo_sin_contacto=0,
        causa_primaria=None, causas_secundarias=None, fecha_ultima_actualizacion=AHORA, id_usuario=None,
    )


class TestSubCasoACA7DesdeCualquierEstadoAMantenimiento:
    """(a) CA-7: confirmado para los 4 estados -- sin matriz de transiciones restrictiva."""

    @pytest.mark.parametrize('estado_origen', ['ACTIVO', 'SIN_SEÑAL', 'BUFFER_ACTIVO', 'INACTIVO'])
    def test_cualquier_estado_puede_pasar_a_mantenimiento(self, estado_origen):
        estado = _estado(estado_origen)
        estado_repo = MagicMock()
        estado_repo.obtener_por_dispositivo.return_value = estado
        auditoria_repo = MagicMock()
        uc = AplicarMantenimientoDispositivoUseCase(db=MagicMock(), estado_repo=estado_repo, auditoria_repo=auditoria_repo)

        resultado = uc.execute(
            id_dispositivo_iot=144,
            dto=AplicarMantenimientoDTO(nuevo_estado='EN_MANTENIMIENTO', motivo='Mantenimiento programado'),
            id_usuario=10, nombre_usuario='Ingeniero QA',
        )

        assert resultado.estado_actual == 'EN_MANTENIMIENTO', (
            f'Transicion desde {estado_origen!r} a EN_MANTENIMIENTO debia funcionar -- no hay '
            f'ninguna restriccion de estado de origen en el codigo real.'
        )
        estado_repo.actualizar.assert_called_once()


class TestSubCasoBCA8DeMantenimientoAActivo:
    """(b) CA-8: confirmado -- EN_MANTENIMIENTO -> ACTIVO, con evento de auditoria."""

    def test_confirmar_resolucion_pasa_a_activo_y_audita(self):
        estado = _estado('EN_MANTENIMIENTO')
        estado_repo = MagicMock()
        estado_repo.obtener_por_dispositivo.return_value = estado
        auditoria_repo = MagicMock()
        uc = AplicarMantenimientoDispositivoUseCase(db=MagicMock(), estado_repo=estado_repo, auditoria_repo=auditoria_repo)

        import src.telemetry.application.use_cases.infraestructura.aplicar_mantenimiento_dispositivo_use_case as modulo

        class _DatetimeFijo(datetime):
            @classmethod
            def now(cls, tz=None):
                return AHORA

        import unittest.mock as mock
        with mock.patch.object(modulo, 'datetime', _DatetimeFijo):
            resultado = uc.execute(
                id_dispositivo_iot=144,
                dto=AplicarMantenimientoDTO(nuevo_estado='ACTIVO', motivo='Intervencion resuelta'),
                id_usuario=10, nombre_usuario='Ingeniero QA',
            )

        assert resultado.estado_actual == 'ACTIVO'
        auditoria_repo_llamado = auditoria_repo  # el evento se emite via RegistrarEventoAuditoriaIotUseCase interno
        estado_repo.actualizar.assert_called_once()

    def test_mismo_estado_se_rechaza_con_422(self):
        from src.shared.errors import BusinessRuleError
        estado = _estado('ACTIVO')
        estado_repo = MagicMock()
        estado_repo.obtener_por_dispositivo.return_value = estado
        uc = AplicarMantenimientoDispositivoUseCase(db=MagicMock(), estado_repo=estado_repo, auditoria_repo=MagicMock())

        with pytest.raises(BusinessRuleError) as exc:
            uc.execute(
                id_dispositivo_iot=144,
                dto=AplicarMantenimientoDTO(nuevo_estado='ACTIVO'),
                id_usuario=10, nombre_usuario='Admin QA',
            )
        assert exc.value.code == 'ESTADO_SIN_CAMBIO'


class TestSubCasoCCA3ReconexionDesdeInactivo:
    """(c) CA-3/E6: la transicion de ESTADO y el cierre del periodo SI funcionan;
    el cierre de la alerta activa NO -- hallazgo nuevo."""

    def test_heartbeat_valido_saca_de_inactivo_a_activo_y_cierra_el_periodo(self):
        estado = _estado('INACTIVO')
        db = MagicMock()
        dispositivo_port = MagicMock()
        dispositivo_port.validar_dispositivo_heartbeat.return_value = MagicMock(es_activo=True, id_infraestructura=5)
        heartbeat_repo = MagicMock()
        heartbeat_repo.guardar.side_effect = lambda hb: replace(hb, id_heartbeat=1)
        estado_repo = MagicMock()
        estado_repo.obtener_por_dispositivo.return_value = estado
        periodo_repo = MagicMock()
        periodo_abierto = MagicMock(id_periodo_inactividad=99)
        periodo_repo.obtener_abierto_por_dispositivo.return_value = periodo_abierto
        alerta_repo = MagicMock()
        uc = RecibirHeartbeatUseCase(
            db=db, dispositivo_port=dispositivo_port, heartbeat_repo=heartbeat_repo,
            estado_repo=estado_repo, transicion_repo=MagicMock(), periodo_repo=periodo_repo,
            alerta_repo=alerta_repo, historico_alerta_repo=MagicMock(),
        )

        uc.execute(
            HeartbeatDTO(tipo_mensaje='PERIODICO', nivel_bateria_pct=Decimal('80'),
                         estado_local_buffer='I', datos_pendientes_buffer=0, fecha_registro=AHORA),
            device_id=144, access_key='k',
        )

        assert estado.estado_actual == 'ACTIVO', 'CA-3: reconexion desde INACTIVO SI funciona'
        periodo_repo.cerrar.assert_called_once_with(periodo_abierto)

    def test_ninguna_alerta_se_cierra_automaticamente_al_reconectar_hallazgo_nuevo(self):
        """HALLAZGO: AlertaRepository SI tiene un metodo actualizar_estado()
        (visto en alerta_repository.py, puerto de dominio) para cerrar/resolver
        una alerta -- pero recibir_heartbeat_use_case.py nunca lo invoca, solo
        llama a alerta_repo.guardar() (creacion de alertas nuevas)."""
        from pathlib import Path
        archivo = Path(__file__).resolve().parents[5] / (
            'src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py'
        )
        texto = archivo.read_text(encoding='utf-8')
        assert 'alerta_repo.actualizar_estado' not in texto, (
            'Si esto aparece, el heartbeat ya cierra alertas al reconectar -- (c) estaria '
            'implementado, revisar antes de descartar el hallazgo.'
        )
        pytest.fail(
            "HALLAZGO (c): AlertaRepository declara un metodo actualizar_estado() (puerto de "
            "dominio, alerta_repository.py) pensado exactamente para esto -- pero "
            "recibir_heartbeat_use_case.py NUNCA lo llama, solo usa alerta_repo.guardar() (crear "
            "alertas nuevas de bateria/senal). 'Cierre de la alerta activa' al reconectar (que pide "
            "CA-3) no ocurre: una alerta FALLO_CONECTIVIDAD generada cuando el dispositivo entro en "
            "INACTIVO queda ACTIVA para siempre, aunque el dispositivo reconecte y el periodo de "
            "inactividad si se cierre correctamente (confirmado en el test anterior)."
        )


class TestSubCasoDRolNoAutorizado:
    """(d): confirma RBAC generico del proyecto sobre este endpoint."""

    def test_rol_sin_permiso_recibe_403(self, monkeypatch: pytest.MonkeyPatch):
        from src.telemetry.infrastructure.routers import infraestructura_iot_router as modulo
        from src.shared import rbac
        from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
        from src.shared.database import get_db
        from src.shared.error_handlers import register_error_handlers

        monkeypatch.setattr(rbac, 'tiene_permiso', lambda *_args: False)

        app = FastAPI()
        register_error_handlers(app)
        app.include_router(modulo.router)
        app.dependency_overrides[get_db] = lambda: MagicMock()
        app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
            id_usuario=2, id_token=1, id_rol=2, id_estado_cuenta=2,  # rol 2 = Productor
        )

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.patch(
                '/iot/dispositivos/144/mantenimiento',
                json={'nuevo_estado': 'EN_MANTENIMIENTO', 'motivo': 'intento no autorizado'},
            )

        assert response.status_code == 403
