"""Caso de uso: Editar umbral ambiental y sus niveles de alerta (Flujo B — RF-17).

Concurrencia optimista mediante ``fecha_actualizacion`` (FA-09 → HTTP 412).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.nivel_alerta_ambiental import NivelAlertaAmbiental
from src.configuration.domain.entities.umbral_ambiental import UmbralAmbiental
from src.configuration.domain.repositories.auditoria_umbral_repository import AuditoriaUmbralRepository
from src.configuration.domain.repositories.umbral_ambiental_repository import UmbralAmbientalRepository
from src.configuration.domain.repositories.variable_ambiental_repository import VariableAmbientalRepository
from src.configuration.domain.value_objects.nivel_alerta import NivelAlerta
from src.configuration.infrastructure.dto.editar_umbral_dto import EditarUmbralDTO
from src.configuration.application.use_cases.umbrales.registrar_umbral_use_case import _validar_rangos
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, NotFoundError, PreconditionFailedError


class EditarUmbralUseCase:

    def __init__(
        self,
        db: Session,
        umbral_repo: UmbralAmbientalRepository,
        variable_repo: VariableAmbientalRepository,
        auditoria_repo: AuditoriaUmbralRepository,
    ) -> None:
        self.db = db
        self.umbral_repo = umbral_repo
        self.variable_repo = variable_repo
        self.auditoria_repo = auditoria_repo

    def execute(
        self,
        id_umbral_ambiental: int,
        dto: EditarUmbralDTO,
        usuario_actual: UsuarioActual,
    ) -> UmbralAmbiental:
        umbral = self.umbral_repo.obtener_por_id(id_umbral_ambiental)
        if umbral is None:
            raise NotFoundError(
                code='UMBRAL_NO_ENCONTRADO',
                message=f"No existe un umbral ambiental con ID {id_umbral_ambiental}.",
            )
        if not umbral.es_activo:
            raise BusinessRuleError(
                code='UMBRAL_INACTIVO',
                message="No se puede editar un umbral inactivo.",
            )

        # FA-09: concurrencia optimista
        ts_actual = umbral.fecha_actualizacion
        ts_dto = dto.fecha_actualizacion
        if ts_actual is not None and ts_dto is not None:
            if ts_actual.astimezone(timezone.utc) != ts_dto.astimezone(timezone.utc):
                raise PreconditionFailedError(
                    code='CONFLICTO_CONCURRENCIA',
                    message="El umbral fue modificado por otro usuario. Recargue los datos e intente de nuevo.",
                )
        elif ts_actual != ts_dto:
            raise PreconditionFailedError(
                code='CONFLICTO_CONCURRENCIA',
                message="El umbral fue modificado por otro usuario. Recargue los datos e intente de nuevo.",
            )

        variable = self.variable_repo.obtener_por_id(umbral.id_variable_ambiental)

        niveles = [
            NivelAlertaAmbiental(
                nivel=NivelAlerta.desde_string(n.nivel),
                limite_inferior=n.limite_inferior,
                limite_superior=n.limite_superior,
            )
            for n in dto.niveles
        ]

        _validar_rangos(dto.valor_min, dto.valor_max, niveles, variable)

        snapshot_anterior = umbral._snapshot()
        umbral.actualizar(
            valor_min=dto.valor_min,
            valor_max=dto.valor_max,
            niveles=niveles,
            id_usuario=usuario_actual.id_usuario,
            ts_ahora=datetime.now(timezone.utc),
        )

        try:
            umbral_actualizado = self.umbral_repo.actualizar(umbral)
            self.auditoria_repo.registrar(
                id_umbral_ambiental=umbral_actualizado.id_umbral_ambiental,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion='UPDATE',
                valores_anteriores=snapshot_anterior,
                valores_nuevos=umbral_actualizado._snapshot(),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return umbral_actualizado
