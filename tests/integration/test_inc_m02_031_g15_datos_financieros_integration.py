"""Integración de TC-M02-031-G15 contra PostgreSQL con rollback exterior."""
from __future__ import annotations

import random
import string
import uuid
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

_JWT_SECRET_INTEGRACION = 'sgpmp-integration-tests-only'


def _id_temporal() -> int:
    return uuid.uuid4().int % (10**9)


def _nombre_temporal(prefijo: str) -> str:
    sufijo = ''.join(random.choices(string.ascii_letters, k=12))
    return f'{prefijo} {sufijo}'


@pytest.fixture(autouse=True)
def catalogo_y_permiso_financiero(db_session: Session) -> None:
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.estados_activos_biologicos
                (id_estado_activo_biologico, nombre)
            VALUES (1, 'ACTIVO'), (2, 'INACTIVO'), (3, 'EN_TRATAMIENTO'),
                   (4, 'AISLADO'), (5, 'CERRADO'), (6, 'BAJA')
            ON CONFLICT (id_estado_activo_biologico) DO NOTHING
            """
        )
    )
    db_session.execute(
        text(
            """
            SELECT setval(
                'modulo1.recursos_id_recurso_seq',
                (SELECT MAX(id_recurso) FROM modulo1.recursos),
                true
            )
            """
        )
    )
    db_session.execute(
        text(
            """
            INSERT INTO modulo1.recursos
                (nombre_recurso, descripcion, es_proceso_especial)
            VALUES (
                'datos_financieros_activo',
                'Seed transaccional TC-M02-031-G15',
                FALSE
            )
            ON CONFLICT (nombre_recurso) DO NOTHING
            """
        )
    )
    id_recurso = db_session.execute(
        text(
            """
            SELECT id_recurso FROM modulo1.recursos
            WHERE nombre_recurso = 'datos_financieros_activo'
            """
        )
    ).scalar_one()
    db_session.execute(
        text(
            """
            INSERT INTO modulo1.permisos (
                nombre, descripcion, id_rol, id_recurso, id_accion, es_activo
            ) VALUES (
                'prod_leer_datos_financieros_activo',
                'Seed transaccional TC-M02-031-G15',
                2, :id_recurso, 2, TRUE
            )
            ON CONFLICT (id_rol, id_recurso, id_accion) DO UPDATE
                SET nombre = EXCLUDED.nombre,
                    descripcion = EXCLUDED.descripcion,
                    es_activo = TRUE
            """
        ),
        {'id_recurso': id_recurso},
    )
    db_session.flush()


def _crear_activo(
    db_session: Session,
    *,
    id_usuario_dueno: int,
    usuarios_con_acceso: list[int],
) -> int:
    sid = _id_temporal()
    db_session.execute(text('SET LOCAL app.usuario_id = :uid'), {'uid': id_usuario_dueno})
    db_session.execute(
        text(
            """
            INSERT INTO modulo9.fincas (
                id_finca, nombre, ubicacion, tamano_h, fecha_actualizacion,
                fecha_creacion, es_activo, id_usuario
            ) VALUES (:id, :nombre, '{}', 10, now(), now(), true, :id_usuario)
            """
        ),
        {
            'id': sid,
            'nombre': _nombre_temporal('Finca Finanzas RF34'),
            'id_usuario': id_usuario_dueno,
        },
    )
    for id_usuario in usuarios_con_acceso:
        db_session.execute(
            text(
                """
                INSERT INTO modulo9.usuarios_fincas (id_usuario, id_finca)
                VALUES (:id_usuario, :id_finca)
                """
            ),
            {'id_usuario': id_usuario, 'id_finca': sid},
        )
    db_session.execute(
        text(
            """
            INSERT INTO modulo9.infraestructuras (
                id_infraestructura, nombre, id_finca, superficie, es_activo, tipo
            ) VALUES (:id, :nombre, :id, 100, true, 'Corral')
            """
        ),
        {'id': sid, 'nombre': _nombre_temporal('Infra Finanzas RF34')},
    )
    id_activo = _id_temporal()
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.activos_biologicos (
                id_activo_biologico, id_especie, identificador,
                id_infraestructura, tipo, fecha_inicio_ciclo, id_estado,
                descripcion, origen_financiero, costo_adquisicion,
                atributos_dinamicos, id_usuario, fecha_creacion,
                soporte_documental, detalles_procedencia
            ) VALUES (
                :id_activo, 2, :identificador, :id_infra, 'INDIVIDUAL',
                current_date, 1, 'Integración TC-M02-031-G15', 'COMPRA',
                1500000, '{}', :id_usuario, now(),
                'soporte_TC-M02-031.pdf', 'Compra documentada'
            )
            """
        ),
        {
            'id_activo': id_activo,
            'identificador': f'G15-{id_activo}',
            'id_infra': sid,
            'id_usuario': id_usuario_dueno,
        },
    )
    db_session.flush()
    return id_activo


@pytest.fixture
def m02_client(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    from src.biological_assets.infrastructure.routers.activo_biologico_router import (
        router as activo_router,
    )
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, '_SECRET_KEY', _JWT_SECRET_INTEGRACION)
    monkeypatch.setattr(jwt_module, '_EXPIRE_HOURS', 8)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(activo_router)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_endpoint_enmascara_para_ingeniero_y_expone_para_productor(
    m02_client: TestClient,
    db_session: Session,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    ingeniero = crear_usuario_db(id_rol=4, estado=2)
    productor = crear_usuario_db(id_rol=2, estado=2)
    id_activo = _crear_activo(
        db_session,
        id_usuario_dueno=productor['id_usuario'],
        usuarios_con_acceso=[ingeniero['id_usuario'], productor['id_usuario']],
    )

    respuesta_ingeniero = m02_client.get(
        f'/activos-biologicos/{id_activo}',
        headers=crear_auth_headers(ingeniero),
    )
    respuesta_productor = m02_client.get(
        f'/activos-biologicos/{id_activo}',
        headers=crear_auth_headers(productor),
    )

    assert respuesta_ingeniero.status_code == 200
    assert respuesta_ingeniero.json()['costo_adquisicion'] is None
    assert respuesta_ingeniero.json()['soporte_documental'] is None

    assert respuesta_productor.status_code == 200
    assert respuesta_productor.json()['costo_adquisicion'] == '1500000.0000'
    assert respuesta_productor.json()['soporte_documental'] == 'soporte_TC-M02-031.pdf'
