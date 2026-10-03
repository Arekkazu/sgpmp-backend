import os
from fastapi import APIRouter, HTTPException, status
from src.infrastructure.http.middlewares.testing_sandbox import cleanup_test_session

router = APIRouter(prefix="/test-control", tags=["Testing"])

@router.delete("/runs/{run_id}")
async def end_test_run(run_id: str):
    if os.getenv("ENABLE_TEST_SANDBOX", "false").lower() != "true":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Sandbox deshabilitado."
        )
        
    success = cleanup_test_session(run_id)
    if success:
        return {"status": "Rollback exitoso"}
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, 
        detail="Run ID no encontrado."
    )