from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases.gestion.actualizar_activo_individual_use_case import (
    ActualizarActivoIndividualUseCase,
)
from src.biological_assets.application.use_cases.gestion.cambiar_fase_use_case import CambiarFaseUseCase
from src.biological_assets.application.use_cases.gestion.consultar_activo_use_case import ConsultarActivoUseCase
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
from src.biological_assets.infrastructure.dto.cambiar_fase_dto import CambiarFaseDTO
from src.biological_assets.infrastructure.dto.registrar_activo_dto import RegistrarActivoBiologicoDTO
from src.biological_assets.infrastructure.repositories.activo_biologico_repository import (
    SqlAlchemyActivoBiologicoRepository,
)
from src.biological_assets.application.use_cases.gestion.consultar_eventos_use_case import ConsultarEventosUseCase
from src.biological_assets.application.use_cases.gestion.registrar_evento_baja_use_case import RegistrarEventoBajaUseCase
from src.biological_assets.application.use_cases.gestion.registrar_evento_crecimiento_use_case import (
    RegistrarEventoCrecimientoUseCase,
)
from src.biological_assets.application.use_cases.gestion.registrar_evento_productivo_use_case import (
    RegistrarEventoProductivoUseCase,
)
from src.biological_assets.application.use_cases.gestion.registrar_evento_sanitario_use_case import (
    RegistrarEventoSanitarioUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import EventoActivo
from src.biological_assets.infrastructure.dto.registrar_evento_baja_dto import RegistrarEventoBajaDTO
from src.biological_assets.infrastructure.dto.registrar_evento_crecimiento_dto import RegistrarEventoCrecimientoDTO
from src.biological_assets.infrastructure.dto.registrar_evento_productivo_dto import RegistrarEventoProductivoDTO
from src.biological_assets.infrastructure.dto.registrar_evento_sanitario_dto import RegistrarEventoSanitarioDTO
from src.biological_assets.infrastructure.repositories.evento_activo_repository import SqlAlchemyEventoActivoRepository
from src.biological_assets.infrastructure.schema.activo_biologico_schema import (
    ActivoBiologicoResponse,
    AsociacionInfraestructuraResponse,
    ConsultaAsociacionResponse,
    DetalleIndividualResponse,
    DetallePoblacionalResponse,
    EventoActivoResponse,
    EventoBajaResponse,
    EventoCrecimientoResponse,
    EventoProductivoResponse,
    EventoSanitarioResponse,
    GestionFaseResponse,
    HistorialEventosResponse,
    HistorialFasesResponse,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix='/activos-biologicos', tags=['Activos Biológicos'])

_RECURSO = 29  # modulo1.recursos: 'activos_biologicos'


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
    )
    activo = use_case.execute(dto, usuario_actual)
    return _activo_to_response(activo)


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
    use_case = ConsultarActivoUseCase(db=db, repo=SqlAlchemyActivoBiologicoRepository(db))
    activo = use_case.execute(id_activo)
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
    use_case = ActualizarActivoIndividualUseCase(db=db, repo=SqlAlchemyActivoBiologicoRepository(db))
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
    )
    resultado = use_case.execute(id_activo, tipo_consulta)

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
        )

    baja = None
    if evento.baja:
        b = evento.baja
        baja = EventoBajaResponse(
            cantidad_afectada=b.cantidad_afectada,
            tipo=b.tipo,
            detalles=b.detalles,
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
    summary='Consultar historial de eventos del lote (RF-36)',
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
    response_model=EventoActivoResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        400: {'model': ErrorResponse},
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
        422: {'model': ErrorResponse},
    },
    summary='Registrar evento de crecimiento del lote (RF-36)',
)
def registrar_evento_crecimiento(
    id_activo: int,
    dto: RegistrarEventoCrecimientoDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> EventoActivoResponse:
    use_case = RegistrarEventoCrecimientoUseCase(
        db=db,
        activo_repo=SqlAlchemyActivoBiologicoRepository(db),
        evento_repo=SqlAlchemyEventoActivoRepository(db),
        infra_port=InfraestructuraM09Adapter(db),
    )
    evento = use_case.execute(id_activo, dto, usuario_actual)
    return _evento_to_response(evento)


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
        422: {'model': ErrorResponse},
    },
    summary='Registrar evento de baja del lote (RF-36)',
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
    )
    evento = use_case.execute(id_activo, dto, usuario_actual)
    return _evento_to_response(evento)


@router.post(
    '/{id_activo}/eventos/sanitario',
    response_model=EventoActivoResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        400: {'model': ErrorResponse},
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
        422: {'model': ErrorResponse},
    },
    summary='Registrar evento sanitario del lote (RF-36)',
)
def registrar_evento_sanitario(
    id_activo: int,
    dto: RegistrarEventoSanitarioDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> EventoActivoResponse:
    use_case = RegistrarEventoSanitarioUseCase(
        db=db,
        activo_repo=SqlAlchemyActivoBiologicoRepository(db),
        evento_repo=SqlAlchemyEventoActivoRepository(db),
    )
    evento = use_case.execute(id_activo, dto, usuario_actual)
    return _evento_to_response(evento)


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
        422: {'model': ErrorResponse},
    },
    summary='Registrar evento productivo del lote (RF-36)',
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
    )
    evento = use_case.execute(id_activo, dto, usuario_actual)
    return _evento_to_response(evento)
