"""Caso de uso: exportar el historial de suministros en CSV, vía síncrona (RF-81).

Solo para volúmenes ≤ ``umbral_exportacion_async`` (10.000 por defecto);
volúmenes mayores deben pasar por ``SolicitarTrabajoHistorialUseCase`` (tipo
EXPORTACION). Reutiliza el mismo patrón de ``csv``+``io.StringIO`` que
``exportar_auditoria_m04_use_case.py``. ``lineas_a_csv`` se reutiliza también
desde el worker del motor async (exportación asíncrona). Registra
``EXPORTACION_HISTORIAL_GENERADA`` en la bitácora de auditoría de M05 (RF-80,
cierre de gap CU-06): la falla de auditoría no bloquea la respuesta.
"""
from __future__ import annotations

import csv
import io
import logging
from dataclasses import replace

from sqlalchemy.orm import Session

from src.shared.errors import AuthorizationError, BusinessRuleError, NotFoundError
from src.supplies.domain.entities.historial_suministro import FiltrosHistorialSuministro, LineaHistorialSuministro
from src.supplies.domain.repositories.activo_consulta_port import ActivoConsultaPort
from src.supplies.domain.repositories.alcance_activo_port import AlcanceActivoPort
from src.supplies.domain.repositories.auditoria_suministro_port import (
    AuditoriaSuministroPort,
    EventoAuditoriaSuministro,
)
from src.supplies.domain.repositories.configuracion_batch_historial_repository import (
    ConfiguracionBatchHistorialRepository,
)
from src.supplies.domain.repositories.historial_suministro_read_port import HistorialSuministroReadPort

logger = logging.getLogger(__name__)

_CAMPOS_CSV = [
    "id_registro_suministro",
    "tipo_suministro",
    "descripcion",
    "fecha_aplicacion",
    "cantidad",
    "unidad_medida",
    "precio_unitario",
    "costo_registro",
    "origen_precio",
    "nombre_activo",
    "especie",
    "nombre_ciclo",
    "estado_ciclo",
]


def _linea_a_dict(l: LineaHistorialSuministro) -> dict:
    return {
        "id_registro_suministro": l.id_registro_suministro,
        "tipo_suministro": l.tipo_suministro,
        "descripcion": l.descripcion,
        "fecha_aplicacion": l.fecha_aplicacion.isoformat(),
        "cantidad": str(l.cantidad),
        "unidad_medida": l.unidad_medida,
        "precio_unitario": str(l.precio_unitario),
        "costo_registro": str(l.costo_registro),
        "origen_precio": l.origen_precio,
        "nombre_activo": l.nombre_activo,
        "especie": l.especie,
        "nombre_ciclo": l.nombre_ciclo,
        "estado_ciclo": l.estado_ciclo,
    }


def lineas_a_csv(lineas: list[LineaHistorialSuministro]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=_CAMPOS_CSV)
    writer.writeheader()
    for l in lineas:
        writer.writerow(_linea_a_dict(l))
    return output.getvalue()


class ExportarHistorialSincronoUseCase:
    def __init__(
        self,
        historial_port: HistorialSuministroReadPort,
        alcance_port: AlcanceActivoPort,
        activo_port: ActivoConsultaPort,
        config_repo: ConfiguracionBatchHistorialRepository,
        db: Session,
        auditoria_port: AuditoriaSuministroPort,
    ) -> None:
        self.historial_port = historial_port
        self.alcance_port = alcance_port
        self.activo_port = activo_port
        self.config_repo = config_repo
        self.db = db
        self.auditoria_port = auditoria_port

    def execute(
        self, filtros: FiltrosHistorialSuministro, *, id_usuario: int, id_rol: int
    ) -> tuple[str, str, int]:
        return self._exportar(filtros, id_usuario=id_usuario, id_rol=id_rol, forzar=False)

    def exportar_forzado(
        self, filtros: FiltrosHistorialSuministro, *, id_usuario: int, id_rol: int
    ) -> tuple[str, str, int]:
        """Usado por el worker del motor async (trabajo EXPORTACION): sin límite
        de tamaño de página — el trabajo ya fue encolado precisamente porque
        supera el umbral síncrono."""
        return self._exportar(filtros, id_usuario=id_usuario, id_rol=id_rol, forzar=True)

    def _exportar(
        self, filtros: FiltrosHistorialSuministro, *, id_usuario: int, id_rol: int, forzar: bool
    ) -> tuple[str, str, int]:
        activo = self.activo_port.obtener(filtros.id_activo_biologico)
        if activo is None:
            raise NotFoundError(
                code="ACTIVO_NO_ENCONTRADO",
                message=f"El activo biológico {filtros.id_activo_biologico} no existe.",
                field="id_activo_biologico",
            )

        ids_permitidos = self.alcance_port.listar_ids_activos_permitidos(id_usuario, id_rol)
        if ids_permitidos is not None and filtros.id_activo_biologico not in ids_permitidos:
            raise AuthorizationError(
                code="ACCESO_DENEGADO",
                message=f"No tiene permisos para exportar el historial del activo {filtros.id_activo_biologico}.",
            )

        config = self.config_repo.obtener()
        limite_pagina = 5_000_000 if forzar else config.umbral_exportacion_async
        filtros_export = replace(filtros, pagina=1, registros_por_pagina=limite_pagina)
        resultado = self.historial_port.consultar(filtros_export, ids_permitidos)

        if not forzar and resultado.total_registros_filtrados > config.umbral_exportacion_async:
            raise BusinessRuleError(
                code="EXPORTACION_REQUIERE_MODO_ASINCRONO",
                message=(
                    f"La exportación contiene {resultado.total_registros_filtrados} registros, que supera "
                    f"el límite de {config.umbral_exportacion_async} para exportación síncrona. Solicítela "
                    "vía POST /suministros/historial/trabajos (tipo EXPORTACION)."
                ),
            )

        contenido = lineas_a_csv(resultado.lineas)
        nombre_archivo = (
            f"Historial_Suministros_{filtros.id_activo_biologico}_"
            f"{filtros.fecha_inicio_filtro or 'inicio'}_{filtros.fecha_fin_filtro or 'fin'}.csv"
        )
        self._auditar_exportacion(filtros, id_usuario)
        return contenido, nombre_archivo, resultado.total_registros_filtrados

    def _auditar_exportacion(self, filtros: FiltrosHistorialSuministro, id_usuario: int) -> None:
        try:
            self.auditoria_port.registrar(
                EventoAuditoriaSuministro(
                    entidad_afectada="historial_suministros",
                    tipo_operacion="EXPORTACION_HISTORIAL_GENERADA",
                    id_usuario=id_usuario,
                    resultado="EXITOSO",
                    id_activo_biologico=filtros.id_activo_biologico,
                    id_ciclo_productivo=filtros.id_ciclo_productivo,
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("Error al auditar EXPORTACION_HISTORIAL_GENERADA para activo %s", filtros.id_activo_biologico)
