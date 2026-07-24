from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases.gestion.actualizar_activo_individual_use_case import (
    ActualizarActivoIndividualUseCase,
)
from src.biological_assets.application.use_cases.gestion.cambiar_estado_use_case import CambiarEstadoUseCase
from src.biological_assets.application.use_cases.gestion.cambiar_fase_use_case import CambiarFaseUseCase
from src.biological_assets.application.use_cases.gestion.cerrar_ciclo_use_case import CerrarCicloUseCase
from src.biological_assets.application.use_cases.gestion.consultar_activo_use_case import ConsultarActivoUseCase
from src.biological_assets.application.use_cases.gestion.listar_activos_use_case import ListarActivosUseCase
from src.biological_assets.application.use_cases.gestion.consultar_historial_fases_use_case import (
    ConsultarHistorialFasesUseCase,
)
from src.biological_assets.application.use_cases.registro.consultar_asociacion_use_case import ConsultarAsociacionUseCase
from src.biological_assets.application.use_cases.registro.registrar_activo_use_case import RegistrarActivoBiologicoUseCase
from src.biological_assets.domain.entities.activo_biologico import GestionFase, HistorialInfraestructura
from src.biological_assets.infrastructure.adapters.ciclo_productivo_m09_adapter import CicloProductivoM09Adapter
from src.biological_assets.infrastructure.adapters.especie_m09_adapter import EspecieM09Adapter
from src.biological_assets.infrastructure.adapters.infraestructura_m09_adapter import InfraestructuraM09Adapter
from src.biological_assets.infrastructure.adapters.parametros_especie_m09_adapter import ParametrosEspecieM09Adapter
from src.biological_assets.infrastructure.dto.actualizar_activo_individual_dto import ActualizarActivoIndividualDTO
from src.biological_assets.infrastructure.dto.cambiar_estado_dto import CambiarEstadoDTO
from src.biological_assets.infrastructure.dto.cambiar_fase_dto import CambiarFaseDTO
from src.biological_assets.infrastructure.dto.cerrar_ciclo_dto import CerrarCicloDTO
from src.biological_assets.infrastructure.dto.listar_activos_dto import ListarActivosDTO
from src.biological_assets.infrastructure.dto.registrar_activo_dto import RegistrarActivoBiologicoDTO
from src.biological_assets.infrastructure.repositories.activo_biologico_repository import (
    SqlAlchemyActivoBiologicoRepository,
)
from src.biological_assets.infrastructure.repositories.historico_estado_repository import (
    SqlAlchemyHistoricoEstadoRepository,
)
from src.biological_assets.application.use_cases.gestion.consultar_eventos_use_case import ConsultarEventosUseCase
from src.biological_assets.application.use_cases.gestion.registrar_evento_baja_use_case import RegistrarEventoBajaUseCase
from src.biological_assets.application.use_cases.gestion.registrar_evento_crecimiento_use_case import (
    RegistrarEventoCrecimientoUseCase,
)
from src.biological_assets.application.use_cases.gestion.registrar_evento_productivo_use_case import (
    RegistrarEventoProductivoUseCase,
)
from src.biological_assets.application.use_cases.gestion.registrar_evento_reproductivo_use_case import (
    RegistrarEventoReproductivoUseCase,
)
from src.biological_assets.application.use_cases.gestion.registrar_evento_sanitario_use_case import (
    RegistrarEventoSanitarioUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import EventoActivo
from src.biological_assets.infrastructure.dto.registrar_evento_baja_dto import RegistrarEventoBajaDTO
from src.biological_assets.infrastructure.dto.registrar_evento_crecimiento_dto import RegistrarEventoCrecimientoDTO
from src.biological_assets.infrastructure.dto.registrar_evento_productivo_dto import RegistrarEventoProductivoDTO
from src.biological_assets.infrastructure.dto.registrar_evento_reproductivo_dto import RegistrarEventoReproductivoDTO
from src.biological_assets.infrastructure.dto.registrar_evento_sanitario_dto import RegistrarEventoSanitarioDTO
from src.biological_assets.infrastructure.repositories.evento_activo_repository import SqlAlchemyEventoActivoRepository
from src.biological_assets.application.use_cases.gestion.consultar_historial_use_case import ConsultarHistorialUseCase
from src.biological_assets.application.use_cases.gestion.consultar_ficha_integral_use_case import ConsultarFichaIntegralUseCase
from src.biological_assets.application.use_cases.gestion.registrar_transferencia_use_case import RegistrarTransferenciaUseCase
from src.biological_assets.infrastructure.dto.consultar_historial_dto import ConsultarHistorialDTO
from src.biological_assets.infrastructure.dto.registrar_transferencia_dto import RegistrarTransferenciaDTO
from src.biological_assets.infrastructure.repositories.transferencia_repository import SqlAlchemyTransferenciaRepository
from src.biological_assets.application.use_cases.gestion.asociar_sensor_activo_use_case import AsociarSensorActivoUseCase
from src.biological_assets.infrastructure.dto.asociar_sensor_activo_dto import AsociarSensorActivoDTO
from src.biological_assets.infrastructure.repositories.asociacion_sensor_activo_repository import (
    SqlAlchemyAsociacionSensorActivoRepository,
)
from src.biological_assets.infrastructure.adapters.sensor_m09_adapter import SensorM09Adapter
from src.biological_assets.application.use_cases.gestion.consultar_indicadores_use_case import ConsultarIndicadoresUseCase
from src.biological_assets.application.use_cases.gestion.consultar_datos_consolidados_use_case import ConsultarDatosConsolidadosUseCase
from src.biological_assets.infrastructure.dto.consultar_indicadores_dto import ConsultarIndicadoresDTO
from src.biological_assets.infrastructure.dto.datos_consolidados_dto import DatosConsolidadosDTO
from src.biological_assets.infrastructure.repositories.indicadores_repository import SqlAlchemyIndicadoresRepository
from src.biological_assets.application.use_cases.gestion.consultar_bitacora_use_case import ConsultarBitacoraUseCase
from src.biological_assets.infrastructure.dto.consultar_bitacora_dto import ConsultarBitacoraDTO
from src.biological_assets.infrastructure.repositories.bitacora_auditoria_repository import SqlAlchemyBitacoraAuditoriaRepository
from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria
from src.biological_assets.infrastructure.schema.activo_biologico_schema import (
    ActivoBiologicoResponse,
    ActivosPaginadosResponse,
    AsociacionInfraestructuraResponse,
    AsociacionSensorActivoResponse,
    CambioEstadoResponse,
    CierreActivoResponse,
    ConsultaAsociacionResponse,
    DetalleIndividualResponse,
    DetallePoblacionalResponse,
    EventoActivoResponse,
    EventoBajaResponse,
    EventoCrecimientoResponse,
    EventoProductivoResponse,
    EventoReproductivoResponse,
    EventoSanitarioResponse,
    FichaIntegralResponse,
    GestionFaseResponse,
    HistorialActivoResponse,
    HistorialEventosResponse,
    HistorialFasesResponse,
    HistoricoEstadoResponse,
    InfraestructuraDisponibleResponse,
    RegistrarEventoCrecimientoResponse,
    RegistrarEventoReproductivoResponse,
    RegistrarEventoSanitarioResponse,
    RegistroHistorialResponse,
    TransferenciaResponse,
    IndicadoresActivoResponse,
    IndicadorZootecnicoResponse,
    DatosConsolidadosResponse,
    BitacoraAuditoriaResponse,
    EventoAuditoriaResponse,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.errors import ValidationError as DomainValidationError
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix='/activos-biologicos', tags=['Activos Biológicos'])

_RECURSO = 29           # modulo1.recursos: 'activos_biologicos'
_RECURSO_SENSOR = 30    # modulo1.recursos: 'asociacion_sensor_activo'
_RECURSO_BITACORA = 31  # modulo1.recursos: 'bitacora_auditoria_m02'


def _activo_to_response(activo) -> ActivoBiologicoResponse:
    di = None
    if activo.detalle_individual:
        d = activo.detalle_individual
        di = DetalleIndividualResponse(
            id_detalle=d.id_detalle,
            raza=d.raza,
            sexo=d.sexo,
            fecha_nacimiento=d.fecha_nacimiento,
            peso_inicial=d.peso_inicial,
            fecha_creacion=d.fecha_creacion,
        )

    dp = None
    if activo.detalle_poblacional:
        p = activo.detalle_poblacional
        dp = DetallePoblacionalResponse(
            id_detalle=p.id_detalle,
            cantidad_inicial=p.cantidad_inicial,
            cantidad_actual=p.cantidad_actual,
            peso_promedio_inicial=p.peso_promedio_inicial,
            peso_promedio=p.peso_promedio,
            biomasa_total=p.biomasa_total,
            densidad=p.densidad,
        )

    return ActivoBiologicoResponse(
        id_activo_biologico=activo.id_activo_biologico,
        id_especie=activo.id_especie,
        tipo=activo.tipo,
        identificador=activo.identificador,
        fecha_inicio_ciclo=activo.fecha_inicio_ciclo,
        detalles_procedencia=activo.detalles_procedencia,
        origen_financiero=activo.origen_financiero,
        costo_adquisicion=activo.costo_adquisicion,
        soporte_documental=activo.soporte_documental,
        descripcion=activo.descripcion,
        id_infraestructura=activo.id_infraestructura,
        atributos_dinamicos=activo.atributos_dinamicos,
        id_estado=activo.id_estado,
        nombre_estado=activo.nombre_estado,
        id_usuario=activo.id_usuario,
        fecha_creacion=activo.fecha_creacion,
        detalle_individual=di,
        detalle_poblacional=dp,
    )


def _historial_to_response(h: HistorialInfraestructura) -> AsociacionInfraestructuraResponse:
    return AsociacionInfraestructuraResponse(
        id_historial=h.id_historial,
        id_activo_biologico=h.id_activo_biologico,
        id_infraestructura=h.id_infraestructura,
        nombre_infraestructura=h.nombre_infraestructura,
        tipo_infraestructura=h.tipo_infraestructura,
        fecha_inicio=h.fecha_inicio,
        fecha_fin=h.fecha_fin,
    )


@router.post(
    '',
    response_model=ActivoBiologicoResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        400: {'model': ErrorResponse},
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        409: {'model': ErrorResponse},
        422: {'model': ErrorResponse},
    },
    summary='Registrar activo biológico (RF-33)',
)
def registrar_activo(
    dto: RegistrarActivoBiologicoDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ActivoBiologicoResponse:
    use_case = RegistrarActivoBiologicoUseCase(
        db=db,
        repo=SqlAlchemyActivoBiologicoRepository(db),
        especie_port=EspecieM09Adapter(db),
        infra_port=InfraestructuraM09Adapter(db),
        parametros_port=ParametrosEspecieM09Adapter(db),
        bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db),
    )
    activo = use_case.execute(dto, usuario_actual)
    return _activo_to_response(activo)


