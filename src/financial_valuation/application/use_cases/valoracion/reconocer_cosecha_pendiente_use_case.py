# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-09 | destroyerban | INC-M06-323-G27 RF-85 FA-1/FA-2: la cosecha pendiente continúa con precio o costos manuales |
"""Caso de uso RF-85 FA-2: el Contador reconoce una cosecha pendiente ingresando a mano sus costos de venta.

La cosecha quedó pendiente porque M09 no tenía costos de venta para la especie. Con los costos manuales y su
justificación (RF-84 R2) se reconoce el producto igual que en el proceso automático. Si falta el precio (FA-1),
el Contador registra antes un precio ESTIMADO justificado en Precios de mercado y la cola retoma la cosecha sola."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.application.use_cases.valoracion.procesar_eventos_m02_use_case import (
    ProcesarEventosM02UseCase,
)
from src.financial_valuation.domain.repositories.evento_m02_port import EventoM02Port
from src.shared.errors import BusinessRuleError, NotFoundError, ValidationError

MIN_JUSTIFICACION = 20


class ReconocerCosechaPendienteUseCase:
    def __init__(self, db: Session, eventos: EventoM02Port, procesador: ProcesarEventosM02UseCase) -> None:
        self.db = db
        self.eventos = eventos
        self.procesador = procesador

    def execute(self, id_evento: int, costos_manuales: Optional[dict], justificacion: Optional[str],
                id_usuario: int) -> dict:
        manuales = {k: v for k, v in (costos_manuales or {}).items() if v is not None}
        if not manuales:
            raise ValidationError(code="COSTOS_VENTA_REQUERIDOS", field="costos_manuales",
                                  message="Ingrese al menos un costo de venta del producto.")
        texto = (justificacion or "").strip()
        if len(texto) < MIN_JUSTIFICACION:
            raise ValidationError(code="JUSTIFICACION_REQUERIDA", field="justificacion", message=(
                f"Justifique los costos de venta ingresados a mano con al menos {MIN_JUSTIFICACION} caracteres."))
        evento = self.eventos.cosecha_pendiente(id_evento)
        if evento is None:
            raise NotFoundError(code="COSECHA_PENDIENTE_NO_ENCONTRADA",
                                message="No hay una cosecha pendiente de reconocer con ese evento productivo.")
        try:
            resultado, detalle = self.procesador.reconocer_cosecha_pendiente(evento, manuales, texto, id_usuario)
            if resultado != "PROCESADO":
                raise BusinessRuleError(code="COSECHA_SIGUE_PENDIENTE", message=detalle or (
                    "La cosecha no se pudo reconocer con los costos ingresados."))
            self.eventos.registrar_procesamiento(id_evento, resultado, "Costos de venta ingresados por el Contador")
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"id_evento": id_evento, "resultado": resultado}
