from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from src.prediction.domain.entities.version_modelo import VersionModelo
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.version_modelo_repository import VersionModeloRepository
from src.shared.errors import NotFoundError


class ActivarVersionModeloUseCase:

    def __init__(
        self,
        *,
        db: Session,
        repo: VersionModeloRepository,
        auditoria_repo: EventoAuditoriaM04Repository,
    ) -> None:
        self._db = db
        self._repo = repo
        self._auditoria_repo = auditoria_repo

    def execute(self, id_version: int, id_usuario: int) -> VersionModelo:
        entidad = self._repo.obtener_por_id(id_version)
        if entidad is None:
            raise NotFoundError(
                code="VERSION_MODELO_NO_ENCONTRADA",
                message=f"No existe la versión de modelo con id {id_version}.",
            )

        # Llama a activar() — lanza BusinessRuleError si no es APROBADO o faltan notas
        entidad.activar()

        version_previa = self._repo.obtener_activo_por_tipo(entidad.tipo_modelo)
        correlacion = uuid.uuid4()

        try:
            if version_previa and version_previa.id_version_modelo != entidad.id_version_modelo:
                version_previa.deprecar()
                self._repo.actualizar(version_previa)
                self._repo.registrar_historial(
                    id_version_modelo=version_previa.id_version_modelo,
                    estado_anterior="ACTIVO",
                    estado_nuevo="DEPRECADO",
                    tipo_actor="USUARIO",
                    id_usuario=id_usuario,
                    correlacion_id=correlacion,
                    motivo=f"Deprecado al activar versión {entidad.id_version_modelo}",
                )

            self._repo.actualizar(entidad)
            self._repo.registrar_historial(
                id_version_modelo=entidad.id_version_modelo,
                estado_anterior="APROBADO",
                estado_nuevo="ACTIVO",
                tipo_actor="USUARIO",
                id_usuario=id_usuario,
                correlacion_id=correlacion,
                motivo="Activación manual",
            )
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        eventos = [("VERSION_ACTIVADA", entidad)]
        if version_previa and version_previa.id_version_modelo != entidad.id_version_modelo:
            eventos.append(("VERSION_DEPRECADA", version_previa))

        for tipo_ev, obj in eventos:
            self._auditoria_repo.registrar(
                tipo_evento=tipo_ev,
                tipo_actor="USUARIO",
                id_usuario=id_usuario,
                id_referencia=str(obj.id_version_modelo),
                entidad_referencia="version_modelo",
                resultado_operacion="EXITOSO",
                severidad_evento="INFO",
                correlacion_id=correlacion,
                payload_evento=obj._snapshot(),
            )
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()

        return entidad
