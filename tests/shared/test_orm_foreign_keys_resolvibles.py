"""Toda FK declarada en el ORM debe apuntar a una tabla mapeada que exista.

INC-M09-64-G31 (#494): `vinculaciones_lecturas`, `alertas` y `reglas_alertas`
declaraban FKs a `modulo3.telemetria` y `modulo9.infraestructura` (en singular;
las tablas son `telemetrias` e `infraestructuras`). SQLAlchemy no lo detecta al
importar: falla al hacer flush (`NoReferencedTableError`), y en la ingesta ese
error se descartaba como warning, así que la vinculación nunca se guardaba.
"""
from __future__ import annotations

import importlib
import pkgutil

import src
from src.shared.base_model import Base


def test_todas_las_fk_del_orm_resuelven() -> None:
    for modulo in pkgutil.walk_packages(src.__path__, "src."):
        if ".infrastructure.models." in modulo.name:
            importlib.import_module(modulo.name)

    rotas = []
    for tabla in Base.metadata.tables.values():
        for fk in tabla.foreign_keys:
            try:
                fk.column
            except Exception:  # NoReferencedTableError / NoReferencedColumnError
                rotas.append(f"{tabla.fullname} -> {fk.target_fullname}")

    assert rotas == []
