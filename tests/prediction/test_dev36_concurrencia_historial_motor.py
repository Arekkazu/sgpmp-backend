# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-36 RF-65: concurrencia optimista (config_version) e historial append-only |
"""DEV-36 (RF-65 CA-9 y Restricción 5): concurrencia optimista e historial de la configuración del motor.

CA-9: POST /prediccion/motor-ia recibe la config_version que el cliente leyó y
responde 412 CONFLICTO_CONCURRENCIA si ya no es la vigente. Restricción 5: el
historial append-only de DB-14 (``modulo4.configuracion_ia_log``) se consulta
por tipo de modelo. Fakes en memoria que imitan el trigger de DB-14.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.prediction.application.use_cases.motor_ia.configurar_motor_use_case import ConfigurarMotorUseCase
from src.prediction.application.use_cases.motor_ia.consultar_historial_motor_use_case import (
    ConsultarHistorialMotorUseCase,
)
from src.prediction.domain.entities.historial_configuracion_motor import VersionConfiguracionMotor
from src.prediction.infrastructure.dto.configurar_motor_dto import ConfigurarMotorDTO
from src.shared.errors import NotFoundError, PreconditionFailedError

TIPO = "MODELO_ESPECIES_GRANDES"
T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)


class _BdConLog:
    """configuraciones_motor_ia + configuracion_ia_log: cada actualizar copia la fila anterior al log."""

    def __init__(self):
        self.fila = None
        self.log: list[VersionConfiguracionMotor] = []
        self.bloqueos = []
        self.reloj = T0

    # ConfiguracionMotorIARepository
    def obtener_por_tipo(self, _tipo, *, bloquear=False):
        self.bloqueos.append(bloquear)
        return copy.deepcopy(self.fila)

    def guardar(self, entidad):
        entidad.id_configuracion_motor, entidad.fecha_creacion = 4, self.reloj
        self.fila = copy.deepcopy(entidad)
        return entidad

    def actualizar(self, entidad):
        anterior = self.fila
        self.reloj += timedelta(minutes=5)
        self.log.append(VersionConfiguracionMotor(
            config_version=anterior.config_version, vigente=False,
            id_usuario_responsable=anterior.id_usuario_responsable, configuracion=anterior._snapshot(),
            fecha_creacion_config=anterior.fecha_creacion, operacion="UPDATE",
            vigente_hasta=self.reloj, id_usuario_cambio=entidad.id_usuario_responsable,
        ))
        self.fila = copy.deepcopy(entidad)
        return entidad

    # HistorialConfiguracionMotorRepository
    def listar_por_tipo(self, _tipo):
        return sorted(copy.deepcopy(self.log), key=lambda v: v.config_version, reverse=True)


class _Db:
    def __init__(self): self.commits = self.rollbacks = 0
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


class _Auditoria:
    def __init__(self): self.eventos = []
    def registrar(self, **kw): self.eventos.append(kw)


class _Versiones:
    def obtener_llave(self, _id): return None


class _SinNodos:
    def listar_nodos_activos(self, _tipo): return []


def _dto(**cambios) -> ConfigurarMotorDTO:
    datos = dict(tipo_modelo=TIPO, ventana_temporal_min=10,
                 umbral_riesgo_alto=Decimal("0.70"), umbral_alerta_critica=Decimal("0.80"))
    datos.update(cambios)
    return ConfigurarMotorDTO(**datos)


def _use_case(bd, db=None, auditoria=None):
    return ConfigurarMotorUseCase(
        db=db or _Db(), repo=bd, auditoria_repo=auditoria or _Auditoria(), version_port=_Versiones(),
        nodo_edge_port=_SinNodos(), sincronizacion_repo=None, config_edge_port=None,
    )


@pytest.fixture
def bd():
    bd = _BdConLog()
    _use_case(bd).execute(_dto(), id_usuario=1)  # config_version 1
    return bd


# ── CA-9: concurrencia optimista ───────────────────────────────────────────

def test_dos_ediciones_con_la_misma_version_la_segunda_es_412(bd):
    _use_case(bd).execute(_dto(config_version=1, ventana_temporal_min=12), id_usuario=1)
    assert bd.fila.config_version == 2

    db, auditoria = _Db(), _Auditoria()
    with pytest.raises(PreconditionFailedError) as exc:
        _use_case(bd, db, auditoria).execute(_dto(config_version=1, ventana_temporal_min=7), id_usuario=3)
    assert (exc.value.code, exc.value.field) == ("CONFLICTO_CONCURRENCIA", "config_version")
    assert "vigente 2, enviada 1" in exc.value.message
    # La segunda no pisó la primera ni dejó rastro.
    assert (bd.fila.config_version, bd.fila.ventana_temporal_min) == (2, 12)
    assert len(bd.log) == 1 and auditoria.eventos == []
    assert (db.commits, db.rollbacks) == (0, 1)  # el rollback libera el bloqueo de la fila


def test_la_lectura_para_editar_bloquea_la_fila(bd):
    _use_case(bd).execute(_dto(config_version=1), id_usuario=1)
    assert bd.bloqueos[-1] is True


def test_editar_sin_config_version_cuando_ya_existe_es_412(bd):
    with pytest.raises(PreconditionFailedError) as exc:
        _use_case(bd).execute(_dto(ventana_temporal_min=7), id_usuario=1)
    assert exc.value.code == "CONFLICTO_CONCURRENCIA"
    assert "Ya existe una configuración" in exc.value.message
    assert bd.fila.config_version == 1


def test_crear_no_exige_config_version():
    bd = _BdConLog()
    resultado = _use_case(bd).execute(_dto(), id_usuario=1)
    assert resultado.es_nueva and resultado.entidad.config_version == 1


def test_con_la_version_vigente_la_edicion_procede_y_sube_la_version(bd):
    resultado = _use_case(bd).execute(_dto(config_version=1, ventana_temporal_min=12), id_usuario=1)
    assert not resultado.es_nueva and resultado.entidad.config_version == 2


# ── Restricción 5: historial append-only ───────────────────────────────────

def _historial(bd, tipo=TIPO):
    return ConsultarHistorialMotorUseCase(repo=bd, historial_repo=bd).execute(tipo)


def test_el_historial_muestra_las_dos_versiones(bd):
    _use_case(bd).execute(_dto(config_version=1, ventana_temporal_min=12), id_usuario=3)
    with pytest.raises(PreconditionFailedError):
        _use_case(bd).execute(_dto(config_version=1, ventana_temporal_min=7), id_usuario=1)

    historial = _historial(bd)
    assert historial.config_version_vigente == 2 and historial.total == 2
    vigente, anterior = historial.versiones
    assert (vigente.config_version, vigente.vigente, vigente.configuracion["ventana_temporal_min"]) == (2, True, 12)
    assert (anterior.config_version, anterior.vigente, anterior.configuracion["ventana_temporal_min"]) == (1, False, 10)
    assert (anterior.operacion, anterior.id_usuario_cambio) == ("UPDATE", 3)
    # Los periodos encadenan: la v2 rige desde que reemplazó a la v1.
    assert anterior.vigente_desde == T0
    assert vigente.vigente_desde == anterior.vigente_hasta and vigente.vigente_hasta is None


def test_sin_cambios_el_historial_solo_tiene_la_vigente(bd):
    historial = _historial(bd)
    assert [v.config_version for v in historial.versiones] == [1]
    assert historial.versiones[0].vigente_desde == T0


def test_si_el_log_empieza_despues_de_la_v1_la_mas_antigua_no_tiene_vigente_desde(bd):
    # Las versiones anteriores a DB-14 no están en el log: no se inventa desde cuándo regía.
    bd.fila.config_version = 3
    _use_case(bd).execute(_dto(config_version=3, ventana_temporal_min=12), id_usuario=1)
    vigente, anterior = _historial(bd).versiones
    assert (anterior.config_version, anterior.vigente_desde) == (3, None)
    assert vigente.vigente_desde == anterior.vigente_hasta


def test_versiones_por_componente_vacia_se_guarda_como_sql_null():
    # ck_configuracion_motor_umbrales_por_paradigma exige IS NULL en INDIVIDUAL/META;
    # con JSON null ('null'::jsonb) crear una configuración INDIVIDUAL fallaba con 400.
    from src.prediction.infrastructure.models.configuracion_motor_ia_model import ConfiguracionMotorIAModel
    assert ConfiguracionMotorIAModel.__table__.c.versiones_activas_por_componente.type.none_as_null


def test_historial_de_tipo_sin_configuracion_es_404():
    with pytest.raises(NotFoundError) as exc:
        _historial(_BdConLog())
    assert exc.value.code == "CONFIGURACION_MOTOR_NO_ENCONTRADA"


def test_historial_de_tipo_desconocido_es_404_sin_consultar(bd):
    bd.bloqueos.clear()
    with pytest.raises(NotFoundError):
        _historial(bd, "NO_EXISTE")
    assert bd.bloqueos == []  # no se manda un valor fuera del enum a PostgreSQL


# ── Router ─────────────────────────────────────────────────────────────────

@pytest.fixture
def cliente(monkeypatch, bd):
    from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
    from src.prediction.infrastructure.routers import motor_ia_router as router_mod
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(router_mod, "SqlAlchemyConfiguracionMotorIARepository", lambda db: bd)
    monkeypatch.setattr(router_mod, "SqlAlchemyHistorialConfiguracionMotorRepository", lambda db: bd)
    monkeypatch.setattr(router_mod, "SqlAlchemyEventoAuditoriaM04Repository", lambda db: _Auditoria())
    monkeypatch.setattr(router_mod, "VersionModeloAdapter", lambda db: _Versiones())
    monkeypatch.setattr(router_mod, "NodoEdgeM09Adapter", lambda db: _SinNodos())
    monkeypatch.setattr(router_mod, "SqlAlchemySincronizacionNodoEdgeRepository", lambda db: None)
    monkeypatch.setattr(router_mod, "ConfigMotorEdgeMqttAdapter", lambda: None)

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router_mod.router)
    app.dependency_overrides[get_db] = lambda: _Db()
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)
    for ruta in router_mod.router.routes:
        for dependencia in ruta.dependencies:
            app.dependency_overrides[dependencia.dependency] = lambda: None
    return TestClient(app)


_BODY = {"tipo_modelo": TIPO, "ventana_temporal_min": 10, "umbral_riesgo_alto": "0.7", "umbral_alerta_critica": "0.8"}


def test_post_dos_ediciones_misma_version_200_y_412_y_get_historial(cliente):
    primera = cliente.post("/prediccion/motor-ia", json={**_BODY, "config_version": 1, "ventana_temporal_min": 12})
    assert primera.status_code == 200 and primera.json()["config_version"] == 2

    segunda = cliente.post("/prediccion/motor-ia", json={**_BODY, "config_version": 1, "ventana_temporal_min": 7})
    assert segunda.status_code == 412
    assert segunda.json()["error_code"] == "CONFLICTO_CONCURRENCIA"

    r = cliente.get(f"/prediccion/motor-ia/{TIPO}/historial")
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert (cuerpo["tipo_modelo"], cuerpo["config_version_vigente"], cuerpo["total"]) == (TIPO, 2, 2)
    assert [(v["config_version"], v["vigente"]) for v in cuerpo["versiones"]] == [(2, True), (1, False)]
    assert cuerpo["versiones"][1]["configuracion"]["ventana_temporal_min"] == 10


def test_get_historial_de_tipo_desconocido_es_404(cliente):
    assert cliente.get("/prediccion/motor-ia/NO_EXISTE/historial").status_code == 404
