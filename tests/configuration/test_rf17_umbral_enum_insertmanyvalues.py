"""RF-17 — Regresión de los 500 en POST /configuracion/umbrales.

INC-M09-27-G24 (#148), INC-M09-26-G28 (#149) e INC-M09-31-G22 (#158) reportan
que una configuración válida de umbral devuelve HTTP 500 con ``Error inesperado
en base de datos`` y no persiste.

Causa raíz (confirmada contra la base `sgpmp`): la columna
``modulo9.niveles_alerta_ambientales.nivel`` es un ENUM nativo de PostgreSQL,
pero el modelo ORM la mapea como ``String(20)`` (patrón documentado en
CLAUDE.md). Cuando el motor arranca con ``insertmanyvalues`` (comportamiento
por defecto de SQLAlchemy 2.0), el INSERT de los tres niveles de un umbral se
agrupa en una sola sentencia y cada parámetro se castea a ``::VARCHAR``, lo que
PostgreSQL rechaza con ``DatatypeMismatch``. Esa excepción no es
``IntegrityError``/``DataError``/``OperationalError``, así que cae al caso
genérico de ``raise_from_db_error`` y sale como 500.

El fix (``use_insertmanyvalues=False``) ya vive en ``src/shared/database.py``
desde el PR #146. La rama de QA desplegada en TEST (`qa/juan-esteban-m09`)
divergió antes de ese PR y perdió la línea, por eso los tres casos fallaron
8/8 en TEST mientras en `dev` el mismo flujo persiste sin problema.

Este test no reproduce el ``DatatypeMismatch`` (necesita el ENUM real de
PostgreSQL, y la base `pruebas` no tiene el schema `modulo9`), pero fija el
invariante que lo previene: el motor del arranque de la API **debe** desactivar
``insertmanyvalues``. Si alguien lo vuelve a quitar (como ocurrió en la rama de
QA), este test lo delata en CI antes de que vuelva a producción.
"""
from __future__ import annotations

import pytest


def test_el_engine_de_produccion_desactiva_insertmanyvalues() -> None:
    """Fija el guard que evita el DatatypeMismatch sobre columnas ENUM."""
    try:
        from src.shared.database import engine
    except RuntimeError as exc:
        pytest.skip(f"DATABASE_URL no configurada en este entorno: {exc}")

    assert engine.dialect.use_insertmanyvalues is False, (
        "insertmanyvalues debe estar desactivado en el motor de la API. "
        "Con el modo por defecto de SQLAlchemy 2.0, el INSERT agrupado de los "
        "tres niveles de un umbral castea la columna `nivel` (ENUM nativo) a "
        "::VARCHAR y PostgreSQL responde DatatypeMismatch -> HTTP 500 "
        "(INC-M09-27/26/31, PR #146)."
    )


def test_la_columna_nivel_se_mapea_como_string_en_el_orm() -> None:
    """La columna `nivel` es String en el ORM (patrón de CLAUDE.md para ENUM).

    Este es el otro extremo del invariante: como el ORM la declara `String`
    (para no recrear el tipo ENUM en un ALTER TABLE), la protección frente al
    DatatypeMismatch depende exclusivamente de que el motor desactive
    ``insertmanyvalues``. Si esta columna se cambiara a `sa.Enum` con
    `native_enum` real, el test anterior dejaría de ser necesario; mientras
    siga siendo `String`, el guard del motor es imprescindible.
    """
    from sqlalchemy import String

    from src.configuration.infrastructure.models.nivel_alerta_ambiental_model import (
        NivelAlertaAmbientalModel,
    )

    column = NivelAlertaAmbientalModel.__table__.c.nivel
    assert isinstance(column.type, String), (
        "nivel debe seguir mapeado como String (ENUM nativo en la DB); si se "
        "cambia a sa.Enum, revisar la interacción con insertmanyvalues."
    )
