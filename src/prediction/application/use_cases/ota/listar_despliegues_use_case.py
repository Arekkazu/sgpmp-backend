# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M04-158-G086 RF-73: identificar consultas globales sin inventar entidades de negocio. |
from __future__ import annotations

import uuid

from typing import Optional

from sqlalchemy.orm import Session

from src.prediction.domain.entities.despliegue_ota import DespliegueOta
from src.prediction.domain.repositories.despliegue_ota_repository import DespliegueOtaRepository
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.version_modelo_port import VersionModeloPort
from src.shared.errors import NotFoundError, ValidationError

_ESTADOS_VALIDOS = {"EXITOSO", "FALLIDO", "PENDIENTE", "SIN_CAMBIOS", "EN_PROCESO"}
_LIMIT_MAX = 100


class ListarDesplieguesUseCase:
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
        id_version: Optional[int],
        id_dispositivo: Optional[int],
        estado: Optional[str],
        limit: int,
        offset: int,
        id_usuario: int,
    ) -> tuple[list[DespliegueOta], int]:
        if id_version is not None and self._version_port.obtener_estado(id_version) is None:
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

        limit = min(limit, _LIMIT_MAX)
        offset = max(offset, 0)

        items, total = self._repo.listar(
            id_version=id_version,
            id_dispositivo=id_dispositivo,
            estado=estado,
            limit=limit,
            offset=offset,
        )

        correlacion = uuid.uuid4()
        try:
            self._auditoria_repo.registrar(
                tipo_evento="HISTORIAL_CONSULTADO",
                tipo_actor="USUARIO",
                payload_evento={
                    "consulta": "DESPLIEGUES_OTA",
                    "id_version_modelo": id_version,
                    "id_dispositivo": id_dispositivo,
                    "estado_filtro": estado,
                    "limit": limit,
                    "offset": offset,
                    "total": total,
                },
                severidad_evento="INFO",
                id_usuario=id_usuario,
                id_referencia=str(id_version) if id_version is not None else str(correlacion),
                correlacion_id=correlacion,
                entidad_referencia="version_modelo" if id_version is not None else "consulta_despliegues_ota",
                resultado_operacion="EXITOSO",
            )
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        return items, total
