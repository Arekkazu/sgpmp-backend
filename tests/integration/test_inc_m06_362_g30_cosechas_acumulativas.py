# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-14 | destroyerban | INC-M06-362-G30 RF-85: cosechas del mismo día del pesaje se acumulan; la que excede se rechaza |
"""INC-M06-362-G30 / TC-M06-136 contra PostgreSQL real: 400, 400 y 300 kg sobre un activo de 1.000 kg.

M02 guarda la fecha de una cosecha como día (medianoche UTC), y el pesaje con su instante real. En el escenario
de QA (activo ya reconocido, pesaje de 1.000 kg y cosechas del mismo día) las cosechas quedaban «antes» del pesaje,
no se descontaban y cada una se calculaba sobre los 1.000 kg.
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal as D

from sqlalchemy import text

from tests.integration.test_m06_flujo_nic41_integration import (  # noqa: F401 (fixtures)
    HOY,
    _activo,
    _configurar,
    _finca,
    _matriz,
    _pesaje,
    _precio,
    contador,
    m06,
)


def _cosecha(db, id_evento: int, id_activo: int, id_metrica: int, kg: str) -> None:
    """Como la guarda M02 (RF-43): fecha de día, anterior al instante del pesaje del mismo día."""
    db.execute(text("SET LOCAL session_replication_role = replica"))
    db.execute(text("""INSERT INTO modulo2.eventos_activos (id_eventos, id_activo_biologico, fecha)
                       VALUES (:e, :a, now() - interval '1 hour')"""), {"e": id_evento, "a": id_activo})
    db.execute(text("""INSERT INTO modulo2.eventos_productivos (id_evento, cantidad, id_metrica_produccion, id_ciclo_productivo)
                       VALUES (:e, :c, :m, 1)"""), {"e": id_evento, "c": D(kg), "m": id_metrica})
    db.execute(text("SET LOCAL session_replication_role = origin"))


def test_tres_cosechas_se_acumulan_y_la_que_excede_se_rechaza(db_session, m06, contador):
    uid = contador["id_usuario"]
    especie = 2
    finca = _finca(db_session, uid)
    _configurar(m06, uid, especie)
    _matriz(m06, uid)
    m06.guardar_asignacion().execute("PRODUCTO_AGRICOLA", "TRASLADO", None, None, "1435", "1586", uid)
    activo = _activo(db_session, finca, uid, especie=especie, origen="compra", costo=D("18000000"))
    pesaje = _pesaje(db_session, activo, "1000", -timedelta(minutes=10))
    _precio(m06, uid, especie, "19789.48", HOY - timedelta(days=10))
    m06.confirmar_reconocimiento().execute(activo, uid)
    # El activo venía reconocido de antes: las cosechas de hoy son elegibles para M06 aunque su fecha (día) sea
    # anterior al instante del pesaje.
    db_session.execute(text("SET LOCAL session_replication_role = replica"))
    db_session.execute(text("""UPDATE modulo6.reconocimientos_iniciales SET fecha_creacion = now() - interval '1 day'
                               WHERE id_activo_biologico = :a"""), {"a": activo})
    db_session.execute(text("SET LOCAL session_replication_role = origin"))
    valor = m06.valoraciones.ultimo_calculo(activo).valor_neto
    id_metrica = db_session.execute(text("""
        INSERT INTO modulo9.metricas_produccion (nombre, unidad_medida, tipo_medicion, tiene_estado, id_especie)
        VALUES (:n, 'kg', 'PESO', false, :e) RETURNING id_metrica_produccion"""),
        {"n": f"Carne {uuid.uuid4().hex[:6]}", "e": especie}).scalar_one()

    for i, kg in enumerate(("400", "400", "300"), start=1):
        _cosecha(db_session, pesaje + i, activo, id_metrica, kg)  # registradas después del pesaje
        m06.procesar_eventos().execute()
    resultados = dict(db_session.execute(text("""SELECT id_evento, resultado::text FROM modulo6.procesamientos_eventos_m02
                                                  WHERE id_evento IN (:p, :c1, :c2, :c3)"""),
                                         {"p": pesaje, "c1": pesaje + 1, "c2": pesaje + 2, "c3": pesaje + 3}).all())
    assert [resultados[pesaje + i] for i in (1, 2, 3)] == ["PROCESADO", "PROCESADO", "MEDICION_PENDIENTE"], resultados
    # El pesaje de 1.000 kg ya no encuentra «crecimiento» frente a lo que queda: sin ganancia falsa.
    assert resultados.get(pesaje) != "PROCESADO", resultados

    productos = db_session.execute(text("""SELECT cantidad_cosechada, valor_reduccion_activo FROM
        modulo6.reconocimientos_productos_agricolas WHERE id_activo_biologico = :a ORDER BY 1"""), {"a": activo}).all()
    assert [p.cantidad_cosechada for p in productos] == [D("400"), D("400")]  # la de 300 kg no se reconoce
    assert sum(p.valor_reduccion_activo for p in productos) <= valor
    restante = m06.valoraciones.ultimo_calculo(activo)
    assert restante.magnitud == D("200")
    assert abs(restante.valor_neto - valor * D("0.2")) <= D("1")
    detalle = db_session.execute(text("""SELECT detalle FROM modulo6.procesamientos_eventos_m02
                                         WHERE id_evento = :e"""), {"e": pesaje + 3}).scalar_one()
    assert "supera la cantidad disponible" in detalle and "200 kg" in detalle, detalle
