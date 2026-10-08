import os
import time
import logging

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

engine = create_engine(
    DATABASE_URL, pool_pre_ping=True, pool_recycle=1800, use_insertmanyvalues=False
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

_MAX_REINTENTOS_CONEXION = 3
_PAUSA_REINTENTO = 0.5


def _conectar_con_reintentos(db: Session) -> None:
    """Toma la conexión del pool reintentando ante fallos transitorios (RF-02)."""
    for intento in range(1, _MAX_REINTENTOS_CONEXION + 1):
        try:
            db.connection()
            return
        except (OperationalError, InterfaceError) as exc:
            db.rollback()
            if intento == _MAX_REINTENTOS_CONEXION:
                logger.error(
                    "No se pudo establecer conexión tras %s intentos: %s",
                    _MAX_REINTENTOS_CONEXION, exc,
                )
                raise ServiceUnavailableError(
                    "BD_NO_DISPONIBLE",
                    "No fue posible conectar con la base de datos. Intenta más tarde.",
                ) from exc
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
        SandboxCapacityExceeded,
    )
    from fastapi import HTTPException, status

    run_id = test_run_id_context.get()

    if run_id:
        test_session = None
        try:
            test_session = get_or_create_test_session(run_id)
            yield test_session
        except SandboxCapacityExceeded as e:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
        except Exception:
            if test_session is not None:
                try:
                    test_session.rollback()
                except Exception:
                    pass
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