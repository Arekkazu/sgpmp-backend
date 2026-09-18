from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases._registrar_evento_bitacora import registrar_evento_bitacora
from src.biological_assets.application.use_cases.gestion._auditoria_rechazos import (
    ejecutar_con_auditoria_de_rechazo,
)
from src.biological_assets.application.use_cases.gestion._event_validations import (
    validar_estado_permite_eventos,
    validar_fecha_evento,
)
from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    EventoActivo,
    EventoAuditoria,
    EventoReproductivo,
)
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.evento_activo_repository import EventoActivoRepository
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsultaPort
from src.biological_assets.infrastructure.dto.registrar_evento_reproductivo_dto import RegistrarEventoReproductivoDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import AppError, BusinessRuleError, ConflictError, NotFoundError

_CATEGORIAS_REQUIEREN_PADRE = {'servicio', 'inseminacion'}
_CATEGORIAS_REQUIEREN_NUM_CRIAS = {'parto', 'aborto', 'nacimiento'}


class RegistrarEventoReproductivoUseCase:

    def __init__(
        self,
        db: Session,
        activo_repo: ActivoBiologicoRepository,
        evento_repo: EventoActivoRepository,
        infra_port: InfraestructuraConsultaPort,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.activo_repo = activo_repo
        self.evento_repo = evento_repo
        self.infra_port = infra_port
        self.bitacora_repo = bitacora_repo

    def execute(
        self,
        id_activo: int,
        dto: RegistrarEventoReproductivoDTO,
        usuario: UsuarioActual,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> EventoActivo:
        return ejecutar_con_auditoria_de_rechazo(
            lambda: self._execute(id_activo, dto, usuario, ids_fincas_permitidas=ids_fincas_permitidas),
            db=self.db,
            bitacora_repo=self.bitacora_repo,
            obtener_activo=self.activo_repo.obtener_por_id,
            id_activo=id_activo,
            id_usuario=usuario.id_usuario,
            rf_origen='RF42',
            tipo_evento_rechazado='EVENTO_REPRODUCTIVO_RECHAZADO',
            clasificacion_biologica='TRANSFORMACION_BIOLOGICA',
            tipos_por_codigo={
                'SECUENCIA_REPRODUCTIVA_INVALIDA': 'SECUENCIA_REPRODUCTIVA_VIOLADA',
            },
        )

    def _execute(
        self,
        id_activo: int,
        dto: RegistrarEventoReproductivoDTO,
        usuario: UsuarioActual,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> EventoActivo:
        activo = self.activo_repo.obtener_por_id(id_activo, ids_fincas_permitidas=ids_fincas_permitidas)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con id {id_activo} no existe.',
            )

        validar_estado_permite_eventos(activo)

        # Precondición RF-42: "El activo debe estar en una fase productiva
        # compatible con reproducción." No existe un catálogo de fases que
        # distinga "reproductiva" de otra (los ciclos biológicos del sistema
        # son etapas de crecimiento secuenciales: larval/juvenil/engorde) —
        # la compatibilidad exigida es simplemente que exista una gestión de
        # fase activa, igual que la E-02 de RF-43 (RegistrarEventoProductivoUseCase).
        # INC-M02-78-G58: antes de este fix no se validaba en absoluto.
        if self.activo_repo.obtener_fase_activa(id_activo) is None:
            raise ConflictError(
                code='FASE_NO_COMPATIBLE_REPRODUCCION',
                message='La fase productiva del activo no permite registrar este tipo de evento.',
            )

        fecha = dto.fecha or datetime.now(timezone.utc)
        validar_fecha_evento(fecha, activo, self.evento_repo)

        # FA-04: validar categoría según tipo de activo
        if activo.tipo == 'POBLACIONAL' and dto.categoria != 'nacimiento':
            raise BusinessRuleError(
                code='EVENTO_NO_PERMITIDO_LOTE',
                message='Los activos de tipo LOTE solo pueden registrar eventos de tipo nacimiento.',
            )

        # FA-05: para servicio/inseminación, el padre es obligatorio y debe existir,
        # estar ACTIVO y pertenecer a la misma finca que el activo objetivo.
        if dto.categoria in _CATEGORIAS_REQUIEREN_PADRE:
            if dto.id_padre is None:
                raise BusinessRuleError(
                    code='PADRE_REQUERIDO',
                    message=f'El tipo de evento {dto.categoria} requiere especificar el activo padre (id_padre).',
                )
            self._validar_activo_relacionado(dto.id_padre, activo, 'padre')

        # INC-M02-77-G56 (OWASP API1, BOLA): id_madre no tiene requisito de categoría,
        # pero si se envía debe validarse igual que id_padre. Antes de este fix no se
        # validaba en absoluto (ni existencia, ni estado, ni finca).
        if dto.id_madre is not None:
            self._validar_activo_relacionado(dto.id_madre, activo, 'madre')

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
        except AppError:
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            registrar_evento_bitacora(self.bitacora_repo, self.db, EventoAuditoria(
                rf_origen='RF42', tipo_evento='EVENTO_REPRODUCTIVO_FALLIDO',
                clasificacion_biologica='TRANSFORMACION_BIOLOGICA', resultado='FALLIDO',
                severidad_log='ERROR', timestamp_evento=datetime.now(timezone.utc),
                id_activo_biologico=id_activo, tipo_activo=activo.tipo,
                detalle_tecnico={'error': str(exc), 'categoria': dto.categoria},
                id_usuario_responsable=usuario.id_usuario,
            ))
            raise

        registrar_evento_bitacora(self.bitacora_repo, self.db, EventoAuditoria(
            rf_origen='RF42', tipo_evento='EVENTO_REPRODUCTIVO_REGISTRADO',
            clasificacion_biologica='TRANSFORMACION_BIOLOGICA', resultado='EXITOSO',
            severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
            id_activo_biologico=id_activo, tipo_activo=activo.tipo,
            descripcion=f'Evento reproductivo registrado: {dto.categoria}',
            detalle_tecnico={'categoria': dto.categoria},
            id_usuario_responsable=usuario.id_usuario,
        ))

        return resultado

    def _validar_activo_relacionado(
        self,
        id_relacionado: int,
        activo_objetivo: ActivoBiologico,
        rol: str,
    ) -> None:
        """FA-05 / INC-M02-77-G56: el padre o la madre referenciados deben existir,
        estar ACTIVO y pertenecer a la misma finca que el activo objetivo.

        Antes de este fix solo se validaba existencia y estado — nada impedía
        enlazar un activo de una finca completamente distinta (BOLA, OWASP API1).
        El caso "existe pero es de otra finca" responde con el mismo código que
        "no existe" a propósito: revelar que el recurso existe fuera del alcance
        de finca del solicitante ya es una fuga de información (mismo principio
        que `ActivoBiologicoRepository.obtener_por_id(ids_fincas_permitidas=...)`,
        que devuelve `None` en vez de distinguir "no existe" de "fuera de alcance").
        """
        mensaje = f'El activo relacionado ({rol}) con id {id_relacionado} no existe o no está activo.'

        relacionado = self.activo_repo.obtener_por_id(id_relacionado)
        if relacionado is None or relacionado.id_estado != 1:  # ACTIVO
            raise NotFoundError(code='ACTIVO_RELACIONADO_NO_ENCONTRADO', message=mensaje)

        infra_objetivo = self.infra_port.obtener_activa(activo_objetivo.id_infraestructura)
        infra_relacionado = self.infra_port.obtener_activa(relacionado.id_infraestructura)
        if (
            infra_objetivo is None
            or infra_relacionado is None
            or infra_objetivo.id_finca != infra_relacionado.id_finca
        ):
            raise NotFoundError(code='ACTIVO_RELACIONADO_NO_ENCONTRADO', message=mensaje)
