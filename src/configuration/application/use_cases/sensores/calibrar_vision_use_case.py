"""Caso de uso: calibración por visión — línea base por (área, especie) (RF-24 v2.0, RFC-011).

Flujo (ficha RF-24 v2.0, modalidad VISION):

1. Precondiciones: el área existe (y está en el alcance del usuario), tiene
   especie y un `tipo_modelo_asignado` POBLACIONAL, al menos una cámara activa
   y alguna observación apta (RF-62). Si no → 422 VISION_NO_DISPONIBLE.
2. Reunión de observaciones de las cámaras activas en la ventana (RF-53/56).
3. Las tres etapas (``calcular_linea_base``).
4. Exitosa: se guarda, reemplaza la línea base vigente y se audita en RF-10
   (si la auditoría falla, rollback y 500). Fallida o no convergida: se guarda
   como tal, la línea base vigente no se toca y se responde 422
   LINEA_BASE_NO_CALCULADA.

Todo rechazo (404/422, y el 403 del router) queda en RF-10 con resultado
FALLIDO, best-effort como en la modalidad SENSOR (RFC-006).
"""
from __future__ import annotations

import datetime
import logging
from typing import NoReturn, Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.calibracion_vision import CalibracionVision, LineaBaseVision
from src.configuration.domain.entities.infraestructura import Infraestructura
from src.configuration.domain.entities.linea_base_vision import ParametrosLineaBase, calcular_linea_base
from src.configuration.domain.entities.observacion_vision import ObservacionVision
from src.configuration.domain.repositories.calibracion_vision_repository import (
    CalibracionVisionRepository,
    LineaBaseVisionRepository,
)
from src.configuration.domain.repositories.camara_area_repository import CamaraAreaRepository
from src.configuration.domain.repositories.infraestructura_repository import InfraestructuraRepository
from src.configuration.domain.repositories.observacion_vision_port import ObservacionVisionPort
from src.configuration.domain.value_objects.calibracion_vision import OrigenDisparo
# Mismos tipos de evento RF-10 y mismo 403 que SENSOR; la modalidad va en detalle.operacion.
from src.configuration.application.use_cases.sensores.registrar_calibracion_use_case import (
    MENSAJE_ACCESO_DENEGADO,
    TIPO_EVENTO_CALIBRACION_EXITOSA,
    TIPO_EVENTO_CALIBRACION_RECHAZADA,
)
from src.configuration.infrastructure.dto.calibrar_vision_dto import CalibrarVisionDTO
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import AppError, BusinessRuleError, InfrastructureError, NotFoundError
from src.shared.tipo_modelo import es_poblacional

logger = logging.getLogger(__name__)



def auditar_rechazo_vision(
    db: Session,
    eventos_repo: EventoRepository,
    *,
    id_usuario: int,
    id_infraestructura: Optional[int],
    error: AppError,
    id_especie: Optional[int] = None,
    extra: Optional[dict] = None,
) -> None:
    """Deja el intento rechazado o fallido en RF-10 con resultado FALLIDO.

    Best-effort, igual que en SENSOR: si la escritura falla queda en el log y el
    rechazo conserva su 4xx.
    """
    try:
        eventos_repo.registrar(
            tipo_evento=TIPO_EVENTO_CALIBRACION_RECHAZADA,
            exitoso=False,
            id_usuario=id_usuario,
            detalle={
                "operacion": "CALIBRACION_VISION",
                "id_infraestructura": id_infraestructura,
                "id_especie": id_especie,
                "codigo_http": error.status_code,
                "codigo_error": error.code,
                "motivo": error.message,
                **(extra or {}),
            },
            descripcion=f"Calibración por visión rechazada (HTTP {error.status_code} {error.code})",
            modulo="MODULO9",
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "RF-24: no se pudo auditar el rechazo de calibración por visión del área %s",
            id_infraestructura,
        )


