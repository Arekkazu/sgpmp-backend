"""Router FastAPI para tipos de dispositivo IoT (`/configuracion/tipos-dispositivo-iot`).

RF-23 — el frontend consume este catálogo para poblar el selector de tipo al
registrar un dispositivo y para mostrar los rangos permitidos por tipo.
Solo lectura; los rangos se gestionan por seed/SQL.

RBAC: reutiliza id_recurso=11 (dispositivos_iot), acción R=2.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.configuration.infrastructure.repositories.tipo_dispositivo_iot_repository import SqlAlchemyTipoDispositivoIotRepository
from src.configuration.infrastructure.schema.tipo_dispositivo_iot_schema import ListaTiposDispositivoIotResponse, TipoDispositivoIotResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/configuracion/tipos-dispositivo-iot", tags=["Configuración - Dispositivos IoT"])

_RECURSO = 11  # modulo1.recursos: 'dispositivos_iot'


@router.get(
    "",
    response_model=ListaTiposDispositivoIotResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Listar tipos de dispositivo IoT y sus rangos (RF-23)",
)
def listar_tipos_dispositivo_iot(
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ListaTiposDispositivoIotResponse:
    tipos = SqlAlchemyTipoDispositivoIotRepository(db).listar()
    items = [TipoDispositivoIotResponse.from_entity(t) for t in tipos]
    return ListaTiposDispositivoIotResponse(total=len(items), items=items)
