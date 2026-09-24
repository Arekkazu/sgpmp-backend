from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases._registrar_evento_bitacora import registrar_evento_bitacora
from src.biological_assets.application.use_cases.gestion._auditoria_rechazos import (
    ejecutar_con_auditoria_de_rechazo,
)
from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria, GestionFase, registros_rf46
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.ciclo_consulta_port import CicloConsultaPort
from src.biological_assets.infrastructure.dto.cambiar_fase_dto import CambiarFaseDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import AppError, BusinessRuleError, ConflictError, NotFoundError, ValidationError


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
        return ejecutar_con_auditoria_de_rechazo(
            lambda: self._execute(id_activo, dto, usuario),
            db=self.db,
            bitacora_repo=self.bitacora_repo,
            obtener_activo=self.repo.obtener_por_id,
            id_activo=id_activo,
            id_usuario=usuario.id_usuario,
            rf_origen='RF37',
            tipo_evento_rechazado='FASE_CAMBIO_RECHAZADO',
            clasificacion_biologica='TRANSFORMACION_BIOLOGICA',
        )

    def _execute(self, id_activo: int, dto: CambiarFaseDTO, usuario: UsuarioActual) -> GestionFase:
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

        # FA-03: determinar la fase "estándar siguiente" en la secuencia --
        # misma lógica de siempre (avanzar un paso desde la última fase
        # realmente registrada), pero ahora basada en la fase persistida
        # (id_ciclos_productivo_biologico) y no en un conteo de filas, para
        # que siga siendo correcta después de una transición no estándar.
        gestiones = self.repo.obtener_gestiones_fases(id_activo)
        gestiones_en_ciclo = [g for g in gestiones if g.id_ciclo_productiva == dto.id_ciclo_productiva]

        if not gestiones_en_ciclo:
            idx_estandar = 0
        else:
            ultima = gestiones_en_ciclo[-1]  # obtener_gestiones_fases ordena por fecha_inicio ASC
            idx_ultima = next(
                (i for i, f in enumerate(ciclo.fases)
                 if f.id_ciclos_productivo_biologico == ultima.id_ciclos_productivo_biologico),
                None,
            )
            idx_estandar = (idx_ultima + 1) if idx_ultima is not None else len(ciclo.fases)

        fase_estandar = ciclo.fases[idx_estandar] if idx_estandar < len(ciclo.fases) else None

        # RF-37 (tarea Taiga fase_destino/confirmacion_no_estandar): sin
        # fase_destino_id explícito, se conserva el comportamiento histórico
        # (avanzar a la fase estándar). Con fase_destino_id, se permite
        # cualquier fase del ciclo -- pero si no es la estándar, exige
        # confirmacion_no_estandar=true o rechaza con 409.
        if dto.fase_destino_id is None:
            if fase_estandar is None:
                raise BusinessRuleError(
                    code='CICLO_COMPLETADO',
                    message=(
                        f'El activo ya completó todas las fases del ciclo "{ciclo.nombre}". '
                        'No es posible avanzar más en este ciclo.'
                    ),
                )
            idx_objetivo = idx_estandar
            fase_objetivo = fase_estandar
            es_no_estandar = False
        else:
            idx_objetivo = next(
                (i for i, f in enumerate(ciclo.fases)
                 if f.id_ciclos_productivo_biologico == dto.fase_destino_id),
                None,
            )
            if idx_objetivo is None:
                raise ValidationError(
                    code='FASE_DESTINO_INVALIDA',
                    message=(
                        f'La fase destino {dto.fase_destino_id} no pertenece a la secuencia '
                        f'del ciclo "{ciclo.nombre}".'
                    ),
                    field='fase_destino_id',
                )
            fase_objetivo = ciclo.fases[idx_objetivo]
            es_no_estandar = (
                fase_estandar is None
                or fase_objetivo.id_ciclos_productivo_biologico != fase_estandar.id_ciclos_productivo_biologico
            )
            if es_no_estandar and not dto.confirmacion_no_estandar:
                raise ConflictError(
                    code='TRANSICION_NO_ESTANDAR_SIN_CONFIRMAR',
                    message=(
                        f'La transición a "{fase_objetivo.nombre_fase}" no es la siguiente fase '
                        f'estándar de la secuencia del ciclo "{ciclo.nombre}". Si esta transición '
                        f'es intencional (salto de fase o retroceso), reenvíe la solicitud con '
                        f'confirmacion_no_estandar=true.'
                    ),
                )

        ahora = dto.fecha_inicio or datetime.now(timezone.utc)

        try:
            # Cerrar fase activa actual si existe (antes de insertar la nueva, por el trigger)
            self.repo.cerrar_gestion_activa(
                id_activo,
                ahora,
                dto.motivo_cambio or '',
                usuario.id_usuario,
            )

            nueva_gestion = GestionFase(
                id_gestion_fases=None,
                id_activo_biologico=id_activo,
                id_ciclo_productiva=dto.id_ciclo_productiva,
                id_ciclos_productivo_biologico=fase_objetivo.id_ciclos_productivo_biologico,
                nombre_ciclo=ciclo.nombre,
                nombre_fase_actual=fase_objetivo.nombre_fase,
                paso_actual=idx_objetivo + 1,
                total_pasos=len(ciclo.fases),
                es_transicion_no_estandar=es_no_estandar,
                fecha_inicio=ahora,
                fecha_finalizacion=None,
                es_activa=True,
                id_usuario=usuario.id_usuario,
                motivo_cambio=dto.motivo_cambio,
            )
            gestion = self.repo.crear_gestion_fase(nueva_gestion)
            self.db.commit()
        except AppError:
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            registrar_evento_bitacora(self.bitacora_repo, self.db, EventoAuditoria(
                rf_origen='RF37', tipo_evento='FASE_CAMBIO_FALLIDO',
                clasificacion_biologica='TRANSFORMACION_BIOLOGICA', resultado='FALLIDO',
                severidad_log='ERROR', timestamp_evento=datetime.now(timezone.utc),
                id_activo_biologico=id_activo, tipo_activo=activo.tipo,
                detalle_tecnico={'error': str(exc)},
                id_usuario_responsable=usuario.id_usuario,
            ))
            raise

        registrar_evento_bitacora(self.bitacora_repo, self.db, EventoAuditoria(
            rf_origen='RF37', tipo_evento='FASE_CAMBIADA',
            clasificacion_biologica='TRANSFORMACION_BIOLOGICA', resultado='EXITOSO',
            severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
            id_activo_biologico=id_activo, tipo_activo=activo.tipo,
            descripcion=f'Fase cambiada a {fase_objetivo.nombre_fase} (paso {idx_objetivo + 1}/{len(ciclo.fases)})',
            detalle_tecnico={
                'fase': fase_objetivo.nombre_fase,
                'ciclo': ciclo.nombre,
                'es_transicion_no_estandar': es_no_estandar,
                'registros_rf46': registros_rf46(gestiones_fases=gestion.id_gestion_fases),
            },
            id_usuario_responsable=usuario.id_usuario,
        ))

        return gestion
