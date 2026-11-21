# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-14 | destroyerban | INC-M06-361-G24 RF-85 FA-4: la cosecha del 100 % deja el activo en cero y en baja (sesión tipo sandbox) |
"""INC-M06-361-G24 / TC-M06-110 contra PostgreSQL real.

``db_session`` es una conexión con transacción externa y ``create_savepoint``, igual que el sandbox de QA: lo
que el caso de uso confirma solo llega a un SAVEPOINT. Con la baja en una sesión aparte (``sesion_sistema``) el
activo creado aquí no existía para M02 y quedaba ACTIVO, sin baja. Ahora la baja corre en la misma sesión.
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
    _escalar,
    _finca,
    _id,
    _matriz,
    _pesaje,
    _precio,
    contador,
    m06,
)

ESTADO_BAJA = 6


def _cosecha(db, id_activo: int, especie: int, kg: str) -> int:
    """Evento productivo de M02 (RF-43): producto de consumo en kg, el mismo que la magnitud del activo."""
    id_metrica = db.execute(text("""
        INSERT INTO modulo9.metricas_produccion (nombre, unidad_medida, tipo_medicion, tiene_estado, id_especie)
        VALUES (:n, 'kg', 'PESO', false, :e) RETURNING id_metrica_produccion"""),
        {"n": f"Carne en canal {uuid.uuid4().hex[:6]}", "e": especie}).scalar_one()
    id_evento = _id()
    db.execute(text("SET LOCAL session_replication_role = replica"))
    db.execute(text("INSERT INTO modulo2.eventos_activos (id_eventos, id_activo_biologico, fecha) VALUES (:e, :a, now())"),
               {"e": id_evento, "a": id_activo})
    db.execute(text("""INSERT INTO modulo2.eventos_productivos (id_evento, cantidad, id_metrica_produccion, id_ciclo_productivo)
                       VALUES (:e, :c, :m, 1)"""), {"e": id_evento, "c": D(kg), "m": id_metrica})
    db.execute(text("SET LOCAL session_replication_role = origin"))
    return id_evento


def test_cosecha_del_100_por_ciento_deja_el_activo_en_cero_y_en_baja(db_session, m06, contador):
    uid = contador["id_usuario"]
    especie = 2
    finca = _finca(db_session, uid)
    _configurar(m06, uid, especie)
    _matriz(m06, uid)
    m06.guardar_asignacion().execute("PRODUCTO_AGRICOLA", "TRASLADO", None, None, "1435", "1586", uid)
    activo = _activo(db_session, finca, uid, especie=especie, origen="compra", costo=D("18000000"))
    _pesaje(db_session, activo, "1000", -timedelta(minutes=5))
    _precio(m06, uid, especie, "19789.48", HOY - timedelta(days=10))
    m06.confirmar_reconocimiento().execute(activo, uid)
    valor_antes = m06.valoraciones.ultimo_calculo(activo).valor_neto

    evento = _cosecha(db_session, activo, especie, "1000")
    resultado = m06.procesar_eventos().execute()
    assert resultado.get("PROCESADO") == 1, resultado

    # Producto y traslado a inventario por el 100 %.
    producto = db_session.execute(text("""SELECT proporcion_cosechada, valor_reduccion_activo FROM
        modulo6.reconocimientos_productos_agricolas WHERE id_activo_biologico = :a"""), {"a": activo}).one()
    assert producto.proporcion_cosechada == 1 and producto.valor_reduccion_activo == valor_antes

    # La baja quedó en M02, en la misma transacción visible para la sesión (TC-M06-110c/d).
    assert _escalar(db_session, "SELECT id_estado FROM modulo2.activos_biologicos WHERE id_activo_biologico = :a",
                    a=activo) == ESTADO_BAJA
    baja = db_session.execute(text("""SELECT eb.tipo::text AS tipo FROM modulo2.eventos_bajas eb
        JOIN modulo2.eventos_activos ea ON ea.id_eventos = eb.id_evento WHERE ea.id_activo_biologico = :a"""),
        {"a": activo}).one()
    assert baja.tipo == "sacrificio"
    auditados = [t for (t,) in db_session.execute(text(
        "SELECT tipo_evento::text FROM modulo6.auditorias_financieras WHERE id_activo_biologico = :a"), {"a": activo})]
    assert "MEDICION_POSTERIOR" in auditados and "MEDICION_PENDIENTE" not in auditados, auditados

    # Valor en cero (TC-M06-110b): sin valor vigente y el historial lo dice.
    assert m06.valoraciones.ultimo_calculo(activo) is None
    historial = m06.valoraciones.historial_activo(activo)
    assert historial["cosechado_completamente"] is True and historial["valor_en_libros_actual"] == 0
    assert any(c["consumido_por_cosecha"] for c in historial["calculos"])
    assert evento  # el evento productivo quedó procesado, no pendiente