@router.get(
    '',
    response_model=ActivosPaginadosResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        400: {'model': ErrorResponse},
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
    },
    summary='Listar activos biológicos con filtros y paginación',
)
def listar_activos(
    tipo: str | None = Query(default=None, description='INDIVIDUAL | POBLACIONAL'),
    id_especie: int | None = Query(default=None, ge=1),
    id_estado: int | None = Query(default=None, ge=1),
    id_infraestructura: int | None = Query(default=None, ge=1),
    pagina: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ActivosPaginadosResponse:
    from pydantic import ValidationError as _PydanticValidationError
    try:
        dto = ListarActivosDTO(
            tipo=tipo,
            id_especie=id_especie,
            id_estado=id_estado,
            id_infraestructura=id_infraestructura,
            pagina=pagina,
            page_size=page_size,
        )
    except (ValueError, _PydanticValidationError) as exc:
        raise DomainValidationError(code='PARAMETROS_INVALIDOS', message=str(exc))

    use_case = ListarActivosUseCase(db=db, repo=SqlAlchemyActivoBiologicoRepository(db))
    registros, total = use_case.execute(dto)
    total_paginas = max(1, (total + page_size - 1) // page_size)
    return ActivosPaginadosResponse(
        total_registros=total,
        pagina_actual=pagina,
        total_paginas=total_paginas,
        registros_por_pagina=page_size,
        registros=[_activo_to_response(a) for a in registros],
    )


def _auditoria_to_response(e: EventoAuditoria) -> EventoAuditoriaResponse:
    return EventoAuditoriaResponse(
        id_bitacora=e.id_bitacora,
        id_evento=str(e.id_evento),
        rf_origen=e.rf_origen,
        tipo_evento=e.tipo_evento,
        clasificacion_biologica=e.clasificacion_biologica,
        id_activo_biologico=e.id_activo_biologico,
        tipo_activo=e.tipo_activo,
        timestamp_evento=e.timestamp_evento,
        timestamp_registro=e.timestamp_registro,
        resultado=e.resultado,
        descripcion=e.descripcion,
        detalle_tecnico=e.detalle_tecnico,
        id_usuario_responsable=e.id_usuario_responsable,
        modulo_consumidor=e.modulo_consumidor,
        severidad_log=e.severidad_log,
        id_evento_correlacionado=str(e.id_evento_correlacionado) if e.id_evento_correlacionado else None,
        hash_integridad=e.hash_integridad,
        registro_incompleto=e.registro_incompleto,
    )


# ── CU13 RF-52 — Consultar bitácora de auditoría ─────────────────────────────

@router.get(
    '/auditoria',
    response_model=BitacoraAuditoriaResponse,
    dependencies=[Depends(require_permission(_RECURSO_BITACORA, 2))],
    responses={
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        422: {'model': ErrorResponse},
    },
    summary='Consultar bitácora de auditoría y trazabilidad (CU13 - RF-52)',
)
def consultar_bitacora(
    rf_origen: str | None = Query(default=None, description='Origen RF (ej. RF33, RF40)'),
    tipo_evento: str | None = Query(default=None, description='Tipo de evento (ej. ACTIVO_REGISTRADO)'),
    id_activo_biologico: int | None = Query(default=None),
    clasificacion_biologica: str | None = Query(
        default=None,
        description='TRANSFORMACION_BIOLOGICA | GESTION_OPERATIVA | SANITARIO | CONTROL_ESTADO | ACCESO_DATOS',
    ),
    resultado: str | None = Query(default=None, description='EXITOSO | FALLIDO | RECHAZADO | ADVERTENCIA'),
    severidad_log: str | None = Query(default=None, description='INFO | WARNING | ERROR | CRITICAL'),
    fecha_inicio: str | None = Query(default=None, description='ISO 8601 UTC (ej. 2025-01-01T00:00:00Z)'),
    fecha_fin: str | None = Query(default=None, description='ISO 8601 UTC (ej. 2025-12-31T23:59:59Z)'),
    pagina: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> BitacoraAuditoriaResponse:
    from datetime import datetime as _dt
    from pydantic import ValidationError as _PydanticValidationError
    try:
        dto = ConsultarBitacoraDTO(
            rf_origen=rf_origen,
            tipo_evento=tipo_evento,
            id_activo_biologico=id_activo_biologico,
            clasificacion_biologica=clasificacion_biologica,
            resultado=resultado,
            severidad_log=severidad_log,
            fecha_inicio=_dt.fromisoformat(fecha_inicio.replace('Z', '+00:00')) if fecha_inicio else None,
            fecha_fin=_dt.fromisoformat(fecha_fin.replace('Z', '+00:00')) if fecha_fin else None,
            pagina=pagina,
            page_size=page_size,
        )
    except (ValueError, _PydanticValidationError) as exc:
        raise DomainValidationError(code='PARAMETROS_INVALIDOS', message=str(exc))

    use_case = ConsultarBitacoraUseCase(
        db=db,
        bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db),
    )
    registros, total = use_case.execute(dto)
    total_paginas = max(1, (total + page_size - 1) // page_size)
    return BitacoraAuditoriaResponse(
        total_registros=total,
        pagina_actual=pagina,
        total_paginas=total_paginas,
        registros_por_pagina=page_size,
        registros=[_auditoria_to_response(r) for r in registros],
    )


def _gestion_to_response(g: GestionFase) -> GestionFaseResponse:
    return GestionFaseResponse(
        id_gestion_fases=g.id_gestion_fases,
        id_activo_biologico=g.id_activo_biologico,
        id_ciclo_productiva=g.id_ciclo_productiva,
        nombre_ciclo=g.nombre_ciclo,
        nombre_fase_actual=g.nombre_fase_actual,
        paso_actual=g.paso_actual,
        total_pasos=g.total_pasos,
        fecha_inicio=g.fecha_inicio,
        fecha_finalizacion=g.fecha_finalizacion,
        es_activa=g.es_activa,
        motivo_cambio=g.motivo_cambio,
    )


@router.get(
    '/{id_activo}',
    response_model=ActivoBiologicoResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
    },
    summary='Consultar activo biológico (RF-35)',
)
def consultar_activo(
    id_activo: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ActivoBiologicoResponse:
    use_case = ConsultarActivoUseCase(
        db=db,
        repo=SqlAlchemyActivoBiologicoRepository(db),
        bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db),
    )
    activo = use_case.execute(id_activo, usuario_actual)
    return _activo_to_response(activo)


@router.patch(
    '/{id_activo}',
    response_model=ActivoBiologicoResponse,
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={
        400: {'model': ErrorResponse},
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
        422: {'model': ErrorResponse},
    },
    summary='Actualizar atributos de activo individual (RF-35)',
)
def actualizar_activo_individual(
    id_activo: int,
    dto: ActualizarActivoIndividualDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ActivoBiologicoResponse:
    use_case = ActualizarActivoIndividualUseCase(
        db=db,
        repo=SqlAlchemyActivoBiologicoRepository(db),
        bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db),
    )
    activo = use_case.execute(id_activo, dto, usuario_actual)
    return _activo_to_response(activo)


@router.post(
    '/{id_activo}/fases',
    response_model=GestionFaseResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={
        400: {'model': ErrorResponse},
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
        422: {'model': ErrorResponse},
    },
    summary='Cambiar fase del ciclo productivo (RF-37)',
)
def cambiar_fase(
    id_activo: int,
    dto: CambiarFaseDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> GestionFaseResponse:
    use_case = CambiarFaseUseCase(
        db=db,
        repo=SqlAlchemyActivoBiologicoRepository(db),
        ciclo_port=CicloProductivoM09Adapter(db),
        bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db),
    )
    gestion = use_case.execute(id_activo, dto, usuario_actual)
    return _gestion_to_response(gestion)


@router.get(
    '/{id_activo}/fases',
    response_model=HistorialFasesResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
    },
    summary='Consultar historial de fases (RF-37)',
)
def historial_fases(
    id_activo: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> HistorialFasesResponse:
    use_case = ConsultarHistorialFasesUseCase(db=db, repo=SqlAlchemyActivoBiologicoRepository(db))
    fases = use_case.execute(id_activo)
    return HistorialFasesResponse(
        id_activo_biologico=id_activo,
        fases=[_gestion_to_response(g) for g in fases],
    )


@router.get(
    '/{id_activo}/infraestructura',
    response_model=ConsultaAsociacionResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        400: {'model': ErrorResponse},
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
    },
    summary='Consultar asociación a infraestructura (RF-34)',
)
def consultar_asociacion(
    id_activo: int,
    tipo_consulta: Literal['ACTIVA', 'HISTORIAL'] = Query(
        'ACTIVA',
        description="'ACTIVA' devuelve la asociación vigente. 'HISTORIAL' devuelve todos los períodos.",
    ),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ConsultaAsociacionResponse:
    use_case = ConsultarAsociacionUseCase(
        db=db,
        repo=SqlAlchemyActivoBiologicoRepository(db),
        bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db),
    )
    resultado = use_case.execute(id_activo, tipo_consulta, usuario_actual)

    if tipo_consulta == 'ACTIVA':
        return ConsultaAsociacionResponse(
            tipo_consulta='ACTIVA',
            id_activo_biologico=id_activo,
            asociacion_activa=_historial_to_response(resultado) if resultado else None,
        )

    return ConsultaAsociacionResponse(
        tipo_consulta='HISTORIAL',
        id_activo_biologico=id_activo,
        historial=[_historial_to_response(h) for h in resultado],
    )


# ── Eventos de lote (CU03 - RF-36) ──────────────────────────────────────────

def _evento_to_response(evento: EventoActivo) -> EventoActivoResponse:
    crecimiento = None
    if evento.crecimiento:
        c = evento.crecimiento
        crecimiento = EventoCrecimientoResponse(
            tipo_medicion=c.tipo_medicion,
            valor_medicion=c.valor_medicion,
            unidad_medida=c.unidad_medida,
            tipo_agregacion=c.tipo_agregacion,
            frecuencia=c.frecuencia,
            nuevo_peso_promedio=c.nuevo_peso_promedio,
            cantidad_medida=c.cantidad_medida,
        )

    baja = None
    if evento.baja:
        b = evento.baja
        baja = EventoBajaResponse(
            cantidad_afectada=b.cantidad_afectada,
            tipo=b.tipo,
            motivo_baja=b.detalles,
        )

    sanitario = None
    if evento.sanitario:
        s = evento.sanitario
        sanitario = EventoSanitarioResponse(
            tipo=s.tipo,
            diagnostico=s.diagnostico,
            medicamento=s.medicamento,
            dosis=s.dosis,
            unidad_dosis=s.unidad_dosis,
            frecuencia=s.frecuencia,
            duracion=s.duracion,
            observaciones=s.observaciones,
        )

    productivo = None
    if evento.productivo:
        p = evento.productivo
        productivo = EventoProductivoResponse(
            cantidad=p.cantidad,
            id_metrica_produccion=p.id_metrica_produccion,
            id_ciclo_productivo=p.id_ciclo_productivo,
            condiciones=p.condiciones,
            tipo_producto=p.tipo_producto,
            unidad_medida=p.unidad_medida,
        )

    reproductivo = None
    if evento.reproductivo:
        r = evento.reproductivo
        reproductivo = EventoReproductivoResponse(
            categoria=r.categoria,
            resultado=r.resultado,
            numero_cria=r.numero_cria,
            id_padre=r.id_padre,
            id_madre=r.id_madre,
        )

    return EventoActivoResponse(
        id_eventos=evento.id_eventos,
        id_activo_biologico=evento.id_activo_biologico,
        fecha=evento.fecha,
        descripcion=evento.descripcion,
        id_usuario=evento.id_usuario,
        crecimiento=crecimiento,
        baja=baja,
        sanitario=sanitario,
        productivo=productivo,
        reproductivo=reproductivo,
    )


@router.get(
    '/{id_activo}/eventos',
    response_model=HistorialEventosResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
        422: {'model': ErrorResponse},
    },
    summary='Consultar historial de eventos del activo (RF-39)',
)
def consultar_eventos(
    id_activo: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> HistorialEventosResponse:
    use_case = ConsultarEventosUseCase(
        db=db,
        activo_repo=SqlAlchemyActivoBiologicoRepository(db),
        evento_repo=SqlAlchemyEventoActivoRepository(db),
    )
    eventos = use_case.execute(id_activo)
    return HistorialEventosResponse(
        id_activo_biologico=id_activo,
        total=len(eventos),
        eventos=[_evento_to_response(e) for e in eventos],
    )


@router.post(
    '/{id_activo}/eventos/crecimiento',
    response_model=RegistrarEventoCrecimientoResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        400: {'model': ErrorResponse},
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
        422: {'model': ErrorResponse},
    },
    summary='Registrar evento de crecimiento del activo (CU06 - RF-40)',
)
def registrar_evento_crecimiento(
    id_activo: int,
    dto: RegistrarEventoCrecimientoDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> RegistrarEventoCrecimientoResponse:
    use_case = RegistrarEventoCrecimientoUseCase(
        db=db,
        activo_repo=SqlAlchemyActivoBiologicoRepository(db),
        evento_repo=SqlAlchemyEventoActivoRepository(db),
        infra_port=InfraestructuraM09Adapter(db),
        parametros_port=ParametrosEspecieM09Adapter(db),
        ciclo_port=CicloProductivoM09Adapter(db),
        bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db),
    )
    evento, fase_avanzada = use_case.execute(id_activo, dto, usuario_actual)
    return RegistrarEventoCrecimientoResponse(
        evento=_evento_to_response(evento),
        fase_avanzada=fase_avanzada,
    )


