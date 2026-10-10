"""Configuración del engine SQLAlchemy y generador de sesiones de base de datos.

Exporta `get_db`, el generador FastAPI/Depends que provee una sesión por request
y la cierra al finalizar, y `SessionLocal` para usos fuera del contexto web.

INC-M01-06-024 / RF-02: una caída de PostgreSQL debe salir como `503` con un
mensaje claro, no como el `OperationalError` crudo que Starlette convierte en
`500 Internal Server Error`. `get_db` reintenta la toma de conexión antes de
rendirse y traduce el fallo a `ServiceUnavailableError`.
"""
import logging
import os
import time
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from src.shared.errors import ServiceUnavailableError

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "Falta la variable de entorno DATABASE_URL. Revisa el .env "
        "(o la configuración del despliegue) antes de arrancar la API."
    )

# Mismo criterio que tests/integration/conftest.py: `pool_pre_ping` descarta la
# conexión muerta antes de entregarla, y `pool_recycle` la renueva antes de que
# el proxy o el servidor la corten por inactividad. Esta es la reconexión
# automática — no hace falta un bucle de reintentos propio a nivel de engine.
#
# `use_insertmanyvalues=False` (#144): el modo "insertmanyvalues" de
# SQLAlchemy 2.0 agrupa varios INSERT del mismo modelo en una sola sentencia y
# castea cada parámetro a `::VARCHAR` explícito. Cualquier columna ORM
# `String` que mapea a un ENUM nativo de Postgres (patrón que este proyecto
# usa a propósito, ver CLAUDE.md) rompe con `DatatypeMismatch` en cuanto se
# insertan 2+ filas del mismo modelo en el mismo flush — con una sola fila no
# falla, por eso pasó desapercibido (ej. los 3 niveles de un umbral ambiental
# siempre se insertan juntos). Desactivarlo vuelve al INSERT fila-por-fila
# (comportamiento de SQLAlchemy < 2.0), sin este riesgo.
engine = create_engine(
    DATABASE_URL, pool_pre_ping=True, pool_recycle=1800, use_insertmanyvalues=False
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Identidad de la transacción para RLS (F2/F4 del control de acceso por BD).
# Las políticas leen `app.current_user_id` / `app.current_role` y los triggers
# de auditoría de modulo2 leen `app.usuario_id`. `set_config(..., true)` muere
# con la transacción, así que todo lo que corría después del primer `commit()`
# del request quedaba sin identidad (bajo RLS: cero filas). La identidad vive
# en `Session.info` y se reaplica al empezar cada transacción de esa sesión;
# no se filtra a otro request porque cada request abre su propia sesión.
_CLAVE_IDENTIDAD = "identidad_rls"

# D1/D4 (decisión del DBA en el PR #485): las tareas de fondo y la ingesta IoT
# corren como un usuario de servicio con filas explícitas en
# `modulo9.usuarios_fincas`, nunca con BYPASSRLS. Lo crea la migración
# `5c3e9b1d7a20`, que también lo deja sin poder iniciar sesión. Su id se
# resuelve por correo (difiere entre bases) al empezar la primera transacción,
# no al crear la sesión: así una BD caída falla dentro del `try` de la tarea.
CORREO_USUARIO_SERVICIO = "servicio.sistema@sgpmp.local"
_ROL_SERVICIO = "Administrador"
_SISTEMA = object()
_id_usuario_servicio: Optional[int] = None


def _set_config(conexion, id_usuario: Optional[int], nombre_rol: Optional[str]) -> None:
    conexion.execute(
        text(
            "SELECT set_config('app.current_user_id', :uid, true), "
            "set_config('app.current_role', :rol, true)"
        ),
        {"uid": "" if id_usuario is None else str(id_usuario), "rol": nombre_rol or ""},
    )
    if id_usuario is not None:
        conexion.execute(
            text("SELECT set_config('app.usuario_id', :uid, true)"), {"uid": str(id_usuario)}
        )


def _id_servicio(conexion) -> int:
    global _id_usuario_servicio
    if _id_usuario_servicio is None:
        # Todavía no hay identidad: bajo RLS solo la función SECURITY DEFINER
        # del login (a7380032a23b) puede resolver un usuario por correo.
        _id_usuario_servicio = conexion.execute(
            text("SELECT modulo1.fn_id_usuario_por_correo(:correo)"),
            {"correo": CORREO_USUARIO_SERVICIO},
        ).scalar()
        if _id_usuario_servicio is None:
            raise RuntimeError(
                f"No existe el usuario de servicio {CORREO_USUARIO_SERVICIO}: "
                "falta aplicar las migraciones (alembic upgrade head)."
            )
    return _id_usuario_servicio


def _aplicar_identidad(conexion, identidad) -> None:
    if identidad is _SISTEMA:
        identidad = (_id_servicio(conexion), _ROL_SERVICIO)
    _set_config(conexion, *identidad)


@event.listens_for(Session, "after_begin")
def _reaplicar_identidad(session: Session, _transaccion, conexion) -> None:
    identidad = session.info.get(_CLAVE_IDENTIDAD)
    if identidad is not None:
        _aplicar_identidad(conexion, identidad)


def _declarar(db: Session, identidad) -> None:
    db.info[_CLAVE_IDENTIDAD] = identidad
    if db.in_transaction():
        _aplicar_identidad(db.connection(), identidad)


def declarar_identidad(db: Session, id_usuario: Optional[int], nombre_rol: Optional[str]) -> None:
    """Declara quién ejecuta la transacción en curso y las siguientes de `db`."""
    _declarar(db, (id_usuario, nombre_rol))


def declarar_identidad_si_anonima(db: Session, id_usuario: int) -> None:
    """Flujos que todavía no tienen identidad (login, registro, refresh, activación,
    recuperación): a partir de aquí actúan como el usuario recién resuelto.

    Nunca pisa una identidad ya declarada: un request autenticado no pasa a
    actuar como otro usuario por una búsqueda.
    """
    if db.info.get(_CLAVE_IDENTIDAD) is None:
        declarar_identidad(db, id_usuario, None)


def declarar_identidad_sistema(db: Session) -> None:
    """Hace que `db` actúe como el usuario de servicio."""
    _declarar(db, _SISTEMA)


def sesion_sistema() -> Session:
    """`SessionLocal()` que actúa como el usuario de servicio (tareas de fondo)."""
    db = SessionLocal()
    declarar_identidad_sistema(db)
    return db


# Mismo idiom que src/shared/email.py, pero con pausa corta: el frontend aborta
# a los 15 s (sgpmp-frontend/src/shared/api/http.ts), así que el presupuesto
# total de reintentos tiene que caber muy por debajo de ese límite.
_MAX_REINTENTOS_CONEXION = 3
_PAUSA_REINTENTO = 0.5


def _conectar_con_reintentos(db: Session) -> None:
    """Toma la conexión del pool reintentando ante fallos transitorios.

    Adelanta al inicio del request el checkout que SQLAlchemy haría en el primer
    query, para poder distinguir "la base de datos no responde" de cualquier
    otro fallo y traducirlo a un error de dominio.

    Args:
        db: Sesión recién creada por `SessionLocal`.

    Raises:
        ServiceUnavailableError: Si la base de datos no responde después de
            agotar los reintentos. Código ``BD_NO_DISPONIBLE``, HTTP 503.
    """
    for intento in range(1, _MAX_REINTENTOS_CONEXION + 1):
        try:
            db.connection()
            return
        except (OperationalError, InterfaceError) as exc:
            # Devuelve la conexión inservible al pool para que el siguiente
            # intento saque una nueva en vez de reusar la que acaba de fallar.
            db.rollback()
            if intento == _MAX_REINTENTOS_CONEXION:
                logger.error(
                    "Base de datos inalcanzable tras %d intentos: %r", intento, exc
                )
                raise ServiceUnavailableError(
                    code="BD_NO_DISPONIBLE",
                    message=(
                        "El servicio no está disponible temporalmente. "
                        "Intenta de nuevo en unos momentos."
                    ),
                    original_error=exc,
                ) from exc
            logger.warning(
                "Reintentando conexión a la base de datos (%d/%d).",
                intento,
                _MAX_REINTENTOS_CONEXION,
            )
            time.sleep(_PAUSA_REINTENTO)


def get_db():
    """Generador de sesiones SQLAlchemy para inyección de dependencias FastAPI.

    Yields:
        Session: Sesión de base de datos activa para el request actual.

    Raises:
        ServiceUnavailableError: Si la base de datos no responde al inicio del
            request. Código ``BD_NO_DISPONIBLE``, HTTP 503.
    """
    db = SessionLocal()
    try:
        _conectar_con_reintentos(db)
        yield db
    except Exception:
        # Sin esto, una excepción a mitad de request deja la transacción abierta
        # hasta el close(), y la sesión puede volver al pool contaminada.
        db.rollback()
        raise
    finally:
        db.close()


def get_db_sistema(db: Session = Depends(get_db)) -> Session:
    """`get_db` para endpoints sin usuario autenticado (ingesta IoT, D4)."""
    declarar_identidad_sistema(db)
    return db
