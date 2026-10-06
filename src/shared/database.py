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

# CORRECCIÓN QA (Punto 1 y 3): Eliminados los imports del sandbox a nivel de módulo
# para romper la importación circular y salvar el despliegue de producción.

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "Falta la variable de entorno DATABASE_URL. Revisa el .env "
        "(o la configuración del despliegue) antes de arrancar la API."
    )

engine = create_engine(
    DATABASE_URL, pool_pre_ping=True, pool_recycle=1800, use_insertmanyvalues=False
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

_MAX_REINTENTOS_CONEXION = 3
_PAUSA_REINTENTO = 0.5


def _conectar_con_reintentos(db: Session) -> None:
    """Toma la conexión del pool reintentando ante fallos transitorios."""
    # (Tu código original intacto)
    for intento in range(1, _MAX_REINTENTOS_CONEXION + 1):
        try:
            db.connection()
            return
        except (OperationalError, InterfaceError) as exc:
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
    """Generador principal de sesiones inyectado en routers."""
  
    if os.getenv("ENABLE_TEST_SANDBOX", "false").lower() != "true":
        db = SessionLocal()
        try:
            _conectar_con_reintentos(db)
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        return


    from src.shared.tesing_context import test_run_id_context
    from src.shared.rollback.infraestructure.testing_sandbox import (
        get_or_create_test_session,
        SandboxCapacityExceeded
    )
    from fastapi import HTTPException, status

    run_id = test_run_id_context.get()
    
    if run_id:
        try:
            test_session = get_or_create_test_session(run_id)
            yield test_session
        except SandboxCapacityExceeded as e:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
        except Exception:
            if 'test_session' in locals():
                # CORRECCIÓN QA (Punto 2): En lugar de un rollback ciego que podría
                # destruir la transacción padre, extraemos explícitamente el SAVEPOINT 
                # (transacción anidada) y le hacemos rollback solo a él.
                nested = test_session.get_nested_transaction()
                if nested is not None:
                    nested.rollback()
                else:
                    # Fallback de seguridad: si no hay nested, garantizamos limpiar 
                    # el estado de error sin matar la conexión principal.
                    test_session.rollback()
            raise
        return

    db = SessionLocal()
    try:
        _conectar_con_reintentos(db)
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()