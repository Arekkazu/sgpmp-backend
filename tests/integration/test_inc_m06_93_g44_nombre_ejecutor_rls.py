# | Fecha      | Nombre   | Que se hizo                                                                                  |
# |------------|----------|----------------------------------------------------------------------------------------------|
# | 2026-11-15 | Arekkazu | INC-M06-93-G44 RF-87 FA-5: el 409 nombra a quien cerró aunque la RLS de usuarios lo oculte |
"""INC-M06-93-G44 (#1123), RF-87 FA-5: cerrar un período ya cerrado responde 409 con la fecha y quien lo cerró.

El nombre salía de un join con ``modulo1.usuarios``, cuya RLS solo deja ver la propia fila a quien no administra
usuarios: si el período lo cerró otro Contador, el 409 salía sin «por …». La prueba corre como ``sgpmp_app`` (el rol
de la API, sujeto a RLS) con la identidad del segundo Contador."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal as D

import pytest
from sqlalchemy import text

from src.shared.database import declarar_identidad
from src.shared.errors import AppError
from tests.integration.test_m06_flujo_nic41_integration import (  # noqa: F401 (fixtures)
    HOY, NIT, _activo, _configurar, _escalar, _finca, _matriz, _pesaje, _precio, m06,
)

pytestmark = pytest.mark.integration


def test_periodo_cerrado_por_otro_contador_responde_409_con_su_nombre(db_session, m06, crear_usuario_db):
    if not _escalar(db_session, "SELECT to_regrole('sgpmp_app') IS NOT NULL AND pg_has_role(current_user, 'sgpmp_app', 'MEMBER')"):
        pytest.skip("La base de pruebas no permite SET ROLE sgpmp_app.")
    quien_cerro = crear_usuario_db(id_rol=5, nombre="Camila", apellidos="Cierre")["id_usuario"]
    otro = crear_usuario_db(id_rol=5)["id_usuario"]
    especie = 2
    finca = _finca(db_session, quien_cerro)
    db_session.execute(text("INSERT INTO modulo9.usuarios_fincas (id_usuario, id_finca) VALUES (:u, :f)"), {"u": otro, "f": finca})
    _configurar(m06, quien_cerro, especie)
    _matriz(m06, quien_cerro)
    activo = _activo(db_session, finca, quien_cerro, especie=especie, origen="compra", costo=D("3000000"))
    _pesaje(db_session, activo, "400", -timedelta(minutes=5))
    _precio(m06, quien_cerro, especie, "8000", HOY - timedelta(days=10))
    m06.confirmar_reconocimiento().execute(activo, quien_cerro)
    periodo = m06.periodos.que_contiene(NIT, HOY).id_periodo_contable
    m06.cierre().execute(periodo, quien_cerro, autorizar_exclusiones=True)

    db_session.execute(text("SET LOCAL ROLE sgpmp_app"))
    declarar_identidad(db_session, otro, None)
    assert not _escalar(db_session, "SELECT count(*) FROM modulo1.usuarios WHERE id_usuario = :u", u=quien_cerro)

    with pytest.raises(AppError) as cerrado:
        m06.cierre().execute(periodo, otro)
    assert cerrado.value.code == "PERIODO_CERRADO"
    assert "por Camila Cierre" in cerrado.value.message
    assert m06.periodos.ultimas_ejecuciones([periodo])[periodo]["nombre_usuario_ejecutor"] == "Camila Cierre"
