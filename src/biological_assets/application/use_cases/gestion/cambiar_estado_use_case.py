from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import HistoricoEstado
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.historico_estado_repository import HistoricoEstadoRepository
from src.biological_assets.infrastructure.dto.cambiar_estado_dto import CambiarEstadoDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError


class CambiarEstadoUseCase:
    def __init__(
        self,
        db: Session,
        repo: ActivoBiologicoRepository,
        historico_repo: HistoricoEstadoRepository,
    ) -> None:
        self.db = db
        self.repo = repo
        self.historico_repo = historico_repo

    def execute(self, id_activo: int, dto: CambiarEstadoDTO, usuario: UsuarioActual) -> HistoricoEstado:
        activo = self.repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con ID {id_activo} no existe.',
            )

        id_estado_anterior = activo.id_estado
        # cambiar_estado valida BAJA irreversible, estado redundante y matriz de transiciones
        activo.cambiar_estado(dto.id_estado_nuevo)

        fecha = datetime.combine(dto.fecha_cambio_estado, datetime.min.time()).replace(tzinfo=timezone.utc)

        try:
            # El INSERT dispara trg_sincronizar_estado_activo que actualiza activos_biologicos.id_estado
            historico = self.historico_repo.registrar(
                id_activo=id_activo,
                id_estado_anterior=id_estado_anterior,
                id_estado_nuevo=dto.id_estado_nuevo,
                fecha=fecha,
                motivo=dto.motivo_cambio,
                usuario_id=usuario.id_usuario,
                modulo_origen='modulo2',
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return historico
