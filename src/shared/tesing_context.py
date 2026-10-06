import contextvars

test_run_id_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "test_run_id", default=None
)