@router.post(
    '/{id_activo}/eventos/baja',
    response_model=EventoActivoResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        400: {'model': ErrorResponse},
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
        409: {'model': ErrorResponse},
        422: {'model': ErrorResponse},
    },
    summary='Registrar baja de activo biológico (CU09 - RF-45)',
)
def registrar_evento_baja(
    id_activo: int,
    dto: RegistrarEventoBajaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> EventoActivoResponse:
    use_case = RegistrarEventoBajaUseCase(
        db=db,
        activo_repo=SqlAlchemyActivoBiologicoRepository(db),
        evento_repo=SqlAlchemyEventoActivoRepository(db),
        infra_port=InfraestructuraM09Adapter(db),
        historico_repo=SqlAlchemyHistoricoEstadoRepository(db),
        bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db),
    )
    evento = use_case.execute(id_activo, dto, usuario_actual)
    return _evento_to_response(evento)


@router.post(
    '/{id_activo}/eventos/sanitario',
    response_model=RegistrarEventoSanitarioResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        400: {'model': ErrorResponse},
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
        409: {'model': ErrorResponse},
        422: {'model': ErrorResponse},
    },
    summary='Registrar evento sanitario del activo (CU07 - RF-41)',
)
def registrar_evento_sanitario(
    id_activo: int,
    dto: RegistrarEventoSanitarioDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> RegistrarEventoSanitarioResponse:
    use_case = RegistrarEventoSanitarioUseCase(
        db=db,
        activo_repo=SqlAlchemyActivoBiologicoRepository(db),
        evento_repo=SqlAlchemyEventoActivoRepository(db),
        historico_repo=SqlAlchemyHistoricoEstadoRepository(db),
        bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db),
    )
    evento, historico = use_case.execute(id_activo, dto, usuario_actual)
    return RegistrarEventoSanitarioResponse(
        evento=_evento_to_response(evento),
        cambio_estado=HistoricoEstadoResponse.model_validate(historico) if historico else None,
    )


