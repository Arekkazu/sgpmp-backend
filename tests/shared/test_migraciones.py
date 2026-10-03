"""INC-M02-51-G44: el arranque avisa si la BD quedó atrás de las migraciones del código."""
from __future__ import annotations

import logging

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from src.shared import migraciones


def _heads_del_codigo() -> list[str]:
    config = Config()
    config.set_main_option("script_location", str(migraciones._DIRECTORIO_ALEMBIC))
    return list(ScriptDirectory.from_config(config).get_heads())


def test_avisa_si_la_bd_no_tiene_las_migraciones_del_codigo(caplog) -> None:
    engine = create_engine("sqlite://")

    with caplog.at_level(logging.ERROR, logger=migraciones.__name__):
        migraciones.verificar_migraciones_aplicadas(engine)

    assert "alembic upgrade head" in caplog.text


def test_no_avisa_si_la_bd_esta_al_dia(caplog) -> None:
    engine = create_engine("sqlite://")
    with engine.begin() as conexion:
        conexion.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)"))
        for head in _heads_del_codigo():
            conexion.execute(text("INSERT INTO alembic_version VALUES (:v)"), {"v": head})

    with caplog.at_level(logging.WARNING, logger=migraciones.__name__):
        migraciones.verificar_migraciones_aplicadas(engine)

    assert caplog.records == []


def test_una_bd_inaccesible_no_tumba_el_arranque(caplog) -> None:
    engine = create_engine("postgresql://sgpmp:sgpmp@127.0.0.1:1/inexistente")

    with caplog.at_level(logging.WARNING, logger=migraciones.__name__):
        migraciones.verificar_migraciones_aplicadas(engine)

    assert "No se pudo verificar" in caplog.text
