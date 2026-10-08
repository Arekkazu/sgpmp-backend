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
    BusinessRuleError,
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


def test_errcode_sensor_ya_activo_es_409_no_500() -> None:
    """INC-M09-107-G64 (#135): el trigger `trg_sensor_asociacion_unica_activa`
    de modulo9 señala P0130 (clase `P0`, no mapeada por psycopg2) — sin este
    mapeo, una condición de carrera al asociar un sensor caía al 500
    genérico en vez del conflicto de negocio correspondiente."""
    exc = _integrity(
        pg_errors.InternalError_,
        sqlstate="P0130",
        message_primary='SENSOR_ALREADY_ASSIGNED: El sensor ID 5 ya está activo en el área "Estanque-01".',
    )

    with pytest.raises(ConflictError) as exc_info:
        raise_from_db_error(exc)

    assert exc_info.value.code == "ASOCIACION_YA_ACTIVA"
    assert exc_info.value.status_code == 409
    assert "SENSOR_ALREADY_ASSIGNED" not in exc_info.value.message


def test_errcode_sensor_finca_distinta_es_422_no_500() -> None:
    """INC-M09-107-G64 (#135): el trigger `trg_sensor_asociacion_finca_fija`
    señala P0140 (misma clase `P0`) cuando el área destino pertenece a una
    finca distinta a la del dispositivo del sensor."""
    exc = _integrity(
        pg_errors.InternalError_,
        sqlstate="P0140",
        message_primary="SENSOR_FINCA_DISTINTA: El sensor ID 5 pertenece al dispositivo de la finca ID 1.",
    )

    with pytest.raises(BusinessRuleError) as exc_info:
        raise_from_db_error(exc)

    assert exc_info.value.code == "SENSOR_FINCA_DISTINTA"
    assert exc_info.value.status_code == 422
    assert "SENSOR_FINCA_DISTINTA:" not in exc_info.value.message


def test_errcode_evento_reproductivo_tipo_invalido_es_422_no_500() -> None:
    """INC-M02-76-G55: el trigger `trg_fn_evento_reproductivo_secuencia` (modulo2)
    señala P0220 (misma clase `P0`, no mapeada por psycopg2) cuando un activo
    POBLACIONAL recibe un evento reproductivo distinto a "nacimiento". El use
    case ya valida esto antes de llegar a la DB, pero sin este mapeo cualquier
    otra vía que dispare el trigger caía al 500 genérico en vez del 422 de
    negocio documentado en RF-42."""
    exc = _integrity(
        pg_errors.InternalError_,
        sqlstate="P0220",
        message_primary=(
            "TYPE_RESTRICTION: Para activos de tipo LOTE (poblacional) solo se "
            "permite el evento reproductivo nacimiento. Categoría recibida: parto."
        ),
    )

    with pytest.raises(BusinessRuleError) as exc_info:
        raise_from_db_error(exc)

    assert exc_info.value.code == "EVENTO_NO_PERMITIDO_LOTE"
    assert exc_info.value.status_code == 422
    assert "TYPE_RESTRICTION:" not in exc_info.value.message


def test_errcode_secuencia_reproductiva_es_422_no_500() -> None:
    """Arekkazu/SGPMP-FRONT-END-PWA#299: un parto que el trigger rechaza por
    secuencia (P0221) salía como 500 "Error inesperado en base de datos"."""
    exc = _integrity(
        pg_errors.InternalError_,
        sqlstate="P0221",
        message_primary=(
            "SEQUENCE_VIOLATION: No se puede registrar parto sin un evento previo "
            "de diagnostico positivo para el activo ID 750."
        ),
    )

    with pytest.raises(BusinessRuleError) as exc_info:
        raise_from_db_error(exc)

    assert exc_info.value.code == "SECUENCIA_REPRODUCTIVA_INVALIDA"
    assert exc_info.value.status_code == 422
    assert "SEQUENCE_VIOLATION:" not in exc_info.value.message


