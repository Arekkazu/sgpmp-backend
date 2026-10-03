"""Implementación SQLAlchemy del puerto ``AuditoriaIdentidadVisualRepository`` (RF-26)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.configuration.domain.entities.auditoria_identidad_visual import AuditoriaIdentidadVisual
from src.configuration.domain.repositories.auditoria_identidad_visual_repository import AuditoriaIdentidadVisualRepository
from src.configuration.infrastructure.models.auditoria_identidad_visual_model import AuditoriaIdentidadVisualModel
from src.identity_access.infrastructure.models.usuarios_model import Usuarios
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyAuditoriaIdentidadVisualRepository(AuditoriaIdentidadVisualRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar(
        self,
        *,
        id_usuario: int,
        valor_anterior: dict,
        valor_nuevo: dict,
    ) -> None:
        orm = AuditoriaIdentidadVisualModel(
            id_usuario=id_usuario,
            fecha_creacion=datetime.now(timezone.utc),
            valor_anterior=valor_anterior,
            valor_nuevo=valor_nuevo,
        )
        try:
            self.db.add(orm)
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)

    def listar_por_finca(self, id_finca: int) -> list[AuditoriaIdentidadVisual]:
        """Consulta únicamente filas canónicas, identificables por ``id_finca``.

        El trigger legado generó duplicados sin ``id_finca`` para los UPDATE.
        No se eliminan por tratarse de historial; se excluyen de esta vista de
        lectura para entregar una operación por cambio confirmado.
        """
        stmt = (
            select(
                AuditoriaIdentidadVisualModel,
                Usuarios.nombre,
                Usuarios.apellidos,
            )
            .join(Usuarios, Usuarios.id_usuario == AuditoriaIdentidadVisualModel.id_usuario)
            .where(
                AuditoriaIdentidadVisualModel.valor_nuevo.contains(
                    {"id_finca": id_finca}
                )
            )
            .order_by(
                AuditoriaIdentidadVisualModel.fecha_creacion.desc(),
                AuditoriaIdentidadVisualModel.id_auditoria_visual.desc(),
            )
        )
        filas = self.db.execute(stmt).all()
        return [
            self._a_entidad(orm, nombre, apellidos)
            for orm, nombre, apellidos in filas
        ]

    @staticmethod
    def _a_entidad(
        orm: AuditoriaIdentidadVisualModel,
        nombre: str | None,
        apellidos: str | None,
    ) -> AuditoriaIdentidadVisual:
        valor_anterior = orm.valor_anterior or {}
        valor_nuevo = orm.valor_nuevo or {}
        return AuditoriaIdentidadVisual(
            id_auditoria_visual=orm.id_auditoria_visual,
            id_finca=int(valor_nuevo["id_finca"]),
            id_usuario=orm.id_usuario,
            usuario=" ".join(p for p in (nombre, apellidos) if p).strip(),
            fecha_creacion=orm.fecha_creacion,
            tipo_operacion="CREATE" if not valor_anterior else "UPDATE",
            valor_anterior=valor_anterior,
            valor_nuevo=valor_nuevo,
        )
