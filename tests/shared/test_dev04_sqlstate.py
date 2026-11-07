"""DEV-04: contexto verificable, contratos HTTP y aislamiento de colisiones."""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg2 import errors as pg_errors
from sqlalchemy.exc import InternalError

from src.shared.db_error_translator import raise_from_db_error
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import AppError, InfrastructureError


CASOS = [
    ("P0001", "modulo3.fn_validar_timestamp_telemetria", "RF-53 [ERROR_TIEMPO]", "ERROR_TIEMPO", 400),
    ("P0002", "modulo3.fn_telemetrias_inmutable", "RF-53 [INMUTABILIDAD]", "TELEMETRIA_INMUTABLE", 422),
    ("P0005", "modulo3.fn_alerta_validar_transicion", "RF-57 [TRANSICION_INVALIDA]", "TRANSICION_INVALIDA", 422),
    ("P0413", "modulo4.trg_fn_predicciones_version_modelo_activo", "MODEL_NOT_ACTIVE: secreto", "MODELO_NO_ACTIVO", 412),
    ("P0413", "modulo4.trg_fn_predicciones_version_modelo_activo", "MODEL_NOT_FOUND: secreto", "VERSION_MODELO_NO_ENCONTRADA", 404),
]


def error_pg(sqlstate, funcion, mensaje, *, contexto=None, pgcode_only=False):
    diag = SimpleNamespace(
        sqlstate=None if pgcode_only else sqlstate,
        context=contexto if contexto is not None else f"PL/pgSQL function {funcion}() line 7 at RAISE",
        message_primary=mensaje,
    )
    try:
        clase = pg_errors.lookup(sqlstate)
    except KeyError:
        clase = pg_errors.InternalError_
    return type("ErrorDriver", (clase,), {"diag": diag, "pgcode": sqlstate})()


@pytest.mark.parametrize("sqlstate,funcion,mensaje,codigo,http", CASOS)
@pytest.mark.parametrize("envoltura", [False, True])
def test_traduce_driver_y_sqlalchemy(sqlstate, funcion, mensaje, codigo, http, envoltura):
    original = error_pg(sqlstate, funcion, mensaje)
    exc = InternalError("SQL secreto", {"clave": "secreto"}, original) if envoltura else original
    with pytest.raises(AppError) as result:
        raise_from_db_error(exc)
    assert (result.value.code, result.value.status_code) == (codigo, http)
    assert "secreto" not in result.value.message
    assert result.value.__cause__ is exc


@pytest.mark.parametrize("sqlstate,funcion,mensaje", [
    ("P0001", "modulo1.trg_fn_no_reutilizar_contrasena", "RF-53 [ERROR_TIEMPO]"),
    ("P0001", "modulo6.trg_periodo", "RF-53 [ERROR_TIEMPO]"),
    ("P0002", "modulo1.trg_fn_proteger_auditoria", "RF-53 [INMUTABILIDAD]"),
    ("P0005", "modulo1.trg_fn_bloquear_eliminacion_rol_en_uso", "ROLE_IN_USE"),
    ("P0413", "modulo4.otra_funcion", "MODEL_NOT_ACTIVE: secreto"),
    ("P0413", "modulo4.trg_fn_predicciones_version_modelo_activo", "OTRO: secreto"),
    ("P0999", "modulo3.fn_validar_timestamp_telemetria", "RF-53 [ERROR_TIEMPO]"),
])
def test_no_reclasifica_otras_reglas(sqlstate, funcion, mensaje):
    with pytest.raises(InfrastructureError) as result:
        raise_from_db_error(InternalError("stmt", {}, error_pg(sqlstate, funcion, mensaje)))
    assert result.value.code == "ERROR_INTERNO"


def test_sin_contexto_no_se_confia_en_el_mensaje():
    with pytest.raises(InfrastructureError):
        raise_from_db_error(error_pg("P0001", "", "RF-53 [ERROR_TIEMPO]", contexto=""))


def test_pgcode_como_respaldo():
    with pytest.raises(AppError) as result:
        raise_from_db_error(error_pg("P0001", CASOS[0][1], "detalle", pgcode_only=True))
    assert result.value.code == "ERROR_TIEMPO"


@pytest.mark.parametrize("funcion_origen", ["modulo1.otra_funcion", "otra_funcion"])
def test_no_confunde_funcion_exterior_con_origen_del_error(funcion_origen):
    contexto = (
        f"PL/pgSQL function {funcion_origen}() line 1 at RAISE\n"
        "PL/pgSQL function modulo3.fn_validar_timestamp_telemetria() line 7 at SQL statement"
    )
    with pytest.raises(InfrastructureError):
        raise_from_db_error(error_pg("P0001", "", "RF-53 [ERROR_TIEMPO]", contexto=contexto))


@pytest.mark.parametrize("sqlstate,funcion,mensaje,codigo,http", CASOS)
@pytest.mark.parametrize("via", ["sqlalchemy", "driver", "dominio"])
def test_handler_http_respeta_contrato(sqlstate, funcion, mensaje, codigo, http, via):
    app = FastAPI()
    register_error_handlers(app)

    @app.post("/prueba")
    def operacion():
        original = error_pg(sqlstate, funcion, mensaje)
        exc = original if via == "driver" else InternalError("SQL secreto", {}, original)
        if via == "dominio":
            raise_from_db_error(exc)
        raise exc

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/prueba")
    assert response.status_code == http
    assert response.json()["error_code"] == codigo
    assert set(response.json()) == {"error_code", "message", "fields", "timestamp"}
    assert "secreto" not in response.text


def test_error_desconocido_http_conserva_500_seguro():
    app = FastAPI()
    register_error_handlers(app)

    @app.post("/desconocido")
    def operacion():
        raise InternalError("SQL secreto", {}, error_pg("P0999", "modulo3.desconocida", "secreto"))

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/desconocido")
    assert response.status_code == 500
    assert response.json()["error_code"] == "ERROR_INTERNO"
    assert "secreto" not in response.text and "P0999" not in response.text
