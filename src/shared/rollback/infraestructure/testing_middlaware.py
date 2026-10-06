import os
import logging
from httpx import request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from tests.shared.tesing_context import test_run_id_context


logger = logging.getLogger(__name__)

class TestSandboxMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if os.getenv("ENABLE_TEST_SANDBOX", "false").lower() != "true":
            return await call_next(request)

        run_id = request.headers.get("X-Test-Run-Id")
        if run_id:
            secret = request.headers.get("X-Sandbox-Secret")
            expected_secret = os.getenv("TEST_SANDBOX_SECRET")
            if not expected_secret or secret != expected_secret:
                return Response(
                    content="Acceso denegado. Secreto de sandbox inválido o ausente.",
                    status_code=403
                )
            
            logger.info(f"[Sandbox] Procesando request {request.method} {request.url.path} para run_id: {run_id}")
            token = test_run_id_context.set(run_id)
            try:
                response = await call_next(request)
                response.headers["X-Test-Run-Id"] = run_id
                return response
            finally:
                test_run_id_context.reset(token)
        else:
            response = await call_next(request)
            
        return response