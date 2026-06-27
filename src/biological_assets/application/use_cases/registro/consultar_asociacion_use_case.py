from __future__ import annotations

from typing import Optional, Union

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import HistorialInfraestructura
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.shared.errors import NotFoundError, ValidationError


class ConsultarAsociacionUseCase:

    def __init__(self, db: Session, repo: ActivoBiologicoRepository) -> None:
        self.db = db
        self.repo = repo

    def execute(
        self,
        id_activo: int,
        tipo_consulta: str,
    ) -> Union[Optional[HistorialInfraestructura], list[HistorialInfraestructura]]:
        if tipo_consulta not in ('ACTIVA', 'HISTORIAL'):
            raise ValidationError(
                code='TIPO_CONSULTA_INVALIDO',
                message="tipo_consulta debe ser 'ACTIVA' o 'HISTORIAL'.",
                field='tipo_consulta',
            )

        activo = self.repo.obtener_por_id(id_activo)
        if not activo:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f"No existe un activo biológico con id {id_activo}.",
            )

        if tipo_consulta == 'ACTIVA':
            return self.repo.obtener_asociacion_activa(id_activo)

        return self.repo.obtener_historial_infraestructura(id_activo)
