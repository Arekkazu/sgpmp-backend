# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-09 | destroyerban | INC-M06-317-G17 RF-84: cálculo en revisión y validación del valor neto ≤ 0 |
"""Caso de uso RF-84 R3 / FA-2: el Contador valida con justificación un cálculo con valor neto ≤ 0.

El cálculo pasa de REVISION_REQUERIDA a CALCULADO y la validación (justificación, Contador y fecha)
queda en ``json_metodo_costo`` y en la auditoría. Sin justificación (ausente, vacía o en blanco)
no se valida."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.application.services.contabilizador import Contabilizador
from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria
from src.financial_valuation.domain.repositories.valoracion_repository import ValoracionRepository
from src.financial_valuation.domain.value_objects.nic41 import Severidad
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationError

MIN_JUSTIFICACION = 20


class ValidarCalculoNoPositivoUseCase:
    def __init__(self, db: Session, valoraciones: ValoracionRepository, contabilizador: Contabilizador) -> None:
        self.db = db
        self.valoraciones = valoraciones
        self.contabilizador = contabilizador

    def execute(self, id_calculo_valor_razonable: int, justificacion: Optional[str], id_usuario: int) -> dict:
        texto = (justificacion or "").strip()
        if len(texto) < MIN_JUSTIFICACION:
            raise ValidationError(code="JUSTIFICACION_VALIDACION_REQUERIDA", field="justificacion", message=(
                f"Para aceptar un valor neto menor o igual a cero escriba una justificación de al menos "
                f"{MIN_JUSTIFICACION} caracteres."))
        calculo = self.valoraciones.obtener_calculo(id_calculo_valor_razonable)
        if calculo is None:
            raise NotFoundError(code="CALCULO_NO_ENCONTRADO", message="El cálculo de valor razonable no existe.")
        if calculo.estado != "REVISION_REQUERIDA":
            raise ConflictError(code="CALCULO_SIN_REVISION_PENDIENTE",
                                message="Este cálculo no está en revisión: no hay nada que validar.")
        periodo = self.contabilizador.periodos.obtener(calculo.id_periodo_contable)
        if periodo is None or not periodo.esta_abierto:
            raise BusinessRuleError(code="PERIODO_NO_ABIERTO", message=(
                "El período contable del cálculo ya no está abierto: el cálculo no se puede validar."))
        validacion = {"justificacion": texto, "id_usuario": id_usuario, "fecha": datetime.now(timezone.utc).isoformat()}
        try:
            self.valoraciones.validar_calculo(id_calculo_valor_razonable, validacion)
            self.contabilizador.auditar(EventoAuditoria(
                tipo_evento="CALCULO_VALOR_RAZONABLE", severidad=Severidad.WARNING.value,
                payload={"estado": "CALCULADO", "estado_anterior": "REVISION_REQUERIDA",
                         "motivo": "VALOR_NETO_NO_POSITIVO_VALIDADO", "justificacion": texto,
                         "valor_neto": str(calculo.valor_neto)},
                id_usuario=id_usuario, id_activo_biologico=calculo.id_activo_biologico,
                id_periodo_contable=calculo.id_periodo_contable, id_referencia=id_calculo_valor_razonable,
                monto_afectado=calculo.valor_neto, datos_anteriores={"estado": "REVISION_REQUERIDA"},
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"id_calculo_valor_razonable": id_calculo_valor_razonable, "id_activo_biologico": calculo.id_activo_biologico,
                "estado": "CALCULADO", "valor_neto": calculo.valor_neto, "validacion": validacion}
