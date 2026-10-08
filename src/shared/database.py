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

from dotenv import load_dotenv
from sqlalchemy import create_engine
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
