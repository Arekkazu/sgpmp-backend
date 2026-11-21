# | Fecha      | Nombre       | Que se hizo                                                                  |
# |------------|--------------|------------------------------------------------------------------------------|
# | 2026-11-21 | destroyerban | INC-M08-379-G001 RF-103: widgets técnicos de IoT solo para Ingeniero y Admin |
"""INC-M08-379-G001 (#1195) contra PostgreSQL con la migración ``046abf6dbaa9``.

Los widgets técnicos de IoT (estado, calibraciones, configuración pendiente y dispositivos sin
comunicación) son del Ingeniero de Campo y del Administrador (RF-103 / RF-60). El catálogo, el PATCH y
los datos del widget filtran con ``ids_legibles_por_rol``: basta con que ese filtro los excluya.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.configuration.infrastructure.repositories.widget_repository import SqlAlchemyWidgetRepository

pytestmark = pytest.mark.integration

TECNICOS = {"estado_iot", "cal_sensores", "cfg_pendiente", "dispositivos_sin_senal"}


def _id_rol(db: Session, nombre: str) -> int:
    return db.execute(text("SELECT id_rol FROM modulo1.roles WHERE nombre_rol = :n"), {"n": nombre}).scalar_one()


def _claves_legibles(db: Session, rol: str) -> set[str]:
    repo = SqlAlchemyWidgetRepository(db)
    ids = repo.ids_legibles_por_rol(_id_rol(db, rol))
    return {w.clave for w in repo.obtener_activos() if w.id_widget in ids}


@pytest.mark.parametrize("rol", ["Productor", "Veterinario", "Contador"])
def test_roles_no_tecnicos_no_reciben_widgets_de_iot(db_session: Session, rol: str):
    legibles = _claves_legibles(db_session, rol)
    assert legibles, f"el catálogo de {rol} no debería quedar vacío"
    assert not legibles & TECNICOS


@pytest.mark.parametrize("rol", ["Ingeniero de Campo", "Administrador"])
def test_ingeniero_y_administrador_conservan_los_widgets_de_iot(db_session: Session, rol: str):
    assert TECNICOS <= _claves_legibles(db_session, rol)


def test_el_productor_conserva_sus_widgets_de_dashboard(db_session: Session):
    legibles = _claves_legibles(db_session, "Productor")
    assert {"semaforo_areas", "temp_galpon", "valor_inventario", "inventario_especies"} <= legibles


def test_ningun_predeterminado_trae_widgets_que_el_rol_no_lee(db_session: Session):
    filas = db_session.execute(text("SELECT id_rol, active_widget FROM modulo9.dashboard_layouts_default")).all()
    repo = SqlAlchemyWidgetRepository(db_session)
    clave_a_id = {w.clave: w.id_widget for w in repo.obtener_activos()}
    for id_rol, activos in filas:
        tecnicos = set(activos) & TECNICOS
        assert {clave_a_id[c] for c in tecnicos} <= repo.ids_legibles_por_rol(id_rol), id_rol
