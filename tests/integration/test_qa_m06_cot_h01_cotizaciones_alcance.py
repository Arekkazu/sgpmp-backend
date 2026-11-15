# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-15 | Arekkazu | QA-M06 CU-COT H-01 RF-COT: el Contador solo ve las cotizaciones de los titulares de sus fincas |
"""CU-COT H-01 (QA M06, 15-11) con RLS real (rol ``sgpmp_app``): Datos → Cotizaciones mostraba al Contador las
cotizaciones de otros titulares, porque la RLS da visión completa a quien opera el cierre. Ahora cada quien ve
las de los titulares de sus fincas; el Administrador protegido, todas."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal as D

from sqlalchemy import text

from tests.integration.test_control_acceso_f4_aislamiento import como_sgpmp_app  # noqa: F401 (fixture)
from tests.integration.test_inc_m06_365_g93_auditoria_alcance import _como, _reconocido
from tests.integration.test_m06_flujo_nic41_integration import (  # noqa: F401 (fixtures)
    HOY,
    _configurar,
    _matriz,
    _precio,
    contador,
    m06,
)


def test_cada_quien_ve_las_cotizaciones_de_los_titulares_de_sus_fincas(db_session, m06, contador, crear_usuario_db,
                                                                       como_sgpmp_app):
    uid = contador["id_usuario"]
    admin = crear_usuario_db(id_rol=1)["id_usuario"]
    _configurar(m06, uid, 2)
    _matriz(m06, uid)
    _precio(m06, uid, 2, "9500", HOY - timedelta(days=10))
    activo_a, _ = _reconocido(db_session, m06, crear_usuario_db(id_rol=2)["id_usuario"], "900123456", "8")
    activo_b, _ = _reconocido(db_session, m06, crear_usuario_db(id_rol=2)["id_usuario"], "860069804", "2")
    db_session.execute(text("""INSERT INTO modulo9.usuarios_fincas (id_usuario, id_finca)
        SELECT :u, i.id_finca FROM modulo2.activos_biologicos a JOIN modulo9.infraestructuras i USING (id_infraestructura)
        WHERE a.id_activo_biologico = :a"""), {"u": uid, "a": activo_a})
    cot_a = m06.registrar_cotizacion().execute([activo_a], D("3500000"), None, None, uid)["id_cotizacion"]
    cot_b = m06.registrar_cotizacion().execute([activo_b], D("3600000"), None, None, uid)["id_cotizacion"]

    _como(db_session, como_sgpmp_app, uid, "Contador")
    assert {c["id_cotizacion"] for c in m06.cotizaciones.listar({})} == {cot_a}
    assert m06.cotizaciones.obtener(cot_b) is None

    db_session.execute(text("RESET ROLE"))
    _como(db_session, como_sgpmp_app, admin, "Administrador")
    assert {cot_a, cot_b} <= {c["id_cotizacion"] for c in m06.cotizaciones.listar({})}
