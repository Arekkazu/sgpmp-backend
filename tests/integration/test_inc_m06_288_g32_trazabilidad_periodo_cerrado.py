# | Fecha      | Nombre         | Que se hizo                                                            |
# |------------|----------------|------------------------------------------------------------------------|
# | 2026-11-09 | LuisfNarvaez01 | INC-M06-288-G32 RF-91: una cadena de período cerrado no aborta el resto |
"""INC-M06-288-G32 (#975): la verificación del período abierto no se cae por una línea arrastrada.

El cierre (RF-87 paso 3) pasa al período siguiente las líneas con trazabilidad incompleta, pero
su variación queda en el período CERRADO. Al re-verificarlas, la cadena nueva se insertaba con el
id de esa variación, TGR-M06-26 (RF-91 R4) la rechazaba y el rollback total respondía 500.

Ahora la cadena nueva se vincula a la línea (el id de la variación queda en los eslabones para
navegar al origen), las demás líneas se verifican y la protección del período cerrado sigue."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal as D

import pytest
from sqlalchemy import text

from src.financial_valuation.infrastructure.repositories.sql import escribir
from src.shared.errors import AppError
from tests.integration.test_m06_flujo_nic41_integration import (
    HOY, NIT, _activo, _configurar, _escalar, _finca, _matriz, _pesaje, _precio, _provision_m05,  # noqa: F401
    contador, m06,
)

pytestmark = pytest.mark.integration


def _periodo_cerrado_con_linea_arrastrada(db_session, m06, uid) -> tuple[int, int, int, int]:
    especie = 2
    finca = _finca(db_session, uid)
    _configurar(m06, uid, especie)
    _matriz(m06, uid)
    activo = _activo(db_session, finca, uid, especie=especie, origen="compra", costo=D("3000000"))
    _pesaje(db_session, activo, "400", -timedelta(minutes=5))
    _precio(m06, uid, especie, "8000", HOY - timedelta(days=10))
    m06.confirmar_reconocimiento().execute(activo, uid)
    _precio(m06, uid, especie, "8500", HOY)
    _pesaje(db_session, activo, "420")
    m06.procesar_eventos().execute()
    periodo = m06.periodos.que_contiene(NIT, HOY)
    cierre = m06.cierre().execute(periodo.id_periodo_contable, uid, autorizar_exclusiones=True)
    siguiente = cierre["id_periodo_siguiente"]

    # Estado de TEST: una línea de variación del período cerrado quedó en el siguiente, pendiente.
    id_linea, id_variacion = db_session.execute(text("""
        SELECT l.id_linea_asiento_nic41, l.id_origen FROM modulo6.lineas_asiento_nic41 l
        WHERE l.id_activo_biologico = :a AND l.tabla_origen = 'variaciones_valor_razonable'
        ORDER BY 1 LIMIT 1"""), {"a": activo}).one()
    db_session.execute(text("SET LOCAL session_replication_role = replica"))
    db_session.execute(text("""UPDATE modulo6.lineas_asiento_nic41
                               SET id_periodo_contable = :p, estado_trazabilidad = 'PENDIENTE_TRAZABILIDAD'
                               WHERE id_linea_asiento_nic41 = :l"""), {"p": siguiente, "l": id_linea})
    db_session.execute(text("SET LOCAL session_replication_role = origin"))
    # Y una línea normal del período abierto (consumo de M05 con fecha del período cerrado → entra al siguiente).
    _provision_m05(db_session, activo, "1000")
    m06.procesar_provisiones().execute()
    return periodo.id_periodo_contable, siguiente, id_linea, id_variacion


def test_linea_arrastrada_no_aborta_la_verificacion_del_periodo(db_session, m06, contador):
    uid = contador["id_usuario"]
    _, siguiente, id_linea, id_variacion = _periodo_cerrado_con_linea_arrastrada(db_session, m06, uid)
    lineas_periodo = _escalar(db_session, "SELECT count(*) FROM modulo6.lineas_asiento_nic41 WHERE id_periodo_contable = :p",
                              p=siguiente)
    assert lineas_periodo >= 2

    resultado = m06.verificar_trazabilidad().execute(siguiente, uid)  # antes: InfrastructureError → HTTP 500

    assert resultado["verificadas"] + len(resultado["pendientes"]) == lineas_periodo
    assert _escalar(db_session, """SELECT count(*) FROM modulo6.lineas_asiento_nic41
                                   WHERE id_periodo_contable = :p AND estado_trazabilidad = 'VERIFICACION_PENDIENTE'""",
                    p=siguiente) == 0
    cadena = m06.trazabilidad.cadena(id_linea)
    assert cadena["estado_verificacion"] is not None and cadena["eslabones"] is not None
    assert cadena["eslabones"]["ids"]["id_variacion_valor_razonable"] == id_variacion  # origen navegable
    assert cadena["eslabones"]["ids"].get("id_evento") and cadena["eslabones"]["ids"].get("id_precio_mercado")
    # La cadena nueva no se vincula por FK a la variación del período cerrado.
    assert _escalar(db_session, """SELECT id_variacion_valor_razonable FROM modulo6.cadenas_trazabilidad_contable
                                   WHERE id_linea_asiento_nic41 = :l ORDER BY id_asiento DESC LIMIT 1""",
                    l=id_linea) is None


def test_la_proteccion_del_periodo_cerrado_sigue_vigente(db_session, m06, contador):
    uid = contador["id_usuario"]
    cerrado, _, id_linea, id_variacion = _periodo_cerrado_con_linea_arrastrada(db_session, m06, uid)
    with pytest.raises(AppError) as exc:
        m06.verificar_trazabilidad().execute(cerrado, uid)
    assert exc.value.code == "PERIODO_NO_ABIERTO"
    # TGR-M06-26 sigue rechazando una cadena vinculada a la variación del período cerrado.
    with pytest.raises(Exception, match="TGR-M06-26"):
        with db_session.begin_nested():
            db_session.execute(text("""INSERT INTO modulo6.cadenas_trazabilidad_contable
                                       (id_variacion_valor_razonable, id_linea_asiento_nic41) VALUES (:v, :l)"""),
                               {"v": id_variacion, "l": id_linea})


def test_un_rechazo_de_la_bd_deja_la_linea_pendiente_y_sigue(db_session, m06, contador, monkeypatch):
    uid = contador["id_usuario"]
    _, siguiente, id_linea, _ = _periodo_cerrado_con_linea_arrastrada(db_session, m06, uid)
    repo = m06.trazabilidad
    original = repo._insertar_cadena

    def _falla_en_la_arrastrada(id_l, *args):
        if id_l == id_linea:  # cualquier rechazo de la BD, traducido por el repositorio
            escribir(db_session, "SELECT modulo6.fn_no_existe()")
        return original(id_l, *args)

    monkeypatch.setattr(repo, "_insertar_cadena", _falla_en_la_arrastrada)
    resultado = m06.verificar_trazabilidad().execute(siguiente, uid)
    [pendiente] = [p for p in resultado["pendientes"] if p["id_linea"] == id_linea]
    assert "no se pudo registrar la verificación" in pendiente["motivo"].lower()
    assert resultado["verificadas"] >= 1
