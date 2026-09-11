from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.prediction.domain.entities.version_modelo import VersionModelo
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.version_modelo_repository import VersionModeloRepository
from src.shared.errors import NotFoundError


class ConsultarVersionesUseCase:

    def __init__(
        self,
        *,
        repo: VersionModeloRepository,
        auditoria_repo: EventoAuditoriaM04Repository,
        db: Session,
    ) -> None:
        self._repo = repo
        self._auditoria_repo = auditoria_repo
        self._db = db

    def listar(
        self,
        *,
        tipo_modelo: Optional[str] = None,
        estado: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        id_usuario: int,
    ) -> tuple[list[VersionModelo], int]:
        items, total = self._repo.listar(
            tipo_modelo=tipo_modelo, estado=estado, limit=limit, offset=offset
        )
        self._auditoria_repo.registrar(
            tipo_evento="HISTORIAL_CONSULTADO",
            tipo_actor="USUARIO",
            id_usuario=id_usuario,
            entidad_referencia="version_modelo",
            resultado_operacion="EXITOSO",
            severidad_evento="INFO",
            payload_evento={
                "filtros": {"tipo_modelo": tipo_modelo, "estado": estado},
                "total_devueltos": len(items),
                "total_encontrados": total,
            },
        )
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
        return items, total

    def obtener_por_id(self, id_version: int, id_usuario: int) -> VersionModelo:
        entidad = self._repo.obtener_por_id(id_version)
        if entidad is None:
            raise NotFoundError(
                code="VERSION_MODELO_NO_ENCONTRADA",
                message=f"No existe la versión de modelo con id {id_version}.",
            )
        self._auditoria_repo.registrar(
            tipo_evento="HISTORIAL_CONSULTADO",
            tipo_actor="USUARIO",
            id_usuario=id_usuario,
            id_referencia=str(id_version),
            entidad_referencia="version_modelo",
            resultado_operacion="EXITOSO",
            severidad_evento="INFO",
            payload_evento={"id_version_modelo": id_version},
        )
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
        return entidad
