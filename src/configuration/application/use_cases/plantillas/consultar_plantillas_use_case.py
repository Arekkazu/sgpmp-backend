"""Caso de uso: Consultar plantillas de configuración e historial de aplicaciones (RF-30)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.application.use_cases.plantillas._auditoria_comun import registrar_intento_fallido
from src.configuration.domain.entities.aplicacion_plantilla import AplicacionPlantilla
from src.configuration.domain.entities.auditoria_plantilla import AuditoriaPlantilla
from src.configuration.domain.entities.plantilla import Plantilla
from src.configuration.domain.repositories.aplicacion_plantilla_repository import AplicacionPlantillaRepository
from src.configuration.domain.repositories.auditoria_plantilla_repository import AuditoriaPlantillaRepository
from src.configuration.domain.repositories.plantilla_repository import PlantillaRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError


class ConsultarPlantillasUseCase:
    """Lista plantillas disponibles, historial de aplicaciones y auditoría.

    INC-M09-01-109 (#319): el RF-30 exige auditar también las operaciones de
    consulta, no solo las de escritura. Cada lectura sobre plantillas queda
    registrada en `auditorias_plantillas` (tipo_operacion='READ'). `listar_auditoria`
    y el esquema estático quedan fuera: el primero es meta (auditar la propia
    consulta de auditoría no aporta), el segundo no lee de la tabla `plantillas`.
    """

    def __init__(
        self,
        db: Session,
        plantilla_repo: PlantillaRepository,
        aplicacion_repo: AplicacionPlantillaRepository,
        auditoria_repo: AuditoriaPlantillaRepository,
    ) -> None:
        self.db = db
        self.plantilla_repo = plantilla_repo
        self.aplicacion_repo = aplicacion_repo
        self.auditoria_repo = auditoria_repo

    def listar_plantillas(self, usuario_actual: UsuarioActual) -> list[Plantilla]:
        resultado = self.plantilla_repo.listar_todas()
        self.auditoria_repo.registrar(
            id_usuario=usuario_actual.id_usuario,
            tipo_operacion="READ",
            valores_nuevos={"operacion": "listar_plantillas", "total": len(resultado)},
        )
        self.db.commit()
        return resultado

    def obtener_plantilla(self, id_plantilla: int, usuario_actual: UsuarioActual) -> Plantilla:
        plantilla = self.plantilla_repo.obtener_por_id(id_plantilla)
        if plantilla is None:
            registrar_intento_fallido(
                self.db,
                self.auditoria_repo,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="READ",
                id_plantilla=id_plantilla,
                detalle={"operacion": "detalle_plantilla", "error": "no encontrada"},
            )
            raise NotFoundError(
                code="PLANTILLA_NO_ENCONTRADA",
                message=f"No existe la plantilla con id {id_plantilla}.",
            )
        self.auditoria_repo.registrar(
            id_plantilla=id_plantilla,
            id_usuario=usuario_actual.id_usuario,
            tipo_operacion="READ",
            valores_nuevos={"operacion": "detalle_plantilla"},
        )
        self.db.commit()
        return plantilla

    def listar_historial(self, usuario_actual: UsuarioActual) -> list[AplicacionPlantilla]:
        resultado = self.aplicacion_repo.listar_todas()
        self.auditoria_repo.registrar(
            id_usuario=usuario_actual.id_usuario,
            tipo_operacion="READ",
            valores_nuevos={"operacion": "listar_historial", "total": len(resultado)},
        )
        self.db.commit()
        return resultado

    def listar_auditoria(self) -> list[AuditoriaPlantilla]:
        return self.auditoria_repo.listar_todas()
