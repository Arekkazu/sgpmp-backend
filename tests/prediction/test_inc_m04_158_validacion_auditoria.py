# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M04-158-G086 RF-73: probar rechazo E1, catalogo cerrado y continuidad del emisor. |
# | 2026-10-29 | Arekkazu | QA-M04-27-10 CU09 H-02 RF-73: NOTAS_REGISTRADAS en el catálogo |
# | 2026-10-30 | Arekkazu | INC-M04-229-G070 RF-72: VENTANA_RETROALIMENTACION_AMPLIADA en el catálogo |
# | 2026-10-31 | Arekkazu | RF-71/RF-73: REENTRENAMIENTO_SOLICITADO en el catálogo |
"""Pruebas unitarias con fakes, sin PostgreSQL."""
from __future__ import annotations

import contextlib
import logging
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import DataError, IntegrityError

from src.prediction.domain.services.validacion_auditoria_m04 import (
    TipoEventoM04, campos_requeridos,
)
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import SqlAlchemyEventoAuditoriaM04Repository
from src.shared.errors import InfrastructureError


class Sesion:
    def __init__(self, error=None):
        self.guardados = []
        self.error = error
        self.intentos = 0

    def begin_nested(self):
        return contextlib.nullcontext()

    def add(self, fila):
        self.pendiente = fila

    def flush(self):
        self.intentos += 1
        if self.error:
            error, self.error = self.error, None
            raise error
        self.guardados.append(self.pendiente)


class Respaldo:
    def __init__(self):
        self.eventos = []

    def guardar(self, evento):
        self.eventos.append(evento)


def evento(**cambios):
    return dict(tipo_evento="HISTORIAL_CONSULTADO", tipo_actor="SISTEMA", id_sistema="M04",
                id_referencia="consulta-1", payload_evento={"consulta": "AUDITORIA_M04"}) | cambios


def repo(db=None, respaldo=None):
    return SqlAlchemyEventoAuditoriaM04Repository(db or Sesion(), respaldo or Respaldo(), pausa_reintento=0)


INVALIDOS = [
    ({"tipo_evento": "EVENTO_INVENTADO"}, "tipo_evento"),
    ({"id_referencia": None}, "id_referencia"),
    ({"id_referencia": " "}, "id_referencia"),
    ({"tipo_actor": "SISTEMA", "id_sistema": None}, "actor"),
    ({"tipo_actor": "SISTEMA", "id_usuario": 8}, "actor"),
    ({"tipo_actor": "USUARIO", "id_usuario": 8}, "actor"),
    ({"tipo_actor": "USUARIO", "id_sistema": None}, "actor"),
    ({"tipo_actor": "DISPOSITIVO_EDGE", "id_sistema": None}, "actor"),
    ({"tipo_actor": "DISPOSITIVO_EDGE", "id_usuario": 8}, "actor"),
    ({"tipo_actor": "OTRO"}, "tipo_actor"),
    ({"payload_evento": {}}, "payload_evento"),
    ({"payload_evento": None}, "payload_evento"),
    ({"payload_evento": []}, "payload_evento"),
    ({"payload_evento": "roto"}, "payload_evento"),
    ({"tipo_evento": "INFERENCIA_EJECUTADA", "payload_evento": {"tipo_modelo": "MODELO_ESPECIES_MEDIANAS"}}, "payload_evento.activo_biologico_id"),
]


@pytest.mark.parametrize("cambios,campo", INVALIDOS)
def test_rechazo_no_persiste_original_y_emite_un_incidente(cambios, campo, caplog):
    db = Sesion()
    correlacion = uuid.uuid4()
    with caplog.at_level(logging.ERROR):
        resultado = repo(db).registrar(**evento(correlacion_id=correlacion, **cambios))
    assert not resultado.aceptado
    assert resultado.codigo == "AUDITORIA_EVENTO_INVALIDO"
    assert campo in resultado.campos_invalidos
    assert len(db.guardados) == 1
    rechazo = db.guardados[0]
    assert rechazo.tipo_evento == "AUDITORIA_EVENTO_INVALIDO"
    assert rechazo.tipo_actor == "SISTEMA" and rechazo.id_usuario is None and rechazo.id_sistema
    assert rechazo.correlacion_id == correlacion
    assert rechazo.severidad_evento == "ERROR" and rechazo.hash_evento
    assert rechazo.id_referencia == rechazo.payload_evento["id_intento"]
    assert resultado.id_evento == rechazo.id_evento
    assert str(correlacion) in caplog.text and "AUDITORIA_EVENTO_INVALIDO" in caplog.text


