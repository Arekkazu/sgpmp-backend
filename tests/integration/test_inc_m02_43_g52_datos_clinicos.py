"""INC-M02-43-G52 / issue #413: GET /activos-biologicos/{id}/eventos devolvía
el historial sanitario completo (diagnóstico, medicamento, dosis) a
cualquier usuario con el permiso genérico de lectura sobre activos_biologicos
(id_recurso=29, accion=2), sin distinguir autorización clínica del rol.

RF-46 (Consulta de Historial) reconoce como actores de la categoría SANITARIO
a Productor, Veterinario y Administrador -- Ingeniero de Campo no está entre
ellos. La migración 4f453b6d2b90 agrega el recurso `datos_clinicos_activo`
(id_recurso=59) con permiso de lectura solo para esos tres roles.

Esta prueba siembra el activo, el evento sanitario y el permiso nuevo dentro
de la transacción de rollback del test, y golpea el endpoint real vía
`TestClient`: el Ingeniero de Campo debe seguir viendo el evento (RF-39 sí lo
autoriza a leer el historial general), pero con los campos clínicos en null;
el Veterinario debe verlos completos.
"""
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

_JWT_SECRET_INTEGRACION = "sgpmp-integration-tests-only"  # igual que conftest


def _id_temporal() -> int:
    return uuid.uuid4().int % (10**9)


def _nombre_temporal(prefijo: str) -> str:
    sufijo = "".join(random.choices(string.ascii_letters, k=12))
    return f"{prefijo} {sufijo}"


@pytest.fixture(autouse=True)
def catalogo_estados_activo(db_session: Session) -> None:
    """`pruebas-integrador` puede no traer precargado el catálogo de estados
    (ver `scripts/provisionar_pruebas.sh`); `trg_fn_activo_biologico_estado_inicial`
    busca el nombre 'ACTIVO' ahí al insertar un activo, así que sin esta fila
    el fixture de contexto de este archivo no puede crear el activo de prueba.
    Datos de catálogo puros, sin relación con lo que se está probando aquí.
    """
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.estados_activos_biologicos (id_estado_activo_biologico, nombre)
            VALUES (1, 'ACTIVO'), (2, 'INACTIVO'), (3, 'EN_TRATAMIENTO'),
                   (4, 'AISLADO'), (5, 'CERRADO'), (6, 'BAJA')
            ON CONFLICT (id_estado_activo_biologico) DO NOTHING
            """
        )
    )
    db_session.flush()


@pytest.fixture(autouse=True)
def permiso_datos_clinicos(db_session: Session) -> None:
    """Representa el estado posterior a la migración 4f453b6d2b90 dentro del rollback del test."""
    db_session.execute(
        text(
            """
            INSERT INTO modulo1.recursos (id_recurso, nombre_recurso, descripcion)
            VALUES (59, 'datos_clinicos_activo', 'Campos clinicos del historial sanitario (RF-41/RF-46)')
            ON CONFLICT (id_recurso) DO NOTHING
            """
        )
    )
    for id_rol, nombre in (
        (1, "admin_leer_datos_clinicos_activo"),
        (3, "vet_leer_datos_clinicos_activo"),
        (2, "prod_leer_datos_clinicos_activo"),
    ):
        db_session.execute(
            text(
                """
                INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
                VALUES (:nombre, 'seed de prueba', :id_rol, 59, 2, TRUE)
                ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING
                """
            ),
            {"nombre": nombre, "id_rol": id_rol},
        )
    db_session.flush()


def _crear_contexto_con_evento_sanitario(db_session: Session, id_usuario_dueno: int) -> int:
    """Veterinario e Ingeniero de Campo no son 'globales' en AlcanceFincaAdapter
    (solo Admin tiene actualizar/desactivar sobre el recurso fincas): quedan
    restringidos a sus fincas en `modulo9.usuarios_fincas` (INC-M02-61-G52). El
    usuario que consulta necesita acceso a la finca del activo de prueba, o el
    activo le sale invisible (404) antes de llegar a la redacción que se prueba.
    """
    tipo_infraestructura = "Corral"
    sid = _id_temporal()
    db_session.execute(text("SET LOCAL app.usuario_id = :uid"), {"uid": id_usuario_dueno})
    db_session.execute(
        text(
            """
            INSERT INTO modulo9.fincas (
                id_finca, nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, es_activo, id_usuario
            ) VALUES (:id, :nombre, '{}', 10, now(), now(), true, :id_usuario)
            """
        ),
        {"id": sid, "nombre": _nombre_temporal("Finca Prueba Clinica"), "id_usuario": id_usuario_dueno},
    )
    db_session.execute(
        text("INSERT INTO modulo9.usuarios_fincas (id_usuario, id_finca) VALUES (:u, :f)"),
        {"u": id_usuario_dueno, "f": sid},
    )
    db_session.execute(
        text(
            """
            INSERT INTO modulo9.infraestructuras (
                id_infraestructura, nombre, id_finca, superficie, es_activo, tipo
            ) VALUES (:id, :nombre, :id, 100, true, :tipo)
            """
        ),
        {"id": sid, "nombre": _nombre_temporal("Infra Prueba Clinica"), "tipo": tipo_infraestructura},
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
                current_date, 1, 'Integración INC-M02-43-G52', 'compra', 100,
                '{}', :id_usuario, now() - interval '1 hour', 'doc', ''
            )
            """
        ),
        {"id_activo": id_activo, "identificador": f"G52-{id_activo}", "id_infra": sid, "id_usuario": id_usuario_dueno},
    )
    # RF-41: TRATAMIENTO/VACUNACION exigen un DIAGNOSTICO previo
    # (trg_fn_evento_sanitario_secuencia) -- dos eventos encadenados,
    # cronologia real de un caso clinico.
    id_evento_diagnostico = _id_temporal()
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.eventos_activos (id_eventos, id_activo_biologico, fecha, id_usuario)
            VALUES (:id_evento, :id_activo, now() - interval '30 minutes', :id_usuario)
            """
        ),
        {"id_evento": id_evento_diagnostico, "id_activo": id_activo, "id_usuario": id_usuario_dueno},
    )
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.eventos_sanitarios (id_evento, tipo, diagnostico)
            VALUES (:id_evento, 'DIAGNOSTICO', 'Mastitis clínica')
            """
        ),
        {"id_evento": id_evento_diagnostico},
    )

    id_evento_tratamiento = _id_temporal()
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.eventos_activos (id_eventos, id_activo_biologico, fecha, id_usuario)
            VALUES (:id_evento, :id_activo, now(), :id_usuario)
            """
        ),
        {"id_evento": id_evento_tratamiento, "id_activo": id_activo, "id_usuario": id_usuario_dueno},
    )
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.eventos_sanitarios (id_evento, tipo, medicamento, dosis, unidad_dosis, frecuencia, duracion, observaciones)
            VALUES (:id_evento, 'TRATAMIENTO', 'Penicilina', 5, 'ml', 2, 7, 'Aislar del resto del lote')
            """
        ),
        {"id_evento": id_evento_tratamiento},
    )
    db_session.flush()
    return id_activo


