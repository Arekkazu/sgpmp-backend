"""Traductor de errores de base de datos a errores de dominio.

Los repositorios SQLAlchemy capturan ``IntegrityError``, ``DataError`` y
``OperationalError`` de psycopg2 y los pasan a ``raise_from_db_error``, que
los convierte en errores del árbol ``AppError``. Esto mantiene la capa de
aplicación libre de dependencias de SQLAlchemy o psycopg2.
"""
from psycopg2 import errors as pg_errors
from sqlalchemy.exc import DataError, IntegrityError, OperationalError

from src.shared.errors import ConflictError, InfrastructureError, ValidationError


def raise_from_db_error(
    exc: Exception,
    conflict_messages: dict[str, str] | None = None,
) -> None:
    """Convierte una excepción de base de datos en un error de dominio y lo lanza.

    Mapeo de excepciones:

    - ``UniqueViolation`` → ``ConflictError`` (HTTP 409). El mensaje se
      personaliza por nombre de constraint usando ``conflict_messages``.
    - ``CheckViolation`` → ``ValidationError`` (HTTP 400).
    - ``ForeignKeyViolation`` → ``InfrastructureError`` (HTTP 500).
    - ``DataError`` → ``ValidationError`` (HTTP 400).
    - ``OperationalError`` → ``InfrastructureError`` (HTTP 500).
    - Cualquier otro caso → ``InfrastructureError`` (HTTP 500).

    Debe llamarse desde el bloque ``except`` del repositorio, antes de que
    la excepción salga de la capa de infraestructura.

    Ejemplo de uso en un repositorio::

        try:
            self.db.flush()
        except IntegrityError as exc:
            raise_from_db_error(exc, {"uq_usuario_correo": "El correo ya está registrado."})

    Args:
        exc: Excepción capturada de SQLAlchemy o psycopg2.
        conflict_messages: Diccionario ``{nombre_constraint: mensaje_usuario}``
            para personalizar el mensaje de ``ConflictError`` según el
            constraint violado. Si el constraint no está en el diccionario,
            se usa el mensaje genérico ``"El recurso ya existe"``.

    Raises:
        ConflictError: Por violación de unicidad (UniqueViolation).
        ValidationError: Por violación de check o dato fuera de rango.
        InfrastructureError: Por violación de FK, error de conexión o
            cualquier otro error de base de datos no mapeado.
    """
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
