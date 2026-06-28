from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import EventoActivo, EventoProductivo
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.evento_activo_repository import EventoActivoRepository
from src.biological_assets.infrastructure.dto.registrar_evento_productivo_dto import RegistrarEventoProductivoDTO
from src.shared.errors import NotFoundError
from src.identity_access.infrastructure.dependencies import UsuarioActual


class RegistrarEventoProductivoUseCase:

    def __init__(
        self,
        db: Session,
        activo_repo: ActivoBiologicoRepository,
        evento_repo: EventoActivoRepository,
    ) -> None:
        self.db = db
        self.activo_repo = activo_repo
        self.evento_repo = evento_repo

    def execute(self, id_activo: int, dto: RegistrarEventoProductivoDTO, usuario: UsuarioActual) -> EventoActivo:
        activo = self.activo_repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(code='ACTIVO_NO_ENCONTRADO', message=f'El lote con id {id_activo} no existe.')
        activo._validar_tipo_poblacional()

        fecha = dto.fecha or datetime.now(timezone.utc)
        evento = EventoActivo(
            id_activo_biologico=id_activo,
            fecha=fecha,
            id_usuario=usuario.id_usuario,
            descripcion=dto.descripcion,
            productivo=EventoProductivo(
                cantidad=dto.cantidad,
                id_metrica_produccion=dto.id_metrica_produccion,
                id_ciclo_productivo=dto.id_ciclo_productivo,
                condiciones=dto.condiciones,
            ),
        )

        try:
            resultado = self.evento_repo.guardar(evento)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return resultado