@router.patch(
    '/{id_activo}/estado',
    response_model=CambioEstadoResponse,
    status_code=200,
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={
        400: {'model': ErrorResponse},
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
        409: {'model': ErrorResponse},
        422: {'model': ErrorResponse},
    },
    summary='Cambiar estado del activo biológico (RF-44)',
)
def cambiar_estado(
    id_activo: int,
    dto: CambiarEstadoDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> CambioEstadoResponse:
    use_case = CambiarEstadoUseCase(
        db=db,
        repo=SqlAlchemyActivoBiologicoRepository(db),
        historico_repo=SqlAlchemyHistoricoEstadoRepository(db),
        bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db),
    )
    historico = use_case.execute(id_activo, dto, usuario_actual)
    return CambioEstadoResponse(
        id_activo_biologico=id_activo,
        estado_anterior=historico.id_estado_anterior,
        estado_nuevo=historico.id_estado_nuevo,
        historial=HistoricoEstadoResponse(
            id_historico=historico.id_historico,
            id_activo_biologico=historico.id_activo_biologico,
            id_estado_anterior=historico.id_estado_anterior,
            id_estado_nuevo=historico.id_estado_nuevo,
            fecha_cambio=historico.fecha_cambio,
            motivo_cambio=historico.motivo_cambio,
            modulo_origen=historico.modulo_origen,
            id_usuario=historico.id_usuario,
        ),
    )