def _no_disponible(id_area: int) -> BusinessRuleError:
    return BusinessRuleError(
        code="VISION_NO_DISPONIBLE",
        message=(
            f"Calibración por visión no disponible: El área {id_area} no cuenta con "
            "observaciones de cámara aptas o no tiene un modelo poblacional asignado. "
            "Verifique las cámaras (RF-21/22) y la configuración del área (RF-20)."
        ),
        field="area_id",
    )


class CalibrarVisionUseCase:

    def __init__(
        self,
        db: Session,
        infraestructura_repo: InfraestructuraRepository,
        camara_repo: CamaraAreaRepository,
        observacion_port: ObservacionVisionPort,
        calibracion_repo: CalibracionVisionRepository,
        linea_base_repo: LineaBaseVisionRepository,
        eventos_repo: EventoRepository,
        parametros: ParametrosLineaBase = ParametrosLineaBase(),
    ) -> None:
        self.db = db
        self.infraestructura_repo = infraestructura_repo
        self.camara_repo = camara_repo
        self.observacion_port = observacion_port
        self.calibracion_repo = calibracion_repo
        self.linea_base_repo = linea_base_repo
        self.eventos_repo = eventos_repo
        self.parametros = parametros

    def execute(
        self,
        dto: CalibrarVisionDTO,
        usuario_actual: UsuarioActual,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> CalibracionVision:
        area: Optional[Infraestructura] = None
        try:
            area, observaciones = self._validar(dto, ids_fincas_permitidas)
        except (NotFoundError, BusinessRuleError) as exc:
            auditar_rechazo_vision(
                self.db,
                self.eventos_repo,
                id_usuario=usuario_actual.id_usuario,
                id_infraestructura=dto.area_id,
                id_especie=area.id_especie if area else None,
                error=exc,
            )
            raise

        resultado = calcular_linea_base(observaciones, self.parametros)
        calibracion = CalibracionVision.desde_resultado(
            resultado,
            id_infraestructura=area.id_infraestructura,
            id_especie=area.id_especie,
            origen_disparo=OrigenDisparo.MANUAL,
            id_usuario=usuario_actual.id_usuario,
            ventana_observacion=dto.ventana_observacion.model_dump(mode="json"),
            fecha_calibracion=dto.fecha_calibracion or datetime.datetime.now(datetime.timezone.utc),
            observaciones=dto.observaciones,
        )

        if not calibracion.es_exitosa:
            self._registrar_fallida(calibracion, usuario_actual)

        try:
            guardada = self.calibracion_repo.guardar(calibracion)
            # Reemplaza la línea base vigente del par (área, especie).
            self.linea_base_repo.publicar(
                LineaBaseVision(
                    id_infraestructura=guardada.id_infraestructura,
                    id_especie=guardada.id_especie,
                    id_calibracion_vision=guardada.id_calibracion_vision,
                    valor=guardada.linea_base,
                    fecha_publicacion=guardada.fecha_calibracion,
                )
            )
            # RF-10: sin traza no hay línea base nueva (rollback y 500, como en SENSOR).
            try:
                self.eventos_repo.registrar(
                    tipo_evento=TIPO_EVENTO_CALIBRACION_EXITOSA,
                    exitoso=True,
                    id_usuario=usuario_actual.id_usuario,
                    detalle={"operacion": "CALIBRACION_VISION", **guardada._snapshot()},
                    descripcion=f"Línea base por visión publicada para el área {guardada.id_infraestructura}",
                    modulo="MODULO9",
                )
            except Exception as exc:
                raise InfrastructureError(
                    code="AUDITORIA_CALIBRACION_FALLIDA",
                    message=(
                        "Error de integridad: No se pudo garantizar la trazabilidad de la "
                        "calibración. El ajuste no ha sido aplicado; por favor, intente de nuevo."
                    ),
                    original_error=exc,
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return guardada

    def _validar(
        self, dto: CalibrarVisionDTO, ids_fincas_permitidas: Optional[list[int]]
    ) -> tuple[Infraestructura, list[ObservacionVision]]:
        # Un área de una finca ajena responde 404, igual que una inexistente (#503).
        area = self.infraestructura_repo.obtener_por_id(
            dto.area_id, ids_fincas_permitidas=ids_fincas_permitidas
        )
        if area is None:
            raise NotFoundError(
                code="AREA_NO_ENCONTRADA",
                message=f"No existe un área productiva con ID {dto.area_id}.",
                field="area_id",
            )
        # RF-20: especie y tipo_modelo_asignado del paradigma POBLACIONAL.
        if area.id_especie is None or not es_poblacional(area.tipo_modelo_asignado):
            raise _no_disponible(dto.area_id)

        camaras_activas = [c for c in self.camara_repo.listar_por_area(dto.area_id) if c.es_activo]
        if not camaras_activas:
            raise _no_disponible(dto.area_id)

        observaciones = self.observacion_port.listar(
            [c.id_dispositivo_iot for c in camaras_activas],
            dto.ventana_observacion.inicio,
            dto.ventana_observacion.fin,
        )
        # Hay observaciones, pero ninguna apta para IA (RF-62): mismo flujo alterno.
        # Sin ninguna observación es un caso de datos insuficientes (Etapa 1).
        if observaciones and not any(o.es_apto_para_ia for o in observaciones):
            raise _no_disponible(dto.area_id)
        return area, observaciones

    def _registrar_fallida(
        self, calibracion: CalibracionVision, usuario_actual: UsuarioActual
    ) -> NoReturn:
        # La ficha pide dejar el intento como FALLIDA (o NO CONVERGIDA) con el
        # motivo de la etapa, sin publicar línea base: la vigente se conserva.
        try:
            guardada = self.calibracion_repo.guardar(calibracion)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        error = BusinessRuleError(
            code="LINEA_BASE_NO_CALCULADA",
            message=(
                "No se pudo calcular la línea base: datos insuficientes o sin convergencia "
                f"para el área {guardada.id_infraestructura} y especie {guardada.id_especie}. "
                "Se conserva la línea base vigente anterior."
            ),
        )
        auditar_rechazo_vision(
            self.db,
            self.eventos_repo,
            id_usuario=usuario_actual.id_usuario,
            id_infraestructura=guardada.id_infraestructura,
            id_especie=guardada.id_especie,
            error=error,
            extra={
                "id_calibracion_vision": guardada.id_calibracion_vision,
                "estado": guardada.estado.value,
                "etapa_fallo": guardada.etapa_fallo.value if guardada.etapa_fallo else None,
                "motivo_etapa": guardada.motivo,
            },
        )
        raise error


class ConsultarCalibracionVisionUseCase:

    def __init__(
        self,
        infraestructura_repo: InfraestructuraRepository,
        calibracion_repo: CalibracionVisionRepository,
        linea_base_repo: LineaBaseVisionRepository,
    ) -> None:
        self.infraestructura_repo = infraestructura_repo
        self.calibracion_repo = calibracion_repo
        self.linea_base_repo = linea_base_repo

    def _area(self, area_id: int, ids_fincas_permitidas: Optional[list[int]]) -> Infraestructura:
        area = self.infraestructura_repo.obtener_por_id(area_id, ids_fincas_permitidas=ids_fincas_permitidas)
        if area is None:
            raise NotFoundError(
                code="AREA_NO_ENCONTRADA",
                message=f"No existe un área productiva con ID {area_id}.",
                field="area_id",
            )
        return area

    def listar_por_area(
        self, area_id: int, *, ids_fincas_permitidas: Optional[list[int]] = None
    ) -> list[CalibracionVision]:
        self._area(area_id, ids_fincas_permitidas)
        return self.calibracion_repo.listar_por_area(area_id)

    def obtener_linea_base_vigente(
        self, area_id: int, *, ids_fincas_permitidas: Optional[list[int]] = None
    ) -> LineaBaseVision:
        area = self._area(area_id, ids_fincas_permitidas)
        linea_base = (
            self.linea_base_repo.obtener_vigente(area_id, area.id_especie)
            if area.id_especie is not None else None
        )
        if linea_base is None:
            raise NotFoundError(
                code="LINEA_BASE_NO_ENCONTRADA",
                message=f"El área {area_id} no tiene una línea base por visión vigente para su especie.",
            )
        return linea_base