def test_errcode_evento_fecha_invalida_es_400_no_500() -> None:
    """INC-M02-75-G53: `trg_fn_evento_fecha_coherente` (modulo2, dispara para
    cualquier tipo de evento vía `eventos_activos`) señala P0215 (misma clase
    `P0`, no mapeada) cuando la fecha del evento es futura o anterior al
    registro del activo. La causa raíz real del incidente era otra (`now()`
    fijo por transacción rechazaba fechas válidas, corregido con
    `clock_timestamp()` en la migración `68232a1efcc2`), pero si algún día una
    fecha sí es genuinamente inválida, este mapeo evita que vuelva a salir
    como 500 genérico."""
    exc = _integrity(
        pg_errors.InternalError_,
        sqlstate="P0215",
        message_primary=(
            "INVALID_DATE: La fecha del evento (2026-09-13 00:00:00+00) no puede "
            "ser futura. Fecha actual del sistema: 2026-09-12 00:00:00+00."
        ),
    )

    with pytest.raises(ValidationError) as exc_info:
        raise_from_db_error(exc)

    assert exc_info.value.code == "FECHA_INVALIDA"
    assert exc_info.value.status_code == 400
    assert "INVALID_DATE:" not in exc_info.value.message


def test_errcode_poblacional_cantidad_invalida_es_400_no_500() -> None:
    """INC-M02-100-G31 (#262): `trg_fn_poblacional_cantidad_inmutable` (modulo2)
    señala P0210 (misma clase `P0`, no mapeada por psycopg2) cuando una
    escritura sobre `detalles_activos_biologicos_poblacionales` deja
    `cantidad_actual` en negativo o intenta modificar `cantidad_inicial`. Sin
    este mapeo, `POST .../eventos/crecimiento` sobre un lote que dispare el
    trigger devolvía 500 ERROR_INTERNO en vez del 400 que ya aplica la
    restricción CHECK gemela para la misma regla de negocio."""
    exc = _integrity(
        pg_errors.InternalError_,
        sqlstate="P0210",
        message_primary="INVALID_VALUE: La cantidad_actual del lote no puede ser negativa. Valor intentado: -3.",
    )

    with pytest.raises(ValidationError) as exc_info:
        raise_from_db_error(exc)

    assert exc_info.value.code == "VALOR_NO_PERMITIDO"
    assert exc_info.value.status_code == 400
    assert "INVALID_VALUE:" not in exc_info.value.message


@pytest.mark.parametrize(
    "sqlstate,mensaje",
    [
        ("P0125", 'DUPLICATE_AREA: Ya existe un área productiva con el nombre "GALPON" en esta finca (case-insensitive).'),
        ("P0101", "DUPLICATE_SPECIES: Ya existe una especie con ese nombre."),
        ("P0107", "DUPLICATE_PATHOLOGY: Ya existe una patología con ese nombre."),
        ("P0110", "DUPLICATE_THRESHOLD: Ya existe un umbral para esa especie y variable."),
        ("P0119", "DUPLICATE_FARM_GLOBAL: Ya existe una finca con ese nombre."),
        ("P0120", "DUPLICATE_FARM_PRODUCER: Ya tienes una finca con ese nombre."),
        ("P0128", "DUPLICATE_SERIAL: Ya existe un dispositivo con ese serial."),
    ],
)
def test_errcodes_duplicados_de_modulo9_son_409_no_500(sqlstate: str, mensaje: str) -> None:
    """INC-M09-20-G49 (#461): `trg_fn_infraestructura_nombre_unique_ci` compara
    sin distinguir mayúsculas y señala P0125 antes de que actúe el UNIQUE, así
    que "GALPON" contra un "Galpon" existente salía como 500 ERROR_INTERNO."""
    exc = _integrity(pg_errors.InternalError_, sqlstate=sqlstate, message_primary=mensaje)

    with pytest.raises(ConflictError) as exc_info:
        raise_from_db_error(exc)

    assert exc_info.value.code == "RECURSO_DUPLICADO"
    assert exc_info.value.status_code == 409
    assert mensaje.split(": ", 1)[0] + ":" not in exc_info.value.message


