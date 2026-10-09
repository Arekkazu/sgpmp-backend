"""El contexto RLS del request sobrevive a los commit() de la misma sesión.

INC-M09-104-G29: el use case de umbrales hace un segundo commit (estado de
sincronización con el Edge) y, sin identidad, la política UPDATE de
``modulo9.umbrales_ambientales`` filtraba la fila: 0 filas, en silencio. Acá se
verifica ``declarar_identidad`` (``src/shared/database.py``) con SQLite y una ``set_config`` falsa que registra cada
llamada; que ``set_config(..., true)`` no se filtre entre conexiones del pool
lo cubre ``tests/integration/test_control_acceso_f2_contexto_sesion_no_fuga.py``.
"""
from __future__ import annotations

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from src.shared.database import declarar_identidad


def _engine_con_set_config(llamadas: list[tuple]):
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _registrar_set_config(conexion_dbapi, _registro):
        def set_config(nombre, valor, local):
            llamadas.append((nombre, valor, local))
            return valor

        conexion_dbapi.create_function("set_config", 3, set_config)

    return engine


def test_se_vuelve_a_declarar_en_cada_transaccion_de_la_sesion() -> None:
    llamadas: list[tuple] = []
    with Session(_engine_con_set_config(llamadas)) as db:
        declarar_identidad(db, 7, "Veterinario")
        db.commit()
        llamadas.clear()

        db.execute(text("SELECT 1"))  # transacción nueva tras el commit

        assert sorted(llamadas) == [
            ("app.current_role", "Veterinario", 1),
            ("app.current_user_id", "7", 1),
            ("app.usuario_id", "7", 1),
        ]


def test_sigue_siendo_local_a_la_transaccion() -> None:
    llamadas: list[tuple] = []
    with Session(_engine_con_set_config(llamadas)) as db:
        declarar_identidad(db, 1, "Administrador")
        db.execute(text("SELECT 1"))  # sin transacción abierta, se aplica al empezar la siguiente

    assert llamadas and all(local == 1 for *_, local in llamadas)


def test_una_sesion_sin_contexto_no_declara_nada() -> None:
    llamadas: list[tuple] = []
    with Session(_engine_con_set_config(llamadas)) as db:
        db.execute(text("SELECT 1"))
        db.commit()
        db.execute(text("SELECT 1"))

    assert llamadas == []


def test_el_contexto_no_pasa_a_otra_sesion() -> None:
    llamadas: list[tuple] = []
    engine = _engine_con_set_config(llamadas)
    with Session(engine) as db:
        declarar_identidad(db, 1, "Administrador")
        db.commit()
    llamadas.clear()

    with Session(engine) as otra:
        otra.execute(text("SELECT 1"))

    assert llamadas == []
