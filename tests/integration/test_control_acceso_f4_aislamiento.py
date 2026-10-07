"""F4 del control de acceso por BD: aislamiento por finca con RLS.

Dos usuarios del mismo rol, cada uno con su finca: ninguno ve ni modifica los
activos del otro, ni siquiera con SQL directo. Las consultas corren como
`sgpmp_app` (el rol con el que se conecta la API) con `SET LOCAL ROLE` dentro
de la transacción de la prueba, así que nada queda escrito. Si corrieran como
superusuario pasarían en verde con la base abierta: la prueba lo comprueba
antes de afirmar nada.

También cubre `declarar_identidad`: la identidad sobrevive a los `commit()`
del request (antes se perdía en el primero) sin filtrarse a otra sesión.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from src.shared.database import declarar_identidad

pytestmark = pytest.mark.integration


def _finca_con_activo(db: Session, id_usuario: int) -> tuple[int, int, int]:
    sid = uuid.uuid4().int % (10**9)
    sufijo = "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:10])
    db.execute(
        text(
            "INSERT INTO modulo9.fincas (id_finca, nombre, ubicacion, tamano_h, "
            "fecha_actualizacion, fecha_creacion, es_activo) "
            "VALUES (:id, :nombre, '{}', 10, now(), now(), TRUE)"
        ),
        {"id": sid, "nombre": f"Finca F Cuatro {sufijo}"},
    )
    db.execute(
        text(
            "INSERT INTO modulo9.infraestructuras (id_infraestructura, nombre, id_finca, "
            "superficie, es_activo, tipo) VALUES (:id, :nombre, :id, 100, TRUE, 'Estanque')"
        ),
        {"id": sid, "nombre": f"Estanque F Cuatro {sufijo}"},
    )
    db.execute(
        text(
            "INSERT INTO modulo9.usuarios_fincas (id_usuario, id_finca) VALUES (:u, :f)"
        ),
        {"u": id_usuario, "f": sid},
    )
    db.execute(text("SELECT set_config('app.usuario_id', :u, true)"), {"u": str(id_usuario)})
    id_activo = db.execute(
        text(
            """
            INSERT INTO modulo2.activos_biologicos (
                id_especie, identificador, id_infraestructura, tipo, fecha_inicio_ciclo,
                id_estado, descripcion, origen_financiero, costo_adquisicion,
                atributos_dinamicos, id_usuario, fecha_creacion, soporte_documental,
                detalles_procedencia
            ) VALUES (
                2, :identificador, :infra, 'INDIVIDUAL', current_date, 1, 'Fixture F4',
                'compra', 100, '{}', :usuario, now(), 'doc', ''
            )
            RETURNING id_activo_biologico
            """
        ),
        {"identificador": f"F4-{uuid.uuid4().hex[:12]}", "infra": sid, "usuario": id_usuario},
    ).scalar_one()
    return sid, sid, id_activo


@pytest.fixture
def como_sgpmp_app(db_session: Session):
    """Pasa la transacción de la prueba al rol de la API con la identidad dada."""
    if db_session.execute(text("SELECT to_regrole('sgpmp_app')")).scalar() is None:
        pytest.skip("La base de pruebas no tiene el rol sgpmp_app (F1).")
    if not db_session.execute(
        text("SELECT pg_has_role(current_user, 'sgpmp_app', 'MEMBER')")
    ).scalar():
        pytest.skip("El usuario de TEST_DATABASE_URL no puede hacer SET ROLE sgpmp_app.")

    def cambiar(id_usuario: int | None) -> None:
        db_session.execute(text("SET LOCAL ROLE sgpmp_app"))
        db_session.execute(
            text(
                "SELECT set_config('app.current_user_id', :u, true), "
                "set_config('app.current_role', 'Productor', true)"
            ),
            {"u": "" if id_usuario is None else str(id_usuario)},
        )
        # Regla 4 del plan: si esto fuera superusuario o BYPASSRLS, todo lo
        # que sigue pasaría en verde con la base abierta.
        fila = db_session.execute(
            text("SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).one()
        assert fila == ("sgpmp_app", False, False)

    # `SET LOCAL ROLE` se deshace con el rollback de la transacción de la prueba.
    return cambiar


def test_cada_usuario_ve_solo_los_activos_de_su_finca(
    db_session, crear_usuario_db, como_sgpmp_app,
) -> None:
    a = crear_usuario_db(id_rol=2)["id_usuario"]
    b = crear_usuario_db(id_rol=2)["id_usuario"]
    finca_a, infra_a, activo_a = _finca_con_activo(db_session, a)
    finca_b, infra_b, activo_b = _finca_con_activo(db_session, b)
    ambos = {"ids": [activo_a, activo_b]}

    como_sgpmp_app(a)
    assert db_session.execute(
        text("SELECT id_activo_biologico FROM modulo2.activos_biologicos WHERE id_activo_biologico = ANY(:ids)"),
        ambos,
    ).scalars().all() == [activo_a]
    assert db_session.execute(
        text("SELECT id_infraestructura FROM modulo9.infraestructuras WHERE id_infraestructura = ANY(:ids)"),
        {"ids": [infra_a, infra_b]},
    ).scalars().all() == [infra_a]
    assert db_session.execute(
        text("SELECT id_finca FROM modulo9.fincas WHERE id_finca = ANY(:ids)"),
        {"ids": [finca_a, finca_b]},
    ).scalars().all() == [finca_a]

    como_sgpmp_app(b)
    assert db_session.execute(
        text("SELECT id_activo_biologico FROM modulo2.activos_biologicos WHERE id_activo_biologico = ANY(:ids)"),
        ambos,
    ).scalars().all() == [activo_b]


def test_no_puede_modificar_ni_llevarse_activos_ajenos(
    db_session, crear_usuario_db, como_sgpmp_app,
) -> None:
    a = crear_usuario_db(id_rol=2)["id_usuario"]
    b = crear_usuario_db(id_rol=2)["id_usuario"]
    _, _, activo_a = _finca_con_activo(db_session, a)
    _, infra_b, activo_b = _finca_con_activo(db_session, b)

    como_sgpmp_app(a)
    editadas = db_session.execute(
        text("UPDATE modulo2.activos_biologicos SET descripcion = 'ajeno' WHERE id_activo_biologico = :id"),
        {"id": activo_b},
    ).rowcount
    assert editadas == 0

    with pytest.raises(DBAPIError, match="row-level security"):
        with db_session.begin_nested():
            db_session.execute(
                text("UPDATE modulo2.activos_biologicos SET id_infraestructura = :infra WHERE id_activo_biologico = :id"),
                {"infra": infra_b, "id": activo_a},
            )


def test_las_vistas_tambien_filtran(db_session, crear_usuario_db, como_sgpmp_app) -> None:
    # Una vista se evalúa con los permisos de su dueño. Si el dueño es
    # superusuario, o es el dueño de la tabla y la tabla no tiene FORCE, la
    # vista devuelve las filas de todas las fincas.
    a = crear_usuario_db(id_rol=2)["id_usuario"]
    b = crear_usuario_db(id_rol=2)["id_usuario"]
    _, _, activo_a = _finca_con_activo(db_session, a)
    _, _, activo_b = _finca_con_activo(db_session, b)

    como_sgpmp_app(a)
    assert db_session.execute(
        text(
            "SELECT id_activo_biologico FROM modulo2.vw_rf48_infraestructura_actual_activo "
            "WHERE id_activo_biologico = ANY(:ids)"
        ),
        {"ids": [activo_a, activo_b]},
    ).scalars().all() == [activo_a]


def test_sin_identidad_no_ve_nada(db_session, crear_usuario_db, como_sgpmp_app) -> None:
    a = crear_usuario_db(id_rol=2)["id_usuario"]
    _, _, activo_a = _finca_con_activo(db_session, a)

    como_sgpmp_app(None)
    assert db_session.execute(
        text("SELECT count(*) FROM modulo2.activos_biologicos WHERE id_activo_biologico = :id"),
        {"id": activo_a},
    ).scalar_one() == 0


def test_identidad_sobrevive_al_commit_sin_filtrarse(integration_engine: Engine) -> None:
    def leer(db: Session) -> tuple:
        return tuple(db.execute(
            text(
                "SELECT current_setting('app.current_user_id', true), "
                "current_setting('app.current_role', true), "
                "current_setting('app.usuario_id', true)"
            )
        ).one())

    with Session(integration_engine) as db:
        declarar_identidad(db, 4242, "Productor")
        assert leer(db) == ("4242", "Productor", "4242")
        db.commit()
        assert leer(db) == ("4242", "Productor", "4242")
        db.rollback()
        assert leer(db) == ("4242", "Productor", "4242")

    with Session(integration_engine) as otra:
        assert leer(otra)[0] in (None, "")
