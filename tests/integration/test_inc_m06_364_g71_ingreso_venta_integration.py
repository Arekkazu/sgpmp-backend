# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-15 | Arekkazu | INC-M06-364-G71 RF-45/RF-93: ingreso por venta de activos en el estado de resultados |
"""INC-M06-364-G71 / TC-M06-G71 contra PostgreSQL real (con la migración ``b8a323f06e9b``).

La baja por venta guarda lo recibido (RF-45); el estado de resultados lo presenta como ingreso y deja el valor en
libros en gastos, así el neto es la utilidad de la venta. La venta no genera línea de asiento."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.biological_assets.domain.entities.activo_biologico import EventoActivo, EventoBaja
from src.biological_assets.infrastructure.repositories.evento_activo_repository import SqlAlchemyEventoActivoRepository
from tests.integration.test_m06_flujo_nic41_integration import (  # noqa: F401 (fixtures)
    HOY, NIT, _activo, _configurar, _finca, _id, _matriz, _pesaje, _precio, contador, m06,
)

pytestmark = pytest.mark.integration


def _baja(db, id_activo: int, tipo: str, valor_venta: str | None = None) -> int:
    id_evento = _id()
    db.execute(text("SET LOCAL session_replication_role = replica"))
    db.execute(text("INSERT INTO modulo2.eventos_activos (id_eventos, id_activo_biologico, fecha) VALUES (:e, :a, now())"),
               {"e": id_evento, "a": id_activo})
    db.execute(text("""INSERT INTO modulo2.eventos_bajas (id_evento, cantidad_afectada, tipo, valor_venta)
                       VALUES (:e, 1, CAST(:t AS modulo2.enum_evento_bajas_tipo), :v)"""),
               {"e": id_evento, "t": tipo, "v": D(valor_venta) if valor_venta else None})
    db.execute(text("SET LOCAL session_replication_role = origin"))
    return id_evento


def _reconocido(db, m06, uid, finca, especie=2) -> int:
    activo = _activo(db, finca, uid, especie=especie, origen="compra", costo=D("3000000"))
    _pesaje(db, activo, "400", -timedelta(minutes=5))
    m06.confirmar_reconocimiento().execute(activo, uid)
    return activo


def test_la_venta_entra_como_ingreso_y_el_valor_en_libros_como_gasto(db_session, m06, contador):
    uid, especie = contador["id_usuario"], 2
    finca = _finca(db_session, uid)
    _configurar(m06, uid, especie)
    _matriz(m06, uid)
    _precio(m06, uid, especie, "8000", HOY - timedelta(days=10))
    vendido = _reconocido(db_session, m06, uid, finca)          # valor en libros 3.040.000
    sin_valor = _reconocido(db_session, m06, uid, finca)

    venta = _baja(db_session, vendido, "venta", "4000000")
    _baja(db_session, sin_valor, "venta")                        # venta registrada antes del campo
    assert m06.procesar_eventos().execute().get("PROCESADO") == 2
    periodo = m06.periodos.que_contiene(NIT, HOY).id_periodo_contable

    estado = m06.constructor_estado.calcular(periodo, {"id_activo_biologico": vendido})
    assert estado["componentes"]["ingresos_venta_activos"] == "4000000.0000"
    assert estado["componentes"]["bajas_activos"] == "3040000.0000"
    assert m06.constructor_estado.calcular(periodo, {})["ventas_sin_valor"] == 1
    # Sin asiento por la venta: la línea de la baja sigue siendo solo el valor en libros.
    assert db_session.execute(text("""SELECT array_agg(valor) FROM modulo6.lineas_asiento_nic41
        WHERE tabla_origen = 'procesamientos_eventos_m02' AND id_origen = :e"""), {"e": venta}).scalar() == [D("3040000.00")]
    payload = db_session.execute(text("""SELECT datos_nuevos FROM modulo6.auditorias_financieras
        WHERE tipo_evento = 'BAJA_ACTIVO_REGISTRADA' AND id_referencia = :e"""), {"e": venta}).scalar()
    assert payload["valor_venta"] == "4000000.00" and payload["resultado_venta"] == "960000.00"


def test_la_bd_solo_acepta_valor_y_referencia_en_una_venta(db_session, m06, contador):
    uid = contador["id_usuario"]
    activo = _activo(db_session, _finca(db_session, uid), uid, especie=2, origen="compra", costo=D("1000"))
    for tipo, columna, valor in (("muerte", "valor_venta", D("10")), ("venta", "valor_venta", D("0")),
                                 ("sacrificio", "referencia_venta", "FE-1")):
        with pytest.raises(IntegrityError):
            with db_session.begin_nested():
                id_evento = _id()
                db_session.execute(text("INSERT INTO modulo2.eventos_activos (id_eventos, id_activo_biologico, fecha) "
                                        "VALUES (:e, :a, now())"), {"e": id_evento, "a": activo})
                db_session.execute(text(f"""INSERT INTO modulo2.eventos_bajas (id_evento, cantidad_afectada, tipo, {columna})
                    VALUES (:e, 1, CAST(:t AS modulo2.enum_evento_bajas_tipo), :v)"""), {"e": id_evento, "t": tipo, "v": valor})


def test_el_repositorio_de_m02_guarda_y_lee_el_valor_de_la_venta(db_session, contador):
    uid = contador["id_usuario"]
    activo = _activo(db_session, _finca(db_session, uid), uid, especie=2, origen="compra", costo=D("1000"))
    repo = SqlAlchemyEventoActivoRepository(db_session)
    db_session.execute(text("SET LOCAL session_replication_role = replica"))  # sin las validaciones de estado de M02
    guardado = repo.guardar(EventoActivo(
        id_activo_biologico=activo, fecha=datetime.now(timezone.utc), id_usuario=uid,
        baja=EventoBaja(cantidad_afectada=1, tipo="venta", detalles="Venta en feria", valor_venta=D("1250000.50"),
                        referencia_venta="FE-1023")))
    db_session.execute(text("SET LOCAL session_replication_role = origin"))

    [leido] = [e for e in repo.listar_por_activo(activo) if e.id_eventos == guardado.id_eventos]
    assert (leido.baja.valor_venta, leido.baja.referencia_venta) == (D("1250000.50"), "FE-1023")
