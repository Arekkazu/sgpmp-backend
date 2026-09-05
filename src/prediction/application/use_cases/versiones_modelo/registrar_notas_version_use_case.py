from __future__ import annotations

from sqlalchemy.orm import Session

from src.prediction.domain.entities.version_modelo import VersionModelo
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.version_modelo_repository import VersionModeloRepository
from src.prediction.infrastructure.dto.registrar_notas_version_dto import RegistrarNotasVersionDTO
from src.shared.errors import NotFoundError


class RegistrarNotasVersionUseCase:

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

    def execute(self, id_version: int, dto: RegistrarNotasVersionDTO, id_usuario: int) -> VersionModelo:
        entidad = self._repo.obtener_por_id(id_version)
        if entidad is None:
            raise NotFoundError(
                code="VERSION_MODELO_NO_ENCONTRADA",
                message=f"No existe la versión de modelo con id {id_version}.",
            )

        entidad.registrar_notas(dto.notas_validacion)

        try:
            entidad = self._repo.actualizar(entidad)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        self._auditoria_repo.registrar(
            tipo_evento="VERSION_APROBADA",
            tipo_actor="USUARIO",
            id_usuario=id_usuario,
            id_referencia=str(entidad.id_version_modelo),
            entidad_referencia="version_modelo",
            resultado_operacion="EXITOSO",
            severidad_evento="INFO",
            payload_evento={
                "accion": "NOTAS_REGISTRADAS",
                "valores_nuevos": entidad._snapshot(),
            },
        )
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()

        return entidad
