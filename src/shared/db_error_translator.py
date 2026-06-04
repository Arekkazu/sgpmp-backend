from psycopg2 import errors as pg_errors
from sqlalchemy.exc import DataError, IntegrityError, OperationalError

from src.shared.errors import ConflictError, InfrastructureError, ValidationError


def raise_from_db_error(
    exc: Exception,
    conflict_messages: dict[str, str] | None = None,
) -> None:
    if isinstance(exc, IntegrityError):
        diag = getattr(exc.orig, "diag", None)
        constraint = getattr(diag, "constraint_name", None)

        if isinstance(exc.orig, pg_errors.UniqueViolation):
            message = (conflict_messages or {}).get(constraint, "El recurso ya existe")
            raise ConflictError(code="UNICIDAD", message=message, field=constraint)

        if isinstance(exc.orig, pg_errors.CheckViolation):
            raise ValidationError(
                code="VAL_ENTRADA",
                message="El valor no cumple con las restricciones permitidas",
                field=constraint,
            )

        if isinstance(exc.orig, pg_errors.ForeignKeyViolation):
            raise InfrastructureError(
                code="INFRAESTRUC",
                message="Referencia a un recurso del sistema que no existe",
                original_error=exc,
            )

        raise InfrastructureError(
            code="INFRAESTRUC",
            message="Error de integridad en base de datos",
            original_error=exc,
        )

    if isinstance(exc, DataError):
        raise ValidationError(
            code="VAL_ENTRADA",
            message="El valor excede el tamaño o formato permitido por la base de datos",
        )

    if isinstance(exc, OperationalError):
        raise InfrastructureError(
            code="INFRAESTRUC",
            message="Error de conexión con la base de datos",
            original_error=exc,
        )

    raise InfrastructureError(
        code="INFRAESTRUC",
        message="Error inesperado en base de datos",
        original_error=exc,
    )
