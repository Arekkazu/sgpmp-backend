from __future__ import annotations

from sqlalchemy.orm import Session

from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.historial_catalogo_repository import HistorialCatalogoRepository
from src.prediction.domain.repositories.modelo_activo_port import ModeloActivoPort
from src.prediction.domain.repositories.patologia_m04_repository import PatologiaM04Repository
from src.shared.errors import ConflictError, NotFoundError


class DesactivarPatologiaUseCase:
    def __init__(
        self,
        *,
        db: Session,
        repo: PatologiaM04Repository,
        historial_repo: HistorialCatalogoRepository,
        auditoria_repo: EventoAuditoriaM04Repository,
        modelo_activo_port: ModeloActivoPort,
    ) -> None:
        self._db = db
        self._repo = repo
        self._historial_repo = historial_repo
        self._auditoria_repo = auditoria_repo
        self._modelo_activo_port = modelo_activo_port

    def execute(self, id_patologia: int, id_usuario: int):
        entidad = self._repo.obtener_por_id(id_patologia)
        if not entidad:
            raise NotFoundError(code="PATOLOGIA_NO_ENCONTRADA", message="Patología no encontrada.")

        # FA-07 / FA-08: verificar modelos activos (cubre ambos flujos alternos)
        if self._modelo_activo_port.tiene_modelos_activos(id_patologia):
            raise ConflictError(
                code="PATOLOGIA_EN_USO_POR_MODELO",
                message="La patología está siendo utilizada por un modelo activo. Desactive el modelo antes de inactivar la patología.",
            )

        snapshot_anterior = entidad._snapshot()
        entidad.desactivar()

        try:
            entidad = self._repo.actualizar(entidad)
            self._historial_repo.registrar(
                id_patologia=entidad.id_patologia,
                version_catalogo=entidad.version_catalogo,
                accion="INACTIVADA",
                datos_nuevos=entidad._snapshot(),
                datos_anteriores=snapshot_anterior,
                id_usuario=id_usuario,
            )
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        self._auditoria_repo.registrar(
            tipo_evento="CATALOGO_PATOLOGIA_INACTIVADA",
            tipo_actor="USUARIO",
            id_usuario=id_usuario,
            id_referencia=str(entidad.id_patologia),
            entidad_referencia="patologia",
            resultado_operacion="EXITOSO",
            payload_evento={"anterior": snapshot_anterior, "nuevo": entidad._snapshot()},
        )
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()

        return entidad
