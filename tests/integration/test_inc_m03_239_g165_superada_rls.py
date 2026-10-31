# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-10-31 | Claude | INC-M03-239-G165 RF-62: VIGENTE→SUPERADA con el rol de la API (RLS) |
"""INC-M03-239-G165 (#874): la segunda evaluación manual y la reevaluación por lote
respondían 500 con el rol de la API porque `telemetria_calidad` no tenía política UPDATE.

Fuerza ``TEST_ROL_APP=sgpmp_app``: con superusuario RLS no aplica y el defecto no se ve.
"""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from src.shared.database import declarar_identidad

from tests.integration.test_inc_m03_104_g165_motor_calidad import equipo_g165, insertar_serie, rutas_g165  # noqa: F401

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _rol_api(monkeypatch):
    monkeypatch.setenv('TEST_ROL_APP', 'sgpmp_app')


def _estados(db, id_telemetria):
    return db.execute(text('''SELECT estado_evaluacion, count(*) FROM modulo3.telemetria_calidad
        WHERE id_telemetria = :t GROUP BY estado_evaluacion'''), {'t': id_telemetria}).all()


def test_segunda_y_tercera_evaluacion_superan_la_vigente(client, db_session, equipo_g165):
    e = equipo_g165
    lectura = insertar_serie(db_session, e, [19.8, 20.2] * 10, 20)

    ids = []
    for _ in range(3):
        r = client.post(f'/iot/calidad/{lectura}/evaluar', headers=e['headers'])
        assert r.status_code == 201, r.text
        ids.append(r.json()['id_evaluacion'])

    assert dict(_estados(db_session, lectura)) == {'VIGENTE': 1, 'SUPERADA': 2}
    vigente = db_session.execute(text('''SELECT id_evaluacion::text, id_evaluacion_superada::text
        FROM modulo3.telemetria_calidad WHERE id_telemetria = :t AND estado_evaluacion = 'VIGENTE' '''),
        {'t': lectura}).one()
    assert vigente == (ids[2], ids[1])


def test_la_politica_solo_permite_vigente_a_superada(client, db_session, equipo_g165):
    e = equipo_g165
    lectura = insertar_serie(db_session, e, [19.8, 20.2] * 10, 20)
    for _ in range(2):
        assert client.post(f'/iot/calidad/{lectura}/evaluar', headers=e['headers']).status_code == 201
    uid, rol = db_session.execute(text(
        'SELECT u.id_usuario, r.nombre_rol FROM modulo1.usuarios u JOIN modulo1.roles r USING (id_rol) '
        'WHERE r.id_rol = 1 ORDER BY u.id_usuario DESC LIMIT 1')).one()

    def actualizar(sql: str) -> int:
        declarar_identidad(db_session, uid, rol)
        db_session.execute(text('SET LOCAL ROLE sgpmp_app'))
        try:
            return db_session.execute(text(sql), {'t': lectura}).rowcount
        finally:
            db_session.execute(text('RESET ROLE'))

    # Una SUPERADA no vuelve a VIGENTE (USING exige VIGENTE).
    assert actualizar("UPDATE modulo3.telemetria_calidad SET estado_evaluacion = 'VIGENTE' "
                      "WHERE id_telemetria = :t AND estado_evaluacion = 'SUPERADA'") == 0
    # La VIGENTE solo puede quedar SUPERADA (WITH CHECK).
    with pytest.raises(DBAPIError):
        actualizar("UPDATE modulo3.telemetria_calidad SET motivo_reevaluacion = 'x' "
                   "WHERE id_telemetria = :t AND estado_evaluacion = 'VIGENTE'")
