"""Pruebas del traductor de errores de base de datos.

Lo que más importa aquí: ningún nombre de constraint de PostgreSQL puede salir
hacia el cliente. Antes de este cambio el frontend recibía
`{"field": "uq_usuario_correo"}` y lo mostraba al usuario como
"Uq usuario correo".
"""
import pytest
from psycopg2 import errors as pg_errors
from sqlalchemy.exc import DataError, IntegrityError, OperationalError

from src.shared.db_error_translator import _campo, raise_from_db_error
from src.shared.errors import (
    ConflictError,
    InfrastructureError,
    ServiceUnavailableError,
    ValidationError,
)


class Diag:
    """Doble del objeto `Diagnostics` de psycopg2."""

    def __init__(self, **kw):
        self.column_name = kw.get("column_name")
        self.constraint_name = kw.get("constraint_name")
        self.table_name = kw.get("table_name")
        self.message_primary = kw.get("message_primary")
        self.sqlstate = kw.get("sqlstate")


def _error_pg(clase, **kw):
    """Crea un error de psycopg2 con un `diag` controlado.

    `diag` es un descriptor de solo lectura del tipo C, así que se sombrea
    declarándolo como atributo de una subclase creada al vuelo.
    """
    return type(f"Fake{clase.__name__}", (clase,), {"diag": Diag(**kw)})()


def _integrity(clase, **kw) -> IntegrityError:
    return IntegrityError("stmt", {}, _error_pg(clase, **kw))


# --- _campo ------------------------------------------------------------------


def test_campo_prefiere_column_name() -> None:
    diag = Diag(column_name="correo", constraint_name="uq_usuario_correo", table_name="usuario")

    assert _campo(diag) == "correo"


def test_campo_limpia_prefijo_de_tipo_y_de_tabla() -> None:
    diag = Diag(constraint_name="uq_usuario_correo", table_name="usuario")

    assert _campo(diag) == "correo"


def test_campo_limpia_el_prefijo_aunque_no_haya_tabla() -> None:
    diag = Diag(constraint_name="ck_valor_min")

    assert _campo(diag) == "valor_min"


@pytest.mark.parametrize("prefijo", ["uq_", "uk_", "fk_", "ck_", "chk_", "pk_", "idx_", "ix_"])
def test_campo_reconoce_todos_los_prefijos(prefijo: str) -> None:
    diag = Diag(constraint_name=f"{prefijo}nombre")

    assert _campo(diag) == "nombre"


def test_campo_sin_diagnostico_devuelve_none() -> None:
    assert _campo(None) is None
    assert _campo(Diag()) is None


# --- raise_from_db_error -----------------------------------------------------


def test_unicidad_no_filtra_el_nombre_del_constraint() -> None:
    exc = _integrity(pg_errors.UniqueViolation, constraint_name="uq_usuario_correo", table_name="usuario")

    with pytest.raises(ConflictError) as exc_info:
        raise_from_db_error(exc)

    error = exc_info.value
    assert error.code == "RECURSO_DUPLICADO"
    assert error.status_code == 409
    assert error.field == "correo"
    assert "uq_" not in (error.field or "")
    assert "uq_" not in error.message


def test_unicidad_usa_el_mensaje_personalizado_del_repositorio() -> None:
    exc = _integrity(pg_errors.UniqueViolation, constraint_name="uq_usuario_correo", table_name="usuario")

    with pytest.raises(ConflictError) as exc_info:
        raise_from_db_error(exc, {"uq_usuario_correo": "El correo ya está registrado."})

    assert exc_info.value.message == "El correo ya está registrado."


def test_check_violation_es_400() -> None:
    exc = _integrity(pg_errors.CheckViolation, constraint_name="ck_peso_positivo", table_name="activo")

    with pytest.raises(ValidationError) as exc_info:
        raise_from_db_error(exc)

    assert exc_info.value.code == "VALOR_NO_PERMITIDO"
    assert exc_info.value.status_code == 400
    assert exc_info.value.field == "peso_positivo"


