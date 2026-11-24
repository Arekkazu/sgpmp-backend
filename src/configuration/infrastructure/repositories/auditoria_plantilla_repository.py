# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Implementación SQLAlchemy del puerto :class:`AuditoriaPlantillaRepository`.

Registro append-only: solo inserta, nunca actualiza ni elimina.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.auditoria_plantilla import AuditoriaPlantilla
from src.configuration.domain.repositories.auditoria_plantilla_repository import AuditoriaPlantillaRepository
from src.configuration.infrastructure.models.auditoria_plantilla_model import AuditoriaPlantillaModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyAuditoriaPlantillaRepository(AuditoriaPlantillaRepository):
    """Implementación SQLAlchemy de ``AuditoriaPlantillaRepository``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: AuditoriaPlantillaModel) -> AuditoriaPlantilla:
        return AuditoriaPlantilla(
            id_auditoria_plantilla=orm.id_auditoria_plantilla,
            id_plantilla=orm.id_plantilla,
            id_usuario=orm.id_usuario,
            tipo_operacion=orm.tipo_operacion,
            resultado=orm.resultado,
            valores_anteriores=orm.valores_anteriores,
            valores_nuevos=orm.valores_nuevos,
            fecha_gestion=orm.fecha_gestion,
        )

    def listar_todas(self) -> list[AuditoriaPlantilla]:
        """Retorna todo el historial de auditoría (creación y versionado).

        CU-07 Flujo D (RF-30): sin esto, no hay forma de consultar quién creó
        o versionó una plantilla y cuándo, aunque el registro ya se guarde en
        cada operación de escritura.
        """
        registros = (
            self.db.query(AuditoriaPlantillaModel)
            .order_by(AuditoriaPlantillaModel.fecha_gestion.desc())
            .all()
        )
        return [self._a_entidad(r) for r in registros]

    def registrar(
        self,
        *,
        id_usuario: int,
        tipo_operacion: str,
        valores_nuevos: dict[str, Any],
        id_plantilla: Optional[int] = None,
        resultado: str = "EXITOSO",
        valores_anteriores: Optional[dict[str, Any]] = None,
    ) -> None:
        """Inserta un registro de auditoría append-only.

        Hace ``flush`` interno. El ``commit`` lo emite el caso de uso (o el
        helper ``registrar_intento_fallido`` para el camino de fallo).

        Args:
            id_usuario: Usuario que ejecutó la operación.
            tipo_operacion: ``CREATE``, ``READ`` o ``APPLY``.
            valores_nuevos: Snapshot del estado tras la operación, o detalle
                del error si ``resultado == "FALLIDO"``.
            id_plantilla: Plantilla sobre la que se realizó la operación.
                ``None`` si el intento falló antes de tener un id (ej. creación
                rechazada por nombre duplicado).
            resultado: ``EXITOSO`` o ``FALLIDO``.
            valores_anteriores: Estado previo, cuando aplica (ej. versionado).
        """
        orm = AuditoriaPlantillaModel(
            id_plantilla=id_plantilla,
            id_usuario=id_usuario,
            tipo_operacion=tipo_operacion,
            resultado=resultado,
            valores_nuevos=valores_nuevos,
            valores_anteriores=valores_anteriores,
        )
        try:
            self.db.add(orm)
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc, {})
