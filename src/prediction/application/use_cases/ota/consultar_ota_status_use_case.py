from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.prediction.domain.entities.despliegue_ota import DespliegueOta
from src.prediction.domain.repositories.despliegue_ota_repository import DespliegueOtaRepository
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.version_modelo_port import VersionModeloPort
from src.shared.errors import NotFoundError, ValidationError

_ESTADOS_VALIDOS = {"EXITOSO", "FALLIDO", "PENDIENTE", "SIN_CAMBIOS", "EN_PROCESO"}


class ConsultarOtaStatusUseCase:
    def __init__(
        self,
        *,
        db: Session,
        repo: DespliegueOtaRepository,
        auditoria_repo: EventoAuditoriaM04Repository,
        version_port: VersionModeloPort,
    ) -> None:
        self._db = db
        self._repo = repo
        self._auditoria_repo = auditoria_repo
        self._version_port = version_port

    def execute(
        self,
        *,
        id_version: int,
        id_dispositivo: Optional[int],
        estado: Optional[str],
        id_usuario: int,
    ) -> tuple[int, list[DespliegueOta]]:
        if self._version_port.obtener_estado(id_version) is None:
            raise NotFoundError(
                code="VERSION_NO_ENCONTRADA",
                message="La versión de modelo especificada no existe.",
            )

        if estado is not None and estado not in _ESTADOS_VALIDOS:
            raise ValidationError(
                code="ESTADO_INVALIDO",
                message=f"El estado '{estado}' no es válido. Valores permitidos: {', '.join(sorted(_ESTADOS_VALIDOS))}.",
                field="estado",
            )

        despliegues = self._repo.obtener_por_version(
            id_version=id_version,
            id_dispositivo=id_dispositivo,
            estado=estado,
        )

        try:
            self._auditoria_repo.registrar(
                tipo_evento="CONSULTA_OTA_STATUS",
                tipo_actor="USUARIO",
                payload_evento={
                    "id_version_modelo": id_version,
                    "id_dispositivo": id_dispositivo,
                    "estado_filtro": estado,
                    "total_despliegues": len(despliegues),
                },
                severidad_evento="INFO",
                id_usuario=id_usuario,
                id_referencia=str(id_version),
                entidad_referencia="version_modelo",
                resultado_operacion="OK",
            )
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        return id_version, despliegues
