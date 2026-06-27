"""Caso de uso: Consultar áreas productivas (GET RF-20).

El DFD (paso 06) exige registrar auditoría tipo GET al listar.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.infraestructura import Infraestructura
from src.configuration.domain.repositories.auditoria_infraestructura_repository import AuditoriaInfraestructuraRepository
from src.configuration.domain.repositories.infraestructura_repository import InfraestructuraRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError


class ConsultarInfraestructurasUseCase:

    def __init__(
        self,
        db: Session,
        infra_repo: InfraestructuraRepository,
        auditoria_repo: AuditoriaInfraestructuraRepository,
    ) -> None:
        self.db = db
        self.infra_repo = infra_repo
        self.auditoria_repo = auditoria_repo

    def listar_por_finca(
        self, id_finca: int, usuario_actual: UsuarioActual, *, solo_activas: bool = False
    ) -> list[Infraestructura]:
        items = self.infra_repo.listar_por_finca(id_finca, solo_activas=solo_activas)
        snapshot = {"id_finca": id_finca, "total": len(items), "solo_activas": solo_activas}
        for infra in items:
            try:
                self.auditoria_repo.registrar(
                    id_infraestructura=infra.id_infraestructura,
                    id_usuario=usuario_actual.id_usuario,
                    tipo_operacion="GET",
                    valores_nuevos=snapshot,
                )
            except Exception:
                pass
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
        return items

    def obtener(self, id_infraestructura: int) -> Infraestructura:
        infra = self.infra_repo.obtener_por_id(id_infraestructura)
        if infra is None:
            raise NotFoundError(
                code="INFRAESTRUCTURA_NO_ENCONTRADA",
                message=f"No existe un área productiva con ID {id_infraestructura}.",
            )
        return infra
