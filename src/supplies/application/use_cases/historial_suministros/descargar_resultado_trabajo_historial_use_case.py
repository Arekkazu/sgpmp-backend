# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-81: descarga de 72 h, 410 al vencer    |
"""Caso de uso: descargar el resultado de una exportación async de historial (RF-81 E3).

Solo aplica a trabajos ``EXPORTACION`` ya ``COMPLETADO`` y solo para quien la
pidió. El archivo se retiene 72 horas (Restricción 3); pasado ese plazo se
eliminó y la descarga responde 410: hay que solicitar una nueva exportación.
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.shared.errors import BusinessRuleError, NotFoundError
from src.supplies.domain.entities.archivo_exportacion import ArchivoExportacion
from src.supplies.domain.repositories.archivo_exportacion_repository import ArchivoExportacionRepository
from src.supplies.domain.repositories.trabajo_historial_suministro_repository import (
    TrabajoHistorialSuministroRepository,
)
from src.supplies.domain.value_objects.estado_trabajo_async import EstadoTrabajoAsync


class DescargarResultadoTrabajoHistorialUseCase:
    def __init__(
        self, trabajo_repo: TrabajoHistorialSuministroRepository, archivo_repo: ArchivoExportacionRepository
    ) -> None:
        self.trabajo_repo = trabajo_repo
        self.archivo_repo = archivo_repo

    def execute(self, id_cola: int, id_usuario: int) -> ArchivoExportacion:
        trabajo = self.trabajo_repo.obtener(id_cola)
        if trabajo is None:
            raise NotFoundError(
                code="TRABAJO_NO_ENCONTRADO",
                message=f"El trabajo de historial {id_cola} no existe.",
                field="id_cola",
            )
        if trabajo.estado != EstadoTrabajoAsync.COMPLETADO:
            raise BusinessRuleError(
                code="TRABAJO_NO_COMPLETADO",
                message=f"El trabajo {id_cola} aún no ha finalizado (estado actual: {trabajo.estado.value}).",
            )
        archivo = self.archivo_repo.obtener_por_referencia("RF81", id_cola)
        if archivo is None:
            raise NotFoundError(
                code="RESULTADO_NO_DISPONIBLE",
                message=f"El trabajo {id_cola} no generó un archivo descargable.",
            )
        archivo.contenido_para(id_usuario, datetime.now(timezone.utc))
        return archivo