@router.post(
    '/{id_activo}/cierre',
    response_model=CierreActivoResponse,
    status_code=200,
    dependencies=[Depends(require_permission(_RECURSO, 4))],
    responses={
        400: {'model': ErrorResponse},
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
        409: {'model': ErrorResponse},
        422: {'model': ErrorResponse},
    },
    summary='Cerrar ciclo productivo del activo biológico (RF-38)',
)
def cerrar_ciclo(
    id_activo: int,
    dto: CerrarCicloDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> CierreActivoResponse:
    use_case = CerrarCicloUseCase(
        db=db,
        repo=SqlAlchemyActivoBiologicoRepository(db),
        evento_repo=SqlAlchemyEventoActivoRepository(db),
        historico_repo=SqlAlchemyHistoricoEstadoRepository(db),
        bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db),
    )
    historico = use_case.execute(id_activo, dto, usuario_actual)
    return CierreActivoResponse(
        id_activo_biologico=id_activo,
        estado='CERRADO',
        fecha_cierre=dto.fecha_cierre,
        motivo_cierre=dto.motivo_cierre,
        fase_finalizada=True,
    )


@router.post(
    '/{id_activo}/eventos/reproductivo',
    response_model=RegistrarEventoReproductivoResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        400: {'model': ErrorResponse},
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
        422: {'model': ErrorResponse},
    },
    summary='Registrar evento reproductivo del activo (CU08 - RF-42)',
)
def registrar_evento_reproductivo(
    id_activo: int,
    dto: RegistrarEventoReproductivoDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> RegistrarEventoReproductivoResponse:
    use_case = RegistrarEventoReproductivoUseCase(
        db=db,
        activo_repo=SqlAlchemyActivoBiologicoRepository(db),
        evento_repo=SqlAlchemyEventoActivoRepository(db),
        bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db),
    )
    evento = use_case.execute(id_activo, dto, usuario_actual)
    return RegistrarEventoReproductivoResponse(evento=_evento_to_response(evento))


