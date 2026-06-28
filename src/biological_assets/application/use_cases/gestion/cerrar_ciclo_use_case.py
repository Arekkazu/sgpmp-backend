from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import HistoricoEstado
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.evento_activo_repository import EventoActivoRepository
from src.biological_assets.domain.repositories.historico_estado_repository import HistoricoEstadoRepository
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.cerrar_ciclo_dto import CerrarCicloDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationError


class CerrarCicloUseCase:
    def __init__(
        self,
        db: Session,
        repo: ActivoBiologicoRepository,
        evento_repo: EventoActivoRepository,
        historico_repo: HistoricoEstadoRepository,
    ) -> None:
        self.db = db
        self.repo = repo
        self.evento_repo = evento_repo
        self.historico_repo = historico_repo

    def execute(self, id_activo: int, dto: CerrarCicloDTO, usuario: UsuarioActual) -> HistoricoEstado:
        # FA-01: activo debe existir
        activo = self.repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con ID {id_activo} no existe.',
            )

        # FA-02: estado debe permitir transición a CERRADO
        if activo.id_estado in (EstadoActivo.CERRADO, EstadoActivo.BAJA):
            nombre = 'CERRADO' if activo.id_estado == EstadoActivo.CERRADO else 'BAJA'
            raise ConflictError(
                code='ESTADO_INVALIDO_PARA_CIERRE',
                message=(
                    f'El activo biológico ya se encuentra en estado {nombre}. '
                    'No es posible realizar un nuevo cierre de ciclo.'
                ),
            )

        # FA-06: no debe tener sensores IoT activos
        if self.repo.tiene_sensores_activos(id_activo):
            raise BusinessRuleError(
                code='SENSORES_ACTIVOS',
                message=(
                    'El activo tiene sensores IoT vinculados activos. '
                    'Desvincule los sensores antes de cerrar el ciclo productivo.'
                ),
            )

        # FA-05: debe tener al menos una fase productiva activa
        fase_activa = self.repo.obtener_fase_activa(id_activo)
        if fase_activa is None:
            raise BusinessRuleError(
                code='SIN_FASE_ACTIVA',
                message=(
                    'El activo no presenta una fase productiva activa. '
                    'Verifique la integridad del ciclo de vida antes de cerrar.'
                ),
            )

        # FA-04: validar fecha contra último evento registrado
        ultima_fecha_evento = self.evento_repo.obtener_ultima_fecha(id_activo)
        if ultima_fecha_evento is not None:
            ultimo_dia_evento = ultima_fecha_evento.date() if isinstance(ultima_fecha_evento, datetime) else ultima_fecha_evento
            if dto.fecha_cierre < ultimo_dia_evento:
                raise ValidationError(
                    code='FECHA_CIERRE_ANTERIOR_ULTIMO_EVENTO',
                    message=(
                        f'La fecha de cierre no puede ser anterior al último registro de actividad '
                        f'del activo ({ultimo_dia_evento.isoformat()}).'
                    ),
                    field='fecha_cierre',
                )

        id_estado_anterior = activo.id_estado
        activo.cambiar_estado(EstadoActivo.CERRADO)

        motivo_completo = dto.motivo_cierre
        if dto.descripcion_cierre:
            motivo_completo = f'{dto.motivo_cierre} — {dto.descripcion_cierre}'

        fecha_cierre_dt = datetime.combine(dto.fecha_cierre, datetime.min.time()).replace(tzinfo=timezone.utc)

        try:
            # Cerrar fase primero: el trigger trg_fn_fase_activo_estado_valido bloquea
            # cambios en gestiones_fases si el activo ya está en CERRADO.
            self.repo.cerrar_gestion_activa(id_activo, fecha_cierre_dt, motivo_completo, usuario.id_usuario)
            # El INSERT dispara trg_sincronizar_estado_activo que actualiza activos_biologicos.id_estado
            historico = self.historico_repo.registrar(
                id_activo=id_activo,
                id_estado_anterior=id_estado_anterior,
                id_estado_nuevo=EstadoActivo.CERRADO,
                fecha=fecha_cierre_dt,
                motivo=motivo_completo,
                usuario_id=usuario.id_usuario,
                modulo_origen='modulo2',
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return historico
