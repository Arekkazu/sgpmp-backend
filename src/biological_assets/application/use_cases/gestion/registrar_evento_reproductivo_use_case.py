from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases.gestion._event_validations import (
    validar_estado_permite_eventos,
    validar_fecha_evento,
)
from src.biological_assets.domain.entities.activo_biologico import EventoActivo, EventoAuditoria, EventoReproductivo
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.evento_activo_repository import EventoActivoRepository
from src.biological_assets.infrastructure.dto.registrar_evento_reproductivo_dto import RegistrarEventoReproductivoDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, NotFoundError

_CATEGORIAS_REQUIEREN_PADRE = {'servicio', 'inseminacion'}
_CATEGORIAS_REQUIEREN_NUM_CRIAS = {'parto', 'aborto', 'nacimiento'}


class RegistrarEventoReproductivoUseCase:

    def __init__(
        self,
        db: Session,
        activo_repo: ActivoBiologicoRepository,
        evento_repo: EventoActivoRepository,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.activo_repo = activo_repo
        self.evento_repo = evento_repo
        self.bitacora_repo = bitacora_repo

    def execute(
        self,
        id_activo: int,
        dto: RegistrarEventoReproductivoDTO,
        usuario: UsuarioActual,
    ) -> EventoActivo:
        activo = self.activo_repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con id {id_activo} no existe.',
            )

        validar_estado_permite_eventos(activo)

        fecha = dto.fecha or datetime.now(timezone.utc)
        validar_fecha_evento(fecha, activo, self.evento_repo)

        # FA-04: validar categoría según tipo de activo
        if activo.tipo == 'LOTE' and dto.categoria != 'nacimiento':
            raise BusinessRuleError(
                code='EVENTO_NO_PERMITIDO_LOTE',
                message='Los activos de tipo LOTE solo pueden registrar eventos de tipo nacimiento.',
            )

        # FA-05: para servicio/inseminación, el padre es obligatorio y debe existir y estar ACTIVO
        if dto.categoria in _CATEGORIAS_REQUIEREN_PADRE:
            if dto.id_padre is None:
                raise BusinessRuleError(
                    code='PADRE_REQUERIDO',
                    message=f'El tipo de evento {dto.categoria} requiere especificar el activo padre (id_padre).',
                )
            padre = self.activo_repo.obtener_por_id(dto.id_padre)
            if padre is None:
                raise NotFoundError(
                    code='ACTIVO_RELACIONADO_NO_ENCONTRADO',
                    message=f'El activo relacionado (padre) con id {dto.id_padre} no existe o no está activo.',
                )
            if padre.id_estado != 1:  # ACTIVO
                raise NotFoundError(
                    code='ACTIVO_RELACIONADO_NO_ENCONTRADO',
                    message=f'El activo relacionado (padre) con id {dto.id_padre} no existe o no está activo.',
                )

        # Validaciones de secuencia lógica (solo para activos INDIVIDUAL)
        if activo.tipo == 'INDIVIDUAL':
            if dto.categoria == 'diagnostico':
                if not self.evento_repo.tiene_servicio_o_inseminacion_previa(id_activo):
                    raise BusinessRuleError(
                        code='SECUENCIA_REPRODUCTIVA_INVALIDA',
                        message=(
                            'No se puede registrar un diagnóstico sin un evento previo de servicio '
                            'o inseminación sobre este activo.'
                        ),
                    )

            if dto.categoria in {'parto', 'aborto'}:
                if not self.evento_repo.tiene_diagnostico_positivo_previo(id_activo):
                    raise BusinessRuleError(
                        code='SECUENCIA_REPRODUCTIVA_INVALIDA',
                        message=(
                            f'No se puede registrar un {dto.categoria} sin un diagnóstico '
                            'con resultado exitoso previo sobre este activo.'
                        ),
                    )

            if dto.categoria == 'nacimiento':
                if not self.evento_repo.tiene_servicio_o_inseminacion_previa(id_activo):
                    raise BusinessRuleError(
                        code='SECUENCIA_REPRODUCTIVA_INVALIDA',
                        message=(
                            'No se puede registrar un nacimiento sin eventos previos de '
                            'servicio o inseminación sobre este activo.'
                        ),
                    )
                if not self.evento_repo.tiene_diagnostico_positivo_previo(id_activo):
                    raise BusinessRuleError(
                        code='SECUENCIA_REPRODUCTIVA_INVALIDA',
                        message=(
                            'No se puede registrar un nacimiento sin un diagnóstico '
                            'con resultado exitoso previo sobre este activo.'
                        ),
                    )

        # Validar numero_crias para eventos que lo requieren
        if dto.categoria in _CATEGORIAS_REQUIEREN_NUM_CRIAS and dto.numero_crias < 1:
            raise BusinessRuleError(
                code='NUMERO_CRIAS_REQUERIDO',
                message=f'El tipo de evento {dto.categoria} requiere al menos 1 cría (numero_crias >= 1).',
            )

        evento = EventoActivo(
            id_activo_biologico=id_activo,
            fecha=fecha,
            id_usuario=usuario.id_usuario,
            descripcion=dto.descripcion,
            reproductivo=EventoReproductivo(
                categoria=dto.categoria,
                resultado=dto.resultado,
                numero_cria=dto.numero_crias,
                id_padre=dto.id_padre,
                id_madre=dto.id_madre,
            ),
        )

        try:
            resultado = self.evento_repo.guardar(evento)
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            if self.bitacora_repo:
                try:
                    self.bitacora_repo.registrar(EventoAuditoria(
                        rf_origen='RF42', tipo_evento='EVENTO_REPRODUCTIVO_FALLIDO',
                        clasificacion_biologica='TRANSFORMACION_BIOLOGICA', resultado='FALLIDO',
                        severidad_log='ERROR', timestamp_evento=datetime.now(timezone.utc),
                        id_activo_biologico=id_activo, tipo_activo=activo.tipo,
                        detalle_tecnico={'error': str(exc), 'categoria': dto.categoria},
                        id_usuario_responsable=usuario.id_usuario,
                    ))
                    self.db.commit()
                except Exception:
                    pass
            raise

        if self.bitacora_repo:
            try:
                self.bitacora_repo.registrar(EventoAuditoria(
                    rf_origen='RF42', tipo_evento='EVENTO_REPRODUCTIVO_REGISTRADO',
                    clasificacion_biologica='TRANSFORMACION_BIOLOGICA', resultado='EXITOSO',
                    severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
                    id_activo_biologico=id_activo, tipo_activo=activo.tipo,
                    descripcion=f'Evento reproductivo registrado: {dto.categoria}',
                    detalle_tecnico={'categoria': dto.categoria},
                    id_usuario_responsable=usuario.id_usuario,
                ))
                self.db.commit()
            except Exception:
                pass

        return resultado
