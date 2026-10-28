# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-27 | destroyerban | INC-M03-116-G59 RF-56: consulta del paquete por id con alcance por finca |
"""INC-M03-116-G59 (RF-56 Postcondición 3 y 5, CA-8): consulta del paquete y su ciclo de vida.

TC-M03-117: GET /iot/paquetes-inferencia/{id}.
TC-M03-118: ciclo de vida en la bitácora RF-63, por paquete (embebido) y con
GET /iot/auditoria?entidad_afectada_tipo=PAQUETE_IA&entidad_afectada_id={id}.
Son pruebas con dobles de repositorio y SQL compilada; la integración con PostgreSQL
necesita TEST_DATABASE_URL.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Query, Session

from src.identity_access.infrastructure.dependencies import get_current_user
from src.shared import rbac
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import NotFoundError
from src.telemetry.application.use_cases.inferencia.consultar_paquete_inferencia_use_case import (
    ConsultarPaqueteInferenciaUseCase,
)
from src.telemetry.domain.entities.evento_auditoria_iot import EventoAuditoriaIot
from src.telemetry.domain.entities.telemetria import PaqueteInferencia
from src.telemetry.domain.repositories.bitacora_auditoria_iot_repository import BitacoraAuditoriaIotRepository
from src.telemetry.domain.repositories.paquete_inferencia_repository import PaqueteInferenciaRepository
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
from src.telemetry.infrastructure.repositories.paquete_inferencia_repository import SqlAlchemyPaqueteInferenciaRepository
from src.telemetry.infrastructure.routers import auditoria_iot_router, paquete_inferencia_router

_T0 = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


def _paquete(id_paquete=11):
    return PaqueteInferencia(
        id_paquetes_inferencia=id_paquete, id_sensor=3, id_dispositivo_iot=2, id_evento_edge_computing=7,
        tipo_variable="TEMPERATURA_AMBIENTAL", valor_numerico=Decimal("38.5"), unidad="°C",
        estado_calidad="LECTURA_VALIDA", estado_desviacion="DESVIACION_SIMPLE", severidad="MODERADO",
        origen="TIEMPO_REAL", contexto_ambiental={"AMBIENTAL": []}, contexto_incompleto=True,
        metadatos={"timestamp_captura": _T0.isoformat()}, fecha_envio=_T0, estado_paquete="PENDIENTE",
        intento_envios=0,
    )


def _evento(tipo, segundos):
    return EventoAuditoriaIot(
        id_evento=uuid4(), tipo_evento=tipo, fecha_hora=_T0 + timedelta(seconds=segundos),
        resultado="EXITOSO", componente_origen="RF56", entidad_afectada_tipo="PAQUETE_IA",
        entidad_afectada_id="11", accion_detallada={"estado_paquete": "PENDIENTE"},
        severidad_log="INFO", clasificacion_registro="TECNICO", retencion_aplicable=365,
        hash_integridad="0" * 64,
    )


def _repos(paquete=None, eventos=()):
    paquetes = Mock(spec=PaqueteInferenciaRepository)
    paquetes.obtener.return_value = paquete
    auditoria = Mock(spec=BitacoraAuditoriaIotRepository)
    auditoria.listar.return_value = (list(eventos), len(eventos))
    return paquetes, auditoria


def test_paquete_inexistente_o_fuera_de_las_fincas_es_404():
    paquetes, auditoria = _repos(None)
    with pytest.raises(NotFoundError) as error:
        ConsultarPaqueteInferenciaUseCase(paquetes, auditoria).execute(99, ids_fincas_permitidas=[4])
    assert error.value.code == "PAQUETE_INFERENCIA_NO_ENCONTRADO"
    paquetes.obtener.assert_called_once_with(99, ids_fincas_permitidas=[4])
    auditoria.listar.assert_not_called()


def test_ciclo_de_vida_son_los_eventos_del_paquete_en_orden_cronologico():
    eventos = [_evento("PAQUETE_ENVIADO_IA", 30), _evento("PAQUETE_INFERENCIA_GENERADO", 0),
               _evento("CONTEXTO_INCOMPLETO", 1)]
    paquetes, auditoria = _repos(_paquete(), eventos)
    resultado = ConsultarPaqueteInferenciaUseCase(paquetes, auditoria).execute(11)
    assert [e.tipo_evento for e in resultado.ciclo_vida] == [
        "PAQUETE_INFERENCIA_GENERADO", "CONTEXTO_INCOMPLETO", "PAQUETE_ENVIADO_IA"]
    auditoria.listar.assert_called_once_with(
        entidad_afectada_tipo="PAQUETE_IA", entidad_afectada_id="11", por_pagina=200)


@pytest.fixture
def cliente(monkeypatch):
    estado = {"permiso": True, "paquete": _paquete(), "eventos": [_evento("PAQUETE_INFERENCIA_GENERADO", 0)],
              "fincas": None}
    monkeypatch.setattr(rbac, "tiene_permiso", lambda *a, **k: estado["permiso"])
    monkeypatch.setattr(paquete_inferencia_router, "_fincas_de_la_bitacora", lambda db, u: estado["fincas"])

    class _Paquetes:
        def __init__(self, db):
            pass

        def obtener(self, id_paquete, *, ids_fincas_permitidas=None):
            estado["fincas_usadas"] = ids_fincas_permitidas
            p = estado["paquete"]
            return p if p and p.id_paquetes_inferencia == id_paquete else None

    class _Bitacora:
        def __init__(self, db):
            pass

        def listar(self, **kw):
            return estado["eventos"], len(estado["eventos"])

    monkeypatch.setattr(paquete_inferencia_router, "SqlAlchemyPaqueteInferenciaRepository", _Paquetes)
    monkeypatch.setattr(paquete_inferencia_router, "SqlAlchemyBitacoraAuditoriaIotRepository", _Bitacora)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(paquete_inferencia_router.router)
    app.dependency_overrides[get_db] = lambda: Mock()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id_usuario=5, id_rol=4, id_estado_cuenta=2)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, estado


def test_get_paquete_devuelve_trazabilidad_y_ciclo_de_vida(cliente):
    client, estado = cliente
    estado["fincas"] = [4]
    respuesta = client.get("/iot/paquetes-inferencia/11")
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert (cuerpo["id_paquete_inferencia"], cuerpo["id_sensor"], cuerpo["id_dispositivo_iot"],
            cuerpo["id_evento_edge_computing"]) == (11, 3, 2, 7)
    assert cuerpo["estado_paquete"] == "PENDIENTE" and cuerpo["intento_envios"] == 0
    assert cuerpo["contexto_incompleto"] is True
    assert [e["tipo_evento"] for e in cuerpo["ciclo_vida"]] == ["PAQUETE_INFERENCIA_GENERADO"]
    assert "componente_origen" not in cuerpo["ciclo_vida"][0]  # RF-63: no se expone
    assert estado["fincas_usadas"] == [4]


def test_get_paquete_inexistente_es_404(cliente):
    client, _ = cliente
    respuesta = client.get("/iot/paquetes-inferencia/12")
    assert respuesta.status_code == 404
    assert respuesta.json()["error_code"] == "PAQUETE_INFERENCIA_NO_ENCONTRADO"


def test_get_paquete_sin_permiso_es_403(cliente):
    client, estado = cliente
    estado["permiso"] = False
    assert client.get("/iot/paquetes-inferencia/11").status_code == 403


def test_id_de_paquete_invalido_es_rechazado(cliente):
    client, _ = cliente
    respuesta = client.get("/iot/paquetes-inferencia/0")
    assert respuesta.status_code == 400 and respuesta.json()["error_code"] == "VAL_ENTRADA"


def test_obtener_aplica_el_alcance_por_finca_por_el_equipo(monkeypatch):
    capturado = {}

    def first(query):
        capturado["sql"] = " ".join(str(query.statement.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})).split())
        return None

    monkeypatch.setattr(Query, "first", first)
    db = Session()
    monkeypatch.setattr(db, "execute", lambda *a, **k: SimpleNamespace(all=lambda: [(2,), (8,)]))
    assert SqlAlchemyPaqueteInferenciaRepository(db).obtener(11, ids_fincas_permitidas=[4]) is None
    assert "modulo3.paquetes_inferencia.id_paquetes_inferencia = 11" in capturado["sql"]
    assert "modulo3.paquetes_inferencia.id_dispositivo_iot IN (2, 8)" in capturado["sql"]


def _sql_listar(monkeypatch, **kw):
    capturado = {}

    def all_(query):
        capturado["sql"] = " ".join(str(query.statement.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})).split())
        return []

    monkeypatch.setattr(Query, "all", all_)
    monkeypatch.setattr(Query, "count", lambda q: 0)
    db = Session()
    monkeypatch.setattr(db, "execute", lambda *a, **k: SimpleNamespace(all=lambda: [(2,)]))
    SqlAlchemyBitacoraAuditoriaIotRepository(db).listar(**kw)
    return capturado["sql"]


def test_bitacora_filtra_por_tipo_de_entidad(monkeypatch):
    sql = _sql_listar(monkeypatch, entidad_afectada_tipo="PAQUETE_IA", entidad_afectada_id="11")
    assert "entidad_afectada_tipo = 'PAQUETE_IA'" in sql and "entidad_afectada_id = '11'" in sql


def test_bitacora_de_paquetes_llega_a_la_finca_por_el_equipo(monkeypatch):
    sql = _sql_listar(monkeypatch, ids_fincas_permitidas=[4])
    assert "entidad_afectada_tipo = 'PAQUETE_IA'" in sql
    assert "modulo3.paquetes_inferencia.id_dispositivo_iot IN (2)" in sql


def test_get_auditoria_acepta_y_valida_entidad_afectada_tipo(monkeypatch):
    usados = {}

    class _Caso:
        def __init__(self, **kw):
            pass

        def listar(self, **kw):
            usados.update(kw)
            return [], 0

    monkeypatch.setattr(rbac, "tiene_permiso", lambda *a, **k: True)
    monkeypatch.setattr(auditoria_iot_router, "_fincas_de_la_bitacora", lambda db, u: None)
    monkeypatch.setattr(auditoria_iot_router, "ConsultarBitacoraIotUseCase", _Caso)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(auditoria_iot_router.router)
    app.dependency_overrides[get_db] = lambda: Mock()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id_usuario=5, id_rol=1, id_estado_cuenta=2)
    with TestClient(app, raise_server_exceptions=False) as client:
        ok = client.get("/iot/auditoria", params={"entidad_afectada_tipo": "PAQUETE_IA", "entidad_afectada_id": "11"})
        invalido = client.get("/iot/auditoria", params={"entidad_afectada_tipo": "NO_EXISTE"})
    assert ok.status_code == 200, ok.text
    assert usados["entidad_afectada_tipo"] == "PAQUETE_IA" and usados["entidad_afectada_id"] == "11"
    assert invalido.status_code == 400 and invalido.json()["error_code"] == "VAL_ENTRADA"


def test_main_registra_la_ruta_de_paquetes():
    import main
    rutas = {getattr(r, "path", None) for r in main.app.routes}
    assert "/iot/paquetes-inferencia/{id_paquete}" in rutas
