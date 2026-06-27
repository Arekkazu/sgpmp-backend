"""Caso de uso: Registrar patología asociada a una especie (Flujo E — RF-16).

Flujo de creación/reutilización:
- Si el nombre no existe globalmente → crea patología + asocia a especie.
- Si existe globalmente y NO está asociada a esta especie → solo asocia.
- Si existe globalmente y YA está asociada a esta especie → 409 (FA-02).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.especie_patologia import EspeciePatologia
from src.configuration.domain.repositories.auditoria_patologia_repository import AuditoriaPatologiaRepository
from src.configuration.domain.repositories.especie_patologia_repository import EspeciePatologiaRepository
from src.configuration.domain.repositories.especie_repository import EspecieRepository
from src.configuration.domain.repositories.patologia_repository import PatologiaRepository
from src.configuration.domain.entities.patologia import Patologia
from src.configuration.domain.value_objects.nombre_patologia import NombrePatologia
from src.configuration.infrastructure.dto.registrar_patologia_dto import RegistrarPatologiaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError


def _snapshot(patologia: Patologia, id_especie: int) -> dict:
    return {
        "id_patologia": patologia.id_patologia,
        "id_especie": id_especie,
        "nombre": patologia.nombre.valor,
        "descripcion": patologia.descripcion,
        "es_activo": patologia.es_activo,
        "fecha_actualizacion": patologia.fecha_actualizacion.isoformat() if patologia.fecha_actualizacion else None,
    }


class RegistrarPatologiaUseCase:

    def __init__(
        self,
        db: Session,
        patologias_repo: PatologiaRepository,
        especie_patologia_repo: EspeciePatologiaRepository,
        especies_repo: EspecieRepository,
        auditoria_repo: AuditoriaPatologiaRepository,
    ) -> None:
        self.db = db
        self.patologias_repo = patologias_repo
        self.especie_patologia_repo = especie_patologia_repo
        self.especies_repo = especies_repo
        self.auditoria_repo = auditoria_repo

    def execute(self, dto: RegistrarPatologiaDTO, usuario_actual: UsuarioActual) -> EspeciePatologia:
        especie = self.especies_repo.obtener_por_id(dto.id_especie)
        if especie is None:
            raise NotFoundError(
                code="ESPECIE_NO_ENCONTRADA",
                message=f"No existe una especie con ID {dto.id_especie}.",
            )
        if not especie.es_activo:
            raise BusinessRuleError(
                code="ESPECIE_INACTIVA",
                message=f"La especie con ID {dto.id_especie} está inactiva.",
            )

        nombre = NombrePatologia(dto.nombre)
        patologia_existente = self.patologias_repo.obtener_por_nombre(nombre)

        try:
            if patologia_existente is None:
                nueva = Patologia.crear(nombre=nombre, descripcion=dto.descripcion)
                patologia_guardada = self.patologias_repo.guardar(nueva, id_usuario_creador=usuario_actual.id_usuario)
                asociacion = self.especie_patologia_repo.asociar(dto.id_especie, patologia_guardada.id_patologia)
                self.auditoria_repo.registrar(
                    id_patologia=patologia_guardada.id_patologia,
                    id_usuario=usuario_actual.id_usuario,
                    tipo_operacion="CREATE",
                    valores_nuevos=_snapshot(patologia_guardada, dto.id_especie),
                )
            else:
                ya_asociada = self.especie_patologia_repo.obtener_por_especie_y_patologia(
                    dto.id_especie, patologia_existente.id_patologia
                )
                if ya_asociada is not None:
                    raise ConflictError(
                        code="PATOLOGIA_DUPLICADA_EN_ESPECIE",
                        message=f"Ya existe una patología con el nombre '{nombre.valor}' para esta especie.",
                        field="nombre",
                    )
                asociacion = self.especie_patologia_repo.asociar(dto.id_especie, patologia_existente.id_patologia)

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return asociacion