@pytest.fixture
def m02_client(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    from src.biological_assets.infrastructure.routers.activo_biologico_router import router as activo_router
    from src.identity_access.infrastructure.routers.usuarios_routers import router as usuarios_router  # noqa: F401
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", _JWT_SECRET_INTEGRACION)
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(activo_router)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(
        app,
        client=("sgpmp-integration-tests", 50000),
        raise_server_exceptions=False,
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_ingeniero_de_campo_ve_el_evento_pero_sin_datos_clinicos(
    m02_client, db_session, crear_usuario_db, crear_auth_headers,
) -> None:
    ingeniero = crear_usuario_db(id_rol=4, estado=2)
    id_activo = _crear_contexto_con_evento_sanitario(db_session, ingeniero["id_usuario"])

    respuesta = m02_client.get(
        f"/activos-biologicos/{id_activo}/eventos",
        headers=crear_auth_headers(ingeniero),
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["total"] == 2
    eventos_sanitarios = [e["sanitario"] for e in cuerpo["eventos"]]
    tratamiento = next(s for s in eventos_sanitarios if s["tipo"] == "TRATAMIENTO")
    diagnostico_evt = next(s for s in eventos_sanitarios if s["tipo"] == "DIAGNOSTICO")

    # El tipo (categoría del evento) se conserva; el detalle clínico no.
    assert diagnostico_evt["diagnostico"] is None
    assert tratamiento["medicamento"] is None
    assert tratamiento["dosis"] is None
    assert tratamiento["unidad_dosis"] is None
    assert tratamiento["frecuencia"] is None
    assert tratamiento["duracion"] is None
    assert tratamiento["observaciones"] is None


def test_veterinario_ve_el_evento_con_datos_clinicos_completos(
    m02_client, db_session, crear_usuario_db, crear_auth_headers,
) -> None:
    veterinario = crear_usuario_db(id_rol=3, estado=2)
    id_activo = _crear_contexto_con_evento_sanitario(db_session, veterinario["id_usuario"])

    respuesta = m02_client.get(
        f"/activos-biologicos/{id_activo}/eventos",
        headers=crear_auth_headers(veterinario),
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["total"] == 2
    eventos_sanitarios = [e["sanitario"] for e in cuerpo["eventos"]]
    tratamiento = next(s for s in eventos_sanitarios if s["tipo"] == "TRATAMIENTO")
    diagnostico_evt = next(s for s in eventos_sanitarios if s["tipo"] == "DIAGNOSTICO")

    assert diagnostico_evt["diagnostico"] == "Mastitis clínica"
    assert tratamiento["medicamento"] == "Penicilina"
    assert tratamiento["dosis"] == "5.00"
    assert tratamiento["unidad_dosis"] == "ml"
    assert tratamiento["observaciones"] == "Aislar del resto del lote"
