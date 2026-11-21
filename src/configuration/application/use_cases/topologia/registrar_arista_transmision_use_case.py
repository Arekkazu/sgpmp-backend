# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RFC-021 RF-110 C21.1: declarar una arista de transmisión entre áreas |
"""Declara por dónde puede pasar una enfermedad de un área a otra (RF-110). Las dos áreas deben existir,
estar activas, ser accesibles para el usuario y pertenecer a la misma finca."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.arista_transmision import AristaTransmision
from src.configuration.domain.repositories.arista_transmision_repository import AristaTransmisionRepository
from src.configuration.domain.repositories.infraestructura_repository import InfraestructuraRepository
from src.configuration.infrastructure.dto.registrar_arista_transmision_dto import RegistrarAristaTransmisionDTO
from src.shared.errors import BusinessRuleError, NotFoundError


class RegistrarAristaTransmisionUseCase:

    def __init__(self, db: Session, arista_repo: AristaTransmisionRepository,
                 infraestructura_repo: InfraestructuraRepository) -> None:
        self.db = db
        self.arista_repo = arista_repo
        self.infraestructura_repo = infraestructura_repo

    def execute(self, dto: RegistrarAristaTransmisionDTO, id_usuario: int,
                ids_fincas_permitidas: Optional[list[int]] = None) -> AristaTransmision:
        fincas = set()
        for campo in ("id_infraestructura_origen", "id_infraestructura_destino"):
            area = self.infraestructura_repo.obtener_por_id(getattr(dto, campo),
                                                            ids_fincas_permitidas=ids_fincas_permitidas)
            if area is None:
                raise NotFoundError(code="AREA_NO_ENCONTRADA",
                                    message=f"No existe el área {getattr(dto, campo)}.", field=campo)
            if not area.es_activo:
                raise BusinessRuleError(code="AREA_INACTIVA",
                                        message=f"El área {area.id_infraestructura} está inactiva.", field=campo)
            fincas.add(area.id_finca)
        if len(fincas) > 1:
            raise BusinessRuleError(code="AREAS_DE_DISTINTA_FINCA",
                                    message="Las dos áreas de una arista deben ser de la misma finca.",
                                    field="id_infraestructura_destino")

        arista = AristaTransmision.declarar(
            id_infraestructura_origen=dto.id_infraestructura_origen,
            id_infraestructura_destino=dto.id_infraestructura_destino,
            via=dto.via, direccion=dto.direccion, intensidad=dto.intensidad,
            factor_barrera=dto.factor_barrera, descripcion=dto.descripcion, id_usuario=id_usuario,
        )
        try:
            arista = self.arista_repo.guardar(arista)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return arista
