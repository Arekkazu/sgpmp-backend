# | Fecha      | Nombre       | Que se hizo                                           |
# |------------|--------------|-------------------------------------------------------|
# | 2026-10-23 | destroyerban | DEV-34 RF-69: códigos HTTP de E2, E3 y E4             |
# | 2026-10-29 | Arekkazu     | QA-M04-27-10 CU09 H-03 RF-73: VERSION_ACTIVADA con id_version_deprecada |
# | 2026-10-31 | Arekkazu     | RFC-010 RF-69: versión por animal, estado SOMBRA y fuente de datos |
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

    def execute(self, id_version: int, id_usuario: int, en_sombra: bool = False) -> VersionModelo:
        """Activa la versión, o con ``en_sombra`` la pone en SOMBRA (RFC-010).

        En los dos casos la llave (tipo_modelo, componente, id_activo_biologico) queda con una
        sola versión en el estado destino: la que estaba ahí pasa a DEPRECADO.
        """
        entidad = self._repo.obtener_por_id(id_version)
        if entidad is None:
            raise NotFoundError(
                code="VERSION_MODELO_NO_ENCONTRADA",
                message=f"No existe la versión de modelo con id {id_version}.",
            )

        estado_anterior = entidad.estado_version
        # ConflictError (409, RF-69 E4) si no viene de APROBADO/SOMBRA; BusinessRuleError si faltan notas
        if en_sombra:
            entidad.poner_en_sombra()
        else:
            entidad.activar()
        destino = entidad.estado_version

        # RF-69 R5 v2.0 (RFC-009 + RFC-010): una versión por estado y por llave.
        version_previa = self._repo.obtener_activo_por_tipo(
            entidad.tipo_modelo, entidad.componente, entidad.id_activo_biologico, estado=destino
        )
        deprecada = (
            version_previa
            if version_previa and version_previa.id_version_modelo != entidad.id_version_modelo
            else None
        )
        correlacion = uuid.uuid4()

        try:
            if deprecada:
                deprecada.deprecar()
                self._repo.actualizar(deprecada)
                self._repo.registrar_historial(
                    id_version_modelo=deprecada.id_version_modelo,
                    estado_anterior=destino,
                    estado_nuevo="DEPRECADO",
                    tipo_actor="USUARIO",
                    id_usuario=id_usuario,
                    correlacion_id=correlacion,
                    motivo=f"Deprecado al pasar a {destino} la versión {entidad.id_version_modelo}",
                )

            self._repo.actualizar(entidad)
            self._repo.registrar_historial(
                id_version_modelo=entidad.id_version_modelo,
                estado_anterior=estado_anterior,
                estado_nuevo=destino,
                tipo_actor="USUARIO",
                id_usuario=id_usuario,
                correlacion_id=correlacion,
                motivo="Puesta en sombra manual" if en_sombra else "Activación manual",
            )
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        eventos = [("VERSION_EN_SOMBRA" if en_sombra else "VERSION_ACTIVADA", entidad)]
        if deprecada:
            eventos.append(("VERSION_DEPRECADA", deprecada))

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
                payload_evento=(
                    # CU09 H-03 (RF-73 CA-15): null en la primera activación del tipo.
                    {
                        **obj._snapshot(),
                        "id_version_nueva": obj.id_version_modelo,
                        "id_version_deprecada": deprecada.id_version_modelo if deprecada else None,
                    }
                    if tipo_ev == "VERSION_ACTIVADA"
                    else obj._snapshot()
                ),
            )
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()

        return entidad
