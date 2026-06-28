from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import EventoActivo, EventoBaja
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.evento_activo_repository import EventoActivoRepository
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsultaPort
from src.biological_assets.infrastructure.dto.registrar_evento_baja_dto import RegistrarEventoBajaDTO
from src.shared.errors import NotFoundError
from src.identity_access.infrastructure.dependencies import UsuarioActual


class RegistrarEventoBajaUseCase:

    def __init__(
        self,
        db: Session,
        activo_repo: ActivoBiologicoRepository,
        evento_repo: EventoActivoRepository,
        infra_port: InfraestructuraConsultaPort,
    ) -> None:
        self.db = db
        self.activo_repo = activo_repo
        self.evento_repo = evento_repo
        self.infra_port = infra_port

    def execute(self, id_activo: int, dto: RegistrarEventoBajaDTO, usuario: UsuarioActual) -> EventoActivo:
        activo = self.activo_repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(code='ACTIVO_NO_ENCONTRADO', message=f'El lote con id {id_activo} no existe.')

        # Aplica la baja en la entidad: reduce cantidad_actual, recalcula biomasa
        activo.aplicar_evento_baja(dto.cantidad_afectada)

        # Recalcula densidad con la nueva cantidad
        infra = self.infra_port.obtener_activa(activo.id_infraestructura)
        if infra and infra.superficie and infra.superficie > 0 and activo.detalle_poblacional:
            dp = activo.detalle_poblacional
            dp.densidad = Decimal(str(dp.cantidad_actual or 0)) / infra.superficie

        fecha = dto.fecha or datetime.now(timezone.utc)
        evento = EventoActivo(
            id_activo_biologico=id_activo,
            fecha=fecha,
            id_usuario=usuario.id_usuario,
            descripcion=dto.descripcion,
            baja=EventoBaja(
                cantidad_afectada=dto.cantidad_afectada,
                tipo=dto.tipo,
                detalles=dto.detalles,
            ),
        )

        try:
            resultado = self.evento_repo.guardar(evento)
            self.activo_repo.actualizar_detalle_poblacional(activo)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return resultado
