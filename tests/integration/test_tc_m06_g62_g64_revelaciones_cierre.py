# | Fecha      | Nombre   | Que se hizo                                                                              |
# |------------|----------|------------------------------------------------------------------------------------------|
# | 2026-11-15 | Arekkazu | TC-M06-G62/G64 RF-92: conciliación con el valor al cierre del período y riesgos climáticos |
"""Informe de revelaciones (RF-92) contra PostgreSQL.

- TC-M06-G62 (#1151): el valor al cierre es el del período, no uno medido después del cierre que entró al siguiente
  (RF-87 v1.1); y el asiento que el cierre trasladó por trazabilidad incompleta (RF-91) aparece como partida
  conciliatoria en los dos períodos, así que ambos cuadran (¶50, CA-4).
- TC-M06-G64 (#1152): la sección de riesgos trae las alertas climáticas de Telemetría y las categorías climática,
  sanitaria y de mercado salen siempre, con su fuente (CA-5)."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal as D

import pytest
from sqlalchemy import text

from tests.integration.test_m06_flujo_nic41_integration import (  # noqa: F401 (fixtures)
    HOY, NIT, _activo, _configurar, _escalar, _finca, _matriz, _pesaje, _precio, contador, m06,
)

pytestmark = pytest.mark.integration


def _calculado(f: dict) -> D:
    return (f["valor_inicio"] + f["compras"] + f["nacimientos_y_otros_ingresos"] + f["transformacion_biologica"]
            + f["precio_mercado"] - f["cosechas"] - f["bajas"] - f["depreciacion_y_deterioro"]
            + f["asientos_trasladados_por_cierre"])


def _fila(m06, id_periodo: int, activo: int) -> dict:
    informe = m06.constructor_informe.construir(id_periodo, {"declaracion_sin_novedad": True})
    [fila] = [r for r in informe["contenido"]["parr_50_conciliacion"] if r["id_activo_biologico"] == activo]
    assert abs(_calculado(fila) - fila["valor_cierre"]) <= D("0.01"), fila
    assert not [a for a in informe["alertas_consistencia"] if a.get("id_activo_biologico") == activo]
    return fila


def test_conciliacion_cuadra_con_asiento_trasladado_y_medicion_posterior_al_cierre(db_session, m06, contador):
    uid = contador["id_usuario"]
    especie = 2
    finca = _finca(db_session, uid)
    _configurar(m06, uid, especie)
    _matriz(m06, uid)
    activo = _activo(db_session, finca, uid, especie=especie, origen="compra", costo=D("3000000"))
    _pesaje(db_session, activo, "400", -timedelta(minutes=5))
    _precio(m06, uid, especie, "8000", HOY - timedelta(days=10))
    m06.confirmar_reconocimiento().execute(activo, uid)  # VN 3.040.000
    _pesaje(db_session, activo, "420")  # sin auditoría en M02: su variación queda con la trazabilidad incompleta
    assert m06.procesar_eventos().execute().get("PROCESADO") == 1  # VN 3.192.000 (TB +152.000)
    periodo = m06.periodos.que_contiene(NIT, HOY).id_periodo_contable
    siguiente = m06.cierre().execute(periodo, uid, autorizar_exclusiones=True)["id_periodo_siguiente"]
    assert _escalar(db_session, """SELECT count(*) FROM modulo6.lineas_asiento_nic41
                                   WHERE id_activo_biologico = :a AND id_periodo_contable = :s""", a=activo, s=siguiente)

    # Hecho posterior al cierre con fecha dentro del período cerrado: se mide en el siguiente (RF-87 v1.1).
    _precio(m06, uid, especie, "8100", HOY)
    medido = m06.medidor.medir(m06.activos.obtener(activo), m06.periodos.obtener(siguiente), HOY, origen="EVENTO",
                               id_usuario=uid, id_usuario_auditoria=uid)
    assert medido.estado == "MEDIDO"  # VN 420 × 8.100 × 0,95 = 3.231.900

    cerrado = _fila(m06, periodo, activo)
    assert cerrado["valor_cierre"] == D("3192000") and cerrado["asientos_trasladados_por_cierre"] > 0
    abierto = _fila(m06, siguiente, activo)
    assert (abierto["valor_inicio"], abierto["valor_cierre"]) == (D("3192000"), D("3231900"))
    assert abierto["asientos_trasladados_por_cierre"] == -cerrado["asientos_trasladados_por_cierre"]


def _alerta(db, infraestructura: int, tipo: str, estado: str = "ACTIVA") -> None:
    db.execute(text("""INSERT INTO modulo3.alertas (tipo_alerta, severidad, estado_alerta, origen_evento, id_infraestructura,
                                                    fecha_evento, tipo_variable)
                       VALUES (CAST(:t AS modulo3.enum_tipo_alerta), 'MODERADO', CAST(:e AS modulo3.enum_estado_alerta),
                               'BACKEND', :i, now(), 'TEMPERATURA_AMBIENTAL')"""), {"t": tipo, "e": estado, "i": infraestructura})


def test_riesgos_traen_las_alertas_climaticas_y_las_tres_categorias(db_session, m06, contador):
    uid = contador["id_usuario"]
    especie = 2
    finca = _finca(db_session, uid)
    _configurar(m06, uid, especie)
    _matriz(m06, uid)
    activo = _activo(db_session, finca, uid, especie=especie, origen="compra", costo=D("3000000"))
    _pesaje(db_session, activo, "400", -timedelta(minutes=5))
    _precio(m06, uid, especie, "8000", HOY - timedelta(days=10))
    m06.confirmar_reconocimiento().execute(activo, uid)
    infraestructura = _escalar(db_session, "SELECT id_infraestructura FROM modulo2.activos_biologicos WHERE id_activo_biologico = :a",
                               a=activo)
    _alerta(db_session, infraestructura, "ESTRES_TERMICO")
    _alerta(db_session, infraestructura, "ESTRES_TERMICO", "DESCARTADA")  # una falsa alarma no es un riesgo
    _alerta(db_session, infraestructura, "TECNICA")  # una falla del dispositivo no es climática
    periodo = m06.periodos.que_contiene(NIT, HOY).id_periodo_contable

    riesgos = m06.constructor_informe.construir(periodo, {"declaracion_sin_novedad": True})["contenido"]["parr_53_riesgos"]

    climaticos = [r for r in riesgos if r["categoria"] == "Climático"]
    assert [(r["tipo"], r["cantidad"]) for r in climaticos] == [("Estrés térmico", 1)]
    assert {"Climático", "Sanitario", "Mercado"} <= {r["categoria"] for r in riesgos}
    assert all(r["fuente"] for r in riesgos)
