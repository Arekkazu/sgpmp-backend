# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-25 | Arekkazu | INC-M04-143/144/145/146 RF-67: historial diagnóstico contra Postgres |
# | 2026-10-30 | Arekkazu | INC-M04-223-G034 RF-68: evento CONTAGIO en el historial |
"""RF-67 contra PostgreSQL real.

- 143-G010: con alertas, la página sigue ordenada por (fecha_evento, id_evento) DESC.
- 144-G012: el nombre de la patología es el vigente a la fecha de la inferencia.
- 145-G012: resultados e historial no admiten UPDATE ni DELETE en la base.
- 146-G012: el mismo evento conserva su id_evento y no se materializa dos veces.

Los datos se siembran con ``session_replication_role = replica`` (sin FKs ni
triggers) dentro de la transacción de la prueba y se vuelve a ``origin`` antes
de ejercitar el código.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from src.prediction.infrastructure.repositories.historial_diagnostico_repository import (
    SqlAlchemyHistorialDiagnosticoRepository,
    id_evento_alerta,
    id_evento_contagio,
)
from tests.integration.test_control_acceso_f4_aislamiento import _finca_con_activo

pytestmark = pytest.mark.integration

T0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def _t(horas: int) -> datetime:
    return T0 + timedelta(hours=horas)


@pytest.fixture
def escenario(db_session, crear_usuario_db):
    db = db_session
    usuario = crear_usuario_db()["id_usuario"]
    db.execute(text("SET LOCAL session_replication_role = replica"))
    _, _, activo = _finca_con_activo(db, usuario)
    sufijo = "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:8])
    viejo, nuevo = f"Patologia Historica {sufijo}", f"Patologia Renombrada {sufijo}"
    pat = db.execute(text(
        "INSERT INTO modulo9.patologias (nombre, es_activo, es_base, version_catalogo) "
        "VALUES (:n, true, false, 1) RETURNING id_patologia"), {"n": nuevo}).scalar_one()
    for cuando, accion, antes, despues in ((_t(0), "CREADA", None, viejo), (_t(2), "MODIFICADA", viejo, nuevo)):
        db.execute(text(
            "INSERT INTO modulo4.historial_catalogo_patologias "
            "(id_patologia, version_catalogo, accion, datos_nuevos, datos_anteriores, id_usuario, timestamp_cambio) "
            "VALUES (:p, 1, :a, CAST(:dn AS jsonb), CAST(:da AS jsonb), 1, :t)"),
            {"p": pat, "a": accion, "dn": json.dumps({"nombre": despues}),
             "da": json.dumps({"nombre": antes}) if antes else None, "t": cuando})

    def inferencia(horas, id_alerta=None):
        return db.execute(text(
            "INSERT INTO modulo4.resultados_inferencia (id_resultado_inferencia, id_activo_biologico, id_especie, "
            "tipo_modelo, id_version_modelo, nivel_riesgo, probabilidad_riesgo, probabilidad_enfermedad, "
            "confianza_global, modo_ejecucion, fecha_inferencia, id_patologia, id_alerta_generada) VALUES "
            "(gen_random_uuid(), :a, 1, 'MODELO_AVES', 1, 2, '{}', '{}', 0.9, 'SERVIDOR', :f, :p, :al) "
            "RETURNING id_resultado_inferencia"),
            {"a": activo, "f": _t(horas), "p": pat, "al": id_alerta}).scalar_one()

    alerta = db.execute(text(
        "INSERT INTO modulo4.alertas_patologicas (id_prediccion, id_activo_biologico, id_finca, id_patologia, "
        "probabilidad_pct, nivel_criticidad, id_notificacion, fecha_generacion) "
        "VALUES (1, :a, 1, :p, 80, 'ALTA', 1, :f) RETURNING id_alerta_patologica"),
        {"a": activo, "p": pat, "f": _t(4)}).scalar_one()
    ri1 = inferencia(1, alerta)  # antes del renombre; su alerta llega después de ri2
    ri2 = inferencia(3)
    ri3 = inferencia(5)
    retro = db.execute(text(
        "INSERT INTO modulo4.retroalimentaciones_clinicas (id_retroalimentacion, id_resultado_inferencia, "
        "id_activo_biologico, estado_retroalimentacion, id_usuario_veterinario, fecha_retroalimentacion) "
        "VALUES (gen_random_uuid(), :r, :a, 'CORRECTO', 1, :f) RETURNING id_retroalimentacion"),
        {"r": ri1, "a": activo, "f": _t(6)}).scalar_one()
    # RF-68 paso 9: el cálculo de contagio del lote también es parte del historial (INC-M04-223-G034).
    contagio = db.execute(text(
        "INSERT INTO modulo4.resultados_riesgo_contagio (id_activo_biologico, id_configuracion_motor, "
        "factor_sanitario_fs, w_fs_aplicado, w_fa_aplicado, w_fd_aplicado, probabilidad_contagio, "
        "nivel_riesgo_contagio, fecha_calculo) VALUES (:a, 1, 0.4, 0.5, 0.3, 0.2, 0.55, 2, :f) "
        "RETURNING id_resultado_contagio"), {"a": activo, "f": _t(7)}).scalar_one()
    db.execute(text("SET LOCAL session_replication_role = origin"))
    return dict(activo=activo, ri1=ri1, ri2=ri2, ri3=ri3, alerta=alerta, retro=retro, viejo=viejo, nuevo=nuevo,
                contagio=contagio)


def _consultar(db, e, cursor=None, limite=51):
    return SqlAlchemyHistorialDiagnosticoRepository(db).consultar(
        id_activo_biologico=e["activo"], fecha_inicio=_t(-1), fecha_fin=_t(10), nivel_riesgo=None,
        id_patologia=None, incluir_alertas=True, cursor=cursor, limite=limite)


def test_con_alertas_la_pagina_sigue_ordenada_y_el_nombre_es_el_historico(db_session, escenario):
    e = escenario
    eventos = _consultar(db_session, e)
    assert [(ev.tipo_evento, ev.id_evento) for ev in eventos] == [
        ("CONTAGIO", id_evento_contagio(e["contagio"])), ("RETROALIMENTACION", e["retro"]), ("INFERENCIA", e["ri3"]), ("ALERTA", id_evento_alerta(e["alerta"])),
        ("INFERENCIA", e["ri2"]), ("INFERENCIA", e["ri1"])]
    nombres = {ev.id_evento: ev.payload.get("nombre_patologia") for ev in eventos}
    assert nombres[e["ri1"]] == e["viejo"]  # inferida antes del renombre
    assert nombres[e["ri2"]] == nombres[e["ri3"]] == nombres[id_evento_alerta(e["alerta"])] == e["nuevo"]


def test_cursor_recorre_sin_repetir_ni_saltar(db_session, escenario):
    primera = _consultar(db_session, escenario, limite=2)
    segunda = _consultar(db_session, escenario, cursor=(primera[-1].fecha_evento, primera[-1].id_evento), limite=10)
    assert [ev.id_evento for ev in primera + segunda] == [ev.id_evento for ev in _consultar(db_session, escenario)]


def test_id_evento_estable_y_materializacion_sin_duplicados(db_session, escenario):
    repo = SqlAlchemyHistorialDiagnosticoRepository(db_session)
    eventos = _consultar(db_session, escenario)
    assert [ev.id_evento for ev in eventos] == [ev.id_evento for ev in _consultar(db_session, escenario)]
    # Una fila de antes del cambio (id aleatorio) para la misma inferencia no se duplica.
    db_session.execute(text(
        "INSERT INTO modulo4.historial_diagnostico_eventos (id_evento, tipo_evento, id_activo_biologico, "
        "fecha_evento, id_resultado_inferencia, payload) VALUES (gen_random_uuid(), 'INFERENCIA', :a, :f, :r, '{}')"),
        {"a": escenario["activo"], "f": _t(5), "r": escenario["ri3"]})
    repo.materializar_eventos(eventos)
    repo.materializar_eventos(eventos)
    filas = db_session.execute(text(
        "SELECT tipo_evento, count(*) FROM modulo4.historial_diagnostico_eventos "
        "WHERE id_activo_biologico = :a GROUP BY 1"), {"a": escenario["activo"]}).all()
    assert dict(filas) == {"INFERENCIA": 3, "ALERTA": 1, "RETROALIMENTACION": 1}  # CONTAGIO no se materializa


def test_contagio_respeta_los_filtros_del_historial(db_session, escenario):
    def tipos(**filtros):
        base = dict(id_activo_biologico=escenario["activo"], fecha_inicio=_t(-1), fecha_fin=_t(10),
                    nivel_riesgo=None, id_patologia=None, incluir_alertas=False, cursor=None, limite=51)
        return [ev.tipo_evento for ev in SqlAlchemyHistorialDiagnosticoRepository(db_session).consultar(**base | filtros)]

    assert "CONTAGIO" in tipos()
    assert "CONTAGIO" in tipos(nivel_riesgo=2)
    assert "CONTAGIO" not in tipos(nivel_riesgo=1)
    assert "CONTAGIO" not in tipos(fecha_fin=_t(6))


@pytest.mark.parametrize("sentencia", [
    "UPDATE modulo4.resultados_inferencia SET nivel_riesgo = 0 WHERE id_resultado_inferencia = :r",
    "DELETE FROM modulo4.resultados_inferencia WHERE id_resultado_inferencia = :r",
    "UPDATE modulo4.historial_diagnostico_eventos SET payload = '{}' WHERE id_resultado_inferencia = :r",
    "DELETE FROM modulo4.historial_diagnostico_eventos WHERE id_resultado_inferencia = :r",
])
def test_resultados_e_historial_son_de_solo_escritura(db_session, escenario, sentencia):
    SqlAlchemyHistorialDiagnosticoRepository(db_session).materializar_eventos(_consultar(db_session, escenario))
    with pytest.raises(DBAPIError) as exc, db_session.begin_nested():
        db_session.execute(text(sentencia), {"r": escenario["ri2"]})
    assert exc.value.orig.pgcode == "P0403"
