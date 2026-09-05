"""Traductor de errores de base de datos a errores de dominio.

Los repositorios SQLAlchemy capturan ``IntegrityError``, ``DataError`` y
``OperationalError`` de psycopg2 y los pasan a ``raise_from_db_error``, que
los convierte en errores del árbol ``AppError``. Esto mantiene la capa de
aplicación libre de dependencias de SQLAlchemy o psycopg2.

Ningún nombre de constraint de PostgreSQL sale hacia el cliente: el ``field``
que viaja en la respuesta es siempre un nombre de columna, derivado por
``_campo`` a partir del diagnóstico de psycopg2.
"""
from psycopg2 import errors as pg_errors
from sqlalchemy.exc import DataError, IntegrityError, OperationalError

from src.shared.errors import (
    ConflictError,
    InfrastructureError,
    ServiceUnavailableError,
    ValidationError,
)

_PREFIJOS_CONSTRAINT = ("uq_", "uk_", "fk_", "ck_", "chk_", "pk_", "idx_", "ix_")


def _campo(diag) -> str | None:
    """Deriva el nombre de columna a partir del diagnóstico de psycopg2.

    Prefiere ``column_name``, que PostgreSQL rellena en varios casos. Si no está,
    limpia el nombre del constraint quitando el prefijo de tipo y el de tabla, de
    modo que ``uq_usuario_correo`` sobre la tabla ``usuario`` sale como
    ``correo``. Sin esto el frontend recibe el nombre crudo del constraint y lo
    muestra al usuario como "Uq usuario correo".

    Args:
        diag: Objeto ``Diagnostics`` de psycopg2, o ``None``.

    Returns:
        Nombre de columna, o ``None`` si no se pudo derivar ninguno.
    """
    if diag is None:
        return None

    if diag.column_name:
        return diag.column_name

    nombre = diag.constraint_name
    if not nombre:
        return None

    for prefijo in _PREFIJOS_CONSTRAINT:
        if nombre.startswith(prefijo):
            nombre = nombre[len(prefijo):]
            break

    tabla = diag.table_name
    if tabla and nombre.startswith(f"{tabla}_"):
        nombre = nombre[len(tabla) + 1:]

    return nombre or None


def raise_from_db_error(
    exc: Exception,
    conflict_messages: dict[str, str] | None = None,
) -> None:
    """Convierte una excepción de base de datos en un error de dominio y lo lanza.

    Mapeo de excepciones:

    - ``UniqueViolation`` → ``ConflictError`` (HTTP 409). El mensaje se
      personaliza por nombre de constraint usando ``conflict_messages``.
    - ``CheckViolation`` → ``ValidationError`` (HTTP 400).
    - ``ForeignKeyViolation`` → ``ConflictError`` (HTTP 409) si el registro está
      referenciado por otros, o ``ValidationError`` (HTTP 400) si el referenciado
      no existe. En ambos casos el origen es el dato que mandó el cliente, no un
      fallo del servidor.
    - ``DataError`` → ``ValidationError`` (HTTP 400).
    - ``OperationalError`` → ``ServiceUnavailableError`` (HTTP 503).
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
            se usa el mensaje genérico.

    Raises:
        ConflictError: Por violación de unicidad, o por FK que impide borrar.
        ValidationError: Por violación de check, FK inexistente o dato fuera de rango.
        ServiceUnavailableError: Por fallo de conectividad con la base de datos.
        InfrastructureError: Por cualquier otro error de base de datos no mapeado.
    """
    if isinstance(exc, IntegrityError):
        diag = getattr(exc.orig, "diag", None)
        constraint = getattr(diag, "constraint_name", None)

        if isinstance(exc.orig, pg_errors.UniqueViolation):
            message = (conflict_messages or {}).get(
                constraint, "Ya existe un registro con esos datos."
            )
            raise ConflictError(code="RECURSO_DUPLICADO", message=message, field=_campo(diag))

        if isinstance(exc.orig, pg_errors.CheckViolation):
            raise ValidationError(
                code="VALOR_NO_PERMITIDO",
                message="El valor no cumple con las restricciones permitidas",
                field=_campo(diag),
            )

        if isinstance(exc.orig, pg_errors.ForeignKeyViolation):
            # ponytail: heurística sobre el texto de PostgreSQL para distinguir
            # "no puedo borrar, hay quien me referencia" de "el referenciado no
            # existe". Si el mensaje cambia, cae al 400 genérico.
            mensaje_pg = getattr(diag, "message_primary", "") or ""
            if "still referenced" in mensaje_pg:
                raise ConflictError(
                    code="REFERENCIA_EN_USO",
                    message="No se puede eliminar: otros registros dependen de este.",
                )
            raise ValidationError(
                code="REFERENCIA_INVALIDA",
                message="El registro relacionado que indicaste no existe.",
                field=_campo(diag),
            )

        raise InfrastructureError(
            code="ERROR_INTERNO",
            message="Error de integridad en base de datos",
            original_error=exc,
        )

    if isinstance(exc, DataError):
        raise ValidationError(
            code="VALOR_FUERA_DE_RANGO",
            message="El valor excede el tamaño o formato permitido por la base de datos",
        )

    if isinstance(exc, OperationalError):
        raise ServiceUnavailableError(
            code="BD_NO_DISPONIBLE",
            message=(
                "El servicio no está disponible temporalmente. "
                "Intenta de nuevo en unos momentos."
            ),
            original_error=exc,
        )

    raise InfrastructureError(
        code="ERROR_INTERNO",
        message="Error inesperado en base de datos",
        original_error=exc,
    )
