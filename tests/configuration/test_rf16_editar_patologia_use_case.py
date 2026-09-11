"""RF-16 / #1633 — Editar patología por especie.

Verifica con fakes (sin BD):
- independencia por especie: editar la patología de una especie no afecta a otra;
- concurrencia optimista (412) con fecha_actualizacion desfasada;
- renombrar hacia un nombre ya usado en la misma especie es rechazado (409).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.configuration.application.use_cases.patologias.editar_patologia_use_case import (
    EditarPatologiaUseCase,
)
from src.configuration.domain.entities.especie_patologia import EspeciePatologia
from src.configuration.domain.value_objects.nombre_patologia import NombrePatologia
from src.configuration.infrastructure.dto.editar_patologia_dto import EditarPatologiaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import ConflictError, PreconditionFailedError

USUARIO = UsuarioActual(id_usuario=1, id_token=1, id_rol=1)
TS_DB = datetime(2026, 5, 10, 8, 0, tzinfo=timezone.utc)


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class EspeciePatologiaRepoFake:
    def __init__(self, rows: list[EspeciePatologia]) -> None:
        self.rows = {r.id_especies_patologias: r for r in rows}

    def obtener_por_id(self, id_ep):
        return self.rows.get(id_ep)

    def obtener_por_especie_y_nombre(self, id_especie, nombre):
        for r in self.rows.values():
            if r.id_especie == id_especie and r.nombre.normalizado() == nombre.normalizado():
                return r
        return None

    def actualizar(self, entidad: EspeciePatologia) -> EspeciePatologia:
        self.rows[entidad.id_especies_patologias] = entidad
        return entidad


class AuditoriaFake:
    def registrar(self, **kwargs) -> None:
        pass


def _row(id_ep, id_especie, nombre, descripcion=None) -> EspeciePatologia:
    return EspeciePatologia(
        id_especies_patologias=id_ep,
        id_especie=id_especie,
        nombre=NombrePatologia(nombre),
        es_activo=True,
        descripcion=descripcion,
        fecha_actualizacion=TS_DB,
    )


def test_edicion_por_especie_es_independiente():
    row_a = _row(1, 10, "Mastitis", "desc-A")
    row_b = _row(2, 20, "Mastitis", "desc-B")
    repo = EspeciePatologiaRepoFake([row_a, row_b])
    uc = EditarPatologiaUseCase(db=DbFake(), especie_patologia_repo=repo, auditoria_repo=AuditoriaFake())

    uc.execute(1, EditarPatologiaDTO(nombre="Mastitis", descripcion="nueva-A", fecha_actualizacion=TS_DB), USUARIO)

    assert repo.rows[1].descripcion == "nueva-A"
    assert repo.rows[2].descripcion == "desc-B"  # la otra especie no cambia


def test_concurrencia_desfasada_412():
    repo = EspeciePatologiaRepoFake([_row(1, 10, "Mastitis")])
    uc = EditarPatologiaUseCase(db=DbFake(), especie_patologia_repo=repo, auditoria_repo=AuditoriaFake())

    with pytest.raises(PreconditionFailedError) as exc:
        uc.execute(
            1,
            EditarPatologiaDTO(nombre="Mastitis", fecha_actualizacion=datetime(2026, 1, 1, tzinfo=timezone.utc)),
            USUARIO,
        )
    assert exc.value.code == "CONFLICTO_CONCURRENCIA"


def test_renombrar_a_nombre_existente_en_especie_conflicto():
    repo = EspeciePatologiaRepoFake([_row(1, 10, "Mastitis"), _row(3, 10, "Cojera")])
    uc = EditarPatologiaUseCase(db=DbFake(), especie_patologia_repo=repo, auditoria_repo=AuditoriaFake())

    with pytest.raises(ConflictError) as exc:
        uc.execute(1, EditarPatologiaDTO(nombre="Cojera", fecha_actualizacion=TS_DB), USUARIO)
    assert exc.value.code == "PATOLOGIA_DUPLICADA_EN_ESPECIE"