@router.post(
    '/{id_activo}/eventos/productivo',
    response_model=EventoActivoResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        400: {'model': ErrorResponse},
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
        409: {'model': ErrorResponse},
        422: {'model': ErrorResponse},
    },
    summary='Registrar evento productivo del activo (CU09 - RF-43)',
)
def registrar_evento_productivo(
    id_activo: int,
    dto: RegistrarEventoProductivoDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> EventoActivoResponse:
    use_case = RegistrarEventoProductivoUseCase(
        db=db,
        activo_repo=SqlAlchemyActivoBiologicoRepository(db),
        evento_repo=SqlAlchemyEventoActivoRepository(db),
        parametros_port=ParametrosEspecieM09Adapter(db),
        ciclo_port=CicloProductivoM09Adapter(db),
        bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db),
    )
    evento = use_case.execute(id_activo, dto, usuario_actual)
    return _evento_to_response(evento)


# ── CU10A — RF-46: Consultar historial ──────────────────────────────────────

@router.get(
    '/{id_activo}/historial',
    response_model=HistorialActivoResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
        422: {'model': ErrorResponse},
    },
    summary='Consultar historial completo del activo biológico (CU10A - RF-46)',
)
def consultar_historial(
    id_activo: int,
    fecha_inicio: str | None = Query(default=None, description='Filtro fecha inicio (YYYY-MM-DD)'),
    fecha_fin: str | None = Query(default=None, description='Filtro fecha fin (YYYY-MM-DD)'),
    categoria_evento: str | None = Query(default=None, description='Categoría de evento'),
    pagina: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> HistorialActivoResponse:
    from datetime import date as date_cls
    from pydantic import ValidationError as _PydanticValidationError
    try:
        dto = ConsultarHistorialDTO(
            fecha_inicio=date_cls.fromisoformat(fecha_inicio) if fecha_inicio else None,
            fecha_fin=date_cls.fromisoformat(fecha_fin) if fecha_fin else None,
            categoria_evento=categoria_evento,
            pagina=pagina,
            page_size=page_size,
        )
    except ValueError as exc:
        raise DomainValidationError(code='PARAMETROS_INVALIDOS', message=f'Formato de fecha inválido: {exc}')
    except _PydanticValidationError as exc:
        first = exc.errors()[0]
        raise DomainValidationError(code='PARAMETROS_INVALIDOS', message=first['msg'].replace('Value error, ', ''))
    use_case = ConsultarHistorialUseCase(
        db=db,
        activo_repo=SqlAlchemyActivoBiologicoRepository(db),
        transferencia_repo=SqlAlchemyTransferenciaRepository(db),
        bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db),
    )
    pagina_historial = use_case.execute(id_activo, dto, usuario_actual)
    return HistorialActivoResponse(
        id_activo_biologico=id_activo,
        total_registros=pagina_historial.total_registros,
        pagina_actual=pagina_historial.pagina_actual,
        total_paginas=pagina_historial.total_paginas,
        registros_por_pagina=pagina_historial.registros_por_pagina,
        registros=[
            RegistroHistorialResponse(
                categoria=r.categoria,
                fecha_evento=r.fecha_evento,
                descripcion=r.descripcion,
                detalle_especifico=r.detalle_especifico,
                usuario_responsable=r.usuario_responsable,
                modulo_origen=r.modulo_origen,
            )
            for r in pagina_historial.registros
        ],
    )


# ── CU10B — RF-47: Ficha integral ───────────────────────────────────────────

