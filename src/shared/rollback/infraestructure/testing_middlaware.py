import os
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.shared.tesing_context import test_run_id_context

logger = logging.getLogger(__name__)


class TestSandboxMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if os.getenv("ENABLE_TEST_SANDBOX", "false").lower() != "true":
            return await call_next(request)

        run_id = request.headers.get("X-Test-Run-Id")
        if not run_id:
            return await call_next(request)

        secret = request.headers.get("X-Sandbox-Secret")
        expected_secret = os.getenv("TEST_SANDBOX_SECRET")
        if not expected_secret or secret != expected_secret:
            return Response(
                content="Acceso denegado. Secreto de sandbox inválido o ausente.",
                status_code=403,
            )

        logger.info(
            "[Sandbox] Procesando request %s %s para run_id: %s",
            request.method, request.url.path, run_id,
        )
        token = test_run_id_context.set(run_id)
        try:
            response = await call_next(request)
            response.headers["X-Test-Run-Id"] = run_id
            return response
        finally:
            test_run_id_context.reset(token)