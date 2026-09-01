"""Infraestructura compartida para pruebas de integración con PostgreSQL.

Cada prueba usa una conexión propia con una transacción exterior. Los commits
realizados por los casos de uso se convierten en savepoints y al finalizar se
revierte la transacción exterior, por lo que la base no conserva datos de prueba.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import Callable, Generator
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import bcrypt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
JWT_SECRET_INTEGRACION = "sgpmp-integration-tests-only"
BASES_PRUEBA_PERMITIDAS = {"pruebas", "pruebas-integrador"}
TABLAS_MODULO1_REQUERIDAS = {
    "acciones",
    "cuentas_usuarios",
    "eventos",
    "notificaciones",
    "notificaciones_canal",
    "permisos",
    "recursos",
    "roles",
    "sesiones",
    "tipos_eventos",
    "tokens",
    "usuarios",
}


def _validar_url_pruebas(url: str) -> None:
    parsed = make_url(url)
    nombre = (parsed.database or "").lower()
    if not parsed.drivername.startswith("postgresql"):
        pytest.fail("TEST_DATABASE_URL debe apuntar a PostgreSQL.")
    if "test" not in nombre and nombre not in BASES_PRUEBA_PERMITIDAS:
        pytest.fail(
            "Protección de seguridad: la base indicada por TEST_DATABASE_URL "
            "debe contener 'test' o pertenecer a la lista explícita de bases "
            "de integración permitidas."
        )


@pytest.fixture(scope="session")
def integration_engine() -> Generator[Engine, None, None]:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Define TEST_DATABASE_URL para ejecutar las pruebas de integración.")

    _validar_url_pruebas(url)
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            nombre_real = connection.execute(text("select current_database()")).scalar_one()
            if nombre_real.lower() != (make_url(url).database or "").lower():
                pytest.fail("La conexión no abrió la base indicada por TEST_DATABASE_URL.")

        tablas = set(inspect(engine).get_table_names(schema="modulo1"))
        faltantes = TABLAS_MODULO1_REQUERIDAS - tablas
        if faltantes:
            pytest.fail(
                "La base de integración no contiene el esquema modulo1 requerido: "
                + ", ".join(sorted(faltantes))
            )
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(integration_engine: Engine) -> Generator[Session, None, None]:
    connection = integration_engine.connect()
    outer_transaction = connection.begin()
    session = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()
        if outer_transaction.is_active:
            outer_transaction.rollback()
        connection.close()


def _importar_modelos_identity_access() -> None:
    """Registra todas las relaciones ORM del módulo antes de atender requests."""
    from src.identity_access.infrastructure.models import acciones_model  # noqa: F401
    from src.identity_access.infrastructure.models import cuenta_usuarios_model  # noqa: F401
    from src.identity_access.infrastructure.models import dispositivos_fcm_model  # noqa: F401
    from src.identity_access.infrastructure.models import estados_cuentas_model  # noqa: F401
    from src.identity_access.infrastructure.models import eventos_model  # noqa: F401
    from src.identity_access.infrastructure.models import gestiones_cuenta_model  # noqa: F401
    from src.identity_access.infrastructure.models import notificaciones_canal_model  # noqa: F401
    from src.identity_access.infrastructure.models import notificaciones_model  # noqa: F401
    from src.identity_access.infrastructure.models import permisos_model  # noqa: F401
    from src.identity_access.infrastructure.models import recursos_model  # noqa: F401
    from src.identity_access.infrastructure.models import roles_model  # noqa: F401
    from src.identity_access.infrastructure.models import sesiones_model  # noqa: F401
    from src.identity_access.infrastructure.models import tipo_eventos_model  # noqa: F401
    from src.identity_access.infrastructure.models import tokens_model  # noqa: F401
    from src.identity_access.infrastructure.models import usuarios_model  # noqa: F401


@pytest.fixture(scope="session")
def integration_app() -> FastAPI:
    _importar_modelos_identity_access()

    from src.identity_access.infrastructure.routers.auditoria_routers import (
        router as auditoria_router,
    )
    from src.identity_access.infrastructure.routers.contrasena_routers import (
        router as contrasena_router,
    )
    from src.identity_access.infrastructure.routers.sesiones_routers import (
        router as sesiones_router,
    )
    from src.identity_access.infrastructure.routers.notificaciones_routers import (
        router as notificaciones_router,
    )
    from src.identity_access.infrastructure.routers.roles_routers import (
        router as roles_router,
    )
    from src.identity_access.infrastructure.routers.usuarios_routers import (
        router as usuarios_router,
    )
    from src.shared.error_handlers import register_error_handlers
    from src.shared.middlewares import RequestContextMiddleware

    app = FastAPI()
    # Igual que en `main.py`: sin este middleware la auditoría no recibe IP ni
    # user-agent, y las pruebas dejarían de reflejar el comportamiento real.
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)
    app.include_router(usuarios_router)
    app.include_router(contrasena_router)
    app.include_router(auditoria_router)
    app.include_router(sesiones_router)
    app.include_router(notificaciones_router)
    app.include_router(roles_router)
    return app


@pytest.fixture
def client(
    integration_app: FastAPI,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    from src.identity_access.infrastructure.adapters import (
        correo_activacion_background_adapter,
    )
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", JWT_SECRET_INTEGRACION)
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    def crear_sesion_background() -> Session:
        """Crea una sesión aislada sobre la transacción exterior de la prueba."""
        return Session(
            bind=db_session.connection(),
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

    integration_app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(
        correo_activacion_background_adapter,
        "SessionLocal",
        crear_sesion_background,
    )
    with TestClient(
        integration_app,
        client=("sgpmp-integration-tests", 50000),
    ) as test_client:
        yield test_client
    integration_app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def password_hash() -> str:
    return bcrypt.hashpw(b"Inicial1!", bcrypt.gensalt(rounds=4)).decode("utf-8")


@pytest.fixture
def crear_usuario_db(
    db_session: Session,
    password_hash: str,
) -> Callable[..., dict[str, Any]]:
    def crear(
        *,
        id_rol: int = 2,
        estado: int = 2,
        nombre: str = "Integracion",
        apellidos: str = "Prueba",
        fecha_registro: datetime | None = None,
        numero_identificacion: str | None = None,
        correo: str | None = None,
    ) -> dict[str, Any]:
        identificador = uuid.uuid4().int
        numero = numero_identificacion or str(identificador % 10**15).zfill(15)
        correo_usuario = correo or f"it-{uuid.uuid4().hex}@example.com"
        fecha = fecha_registro or datetime.now(timezone.utc).replace(tzinfo=None)

        fila = db_session.execute(
            text(
                """
                INSERT INTO modulo1.usuarios (
                    tipo_identificacion, numero_identificacion, nombre, apellidos,
                    fecha_nacimiento, genero, correo_electronico,
                    contrasena_cifrada, telefono, direccion, id_rol, fecha_registro
                ) VALUES (
                    'CC', :numero, :nombre, :apellidos, :fecha_nacimiento,
                    CAST('M' AS modulo1.enum_usuario_genero), :correo,
                    :contrasena, '3001234567', 'Direccion Integracion', :id_rol, :fecha
                )
                RETURNING id_usuario, version
                """
            ),
            {
                "numero": numero,
                "nombre": nombre,
                "apellidos": apellidos,
                "fecha_nacimiento": date(1990, 1, 1),
                "correo": correo_usuario,
                "contrasena": password_hash,
                "id_rol": id_rol,
                "fecha": fecha,
            },
        ).mappings().one()

        cuenta = db_session.execute(
            text(
                """
                INSERT INTO modulo1.cuentas_usuarios (
                    id_usuario, id_estado_cuenta, tiene_correo_verificado,
                    fecha_verificacion, ultimo_acceso
                ) VALUES (
                    :id_usuario, :estado, :verificado,
                    CASE WHEN :verificado THEN now() ELSE NULL END, now()
                )
                RETURNING id_cuenta_usuario
                """
            ),
            {
                "id_usuario": fila["id_usuario"],
                "estado": estado,
                "verificado": estado == 2,
            },
        ).scalar_one()
        db_session.flush()
        return {
            "id_usuario": fila["id_usuario"],
            "id_cuenta_usuario": cuenta,
            "id_rol": id_rol,
            "version": fila["version"],
            "correo": correo_usuario,
            "numero_identificacion": numero,
        }

    return crear


@pytest.fixture
def crear_auth_headers(
    db_session: Session,
) -> Callable[[dict[str, Any]], dict[str, str]]:
    def crear(usuario: dict[str, Any]) -> dict[str, str]:
        ahora = datetime.now(timezone.utc)
        id_token = db_session.execute(
            text(
                """
                INSERT INTO modulo1.tokens (token_tipo, fecha_expiracion)
                VALUES (CAST('acceso' AS modulo1.enum_token_tipo), :expira)
                RETURNING id_token
                """
            ),
            {"expira": ahora + timedelta(hours=8)},
        ).scalar_one()
        db_session.execute(
            text(
                """
                INSERT INTO modulo1.sesiones (
                    id_token, direccion_ip, agente_usuario, fecha_inicio,
                    fecha_finalizacion, es_activa, id_cuenta_usuario
                ) VALUES (
                    :id_token, '127.0.0.1', 'pytest-integration', :inicio,
                    :fin, TRUE, :id_cuenta
                )
                """
            ),
            {
                "id_token": id_token,
                "inicio": ahora,
                "fin": ahora + timedelta(hours=8),
                "id_cuenta": usuario["id_cuenta_usuario"],
            },
        )
        db_session.flush()

        token = jose_jwt.encode(
            {
                "sub": str(usuario["id_usuario"]),
                "jti": str(id_token),
                "rol": usuario["id_rol"],
                "iat": ahora,
                "exp": ahora + timedelta(hours=8),
            },
            JWT_SECRET_INTEGRACION,
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}

    return crear


@pytest.fixture
def crear_evento_db(db_session: Session) -> Callable[..., int]:
    def crear(
        *,
        id_usuario: int,
        tipo_evento: int,
        categoria: str,
        detalle: dict[str, Any] | None = None,
        fecha: datetime | None = None,
        hash_integridad: str | None = None,
    ) -> int:
        """Inserta un evento de auditoría válido.

        Por defecto calcula el hash real del contenido con la misma fórmula del
        repositorio, porque desde RF-10 un evento sin hash o con hash que no
        cuadra ya no cuenta como íntegro. Para probar la detección de
        manipulación se pasa `hash_integridad` explícito.
        """
        fecha_evento = fecha or datetime.now(timezone.utc)
        contenido = detalle or {"origen": "integracion"}
        if hash_integridad is None:
            hash_integridad = hashlib.sha256(
                json.dumps(
                    {
                        "tipo_evento": tipo_evento,
                        "fecha_evento": fecha_evento.isoformat(),
                        "id_usuario": id_usuario,
                        "resultado": "exitoso",
                        "modulo": "MODULO1",
                        "detalle": contenido,
                    },
                    sort_keys=True,
                    default=str,
                ).encode("utf-8")
            ).hexdigest()

        return db_session.execute(
            text(
                """
                INSERT INTO modulo1.eventos (
                    tipo_evento, fecha_evento, modulo, resultado, detalle,
                    id_usuario, categoria, estado, hash_integridad
                ) VALUES (
                    :tipo, :fecha, 'MODULO1',
                    CAST('exitoso' AS modulo1.enum_evento_resultado),
                    CAST(:detalle AS jsonb), :usuario, :categoria, 'PROCESADO', :hash
                )
                RETURNING id_evento
                """
            ),
            {
                "tipo": tipo_evento,
                "fecha": fecha_evento,
                "detalle": json.dumps(contenido),
                "usuario": id_usuario,
                "categoria": categoria,
                "hash": hash_integridad,
            },
        ).scalar_one()

    return crear


@pytest.fixture
def ejecutar_sql_anotacion(db_session: Session) -> Callable[[str], None]:
    def ejecutar(nombre: str) -> None:
        contenido = (ROOT / "anotaciones" / "modulo_1" / nombre).read_text(
            encoding="utf-8"
        )
        contenido = re.sub(
            r"(?im)^\s*(BEGIN|COMMIT);\s*$",
            "",
            contenido,
        )
        db_session.connection().exec_driver_sql(contenido)

    return ejecutar
