"""RF-16: el nombre de una métrica productiva es único por especie, no global.

`trg_fn_metricas_produccion_nombre_unique_ci` rechazaba "Peso vivo" en una
especie porque otra ya la tenía (P0109). La migración `3a9d5e7c1b24` agrega el
filtro por especie. Requiere la base de integración en `alembic upgrade head`.
"""
from __future__ import annotations

import random
import string
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.integration


def _crear_especie(db_session) -> int:
    sid = uuid.uuid4().int % (10**9)
    nombre = "Especie " + "".join(random.choices(string.ascii_letters, k=12))
    db_session.execute(
        text(
            "INSERT INTO modulo9.especies (id_especie, nombre, fecha_creacion, es_activo, grupo_manejo) "
            "VALUES (:id, :nombre, now(), TRUE, 'ACUICULTURA')"
        ),
        {"id": sid, "nombre": nombre},
    )
    return sid


def _crear_metrica(db_session, nombre: str, id_especie: int) -> None:
    db_session.execute(
        text(
            "INSERT INTO modulo9.metricas_produccion "
            "(nombre, unidad_medida, tipo_medicion, tiene_estado, id_especie) "
            "VALUES (:nombre, 'g', 'PESO', FALSE, :id_especie)"
        ),
        {"nombre": nombre, "id_especie": id_especie},
    )
    db_session.flush()


def test_mismo_nombre_en_otra_especie_se_permite_y_en_la_misma_no(db_session):
    nombre = "Peso vivo " + "".join(random.choices(string.ascii_lowercase, k=8))
    especie_a, especie_b = _crear_especie(db_session), _crear_especie(db_session)

    _crear_metrica(db_session, nombre, especie_a)
    _crear_metrica(db_session, nombre.upper(), especie_b)

    with pytest.raises(DBAPIError, match="DUPLICATE_METRIC"):
        with db_session.begin_nested():
            _crear_metrica(db_session, f"  {nombre.lower()} ", especie_a)