@router.get(
    '/{id_activo}/ficha-integral',
    response_model=FichaIntegralResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
    },
    summary='Consultar ficha integral del activo biológico (CU10B - RF-47)',
)
def consultar_ficha_integral(
    id_activo: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> FichaIntegralResponse:
    use_case = ConsultarFichaIntegralUseCase(
        db=db,
        activo_repo=SqlAlchemyActivoBiologicoRepository(db),
        bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db),
    )
    ficha = use_case.execute(id_activo, usuario_actual)
    return FichaIntegralResponse(
        id_activo_biologico=ficha.id_activo_biologico,
        identificador=ficha.identificador,
        tipo=ficha.tipo,
        especie=ficha.especie,
        fecha_registro=ficha.fecha_registro,
        dias_en_sistema=ficha.dias_en_sistema,
        estado_actual=ficha.estado_actual,
        infraestructura_asociada=ficha.infraestructura_asociada,
        fase_productiva_activa=ficha.fase_productiva_activa,
        raza=ficha.raza,
        sexo=ficha.sexo,
        fecha_nacimiento=ficha.fecha_nacimiento,
        peso_actual=ficha.peso_actual,
        unidad_peso=ficha.unidad_peso,
        fecha_ultimo_peso=ficha.fecha_ultimo_peso,
        cantidad_actual=ficha.cantidad_actual,
        biomasa_total=ficha.biomasa_total,
        densidad=ficha.densidad,
        eventos_sanitarios=ficha.eventos_sanitarios,
        eventos_productivos=ficha.eventos_productivos,
        eventos_crecimiento=ficha.eventos_crecimiento,
        eventos_reproductivos=ficha.eventos_reproductivos,
        indicadores=ficha.indicadores,
        advertencias=ficha.advertencias,
    )


# ── CU10C — RF-48: Infraestructuras disponibles y transferencia ─────────────

@router.get(
    '/{id_activo}/transferencias/disponibles',
    response_model=list[InfraestructuraDisponibleResponse],
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
    },
    summary='Listar infraestructuras disponibles para transferencia (CU10C - RF-48)',
)
def listar_infraestructuras_disponibles(
    id_activo: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> list[InfraestructuraDisponibleResponse]:
    use_case = RegistrarTransferenciaUseCase(
        db=db,
        activo_repo=SqlAlchemyActivoBiologicoRepository(db),
        transferencia_repo=SqlAlchemyTransferenciaRepository(db),
        infra_port=InfraestructuraM09Adapter(db),
        bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db),
    )
    infras = use_case.listar_infraestructuras_disponibles(id_activo, usuario_actual)
    return [InfraestructuraDisponibleResponse(**i) for i in infras]


@router.post(
    '/{id_activo}/transferencias',
    response_model=TransferenciaResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
        409: {'model': ErrorResponse},
        422: {'model': ErrorResponse},
        500: {'model': ErrorResponse},
    },
    summary='Registrar transferencia interna del activo biológico (CU10C - RF-48)',
)
def registrar_transferencia(
    id_activo: int,
    dto: RegistrarTransferenciaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> TransferenciaResponse:
    use_case = RegistrarTransferenciaUseCase(
        db=db,
        activo_repo=SqlAlchemyActivoBiologicoRepository(db),
        transferencia_repo=SqlAlchemyTransferenciaRepository(db),
        infra_port=InfraestructuraM09Adapter(db),
        bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db),
    )
    resultado = use_case.execute(id_activo, dto, usuario_actual)
    return TransferenciaResponse(
        id_movimiento=resultado.id_movimiento,
        id_activo_biologico=resultado.id_activo_biologico,
        infraestructura_origen=resultado.nombre_infra_origen,
        infraestructura_destino=resultado.nombre_infra_destino,
        fecha_transferencia=resultado.fecha_transferencia,
        motivo_transferencia=resultado.motivo_transferencia,
        mensaje=(
            f'Transferencia registrada exitosamente. '
            f'El activo fue transferido a {resultado.nombre_infra_destino} '
            f'en fecha {resultado.fecha_transferencia.date().isoformat()}.'
        ),
    )


# ── CU11 RF-49 — Asociar sensor IoT al activo biológico ──────────────────────

@router.post(
    '/{id_activo}/sensores',
    status_code=201,
    response_model=AsociacionSensorActivoResponse,
    responses={
        404: {'model': ErrorResponse},
        409: {'model': ErrorResponse},
        422: {'model': ErrorResponse},
    },
    summary='Asociar sensor IoT a un activo biológico (RF-49)',
    dependencies=[Depends(require_permission(_RECURSO_SENSOR, 1))],
)
def asociar_sensor_iot(
    id_activo: int,
    dto: AsociarSensorActivoDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> AsociacionSensorActivoResponse:
    use_case = AsociarSensorActivoUseCase(
        db=db,
        repo=SqlAlchemyAsociacionSensorActivoRepository(db),
        activo_repo=SqlAlchemyActivoBiologicoRepository(db),
        sensor_port=SensorM09Adapter(db),
        infra_port=InfraestructuraM09Adapter(db),
        bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db),
    )
    resultado = use_case.execute(id_activo, dto, usuario_actual)
    return AsociacionSensorActivoResponse(
        id_asociacion_activo_sensor=resultado.id_asociacion_activo_sensor,
        id_activo_biologico=resultado.id_activo_biologico,
        tipo_activo=resultado.tipo_activo,
        tipo_asociacion=resultado.tipo_asociacion,
        dispositivo_iot_id=resultado.dispositivo_iot_id,
        sensor_id=resultado.sensor_id,
        id_infraestructura=resultado.id_infraestructura,
        fecha_inicio=resultado.fecha_inicio,
        fecha_fin=resultado.fecha_fin,
        estado_asociacion=resultado.estado_asociacion,
        motivo=resultado.motivo,
        advertencia=None,
    )


