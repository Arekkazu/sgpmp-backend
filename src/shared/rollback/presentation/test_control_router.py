import os
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from src.shared.database import get_db
from src.shared.rollback.infraestructure.testing_sandbox import cleanup_test_session


def verify_sandbox_secret(x_sandbox_secret: str = Header(..., alias="X-Sandbox-Secret")):
    expected_secret = os.getenv("TEST_SANDBOX_SECRET")
    if not expected_secret or x_sandbox_secret != expected_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Secreto de sandbox inválido o ausente.",
        )


router = APIRouter(
    prefix="/test-control",
    tags=["Testing"],
    dependencies=[Depends(verify_sandbox_secret)],
)


class QueryRequest(BaseModel):
    query: str


@router.delete("/runs/{run_id}")
async def end_test_run(run_id: str):
    success = cleanup_test_session(run_id)
    if success:
        return {"status": "Rollback exitoso"}
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Run ID no encontrado.",
    )


@router.post("/query")
def execute_test_query(
    payload: QueryRequest,
    x_test_run_id: str = Header(..., alias="X-Test-Run-Id"),
    db: Session = Depends(get_db),
):
    """
    Permite a QA ejecutar consultas SELECT dentro de la transacción del
    sandbox, en una sub-transacción de solo lectura con timeout de 2s.
    El aislamiento READ ONLY + statement_timeout protege la transacción
    principal del run_id, sin depender de filtrar palabras en el texto.
    """
    cleaned_query = payload.query.strip()

    if not cleaned_query.upper().startswith("SELECT"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operación denegada. Solo se permiten consultas SELECT en el sandbox.",
        )

    if ";" in cleaned_query:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operación denegada. No se permiten múltiples sentencias SQL.",
        )

    safe_query = f"SELECT * FROM ({cleaned_query}) AS query_sandbox LIMIT 100"

    try:
        db.execute(text("SAVEPOINT sandbox_query"))
        try:
            db.execute(text("SET LOCAL transaction_read_only = on"))
            db.execute(text("SET LOCAL statement_timeout = '2s'"))
            result = db.execute(text(safe_query))
            rows = [dict(row) for row in result.mappings().all()]
        finally:
            # Siempre se revierte al savepoint: descarta los SET LOCAL y limpia
            # el estado abortado si la consulta falló. No afecta los datos de la corrida.
            db.execute(text("ROLLBACK TO SAVEPOINT sandbox_query"))
            db.execute(text("RELEASE SAVEPOINT sandbox_query"))
        return {"data": rows}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error ejecutando la consulta: {str(e)}",
        )