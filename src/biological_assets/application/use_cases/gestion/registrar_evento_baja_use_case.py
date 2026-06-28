from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases.gestion._event_validations import (
    validar_estado_permite_eventos,
    validar_fecha_evento,
)
from src.biological_assets.domain.entities.activo_biologico import EventoActivo, EventoBaja
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.evento_activo_repository import EventoActivoRepository
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsultaPort
from src.biological_assets.infrastructure.dto.registrar_evento_baja_dto import RegistrarEventoBajaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError


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
            raise NotFoundError(code='ACTIVO_NO_ENCONTRADO', message=f'El activo biológico con id {id_activo} no existe.')

        # RF-39: ACTIVO, EN_TRATAMIENTO y AISLADO permiten eventos de baja
        validar_estado_permite_eventos(activo)

        fecha = dto.fecha or datetime.now(timezone.utc)
        validar_fecha_evento(fecha, activo, self.evento_repo)

        # La baja de cantidad solo aplica a activos POBLACIONAL
        activo.aplicar_evento_baja(dto.cantidad_afectada)

        infra = self.infra_port.obtener_activa(activo.id_infraestructura)
        if infra and infra.superficie and infra.superficie > 0 and activo.detalle_poblacional:
            dp = activo.detalle_poblacional
            dp.densidad = Decimal(str(dp.cantidad_actual or 0)) / infra.superficie

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