# ── CU12 RF-51 — Consultar indicadores zootécnicos ───────────────────────────

@router.get(
    '/{id_activo}/indicadores',
    response_model=IndicadoresActivoResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        400: {'model': ErrorResponse},
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
    },
    summary='Consultar indicadores zootécnicos del activo biológico (CU12 - RF-51)',
)
def consultar_indicadores(
    id_activo: int,
    fecha_inicio: str | None = Query(default=None, description='Filtro fecha inicio (YYYY-MM-DD)'),
    fecha_fin: str | None = Query(default=None, description='Filtro fecha fin (YYYY-MM-DD)'),
    tipo_indicador: str = Query(
        default='TODOS',
        description='Tipo de indicador: CRECIMIENTO | PRODUCCION | SANITARIO | EFICIENCIA | TODOS',
    ),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> IndicadoresActivoResponse:
    from datetime import date as date_cls
    from pydantic import ValidationError as _PydanticValidationError
    try:
        dto = ConsultarIndicadoresDTO(
            fecha_inicio=date_cls.fromisoformat(fecha_inicio) if fecha_inicio else None,
            fecha_fin=date_cls.fromisoformat(fecha_fin) if fecha_fin else None,
            tipo_indicador=tipo_indicador,
        )
    except ValueError as exc:
        raise DomainValidationError(code='PARAMETROS_INVALIDOS', message=f'Parámetro inválido: {exc}')
    except _PydanticValidationError as exc:
        first = exc.errors()[0]
        raise DomainValidationError(code='PARAMETROS_INVALIDOS', message=first['msg'].replace('Value error, ', ''))

    use_case = ConsultarIndicadoresUseCase(
        db=db,
        activo_repo=SqlAlchemyActivoBiologicoRepository(db),
        indicadores_repo=SqlAlchemyIndicadoresRepository(db),
        bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db),
    )
    resultado = use_case.execute(id_activo, dto, usuario_actual)
    return IndicadoresActivoResponse(
        id_activo_biologico=resultado.id_activo_biologico,
        tipo_activo=resultado.tipo_activo,
        indicadores=[
            IndicadorZootecnicoResponse(
                tipo=ind.tipo,
                valor=ind.valor,
                unidad=ind.unidad,
                periodo_inicio=ind.periodo_inicio,
                periodo_fin=ind.periodo_fin,
                variables_usadas=ind.variables_usadas,
                fecha_calculo=ind.fecha_calculo,
                disponible=ind.disponible,
            )
            for ind in resultado.indicadores
        ],
        advertencias=resultado.advertencias,
    )


# ── CU12 RF-50 — Exponer datos consolidados para módulos externos ─────────────

@router.get(
    '/{id_activo}/datos-consolidados',
    response_model=DatosConsolidadosResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        400: {'model': ErrorResponse},
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
    },
    summary='Exponer datos consolidados del activo biológico para módulos analíticos (CU12 - RF-50)',
)
def consultar_datos_consolidados(
    id_activo: int,
    tipo_dato: str = Query(
        default='todos',
        description='Sección de datos: eventos | fases | estado | metricas | todos',
    ),
    fecha_inicio: str | None = Query(default=None, description='Filtro fecha inicio (YYYY-MM-DD)'),
    fecha_fin: str | None = Query(default=None, description='Filtro fecha fin (YYYY-MM-DD)'),
    pagina: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> DatosConsolidadosResponse:
    from datetime import date as date_cls
    from pydantic import ValidationError as _PydanticValidationError
    try:
        dto = DatosConsolidadosDTO(
            tipo_dato=tipo_dato,
            fecha_inicio=date_cls.fromisoformat(fecha_inicio) if fecha_inicio else None,
            fecha_fin=date_cls.fromisoformat(fecha_fin) if fecha_fin else None,
            pagina=pagina,
            page_size=page_size,
        )
    except ValueError as exc:
        raise DomainValidationError(code='PARAMETROS_INVALIDOS', message=f'Parámetro inválido: {exc}')
    except _PydanticValidationError as exc:
        first = exc.errors()[0]
        raise DomainValidationError(code='PARAMETROS_INVALIDOS', message=first['msg'].replace('Value error, ', ''))

    use_case = ConsultarDatosConsolidadosUseCase(
        db=db,
        activo_repo=SqlAlchemyActivoBiologicoRepository(db),
        indicadores_repo=SqlAlchemyIndicadoresRepository(db),
        bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db),
    )
    datos = use_case.execute(id_activo, dto, usuario_actual)
    return DatosConsolidadosResponse(
        id_activo_biologico=datos.id_activo_biologico,
        identificador=datos.identificador,
        tipo_activo=datos.tipo_activo,
        especie=datos.especie,
        estado_actual=datos.estado_actual,
        infraestructura_asociada=datos.infraestructura_asociada,
        fase_productiva_activa=datos.fase_productiva_activa,
        historial_eventos=datos.secciones.historial_eventos,
        historial_fases=datos.secciones.historial_fases,
        historico_estados=datos.secciones.historico_estados,
        metricas_actuales=datos.secciones.metricas_actuales,
        total_registros=datos.secciones.total_registros,
        pagina_actual=datos.secciones.pagina_actual,
        total_paginas=datos.secciones.total_paginas,
        registros_por_pagina=datos.secciones.registros_por_pagina,
        fecha_generacion=datos.fecha_generacion,
    )
