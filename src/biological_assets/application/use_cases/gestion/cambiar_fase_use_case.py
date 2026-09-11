from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria, GestionFase
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.ciclo_consulta_port import CicloConsultaPort
from src.biological_assets.infrastructure.dto.cambiar_fase_dto import CambiarFaseDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, NotFoundError, ValidationError


class CambiarFaseUseCase:
    def __init__(
        self,
        db: Session,
        repo: ActivoBiologicoRepository,
        ciclo_port: CicloConsultaPort,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.repo = repo
        self.ciclo_port = ciclo_port
        self.bitacora_repo = bitacora_repo

    def execute(self, id_activo: int, dto: CambiarFaseDTO, usuario: UsuarioActual) -> GestionFase:
        # FA-01: activo debe existir
        activo = self.repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con ID {id_activo} no existe.',
            )

        # FA-02: ciclo productivo debe existir y tener fases
        ciclo = self.ciclo_port.obtener_ciclo_con_fases(dto.id_ciclo_productiva)
        if ciclo is None:
            raise ValidationError(
                code='CICLO_INVALIDO',
                message=f'El ciclo productivo con ID {dto.id_ciclo_productiva} no existe.',
                field='id_ciclo_productiva',
            )
        if not ciclo.fases:
            raise ValidationError(
                code='CICLO_SIN_FASES',
                message=f'El ciclo productivo "{ciclo.nombre}" no tiene fases biológicas configuradas.',
                field='id_ciclo_productiva',
            )

        # FA-03: determinar la siguiente fase en la secuencia
        gestiones = self.repo.obtener_gestiones_fases(id_activo)
        gestiones_en_ciclo = [g for g in gestiones if g.id_ciclo_productiva == dto.id_ciclo_productiva]
        fase_siguiente_idx = len(gestiones_en_ciclo)  # 0-based

        if fase_siguiente_idx >= len(ciclo.fases):
            raise BusinessRuleError(
                code='CICLO_COMPLETADO',
                message=(
                    f'El activo ya completó todas las fases del ciclo "{ciclo.nombre}". '
                    'No es posible avanzar más en este ciclo.'
                ),
            )

        fase_actual = ciclo.fases[fase_siguiente_idx]
        ahora = dto.fecha_inicio or datetime.now(timezone.utc)

        try:
            # Cerrar fase activa actual si existe (antes de insertar la nueva, por el trigger)
            self.repo.cerrar_gestion_activa(id_activo, ahora, dto.motivo_cambio or '')

            nueva_gestion = GestionFase(
                id_gestion_fases=None,
                id_activo_biologico=id_activo,
                id_ciclo_productiva=dto.id_ciclo_productiva,
                nombre_ciclo=ciclo.nombre,
                nombre_fase_actual=fase_actual.nombre_fase,
                paso_actual=fase_siguiente_idx + 1,
                total_pasos=len(ciclo.fases),
                fecha_inicio=ahora,
                fecha_finalizacion=None,
                es_activa=True,
                id_usuario=usuario.id_usuario,
                motivo_cambio=dto.motivo_cambio,
            )
            gestion = self.repo.crear_gestion_fase(nueva_gestion)
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            if self.bitacora_repo:
                try:
                    self.bitacora_repo.registrar(EventoAuditoria(
                        rf_origen='RF37', tipo_evento='FASE_CAMBIO_FALLIDO',
                        clasificacion_biologica='TRANSFORMACION_BIOLOGICA', resultado='FALLIDO',
                        severidad_log='ERROR', timestamp_evento=datetime.now(timezone.utc),
                        id_activo_biologico=id_activo, tipo_activo=activo.tipo,
                        detalle_tecnico={'error': str(exc)},
                        id_usuario_responsable=usuario.id_usuario,
                    ))
                    self.db.commit()
                except Exception:
                    pass
            raise

        if self.bitacora_repo:
            try:
                self.bitacora_repo.registrar(EventoAuditoria(
                    rf_origen='RF37', tipo_evento='FASE_CAMBIADA',
                    clasificacion_biologica='TRANSFORMACION_BIOLOGICA', resultado='EXITOSO',
                    severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
                    id_activo_biologico=id_activo, tipo_activo=activo.tipo,
                    descripcion=f'Fase cambiada a {fase_actual.nombre_fase} (paso {fase_siguiente_idx + 1}/{len(ciclo.fases)})',
                    detalle_tecnico={'fase': fase_actual.nombre_fase, 'ciclo': ciclo.nombre},
                    id_usuario_responsable=usuario.id_usuario,
                ))
                self.db.commit()
            except Exception:
                pass

        return gestion
