# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | #512 RF-16/RF-37: ciclos productivos de la especie con sus fases en orden |
"""Registrar un ciclo productivo: nombre único en la especie y fases en orden (RF-16, RF-37)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.application.use_cases.ciclos_productivos._fases import resolver_fases
from src.configuration.domain.entities.ciclo_productivo import CicloProductivo
from src.configuration.domain.repositories.ciclo_biologico_repository import CicloBiologicoRepository
from src.configuration.domain.repositories.ciclo_productivo_repository import CicloProductivoRepository
from src.configuration.domain.repositories.especie_repository import EspecieRepository
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError


def nombre_duplicado(nombre: str) -> ConflictError:
    return ConflictError(code="CICLO_PRODUCTIVO_DUPLICADO", field="nombre",
                         message=f"La especie ya tiene un ciclo productivo llamado «{nombre}».")


class RegistrarCicloProductivoUseCase:
    def __init__(self, db: Session, ciclos: CicloProductivoRepository, etapas: CicloBiologicoRepository,
                 especies: EspecieRepository) -> None:
        self.db, self.ciclos, self.etapas, self.especies = db, ciclos, etapas, especies

    def execute(self, id_especie: int, nombre: str, ids_etapas: list[int]) -> CicloProductivo:
        especie = self.especies.obtener_por_id(id_especie)
        if especie is None:
            raise NotFoundError(code="ESPECIE_NO_ENCONTRADA", message="La especie no existe.")
        if not especie.es_activo:
            raise BusinessRuleError(code="ESPECIE_INACTIVA",
                                    message="La especie está inactiva: no se le pueden agregar ciclos productivos.")
        ciclo = CicloProductivo.crear(nombre, id_especie, resolver_fases(self.etapas, id_especie, ids_etapas))
        if self.ciclos.existe_nombre(id_especie, ciclo.nombre):
            raise nombre_duplicado(ciclo.nombre)
        try:
            ciclo = self.ciclos.guardar(ciclo)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return ciclo
