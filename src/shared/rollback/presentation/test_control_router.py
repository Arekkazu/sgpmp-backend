import os
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from shared.rollback.infraestructure.testing_sandbox import cleanup_test_session
from sqlalchemy import text
from pydantic import BaseModel
from src.shared.database import get_db


router = APIRouter(prefix="/test-control", tags=["Testing"])
class QueryRequest(BaseModel):
    query: str



def verify_sandbox_secret(x_sandbox_secret: str = Header(..., alias="X-Sandbox-Secret")):
    expected_secret = os.getenv("TEST_SANDBOX_SECRET")
    
    if not expected_secret or x_sandbox_secret != expected_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Secreto de sandbox inválido o ausente."
        )

router = APIRouter(
    prefix="/test-control", 
    tags=["Testing"],
    dependencies=[Depends(verify_sandbox_secret)]
)

@router.delete("/runs/{run_id}")
async def end_test_run(run_id: str):
    success = cleanup_test_session(run_id)
    if success:
        return {"status": "Rollback exitoso"}
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, 
        detail="Run ID no encontrado."
    )


@router.post("/query")
def execute_test_query(
    payload: QueryRequest,
    x_test_run_id: str = Header(..., alias="X-Test-Run-Id"),
    db: Session = Depends(get_db)
):
    """
    Permite a QA ejecutar consultas SQL crudas dentro de la transacción del sandbox 
    para validar la persistencia de datos en memoria sin hacer COMMIT.
    """
    if os.getenv("ENABLE_TEST_SANDBOX", "false").lower() != "true":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Test sandbox endpoint disabled."
        )

    cleaned_query = payload.query.strip()
    if not cleaned_query.upper().startswith("SELECT"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Operación denegada. Solo se permiten consultas SELECT en el sandbox."
        )

    try:
        result = db.execute(text(cleaned_query))
        
     
        rows = result.mappings().all()
        return {"data": [dict(row) for row in rows]}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Error ejecutando la consulta: {str(e)}"
        )