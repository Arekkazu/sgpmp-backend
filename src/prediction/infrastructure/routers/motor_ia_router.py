# | Fecha      | Nombre       | Que se hizo                                           |
# |------------|--------------|-------------------------------------------------------|
# | 2026-10-23 | destroyerban | DEV-33 RF-65: E2 y E5 responden 409                 |
# | 2026-10-23 | Arekkazu     | DEV-36 RF-65: 412 por config_version y GET /{tipo_modelo}/historial |
"""Router FastAPI para configuración del motor de inferencia IA (`/prediccion/motor-ia`).

RF-65 CU-02: Configurar parámetros del motor de inferencia por tipo de modelo (v2.0, RFC-009:
los umbrales y la versión activa dependen del paradigma del tipo_modelo).
  POST  /prediccion/motor-ia              — Crear o actualizar configuración (append-only vía auditoría)
  GET   /prediccion/motor-ia              — Listar todas las configuraciones activas
  GET   /prediccion/motor-ia/{tipo_modelo}— Obtener configuración por tipo de modelo
  GET   /prediccion/motor-ia/{tipo_modelo}/sincronizacion — Estado en cada nodo Edge (DEV-09)
  GET   /prediccion/motor-ia/{tipo_modelo}/historial — Versiones de la configuración (DEV-36, R5)

DEV-36 (RF-65 CA-9): editar exige la ``config_version`` que el cliente leyó; si otro
usuario guardó antes, 412 CONFLICTO_CONCURRENCIA.

DEV-09 (RF-65 E7/E8/E10): al guardar, la configuración se envía a los nodos Edge
del tipo_modelo por el broker (``origen: "config_motor"``) y el código HTTP
refleja el resultado, con la configuración ya guardada en todos los casos:
  201 / 200  todos los nodos confirmaron la misma config_version (o no hay nodos)
  202        algún nodo quedó PENDIENTE (desconectado, E7) o FALLIDA (sin ACK, E8)
  409        algún nodo confirmó otra config_version: DESINCRONIZADO (E10)

Autorización RBAC:
  recurso configuracion_motor_ia = id_recurso 41
  C=1 (Administrador, Veterinario), R=2 (Administrador, Veterinario, Ingeniero)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.prediction.application.use_cases.motor_ia.configurar_motor_use_case import ConfigurarMotorUseCase
from src.prediction.application.use_cases.motor_ia.consultar_motor_use_case import ConsultarMotorUseCase
from src.prediction.application.use_cases.motor_ia.consultar_sincronizacion_motor_use_case import (
    ConsultarSincronizacionMotorUseCase,
)
from src.prediction.infrastructure.adapters.config_motor_edge_mqtt_adapter import ConfigMotorEdgeMqttAdapter
from src.prediction.infrastructure.adapters.nodo_edge_m09_adapter import NodoEdgeM09Adapter
from src.prediction.infrastructure.adapters.version_modelo_adapter import VersionModeloAdapter
from src.prediction.infrastructure.dto.configurar_motor_dto import ConfigurarMotorDTO
from src.prediction.infrastructure.repositories.configuracion_motor_ia_repository import SqlAlchemyConfiguracionMotorIARepository
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import SqlAlchemyEventoAuditoriaM04Repository
from src.prediction.infrastructure.repositories.sincronizacion_nodo_edge_repository import (
    SqlAlchemySincronizacionNodoEdgeRepository,
)
from src.prediction.infrastructure.schema.configuracion_motor_ia_schema import (
    ConfiguracionMotorIAGuardadaResponse,
    ConfiguracionMotorIAListResponse,
    HistorialConfiguracionMotorResponse,
    VersionConfiguracionMotorResponse,
    ConfiguracionMotorIAResponse,
    SincronizacionMotorSchema,
)
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/prediccion/motor-ia", tags=["Predicción M04 - Motor de Inferencia IA"])

_RECURSO = 41  # modulo1.recursos: 'configuracion_motor_ia'


@router.post(
    "",
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        200: {"model": ConfiguracionMotorIAGuardadaResponse, "description": "Configuración actualizada y aplicada en sus nodos"},
        201: {"model": ConfiguracionMotorIAGuardadaResponse, "description": "Configuración creada y aplicada en sus nodos"},
        202: {
            "model": ConfiguracionMotorIAGuardadaResponse,
            "description": "Configuración guardada; algún nodo quedó PENDIENTE (E7) o FALLIDA (E8)",
        },
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        412: {"model": ErrorResponse, "description": "CONFLICTO_CONCURRENCIA: config_version distinta a la vigente (CA-9)"},
        409: {
            "model": ConfiguracionMotorIAGuardadaResponse,
            "description": (
                "E10: configuración guardada; algún nodo confirmó otra config_version (cuerpo de configuración). "
                "E2 MODELO_NO_ACTIVO / E5 VERSION_MODELO_INCOMPATIBLE: no se guarda nada (cuerpo ErrorResponse)"
            ),
        },
        422: {"model": ErrorResponse},
    },
    summary="Configurar motor de inferencia IA por tipo de modelo (RF-65)",
)
def configurar_motor(
    dto: ConfigurarMotorDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> JSONResponse:
    use_case = ConfigurarMotorUseCase(
        db=db,
        repo=SqlAlchemyConfiguracionMotorIARepository(db),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db),
        version_port=VersionModeloAdapter(db),
        nodo_edge_port=NodoEdgeM09Adapter(db),
        sincronizacion_repo=SqlAlchemySincronizacionNodoEdgeRepository(db),
        config_edge_port=ConfigMotorEdgeMqttAdapter(),
    )
    resultado = use_case.execute(dto, usuario_actual.id_usuario)
    if resultado.sincronizacion.hay_desincronizados:
        status_code = 409
    elif resultado.sincronizacion.hay_sin_confirmar:
        status_code = 202
    else:
        status_code = 201 if resultado.es_nueva else 200
    respuesta = ConfiguracionMotorIAGuardadaResponse(
        **ConfiguracionMotorIAResponse.from_entity(resultado.entidad).model_dump(),
        sincronizacion=SincronizacionMotorSchema.model_validate(resultado.sincronizacion),
    )
    return JSONResponse(content=respuesta.model_dump(mode="json"), status_code=status_code)


@router.get(
    "",
    response_model=ConfiguracionMotorIAListResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Listar configuraciones del motor de inferencia IA (RF-65)",
)
def listar_configuraciones(
    db: Session = Depends(get_db),
) -> ConfiguracionMotorIAListResponse:
    use_case = ConsultarMotorUseCase(repo=SqlAlchemyConfiguracionMotorIARepository(db))
    items = use_case.listar()
    return ConfiguracionMotorIAListResponse(
        total=len(items),
        items=[ConfiguracionMotorIAResponse.from_entity(e) for e in items],
    )


@router.get(
    "/{tipo_modelo}",
    response_model=ConfiguracionMotorIAResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Obtener configuración del motor por tipo de modelo (RF-65)",
)
def obtener_configuracion(
    tipo_modelo: str,
    db: Session = Depends(get_db),
) -> ConfiguracionMotorIAResponse:
    use_case = ConsultarMotorUseCase(repo=SqlAlchemyConfiguracionMotorIARepository(db))
    entidad = use_case.obtener_por_tipo(tipo_modelo)
    return ConfiguracionMotorIAResponse.from_entity(entidad)


@router.get(
    "/{tipo_modelo}/sincronizacion",
    response_model=SincronizacionMotorSchema,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Estado de la configuración del motor en cada nodo Edge (RF-65)",
)
def consultar_sincronizacion(
    tipo_modelo: str,
    db: Session = Depends(get_db),
) -> SincronizacionMotorSchema:
    use_case = ConsultarSincronizacionMotorUseCase(
        repo=SqlAlchemyConfiguracionMotorIARepository(db),
        sincronizacion_repo=SqlAlchemySincronizacionNodoEdgeRepository(db),
    )
    return SincronizacionMotorSchema.model_validate(use_case.execute(tipo_modelo))


@router.get(
    "/{tipo_modelo}/historial",
    response_model=HistorialConfiguracionMotorResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Historial append-only de la configuración del motor (RF-65 R5)",
)
def consultar_historial(
    tipo_modelo: str,
    db: Session = Depends(get_db),
) -> HistorialConfiguracionMotorResponse:
    """La versión vigente y todas las anteriores, de la más nueva a la más vieja.

    **Acceso:** `configuracion_motor_ia` · Leer.
    """
    versiones = ConsultarMotorUseCase(repo=SqlAlchemyConfiguracionMotorIARepository(db)).historial(tipo_modelo)
    return HistorialConfiguracionMotorResponse(
        tipo_modelo=tipo_modelo,
        total=len(versiones),
        items=[VersionConfiguracionMotorResponse.from_entity(v) for v in versiones],
    )
