from src.shared.database import SessionLocal, engine
from tests.shared.tesing_context import test_run_id_context
from fastapi import HTTPException, status

# Ahora importas el sandbox aquí, rompiendo el círculo
from src.shared.rollback.infraestructure.testing_sandbox import (
    get_or_create_test_session,
    SandboxCapacityExceeded
)

def get_db():
    run_id = test_run_id_context.get()
    if run_id:
        try:
            test_session = get_or_create_test_session(run_id)
            yield test_session
        except SandboxCapacityExceeded as e:
            raise HTTPException(status_code=429, detail=str(e))
        except Exception:
            test_session.rollback()
            raise
        return

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()