@pytest.mark.parametrize("actor,usuario,sistema", [("USUARIO", 8, None), ("SISTEMA", None, "M04"), ("DISPOSITIVO_EDGE", None, "serial-8")])
def test_actor_valido_y_referencia_se_conservan(actor, usuario, sistema):
    db = Sesion()
    resultado = repo(db).registrar(**evento(tipo_actor=actor, id_usuario=usuario, id_sistema=sistema))
    assert resultado.aceptado and resultado.codigo is None
    assert len(db.guardados) == 1 and db.guardados[0].id_evento == resultado.id_evento
    assert db.guardados[0].id_referencia == "consulta-1"
    assert db.guardados[0].origen_dato == ("EDGE" if actor == "DISPOSITIVO_EDGE" else "BACKEND")


@pytest.mark.parametrize("campo", campos_requeridos("INFERENCIA_EJECUTADA", {}))
def test_inferencia_requiere_cada_campo_del_esquema(campo):
    payload = dict.fromkeys(campos_requeridos("INFERENCIA_EJECUTADA", {}), None)
    payload.pop(campo)
    resultado = repo().registrar(**evento(tipo_evento="INFERENCIA_EJECUTADA", payload_evento=payload))
    assert not resultado.aceptado and "payload_evento." + campo in resultado.campos_invalidos


def test_inferencia_completa_admite_ceros_false_y_campos_no_aplicables():
    payload = dict.fromkeys(campos_requeridos("INFERENCIA_EJECUTADA", {}), None)
    payload.update(latencia_ms=0, contexto_incompleto=False, probabilidad_riesgo_alto=0)
    assert repo().registrar(**evento(tipo_evento="INFERENCIA_EJECUTADA", payload_evento=payload)).aceptado


def test_tipo_valido_sin_minimos_especificos_no_se_confunde_con_desconocido():
    assert campos_requeridos("HISTORIAL_CONSULTADO", {}) == []
    with pytest.raises(ValueError):
        campos_requeridos("EVENTO_INVENTADO", {})
    assert len(TipoEventoM04) == 44


class ErrorPG(Exception):
    def __init__(self, codigo, mensaje, constraint=None):
        super().__init__(mensaje)
        self.pgcode = codigo
        self.diag = SimpleNamespace(constraint_name=constraint)


@pytest.mark.parametrize("error,campo", [
    (DataError("INSERT", {}, ErrorPG("22P02", 'invalid enum modulo4.enum_tipo_evento_auditoria_m04')), "tipo_evento"),
    (IntegrityError("INSERT", {}, ErrorPG("23514", 'rechazo', "chk_eam_actor_exclusivo")), "actor"),
])
def test_fallback_bd_no_reintenta_ni_respalda_evento_invalido(error, campo):
    db, respaldo = Sesion(error), Respaldo()
    resultado = repo(db, respaldo).registrar(**evento())
    assert not resultado.aceptado and resultado.campos_invalidos == (campo,)
    assert db.intentos == 2  # intento original y el incidente E1
    assert len(db.guardados) == 1 and db.guardados[0].tipo_evento == "AUDITORIA_EVENTO_INVALIDO"
    assert respaldo.eventos == []


def test_fk_ajena_al_contrato_no_se_convierte_en_rechazo_e1():
    db = Sesion(IntegrityError("INSERT", {}, ErrorPG("23503", "fk_eam_usuario")))
    assert repo(db).registrar(**evento()).aceptado  # reintento exitoso
    assert db.intentos == 2 and db.guardados[0].tipo_evento == "HISTORIAL_CONSULTADO"


def test_caida_de_bd_respalda_solo_el_incidente_de_un_rechazo():
    class Caida(Sesion):
        def flush(self):
            raise RuntimeError("conexion caida")
    respaldo = Respaldo()
    resultado = repo(Caida(), respaldo).registrar(**evento(tipo_evento="EVENTO_INVENTADO"))
    assert not resultado.aceptado
    assert [e["tipo_evento"] for e in respaldo.eventos] == ["AUDITORIA_EVENTO_INVALIDO", "AUDITORIA_FALLA_PERSISTENCIA"]
    assert all(e["id_referencia"] for e in respaldo.eventos)


def test_rechazo_no_se_pierde_en_silencio_si_tambien_falla_el_respaldo():
    class Caida(Sesion):
        def flush(self):
            raise RuntimeError("conexion caida")
    class DiscoRoto:
        def guardar(self, _evento):
            raise OSError("disco lleno")
    with pytest.raises(InfrastructureError) as exc:
        repo(Caida(), DiscoRoto()).registrar(**evento(payload_evento={}))
    assert exc.value.code == "AUDITORIA_M04_NO_PERSISTIDA"
