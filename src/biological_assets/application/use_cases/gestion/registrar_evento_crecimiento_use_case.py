from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import EventoActivo, EventoCrecimiento
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.evento_activo_repository import EventoActivoRepository
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsultaPort
from src.biological_assets.infrastructure.dto.registrar_evento_crecimiento_dto import RegistrarEventoCrecimientoDTO
from src.shared.errors import NotFoundError
from src.identity_access.infrastructure.dependencies import UsuarioActual


class RegistrarEventoCrecimientoUseCase:

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

    def execute(self, id_activo: int, dto: RegistrarEventoCrecimientoDTO, usuario: UsuarioActual) -> EventoActivo:
        activo = self.activo_repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(code='ACTIVO_NO_ENCONTRADO', message=f'El lote con id {id_activo} no existe.')

        infra = self.infra_port.obtener_activa(activo.id_infraestructura)

        # Aplica el evento en la entidad: actualiza peso_promedio, biomasa_total y densidad
        superficie = infra.superficie if infra and infra.superficie else None
        activo.aplicar_evento_crecimiento(
            nuevo_peso_promedio=dto.valor_medicion,
            superficie=superficie,
        )

        fecha = dto.fecha or datetime.now(timezone.utc)
        evento = EventoActivo(
            id_activo_biologico=id_activo,
            fecha=fecha,
            id_usuario=usuario.id_usuario,
            descripcion=dto.descripcion,
            crecimiento=EventoCrecimiento(
                tipo_medicion=dto.tipo_medicion,
                valor_medicion=dto.valor_medicion,
                unidad_medida=dto.unidad_medida,
                tipo_agregacion=dto.tipo_agregacion,
                frecuencia=dto.frecuencia,
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