def test_fk_referenciada_es_conflicto_no_error_del_servidor() -> None:
    exc = _integrity(
        pg_errors.ForeignKeyViolation,
        constraint_name="fk_ciclo_especie",
        message_primary='update or delete on table "especie" violates foreign key '
                        'constraint: key is still referenced from table "ciclo"',
    )

    with pytest.raises(ConflictError) as exc_info:
        raise_from_db_error(exc)

    assert exc_info.value.code == "REFERENCIA_EN_USO"
    assert exc_info.value.status_code == 409


def test_fk_inexistente_es_dato_invalido_del_cliente() -> None:
    exc = _integrity(
        pg_errors.ForeignKeyViolation,
        constraint_name="fk_ciclo_especie",
        table_name="ciclo",
        message_primary='insert or update on table "ciclo" violates foreign key '
                        'constraint: key is not present in table "especie"',
    )

    with pytest.raises(ValidationError) as exc_info:
        raise_from_db_error(exc)

    assert exc_info.value.code == "REFERENCIA_INVALIDA"
    assert exc_info.value.status_code == 400


def test_errcode_duplicate_stage_es_409_no_500() -> None:
    """RF-32 (#128/#129): DUPLICATE_STAGE (P0104) es un error de clase `P0`
    (PL/pgSQL) que psycopg2 no clasifica como `IntegrityError`. Sin este mapeo
    explícito caía al catch-all -> 500, aunque fuera un choque de nombre real."""
    exc = _integrity(
        pg_errors.InternalError_,
        sqlstate="P0104",
        message_primary='DUPLICATE_STAGE: Ya existe una etapa llamada "Engorde" para esta especie.',
    )

    with pytest.raises(ConflictError) as exc_info:
        raise_from_db_error(exc)

    assert exc_info.value.code == "RECURSO_DUPLICADO"
    assert exc_info.value.status_code == 409
    assert "DUPLICATE_STAGE" not in exc_info.value.message
    assert "Engorde" in exc_info.value.message


def test_errcode_duplicate_metric_es_409_no_500() -> None:
    exc = _integrity(
        pg_errors.InternalError_,
        sqlstate="P0109",
        message_primary='DUPLICATE_METRIC: Ya existe una métrica productiva con el nombre "Peso".',
    )

    with pytest.raises(ConflictError) as exc_info:
        raise_from_db_error(exc)

    assert exc_info.value.code == "RECURSO_DUPLICADO"
    assert exc_info.value.status_code == 409


def test_integrity_error_no_mapeado_es_500() -> None:
    exc = _integrity(pg_errors.NotNullViolation, constraint_name="algo")

    with pytest.raises(InfrastructureError) as exc_info:
        raise_from_db_error(exc)

    assert exc_info.value.code == "ERROR_INTERNO"
    assert exc_info.value.status_code == 500


def test_data_error_es_400() -> None:
    with pytest.raises(ValidationError) as exc_info:
        raise_from_db_error(DataError("stmt", {}, Exception("value too long")))

    assert exc_info.value.code == "VALOR_FUERA_DE_RANGO"
    assert exc_info.value.status_code == 400


def test_operational_error_es_503_no_500() -> None:
    with pytest.raises(ServiceUnavailableError) as exc_info:
        raise_from_db_error(OperationalError("stmt", {}, Exception("server closed the connection")))

    assert exc_info.value.code == "BD_NO_DISPONIBLE"
    assert exc_info.value.status_code == 503
    assert "server closed" not in exc_info.value.message


def test_excepcion_desconocida_es_500() -> None:
    with pytest.raises(InfrastructureError) as exc_info:
        raise_from_db_error(ValueError("algo raro"))

    assert exc_info.value.code == "ERROR_INTERNO"
    assert exc_info.value.status_code == 500
