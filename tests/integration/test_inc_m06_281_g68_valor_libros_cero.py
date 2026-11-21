# | Fecha      | Nombre         | Que se hizo                                                              |
# |------------|----------------|--------------------------------------------------------------------------|
# | 2026-11-09 | LuisfNarvaez01 | INC-M06-281-G68-07 RF-88: alerta persistente al llevar el valor en libros a cero |
"""INC-M06-281-G68-07 (#968), escenario TC-M06-07 de QA.

Costo 10.000.000, depreciación 7.000.000, deterioro 5.000.000 → resultado matemático −2.000.000.
El valor en libros queda en 0, la línea de deterioro es por lo que quedaba (3.000.000) y queda
una alerta persistente ``VALOR_LIBROS_AJUSTADO_A_CERO``, consultable por el activo, con el valor
calculado y el aplicado; distinta del evento genérico ``DETERIORO_REGISTRADO``."""
from __future__ import annotations

from decimal import Decimal as D

import pytest
from sqlalchemy import text

from tests.integration.test_m06_flujo_nic41_integration import (  # noqa: F401 (fixtures)
    HOY, NIT, _activo, _configurar, _finca, _id, _matriz, _pesaje, contador, m06,
)

pytestmark = pytest.mark.integration


class _Notificador:
    def __init__(self) -> None:
        self.avisos: list[tuple[str, dict]] = []

    def a_contadores(self, tipo_evento, mensaje, detalle, id_finca=None) -> None:
        self.avisos.append((mensaje, detalle))


def _evento_sanitario(db, id_activo: int) -> int:
    id_evento = _id()
    db.execute(text("SET LOCAL session_replication_role = replica"))
    db.execute(text("INSERT INTO modulo2.eventos_activos (id_eventos, id_activo_biologico, fecha) VALUES (:e, :a, now())"),
               {"e": id_evento, "a": id_activo})
    db.execute(text("INSERT INTO modulo2.eventos_sanitarios (id_evento, tipo, diagnostico) VALUES (:e, 'DIAGNOSTICO', 'Brucelosis')"),
               {"e": id_evento})
    db.execute(text("SET LOCAL session_replication_role = origin"))
    return id_evento


def test_valor_en_libros_negativo_queda_en_cero_con_alerta_persistente(db_session, m06, contador):
    uid = contador["id_usuario"]
    especie = 3  # sin precios: modelo de costo (NIC 41 ¶30)
    finca = _finca(db_session, uid)
    _configurar(m06, uid, especie, vida=24)
    activo = _activo(db_session, finca, uid, especie=especie, origen="compra", costo=D("10000000"))
    _pesaje(db_session, activo, "30")
    assert m06.confirmar_reconocimiento().execute(activo, uid)["indicador_valoracion"] == "VALORACION_POR_COSTO"
    db_session.execute(text("""UPDATE modulo6.valoraciones_por_costos SET depreciacion_acumulada = 7000000,
                                      valor_contable_por_costo = 3000000
                               WHERE id_activo_biologico = :a AND es_activa"""), {"a": activo})
    notificador = _Notificador()
    m06.__dict__["notificador"] = notificador

    resultado = m06.registrar_deterioro().execute(
        activo, _evento_sanitario(db_session, activo), D("5000000"),
        "Brucelosis confirmada: pérdida de capacidad productiva del animal", uid)

    assert resultado["valor_contable"] == 0
    assert resultado["valor_libros_calculado"] == D("-2000000.0000")
    [linea] = [ln for ln in m06.asientos.del_activo(activo) if ln.tipo_hecho == "DETERIORO_ACTIVO_COSTO"]
    assert linea.valor == D("3000000.00")

    eventos = m06.consultar_auditoria().execute(
        {"id_activo_biologico": activo, "tipo_evento": ["VALOR_LIBROS_AJUSTADO_A_CERO"]}, 1, 100, True)
    [alerta] = eventos["eventos"]
    assert alerta["descripcion_evento"] == "Valor en libros negativo ajustado a cero"
    assert alerta["severidad"] == "WARNING"
    assert alerta["resumen_payload"]["valor_calculado"] == "-2000000.0000"
    assert alerta["resumen_payload"]["valor_aplicado"] == "0.0000"
    assert alerta["fecha_hora"] is not None and alerta["integridad_verificable"]

    [(mensaje, detalle)] = notificador.avisos
    assert detalle["id_activo_biologico"] == activo and detalle["valor_calculado"] == "-2000000.0000"
    assert "None" not in mensaje and "RF" not in mensaje


def test_la_depreciacion_del_cierre_que_lleva_a_negativo_genera_la_alerta(db_session, m06, contador):
    uid = contador["id_usuario"]
    especie = 3
    finca = _finca(db_session, uid)
    _configurar(m06, uid, especie, vida=24)
    _matriz(m06, uid)
    activo = _activo(db_session, finca, uid, especie=especie, origen="compra", costo=D("10000000"))
    _pesaje(db_session, activo, "30")
    m06.confirmar_reconocimiento().execute(activo, uid)
    # 30 meses de una vida útil de 24: depreciación total (10.000.000) + deterioro previo 5.000.000 → −5.000.000.
    db_session.execute(text("""UPDATE modulo6.valoraciones_por_costos
                               SET fecha_adquisicion = fecha_adquisicion - interval '30 months',
                                   deterioro_acumulado = 5000000, valor_contable_por_costo = 5000000
                               WHERE id_activo_biologico = :a AND es_activa"""), {"a": activo})
    periodo = m06.periodos.que_contiene(NIT, HOY)

    m06.cierre().execute(periodo.id_periodo_contable, uid, autorizar_exclusiones=True)

    eventos = m06.consultar_auditoria().execute(
        {"id_activo_biologico": activo, "tipo_evento": ["VALOR_LIBROS_AJUSTADO_A_CERO"]}, 1, 100, True)
    [alerta] = eventos["eventos"]
    assert alerta["resumen_payload"]["origen"] == "DEPRECIACION"
    assert alerta["resumen_payload"]["valor_calculado"] == "-5000000.0000"


def test_deterioro_que_no_lleva_a_negativo_no_genera_la_alerta(db_session, m06, contador):
    uid = contador["id_usuario"]
    especie = 3
    finca = _finca(db_session, uid)
    _configurar(m06, uid, especie, vida=24)
    activo = _activo(db_session, finca, uid, especie=especie, origen="compra", costo=D("10000000"))
    _pesaje(db_session, activo, "30")
    m06.confirmar_reconocimiento().execute(activo, uid)
    m06.__dict__["notificador"] = _Notificador()

    resultado = m06.registrar_deterioro().execute(
        activo, _evento_sanitario(db_session, activo), D("1000000"),
        "Cojera crónica con pérdida parcial de capacidad productiva", uid)

    assert resultado["valor_contable"] == D("9000000.0000")
    eventos = m06.consultar_auditoria().execute(
        {"id_activo_biologico": activo, "tipo_evento": ["VALOR_LIBROS_AJUSTADO_A_CERO"]}, 1, 100, True)
    assert eventos["total_registros"] == 0 and m06.notificador.avisos == []
