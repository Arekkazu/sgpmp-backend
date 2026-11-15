# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-14 | Arekkazu | INC-M06-365-G93 RF-94: la auditoría se acota a los titulares de las fincas del usuario |
"""INC-M06-365-G93 / TC-M06-G93 con RLS real (rol ``sgpmp_app``): la auditoría financiera de otro titular no se ve.

Antes, el Contador, el Revisor Fiscal y el Auditor consultaban eventos de períodos y activos de titulares con los
que no tenían relación. Ahora cada quien ve los de los titulares de sus fincas; el Administrador, todos."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal as D

import pytest
from sqlalchemy import text

from src.shared.database import declarar_identidad
from src.shared.errors import NotFoundError
from tests.integration.test_control_acceso_f4_aislamiento import como_sgpmp_app  # noqa: F401 (fixture)
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


def _como(db, como_sgpmp_app, id_usuario: int, rol: str) -> None:
    """Rol de la API con la identidad declarada como la declara el request (``como_sistema`` la restaura)."""
    como_sgpmp_app(id_usuario, rol)
    declarar_identidad(db, id_usuario, rol)


def _reconocido(db, m06, uid, nit, dv, especie=2):
    finca = _finca(db, uid, nit=nit, dv=dv)
    activo = _activo(db, finca, uid, especie=especie, origen="compra", costo=D("3000000"))
    _pesaje(db, activo, "450", -timedelta(minutes=10))
    m06.confirmar_reconocimiento().execute(activo, uid)
    periodo = db.execute(text("""SELECT id_periodo_contable FROM modulo6.reconocimientos_iniciales
                                 WHERE id_activo_biologico = :a"""), {"a": activo}).scalar_one()
    return activo, periodo


def test_cada_quien_ve_la_auditoria_de_los_titulares_de_sus_fincas(db_session, m06, contador, crear_usuario_db,
                                                                    como_sgpmp_app):
    uid = contador["id_usuario"]
    otro = crear_usuario_db(id_rol=2)["id_usuario"]  # productor de otro titular
    admin = crear_usuario_db(id_rol=1)["id_usuario"]
    _configurar(m06, uid, 2)
    _matriz(m06, uid)
    _precio(m06, uid, 2, "9500", HOY - timedelta(days=10))
    # Los eventos de A los firma otro usuario: el Contador los ve por la finca asignada, no por haberlos firmado.
    productor_a = crear_usuario_db(id_rol=2)["id_usuario"]
    activo_a, periodo_a = _reconocido(db_session, m06, productor_a, "900123456", "8")
    db_session.execute(text("""INSERT INTO modulo9.usuarios_fincas (id_usuario, id_finca)
        SELECT :u, i.id_finca FROM modulo2.activos_biologicos a JOIN modulo9.infraestructuras i USING (id_infraestructura)
        WHERE a.id_activo_biologico = :a"""), {"u": uid, "a": activo_a})
    activo_b, periodo_b = _reconocido(db_session, m06, otro, "860069804", "2")
    consultar = m06.consultar_auditoria()

    _como(db_session, como_sgpmp_app, uid, "Contador")
    propios = consultar.execute({"tipo_evento": ["RECONOCIMIENTO_INICIAL"]}, 1, 500, legible=False)
    assert propios["total_registros"] >= 1
    assert {e["id_periodo_contable"] for e in propios["eventos"]} == {periodo_a}
    assert consultar.execute({"id_activo_biologico": activo_a}, 1, 500, legible=False)["total_registros"] >= 1
    assert consultar.execute({"tipo_evento": ["PRECIO_REGISTRADO"]}, 1, 500, legible=False)["total_registros"] >= 1
    with pytest.raises(NotFoundError) as periodo_ajeno:
        consultar.execute({"id_periodo_contable": periodo_b}, 1, 500, legible=False)
    assert periodo_ajeno.value.code == "PERIODO_NO_ENCONTRADO"
    with pytest.raises(NotFoundError) as activo_ajeno:
        consultar.execute({"id_activo_biologico": activo_b}, 1, 500, legible=False)
    assert activo_ajeno.value.code == "ACTIVO_NO_ENCONTRADO"
    with pytest.raises(NotFoundError):
        consultar.actores(periodo_b)

    db_session.execute(text("RESET ROLE"))
    _como(db_session, como_sgpmp_app, admin, "Administrador")
    todos = consultar.execute({"tipo_evento": ["RECONOCIMIENTO_INICIAL"]}, 1, 500, legible=False)
    assert {periodo_a, periodo_b} <= {e["id_periodo_contable"] for e in todos["eventos"]}
    assert consultar.execute({"id_periodo_contable": periodo_b}, 1, 500, legible=False)["total_registros"] >= 1
