# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RFC-021 RF-110 C21.1: API de aristas de transmisión entre áreas  |
# | 2026-11-02 | Arekkazu | RF-110: PATCH para editar vía, dirección, intensidad y barrera    |
"""Topología sanitaria de la finca (RF-110, RFC-021): por dónde puede pasar una enfermedad entre áreas.

  POST  /configuracion/topologia-sanitaria/aristas                — Declarar una arista
  GET   /configuracion/topologia-sanitaria/aristas?id_finca=      — Aristas activas de la finca
  PATCH /configuracion/topologia-sanitaria/aristas/{id}            — Editar vía, dirección, intensidad o barrera
  PATCH /configuracion/topologia-sanitaria/aristas/{id}/desactivar — Desactivar

RBAC: id_recurso=87 (topologia_sanitaria, migración 33ae7f41e560).
  Administrador y Veterinario: C/R/U/D · Productor e Ingeniero: R.
RF-68 usa las aristas activas para la exposición de cada área a los focos de sus vecinas.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.topologia.desactivar_arista_transmision_use_case import (
    DesactivarAristaTransmisionUseCase,
)
from src.configuration.application.use_cases.topologia.editar_arista_transmision_use_case import (
    EditarAristaTransmisionUseCase,
)
from src.configuration.application.use_cases.topologia.listar_aristas_transmision_use_case import (
    ListarAristasTransmisionUseCase,
)
from src.configuration.application.use_cases.topologia.registrar_arista_transmision_use_case import (
    RegistrarAristaTransmisionUseCase,
)
from src.configuration.domain.entities.arista_transmision import AristaTransmision
from src.configuration.infrastructure.dto.registrar_arista_transmision_dto import (
    EditarAristaTransmisionDTO,
    RegistrarAristaTransmisionDTO,
)
from src.configuration.infrastructure.repositories.arista_transmision_repository import (
    SqlAlchemyAristaTransmisionRepository,
)
from src.configuration.infrastructure.repositories.infraestructura_repository import (
    SqlAlchemyInfraestructuraRepository,
)
from src.configuration.infrastructure.schema.arista_transmision_schema import AristaTransmisionResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.alcance_finca_adapter import AlcanceFincaAdapter
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/configuracion/topologia-sanitaria", tags=["Configuración - Topología sanitaria"])

_RECURSO = 87  # modulo1.recursos: 'topologia_sanitaria'


def _respuesta(arista: AristaTransmision) -> AristaTransmisionResponse:
    return AristaTransmisionResponse.model_validate(arista)


def _alcance(db: Session, usuario_actual: UsuarioActual) -> list[int] | None:
    return AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(usuario_actual.id_usuario, usuario_actual.id_rol)


@router.post(
    "/aristas",
    response_model=AristaTransmisionResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse},
               409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Declarar una arista de transmisión entre dos áreas (RF-110)",
)
def registrar_arista(
    dto: RegistrarAristaTransmisionDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> AristaTransmisionResponse:
    """Peso = `intensidad × factor_barrera`. 404 si un área no existe o no es del usuario; 422 si está
    inactiva, si son la misma área o de fincas distintas; 409 si ya hay una arista activa con el mismo
    origen, destino y vía."""
    arista = RegistrarAristaTransmisionUseCase(
        db, SqlAlchemyAristaTransmisionRepository(db), SqlAlchemyInfraestructuraRepository(db),
    ).execute(dto, usuario_actual.id_usuario, _alcance(db, usuario_actual))
    return _respuesta(arista)


@router.get(
    "/aristas",
    response_model=list[AristaTransmisionResponse],
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Aristas activas de la topología sanitaria de una finca (RF-110)",
)
def listar_aristas(
    id_finca: int = Query(..., gt=0),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> list[AristaTransmisionResponse]:
    aristas = ListarAristasTransmisionUseCase(SqlAlchemyAristaTransmisionRepository(db)).execute(
        id_finca, _alcance(db, usuario_actual),
    )
    return [_respuesta(a) for a in aristas]


@router.patch(
    "/aristas/{id_arista_transmision}",
    response_model=AristaTransmisionResponse,
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse},
               409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Editar una arista de transmisión (RF-110)",
)
def editar_arista(
    id_arista_transmision: int,
    dto: EditarAristaTransmisionDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> AristaTransmisionResponse:
    """Solo cambian los campos enviados. 404 si la arista no existe o es de un área ajena; 422 si está
    inactiva o no se envió nada; 409 si con la nueva vía repite otra arista activa."""
    arista = EditarAristaTransmisionUseCase(db, SqlAlchemyAristaTransmisionRepository(db)).execute(
        id_arista_transmision, dto,
    )
    return _respuesta(arista)


@router.patch(
    "/aristas/{id_arista_transmision}/desactivar",
    response_model=AristaTransmisionResponse,
    dependencies=[Depends(require_permission(_RECURSO, 4))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse},
               422: {"model": ErrorResponse}},
    summary="Desactivar una arista de transmisión (RF-110)",
)
def desactivar_arista(
    id_arista_transmision: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> AristaTransmisionResponse:
    arista = DesactivarAristaTransmisionUseCase(db, SqlAlchemyAristaTransmisionRepository(db)).execute(
        id_arista_transmision,
    )
    return _respuesta(arista)
