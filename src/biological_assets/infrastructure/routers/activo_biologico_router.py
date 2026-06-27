from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases.registro.consultar_asociacion_use_case import ConsultarAsociacionUseCase
from src.biological_assets.application.use_cases.registro.registrar_activo_use_case import RegistrarActivoBiologicoUseCase
from src.biological_assets.domain.entities.activo_biologico import HistorialInfraestructura
from src.biological_assets.infrastructure.adapters.especie_m09_adapter import EspecieM09Adapter
from src.biological_assets.infrastructure.adapters.infraestructura_m09_adapter import InfraestructuraM09Adapter
from src.biological_assets.infrastructure.adapters.parametros_especie_m09_adapter import ParametrosEspecieM09Adapter
from src.biological_assets.infrastructure.dto.registrar_activo_dto import RegistrarActivoBiologicoDTO
from src.biological_assets.infrastructure.repositories.activo_biologico_repository import (
    SqlAlchemyActivoBiologicoRepository,
)
from src.biological_assets.infrastructure.schema.activo_biologico_schema import (
    ActivoBiologicoResponse,
    AsociacionInfraestructuraResponse,
    ConsultaAsociacionResponse,
    DetalleIndividualResponse,
    DetallePoblacionalResponse,
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
