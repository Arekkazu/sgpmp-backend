import os
from httpx import request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from tests.shared.tesing_context import test_run_id_context

class TestSandboxMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if os.getenv("ENABLE_TEST_SANDBOX", "false").lower() != "true":
            return await call_next(request)

        run_id = request.headers.get("X-Test-Run-Id")
        if run_id:
            # Guardamos el ID en el contexto de FastAPI para que get_db pueda leerlo
            token = test_run_id_context.set(run_id)
            try:
                response = await call_next(request)
            finally:
                test_run_id_context.reset(token)
        else:
            response = await call_next(request)
            
        return response