# | Fecha      | Nombre         | Que se hizo                                                              |
# |------------|----------------|--------------------------------------------------------------------------|
# | 2026-11-09 | LuisfNarvaez01 | INC-M05-283-G42 / INC-M05-284-G43 RF-81: tope de página y datos del evento |
"""Historial de Suministros (RF-81).

- INC-M05-283-G42 (#970): ``registros_por_pagina`` > 200 no se rechaza (antes 400 VAL_ENTRADA);
  se aplica el máximo de 200.
- INC-M05-284-G43 (#971): los eventos ``CONSULTA_HISTORIAL_EJECUTADA`` y
  ``EXPORTACION_HISTORIAL_GENERADA`` guardan los filtros aplicados y el total de registros
  retornados, también cuando la consulta no devuelve resultados (0)."""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from tests.integration.test_m05_flujo_completo_integration import (  # noqa: F401 (fixtures)
    HOY, _catalogos, _consumo, _escenario, admin, cliente,
)

pytestmark = pytest.mark.integration


def _ultimo_evento(db, tipo: str, id_activo: int) -> dict:
    return db.execute(text("""SELECT datos_nuevos FROM modulo5.auditorias_suministros
                              WHERE tipo_operacion::text = :t
                                AND id_activo_biologico = :a
                              ORDER BY id_auditoria_suministro DESC LIMIT 1"""), {"t": tipo, "a": id_activo}).scalar()


@pytest.fixture
def con_registros(cliente, db_session, admin):
    usuario, headers = admin
    esc = _escenario(db_session, usuario["id_usuario"])
    for hora in ("06:00", "12:00", "18:00"):
        assert _consumo(cliente, headers, esc, hora).status_code == 201
    return esc, headers


def test_mas_de_200_por_pagina_se_limita_a_200(cliente, db_session, con_registros):
    esc, headers = con_registros
    r = cliente.get("/suministros/historial", headers=headers,
                    params={"id_activo_biologico": esc["activo"], "registros_por_pagina": 201})
    assert r.status_code == 200, r.text
    assert len(r.json()["items"]) == 3 and r.json()["resumen"]["total_paginas"] == 1
    assert _ultimo_evento(db_session, "CONSULTA_HISTORIAL_EJECUTADA", esc["activo"])["registros_por_pagina"] == 200
    assert cliente.get("/suministros/historial", headers=headers,
                       params={"id_activo_biologico": esc["activo"], "registros_por_pagina": 0}).status_code == 400


def test_evento_de_consulta_guarda_filtros_y_total(cliente, db_session, con_registros):
    esc, headers = con_registros
    r = cliente.get("/suministros/historial", headers=headers, params={
        "id_activo_biologico": esc["activo"], "tipo_suministro_filtro": "ALIMENTO", "registros_por_pagina": 2})
    assert r.status_code == 200, r.text
    datos = _ultimo_evento(db_session, "CONSULTA_HISTORIAL_EJECUTADA", esc["activo"])
    assert datos["filtros_aplicados"]["tipo_suministro_filtro"] == "ALIMENTO"
    assert datos["filtros_aplicados"]["id_activo_biologico"] == esc["activo"]
    assert (datos["total_registros_retornados"], datos["total_registros_filtrados"]) == (2, 3)


def test_evento_de_consulta_sin_resultados_guarda_total_cero(cliente, db_session, con_registros):
    esc, headers = con_registros
    desde, hasta = HOY - timedelta(days=400), HOY - timedelta(days=300)
    r = cliente.get("/suministros/historial", headers=headers, params={
        "id_activo_biologico": esc["activo"], "fecha_inicio_filtro": desde.isoformat(),
        "fecha_fin_filtro": hasta.isoformat()})
    assert r.status_code == 200 and r.json()["items"] == []
    datos = _ultimo_evento(db_session, "CONSULTA_HISTORIAL_EJECUTADA", esc["activo"])
    assert datos["total_registros_retornados"] == 0
    assert (datos["filtros_aplicados"]["fecha_inicio_filtro"], datos["filtros_aplicados"]["fecha_fin_filtro"]) == (
        desde.isoformat(), hasta.isoformat())


@pytest.mark.parametrize("formato", ["PDF", "EXCEL"])
def test_evento_de_exportacion_guarda_filtros_formato_y_total(cliente, db_session, con_registros, formato):
    esc, headers = con_registros
    r = cliente.get("/suministros/historial/exportar", headers=headers, params={
        "id_activo_biologico": esc["activo"], "formato_exportacion": formato})
    assert r.status_code == 200, r.text
    datos = _ultimo_evento(db_session, "EXPORTACION_HISTORIAL_GENERADA", esc["activo"])
    assert datos["formato_exportacion"] == formato and datos["total_registros_retornados"] == 3
    assert datos["filtros_aplicados"]["tipo_suministro_filtro"] == "TODOS"
