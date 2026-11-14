# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-77 RNF: regenerar desde el historial   |
# | 2026-11-07 | Leandro | INC-M05-272-G25 RF-77: auditar la regeneracion sin alterar el snapshot guardado. |
"""Caso de uso: consultar un reporte de gastos ya generado (RF-77).

La consulta relee el snapshot persistido de un reporte
síncrono o el resultado de un trabajo async ya completado. ``regenerar`` vuelve
a calcular el reporte con los parámetros guardados y el estado actual de los
datos, con la advertencia del RNF "Historial de reportes" y auditoría de la acción.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError
from src.supplies.domain.entities.reporte_gasto import ReporteGasto
from src.supplies.domain.repositories.auditoria_suministro_port import (
    AuditoriaSuministroPort,
    EventoAuditoriaSuministro,
)
from src.supplies.domain.repositories.reporte_gasto_repository import ReporteGastoRepository


class ConsultarReporteGastosUseCase:
    def __init__(self, reporte_repo: ReporteGastoRepository, db: Session,
                 auditoria_port: AuditoriaSuministroPort, generador: Optional[object] = None) -> None:
        self.db = db
        self.auditoria_port = auditoria_port
        self.reporte_repo = reporte_repo
        self.generador = generador

    def execute(self, id_reporte_gasto_acumulado: int) -> ReporteGasto:
        reporte = self.reporte_repo.obtener(id_reporte_gasto_acumulado)
        if reporte is None:
            raise NotFoundError(
                code="REPORTE_NO_ENCONTRADO",
                message=f"El reporte de gastos {id_reporte_gasto_acumulado} no existe.",
                field="id_reporte_gasto_acumulado",
            )
        return reporte

    def regenerar(self, id_reporte_gasto_acumulado: int, usuario_actual: UsuarioActual) -> tuple[ReporteGasto, str]:
        original = self.execute(id_reporte_gasto_acumulado)
        parametros = original.parametros or {
            "fecha_inicio": original.fecha_inicio.isoformat(),
            "fecha_fin": original.fecha_fin.isoformat(),
            "tipo_periodo": original.tipo_periodo,
            "id_activo_biologico": original.id_activo_biologico,
            "id_infraestructura": original.id_infraestructura,
        }
        reporte = self.generador.construir_desde_parametros(parametros, usuario_actual)
        advertencia = (
            f"Este reporte fue generado originalmente el {original.fecha_generacion.isoformat(timespec='seconds')}. "
            "Los datos mostrados corresponden al estado actual del sistema y pueden diferir del reporte original "
            "si hubo modificaciones en los registros del período consultado. Se recomienda exportar y guardar el "
            "reporte si requiere conservar los valores exactos."
        )
        try:
            self.auditoria_port.registrar(
                EventoAuditoriaSuministro(
                    entidad_afectada="reporte_gastos_acumulados",
                    tipo_operacion="SELECT",
                    id_usuario=usuario_actual.id_usuario,
                    resultado="EXITOSO",
                    id_activo_biologico=reporte.id_activo_biologico,
                    detalle_causa="Reporte de gastos regenerado con los datos actuales.",
                    datos_nuevos={
                        "accion": "REGENERACION",
                        "id_reporte_gasto_acumulado": original.id_reporte_gasto_acumulado,
                        "parametros": parametros,
                        "gasto_total_acumulado": str(reporte.gasto_total_acumulado),
                    },
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return reporte, advertencia
