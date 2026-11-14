# | Fecha      | Nombre  | Que se hizo                                           |
# |------------|---------|-------------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-30 RF-57: prueba autorizacion y transiciones REST  |
# | 2026-10-23 | Arekkazu | INTEG RFC-012..016 DEV-30/49: recurso alertas_operativas e historial por trigger |
# | 2026-10-28 | destroyerban | INC-M03-172-G79 RF-57 CA-11: estado no catalogado es 422 TRANSICION_INVALIDA, no 400 |
"""DEV-30: dominio y HTTP con repositorios/datos de permisos explícitos en memoria.

Estas pruebas no demuestran el despliegue de DB-08 ni la autenticación JWT real.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared import rbac
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import BusinessRuleError
from src.telemetry.application.use_cases.alertas.actualizar_estado_alerta_use_case import ActualizarEstadoAlertaUseCase
from src.telemetry.domain.entities.alerta import Alerta, AmbitoAlerta, EstadoAlerta
from src.telemetry.infrastructure.dto.actualizar_estado_alerta_dto import ActualizarEstadoAlertaDTO
from src.telemetry.infrastructure.routers import alerta_router


def _alerta(estado="ACTIVA"):
    ahora = datetime.now(timezone.utc)
    return Alerta(
        id_alerta=71, tipo_alerta="ESTRES_TERMICO", severidad="LEVE",
        estado_alerta=estado, origen_evento="EDGE", tipo_variable="TEMPERATURA_AMBIENTAL",
        fecha_evento=ahora, fecha_generacion=ahora,
    )


@pytest.mark.parametrize("destino", [e.value for e in EstadoAlerta] + ["CERRADA"])
def test_vencida_es_terminal_sin_mutaciones(destino):
    alerta = _alerta("VENCIDA")
    previo = deepcopy(alerta)
    with pytest.raises(BusinessRuleError) as exc:
        alerta.transicionar(destino, id_usuario=43, motivo="intento manual")
    assert (exc.value.status_code, exc.value.code) == (422, "TRANSICION_INVALIDA")
    assert alerta == previo


@pytest.mark.parametrize("origen", ["ACTIVA", "EN_ATENCION"])
def test_vencimiento_interno_por_sla_se_conserva(origen):
    alerta = _alerta(origen)
    alerta.transicionar("VENCIDA", id_usuario=43, motivo="SLA")
    assert alerta.estado_alerta == "VENCIDA"


@pytest.mark.parametrize("estado", ["CERRADA", "VENCIDA", "cerrada", "vencida"])
def test_dto_delega_estados_manuales_al_dominio(estado):
    assert ActualizarEstadoAlertaDTO(nuevo_estado=estado).nuevo_estado == estado.upper()


@pytest.mark.parametrize("valor", [12, ["EN_ATENCION"]])
def test_dto_conserva_validacion_estructural(valor):
    with pytest.raises(ValidationError):
        ActualizarEstadoAlertaDTO(nuevo_estado=valor)


@pytest.mark.parametrize("valor", ["DESCONOCIDO", "", None])
def test_dto_deja_el_estado_no_catalogado_al_dominio(valor):
    # G79 (CA-11): no es un error de forma; el caso de uso responde 422 TRANSICION_INVALIDA.
    assert ActualizarEstadoAlertaDTO(nuevo_estado=valor).nuevo_estado == (valor.upper() if valor is not None else None)


@pytest.fixture
def flujo(monkeypatch):
    almacen = {"alerta": _alerta(), "historial": [], "auditoria": []}
    db = Mock()
    repo = Mock()
    repo.obtener_por_id.side_effect = lambda _id: deepcopy(almacen["alerta"])

    def actualizar(**datos):
        alerta = almacen["alerta"]
        alerta.estado_alerta = datos["nuevo_estado"]
        alerta.fecha_atencion = datos["fecha_atencion"]
        alerta.fecha_resolucion = datos["fecha_resolucion"]
        return deepcopy(alerta)

    repo.actualizar_estado.side_effect = actualizar
    historico = Mock()
    historico.registrar.side_effect = lambda **kw: almacen["historial"].append(kw)
    auditoria = Mock()

    def registrar(evento):
        evento.id_evento = uuid4()
        almacen["auditoria"].append(evento)
        return evento

    auditoria.registrar.side_effect = registrar
    monkeypatch.setattr(alerta_router, "SqlAlchemyAlertaRepository", lambda _: repo)
    monkeypatch.setattr(alerta_router, "SqlAlchemyHistoricoEstadoAlertaRepository", lambda _: historico)
    monkeypatch.setattr(alerta_router, "SqlAlchemyBitacoraAuditoriaIotRepository", lambda _: auditoria)
    # Roles arbitrarios: la decisión depende de permisos, no del identificador.
    usuario = UsuarioActual(id_usuario=43, id_token=1, id_rol=871, id_estado_cuenta=2)
    permisos = {"U": True, "D": False}
    permiso_u = Mock(side_effect=lambda _db, _rol, recurso, accion: permisos["U"] and (recurso, accion) == (32, 3))
    permiso_d = Mock(side_effect=lambda _db, _rol, recurso, accion: permisos["D"] and (recurso, accion) == ("alertas_operativas", 4))
    monkeypatch.setattr(rbac, "tiene_permiso", permiso_u)
    monkeypatch.setattr(alerta_router, "tiene_permiso_sobre", permiso_d)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(alerta_router.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: usuario
    with TestClient(app) as client:
        yield client, almacen, db, repo, usuario, permisos, permiso_d


def _patch(flujo, estado):
    return flujo[0].patch("/iot/alertas/71/estado", json={"nuevo_estado": estado, "motivo": "Revisión"})


def test_u_sin_d_no_permite_descartar(flujo):
    respuesta = _patch(flujo, "descartada")
    assert respuesta.status_code == 403
    assert respuesta.json()["error_code"] == "ACCESO_DENEGADO"
    assert "id_alerta" not in respuesta.json()
    assert flujo[1]["alerta"].estado_alerta == "ACTIVA"
    assert flujo[1]["historial"] == []
    flujo[3].obtener_por_id.assert_not_called()
    flujo[3].actualizar_estado.assert_not_called()
    flujo[2].commit.assert_not_called()
    flujo[6].assert_called_once_with(flujo[2], flujo[4].id_rol, "alertas_operativas", 4)


def test_permiso_d_explicito_permite_descartar(flujo):
    flujo[5]["D"] = True
    respuesta = _patch(flujo, "DESCARTADA")
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado_alerta"] == "DESCARTADA"
    assert flujo[1]["alerta"].estado_alerta == "DESCARTADA"
    # DEV-49: el historial lo escribe el trigger de RF-57 en PostgreSQL, no Python.
    assert flujo[1]["historial"] == []
    flujo[2].commit.assert_called_once()


def test_d_no_sustituye_el_permiso_general_u(flujo):
    flujo[5].update(U=False, D=True)
    respuesta = _patch(flujo, "DESCARTADA")
    assert respuesta.status_code == 403
    flujo[3].actualizar_estado.assert_not_called()
    flujo[6].assert_not_called()


def test_cuenta_inactiva_no_aplica_permisos(flujo):
    flujo[4].id_estado_cuenta = 3
    flujo[5]["D"] = True
    respuesta = _patch(flujo, "DESCARTADA")
    assert respuesta.status_code == 403
    assert respuesta.json()["error_code"] == "CUENTA_NO_ACTIVA"
    flujo[3].actualizar_estado.assert_not_called()


@pytest.mark.parametrize("estado", ["CERRADA", "VENCIDA"])
def test_rest_rechaza_transicion_y_conserva_registros(flujo, estado):
    previo = deepcopy(flujo[1]["alerta"])
    respuesta = _patch(flujo, estado)
    assert respuesta.status_code == 422, respuesta.text
    assert respuesta.json()["error_code"] == "TRANSICION_INVALIDA"
    assert flujo[1]["alerta"] == previo
    assert flujo[1]["historial"] == []
    flujo[3].actualizar_estado.assert_not_called()
    flujo[2].rollback.assert_called_once()
    assert len(flujo[1]["auditoria"]) == 1
    assert flujo[1]["auditoria"][0].tipo_evento == "TRANSICION_ALERTA_RECHAZADA"


def test_rest_no_reabre_vencida(flujo):
    flujo[1]["alerta"].estado_alerta = "VENCIDA"
    respuesta = _patch(flujo, "EN_ATENCION")
    assert respuesta.status_code == 422
    assert respuesta.json()["error_code"] == "TRANSICION_INVALIDA"
    assert flujo[1]["alerta"].estado_alerta == "VENCIDA"
    flujo[3].actualizar_estado.assert_not_called()


@pytest.mark.parametrize("estado", ["CERRADA", "VENCIDA"])
def test_fallo_de_auditoria_conserva_error_de_transicion(flujo, estado):
    auditoria = alerta_router.SqlAlchemyBitacoraAuditoriaIotRepository(flujo[2])
    auditoria.registrar.side_effect = RuntimeError("Fallo de auditoría inducido")
    respuesta = _patch(flujo, estado)
    assert respuesta.status_code == 422
    assert respuesta.json()["error_code"] == "TRANSICION_INVALIDA"
    assert flujo[1]["alerta"].estado_alerta == "ACTIVA"
    assert flujo[1]["historial"] == []
    assert flujo[1]["auditoria"] == []


def test_transicion_valida_no_requiere_descarte(flujo):
    respuesta = _patch(flujo, "EN_ATENCION")
    assert respuesta.status_code == 200
    assert respuesta.json()["estado_alerta"] == "EN_ATENCION"
    assert flujo[1]["auditoria"] == []
    flujo[6].assert_not_called()


def test_desconocido_es_422_transicion_invalida(flujo):
    respuesta = _patch(flujo, "DESCONOCIDO")
    assert respuesta.status_code == 422 and respuesta.json()["error_code"] == "TRANSICION_INVALIDA"
    flujo[3].actualizar_estado.assert_not_called()


def test_ambito_operativo_no_modifica_alerta_tecnica(flujo):
    flujo[1]["alerta"].tipo_alerta = "TECNICA"
    respuesta = _patch(flujo, "EN_ATENCION")
    assert respuesta.status_code == 404
    flujo[3].actualizar_estado.assert_not_called()


def test_error_de_persistencia_ejecuta_rollback(flujo):
    flujo[3].actualizar_estado.side_effect = RuntimeError("fallo de persistencia")
    caso = ActualizarEstadoAlertaUseCase(
        db=flujo[2], alerta_repo=flujo[3], historico_repo=Mock(), ambito=AmbitoAlerta.OPERATIVA,
    )
    with pytest.raises(RuntimeError, match="persistencia"):
        caso.execute(71, ActualizarEstadoAlertaDTO(nuevo_estado="EN_ATENCION"), 43)
    flujo[2].rollback.assert_called_once()
    flujo[2].commit.assert_not_called()
    assert flujo[1]["alerta"].estado_alerta == "ACTIVA"