def test_errcode_estado_historial_inconsistente_es_409_no_500() -> None:
    """INC-M02-56-G31 (#456): `trg_fn_estado_activo_unico_vigente` señala P0212
    cuando el estado anterior declarado no coincide con el último del
    historial; antes caía al fallback genérico y la baja respondía 500."""
    exc = _integrity(
        pg_errors.InternalError_,
        sqlstate="P0212",
        message_primary=(
            "STATE_INCONSISTENCY: El estado anterior declarado (ID 3) no coincide con el "
            "último estado registrado para el activo (ID 1)."
        ),
    )

    with pytest.raises(ConflictError) as exc_info:
        raise_from_db_error(exc)

    assert exc_info.value.code == "ESTADO_ACTIVO_INCONSISTENTE"
    assert exc_info.value.status_code == 409
    assert "STATE_INCONSISTENCY:" not in exc_info.value.message


def test_errcode_baja_cantidad_invalida_es_400() -> None:
    exc = _integrity(
        pg_errors.InternalError_,
        sqlstate="P0224",
        message_primary="INVALID_VALUE: Para bajas en lotes la cantidad_afectada debe ser mayor a cero. Valor recibido: 0.",
    )

    with pytest.raises(ValidationError) as exc_info:
        raise_from_db_error(exc)

    assert exc_info.value.code == "VALOR_NO_PERMITIDO"
    assert exc_info.value.status_code == 400
    assert "INVALID_VALUE:" not in exc_info.value.message


def test_errcode_baja_supera_existencia_es_422() -> None:
    exc = _integrity(
        pg_errors.InternalError_,
        sqlstate="P0225",
        message_primary=(
            "INVENTORY_INCONSISTENCY: La cantidad a dar de baja (50) es superior a la "
            "existencia actual del lote (10). Activo ID 7."
        ),
    )

    with pytest.raises(BusinessRuleError) as exc_info:
        raise_from_db_error(exc)

    assert exc_info.value.code == "CANTIDAD_BAJA_SUPERIOR_EXISTENCIA"
    assert exc_info.value.status_code == 422
    assert "INVENTORY_INCONSISTENCY:" not in exc_info.value.message


@pytest.mark.parametrize(
    "mensaje,clase,codigo,estado",
    [
        (
            'INVALID_TRANSITION: La transición de estado "ACTIVO" → "CERRADO" no está permitida.',
            BusinessRuleError, "TRANSICION_INVALIDA", 422,
        ),
        (
            "REDUNDANT_TRANSITION: El estado nuevo es igual al estado actual.",
            ConflictError, "ESTADO_REDUNDANTE", 409,
        ),
    ],
)
def test_errcode_transicion_de_estado_es_error_de_negocio(mensaje, clase, codigo, estado) -> None:
    exc = _integrity(pg_errors.InternalError_, sqlstate="P0211", message_primary=mensaje)

    with pytest.raises(clase) as exc_info:
        raise_from_db_error(exc)

    assert exc_info.value.code == codigo
    assert exc_info.value.status_code == estado


@pytest.mark.parametrize(
    "mensaje",
    [
        "MISSING_FIELD: El campo modulo_origen es obligatorio para trazabilidad.",
        "DIRECT_STATE_CHANGE: No se permite modificar id_estado directamente en activos_biologicos.",
    ],
)
def test_errcode_p0211_de_bug_de_aplicacion_sigue_siendo_500(mensaje: str) -> None:
    """P0211 también lo lanzan `MISSING_FIELD` y `DIRECT_STATE_CHANGE`, que
    indican un bug de la aplicación; convertirlos en 4xx lo escondería."""
    exc = _integrity(pg_errors.InternalError_, sqlstate="P0211", message_primary=mensaje)

    with pytest.raises(InfrastructureError) as exc_info:
        raise_from_db_error(exc)

    assert exc_info.value.status_code == 500


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


def test_byte_nulo_de_psycopg2_es_400_no_500() -> None:
    """INC-M02-57-G06 (#93): psycopg2 rechaza un byte nulo embebido con un
    ValueError de Python plano en la adaptación del parámetro — no una
    subclase de IntegrityError/DataError/OperationalError — así que sin este
    mapeo caía al catch-all -> 500, aunque el dato mal formado sea del cliente.
    `BaseDTO` ya lo bloquea en la frontera; esto es la red de seguridad del
    repositorio para cualquier valor que la esquive."""
    exc = ValueError("A string literal cannot contain NUL (0x00) characters.")

    with pytest.raises(ValidationError) as exc_info:
        raise_from_db_error(exc)

    assert exc_info.value.code == "VALOR_NO_PERMITIDO"
    assert exc_info.value.status_code == 400
