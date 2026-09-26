"""INC-M02-61-G52 (RF-41, RF-46; frontend #97) — acceso M:N de usuarios a fincas.

Un Veterinario consultaba un activo que el Administrador acababa de crear y
recibía 404: el alcance por finca se resolvía con ``modulo9.fincas.id_usuario``
(1 finca = 1 dueño) y el Veterinario nunca es dueño de la finca que atiende.
Asignársela respondía 409 porque la finca ya tenía dueño.

Requiere ``TEST_DATABASE_URL`` con la migración ``1b9536d4411c`` aplicada.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.configuration.domain.entities.finca import Finca
from src.configuration.domain.value_objects.nombre_finca import NombreFinca
from src.configuration.domain.value_objects.tamano_h import TamanoH
from src.configuration.domain.value_objects.ubicacion_finca import UbicacionFinca
from src.configuration.infrastructure.repositories.finca_repository import SqlAlchemyFincaRepository
from src.shared.alcance_finca_adapter import AlcanceFincaAdapter

pytestmark = pytest.mark.integration

ID_ROL_ADMINISTRADOR = 1


@pytest.fixture(autouse=True)
def _requiere_migracion(db_session: Session) -> None:
    if db_session.execute(text("SELECT to_regclass('modulo9.usuarios_fincas')")).scalar() is None:
        pytest.skip("La base de pruebas no tiene aplicada la migración 1b9536d4411c.")


@pytest.fixture
def rol_sin_alcance_global(db_session: Session) -> int:
    """Rol sin permiso de gestión sobre fincas: el caso del Veterinario."""
    return db_session.execute(
        text("INSERT INTO modulo1.roles (nombre_rol) VALUES (:nombre) RETURNING id_rol"),
        {"nombre": f"IT sin alcance global {uuid.uuid4().hex[:8]}"},
    ).scalar_one()


def _finca_con_propietario(db_session: Session, id_usuario: int) -> int:
    ahora = datetime.now(timezone.utc)
    finca = SqlAlchemyFincaRepository(db_session).guardar(
        Finca.crear(
            # NombreFinca solo admite letras: el sufijo único se escribe con a-p.
            nombre=NombreFinca("Finca IT " + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:10])),
            ubicacion=UbicacionFinca(
                departamento="Huila",
                municipio="Neiva",
                vereda="Centro",
                latitud=Decimal("2.93"),
                longitud=Decimal("-75.28"),
            ),
            tamano_h=TamanoH(Decimal("12.5")),
            id_usuario=id_usuario,
            fecha_creacion=ahora,
            fecha_actualizacion=ahora,
        )
    )
    return finca.id_finca


def _permitidas(db_session: Session, id_usuario: int, id_rol: int) -> list[int]:
    return AlcanceFincaAdapter(db_session).listar_ids_fincas_permitidas(id_usuario, id_rol) or []


def test_registrar_finca_con_propietario_le_concede_acceso(
    db_session, crear_usuario_db, rol_sin_alcance_global,
) -> None:
    productor = crear_usuario_db(id_rol=rol_sin_alcance_global)

    id_finca = _finca_con_propietario(db_session, productor["id_usuario"])

    assert _permitidas(db_session, productor["id_usuario"], rol_sin_alcance_global) == [id_finca]


def test_veterinario_asignado_a_finca_ajena_accede_a_ella(
    client, db_session, crear_usuario_db, crear_auth_headers, rol_sin_alcance_global,
) -> None:
    admin = crear_usuario_db(id_rol=ID_ROL_ADMINISTRADOR)
    productor = crear_usuario_db(id_rol=rol_sin_alcance_global)
    veterinario = crear_usuario_db(id_rol=rol_sin_alcance_global)
    id_finca = _finca_con_propietario(db_session, productor["id_usuario"])
    headers = crear_auth_headers(admin)
    assert _permitidas(db_session, veterinario["id_usuario"], rol_sin_alcance_global) == []

    r = client.put(
        f"/usuarios/{veterinario['id_usuario']}/fincas",
        json={"ids_fincas": [id_finca]},
        headers=headers,
    )

    # Antes: 409 FINCA_YA_ASIGNADA, porque la finca ya tenía dueño.
    assert r.status_code == 200, r.text
    assert _permitidas(db_session, veterinario["id_usuario"], rol_sin_alcance_global) == [id_finca]
    # M:N: el propietario conserva su acceso.
    assert _permitidas(db_session, productor["id_usuario"], rol_sin_alcance_global) == [id_finca]

    detalle = client.get(f"/usuarios/{veterinario['id_usuario']}/detalle", headers=headers)
    assert detalle.status_code == 200, detalle.text
    assert [f["id_finca"] for f in detalle.json()["fincas"]] == [id_finca]

    finca_contexto = db_session.execute(
        text("SELECT id_finca FROM modulo9.vw_rf25_contexto_usuario WHERE id_usuario = :id"),
        {"id": veterinario["id_usuario"]},
    ).scalar()
    assert finca_contexto == id_finca


def test_retirar_la_finca_revoca_el_acceso_sin_tocar_al_propietario(
    client, db_session, crear_usuario_db, crear_auth_headers, rol_sin_alcance_global,
) -> None:
    admin = crear_usuario_db(id_rol=ID_ROL_ADMINISTRADOR)
    productor = crear_usuario_db(id_rol=rol_sin_alcance_global)
    veterinario = crear_usuario_db(id_rol=rol_sin_alcance_global)
    id_finca = _finca_con_propietario(db_session, productor["id_usuario"])
    headers = crear_auth_headers(admin)
    url = f"/usuarios/{veterinario['id_usuario']}/fincas"

    client.put(url, json={"ids_fincas": [id_finca]}, headers=headers)
    r = client.put(url, json={"ids_fincas": []}, headers=headers)

    assert r.status_code == 200, r.text
    assert _permitidas(db_session, veterinario["id_usuario"], rol_sin_alcance_global) == []
    assert _permitidas(db_session, productor["id_usuario"], rol_sin_alcance_global) == [id_finca]
    dueno = db_session.execute(
        text("SELECT id_usuario FROM modulo9.fincas WHERE id_finca = :id"), {"id": id_finca},
    ).scalar()
    assert dueno == productor["id_usuario"]

    # Volver a asignarla reactiva la misma fila, sin duplicar.
    client.put(url, json={"ids_fincas": [id_finca]}, headers=headers)
    filas = db_session.execute(
        text(
            "SELECT es_activo FROM modulo9.usuarios_fincas "
            "WHERE id_usuario = :u AND id_finca = :f"
        ),
        {"u": veterinario["id_usuario"], "f": id_finca},
    ).scalars().all()
    assert filas == [True]


def test_finca_inexistente_responde_404(
    client, crear_usuario_db, crear_auth_headers, rol_sin_alcance_global,
) -> None:
    admin = crear_usuario_db(id_rol=ID_ROL_ADMINISTRADOR)
    veterinario = crear_usuario_db(id_rol=rol_sin_alcance_global)

    r = client.put(
        f"/usuarios/{veterinario['id_usuario']}/fincas",
        json={"ids_fincas": [2_000_000_000]},
        headers=crear_auth_headers(admin),
    )

    assert r.status_code == 404
    assert r.json()["error_code"] == "FINCA_NO_ENCONTRADA"
