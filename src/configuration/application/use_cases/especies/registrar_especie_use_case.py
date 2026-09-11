"""Caso de uso: Registrar nueva especie en el catálogo (Flujo A — RF-15).

Solo el Administrador puede registrar especies nuevas.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.repositories.auditoria_especie_repository import AuditoriaEspecieRepository
from src.configuration.domain.repositories.especie_repository import EspecieRepository
from src.configuration.domain.value_objects.nombre_especie import NombreEspecie
from src.configuration.infrastructure.dto.registrar_especie_dto import RegistrarEspecieDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import ConflictError


def _snapshot(especie: Especie) -> dict:
    return {
        "id_especie": especie.id_especie,
        "nombre": especie.nombre.valor,
        "descripcion": especie.descripcion,
        "es_activo": especie.es_activo,
        "fecha_creacion": especie.fecha_creacion.isoformat() if especie.fecha_creacion else None,
        "fecha_actualizacion": especie.fecha_actualizacion.isoformat() if especie.fecha_actualizacion else None,
    }


class RegistrarEspecieUseCase:
    """Registra una especie nueva en el catálogo maestro."""

    def __init__(
        self,
        db: Session,
        especies_repo: EspecieRepository,
        auditoria_repo: AuditoriaEspecieRepository,
    ) -> None:
        self.db = db
        self.especies_repo = especies_repo
        self.auditoria_repo = auditoria_repo

    def execute(self, dto: RegistrarEspecieDTO, usuario_actual: UsuarioActual) -> Especie:
        nombre = NombreEspecie(dto.nombre)

        existente = self.especies_repo.obtener_por_nombre(nombre)
        if existente is not None:
            raise ConflictError(
                code="ESPECIE_DUPLICADA",
                message=f"La especie '{nombre.valor}' ya se encuentra registrada en el catálogo.",
                field="nombre",
            )

        especie = Especie.crear(
            nombre=nombre,
            descripcion=dto.descripcion,
            fecha_creacion=datetime.now(timezone.utc),
        )

        try:
            especie_guardada = self.especies_repo.guardar(especie)
            self.auditoria_repo.registrar(
                id_especie=especie_guardada.id_especie,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="CREATE",
                valores_nuevos=_snapshot(especie_guardada),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return especie_guardada
