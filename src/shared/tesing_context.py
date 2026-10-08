from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

test_run_id_context: ContextVar[Optional[str]] = ContextVar(
    "test_run_id_context", default=None
)