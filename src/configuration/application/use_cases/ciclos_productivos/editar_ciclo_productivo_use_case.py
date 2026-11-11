# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | #512 RF-16/RF-37: ciclos productivos de la especie con sus fases en orden |
"""Editar un ciclo productivo; con activos que ya lo usan solo cambia el nombre (RF-37)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.application.use_cases.ciclos_productivos._fases import resolver_fases
from src.configuration.application.use_cases.ciclos_productivos.registrar_ciclo_productivo_use_case import (
    nombre_duplicado,
)
from src.configuration.domain.entities.ciclo_productivo import CicloProductivo
from src.configuration.domain.repositories.ciclo_biologico_repository import CicloBiologicoRepository
from src.configuration.domain.repositories.ciclo_productivo_repository import CicloProductivoRepository
from src.shared.errors import NotFoundError


def obtener_o_404(ciclos: CicloProductivoRepository, id_ciclo_productivo: int) -> CicloProductivo:
    ciclo = ciclos.obtener(id_ciclo_productivo)
    if ciclo is None:
        raise NotFoundError(code="CICLO_PRODUCTIVO_NO_ENCONTRADO", message="El ciclo productivo no existe.")
    return ciclo


class EditarCicloProductivoUseCase:
    def __init__(self, db: Session, ciclos: CicloProductivoRepository, etapas: CicloBiologicoRepository) -> None:
        self.db, self.ciclos, self.etapas = db, ciclos, etapas

    def execute(self, id_ciclo_productivo: int, nombre: str, ids_etapas: list[int]) -> CicloProductivo:
        ciclo = obtener_o_404(self.ciclos, id_ciclo_productivo)
        fases = (ciclo.fases if ids_etapas == [f.id_ciclo_biologico for f in ciclo.fases]  # una etapa ya inactiva sigue
                 else resolver_fases(self.etapas, ciclo.id_especie, ids_etapas))
        ciclo.redefinir(nombre, fases)
        if self.ciclos.existe_nombre(ciclo.id_especie, ciclo.nombre, excluir=id_ciclo_productivo):
            raise nombre_duplicado(ciclo.nombre)
        try:
            ciclo = self.ciclos.guardar(ciclo)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return ciclo
