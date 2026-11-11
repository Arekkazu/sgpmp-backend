# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-COT 5.4/5.5: modificar o anular una cotización antes del cierre |
# | 2026-11-08 | Arekkazu | INC-M06-335-G91 RF-COT: el aviso de cotización no modificable nombra el estado, no su valor de enum |
"""Casos de uso RF-COT fases 8-9 con control optimista por ``version`` (5.9, FA-11)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria
from src.financial_valuation.domain.repositories.auditoria_financiera_repository import AuditoriaFinancieraRepository
from src.financial_valuation.domain.repositories.cotizacion_repository import CotizacionRepository
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, PreconditionFailedError
from src.shared.fechas import hoy_usuario

CAMPOS_MODIFICABLES = ("valor_cotizacion_propuesto", "condiciones", "fecha_vencimiento")

_ETIQUETA_ESTADO = {"VENCIDA": "vencida", "ANULADA": "anulada", "CONVERTIDA_EN_VENTA": "convertida en venta"}


class ModificarCotizacionUseCase:
    def __init__(self, db: Session, cotizaciones: CotizacionRepository, auditoria: AuditoriaFinancieraRepository) -> None:
        self.db = db
        self.cotizaciones = cotizaciones
        self.auditoria = auditoria

    def _vigente(self, id_cotizacion: int) -> dict:
        cotizacion = self.cotizaciones.obtener(id_cotizacion)
        if cotizacion is None:
            raise NotFoundError(code="COTIZACION_NO_ENCONTRADA", message="La cotización no existe.")
        if cotizacion["estado_periodo"] == "CERRADO":  # FA-8
            raise BusinessRuleError(code="PERIODO_CONTABLE_CERRADO", message="La cotización es de un período cerrado.")
        if cotizacion["estado"] != "COTIZADO":
            estado = _ETIQUETA_ESTADO.get(cotizacion["estado"], "cerrada")
            raise BusinessRuleError(code="COTIZACION_NO_MODIFICABLE", message=f"La cotización está {estado}: ya no se puede cambiar.")
        return cotizacion

    def modificar(self, id_cotizacion: int, version: int, cambios: dict, justificacion: str, id_usuario: int) -> dict:
        no_permitidos = [c for c in cambios if c not in CAMPOS_MODIFICABLES]
        if no_permitidos:  # FA-9
            raise ConflictError(code="CAMPO_NO_MODIFICABLE", message=f"No se pueden modificar: {', '.join(no_permitidos)}.")
        if len((justificacion or "").strip()) < 10:
            raise BusinessRuleError(code="JUSTIFICACION_OBLIGATORIA", message="Justifique la modificación (mínimo 10 caracteres).")
        cotizacion = self._vigente(id_cotizacion)
        if "valor_cotizacion_propuesto" in cambios and cambios["valor_cotizacion_propuesto"] <= 0:
            raise BusinessRuleError(code="VALOR_COTIZACION_INVALIDO", message="El valor propuesto debe ser mayor a cero.")
        if cambios.get("fecha_vencimiento") and cambios["fecha_vencimiento"] < cotizacion["fecha_emision"]:
            raise BusinessRuleError(code="FECHA_VENCIMIENTO_INVALIDA",
                                    message="El vencimiento no puede ser anterior a la fecha de emisión.")
        return self._guardar(cotizacion, version, cambios, "COTIZACION_MODIFICADA", justificacion, id_usuario)

    def anular(self, id_cotizacion: int, version: int, motivo: str, id_usuario: int) -> dict:
        if len((motivo or "").strip()) < 20:  # FA-10
            raise BusinessRuleError(code="MOTIVO_ANULACION_OBLIGATORIO",
                                    message="El motivo de anulación es obligatorio (mínimo 20 caracteres).")
        cotizacion = self._vigente(id_cotizacion)
        return self._guardar(cotizacion, version, {"estado": "ANULADA", "motivo_anulacion": motivo.strip()},
                             "COTIZACION_ANULADA", motivo, id_usuario)

    def _guardar(self, cotizacion, version, cambios, tipo_evento, justificacion, id_usuario) -> dict:
        try:
            if not self.cotizaciones.actualizar(cotizacion["id_cotizacion"], version, cambios):
                raise PreconditionFailedError(code="CONFLICTO_CONCURRENCIA", message=(
                    "La cotización fue modificada por otro usuario. Recárguela y reintente."))
            self.auditoria.registrar(EventoAuditoria(
                tipo_evento=tipo_evento, severidad="INFO", id_usuario=id_usuario,
                payload={"cambios": cambios, "justificacion": justificacion.strip()},
                datos_anteriores={k: cotizacion.get(k) for k in (*CAMPOS_MODIFICABLES, "estado")},
                id_periodo_contable=cotizacion["id_periodo_contable"], id_referencia=cotizacion["id_cotizacion"],
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.cotizaciones.obtener(cotizacion["id_cotizacion"])

    def vencer(self) -> int:
        """Fase 7: monitoreo diario de vencimientos (proceso de fondo)."""
        try:
            vencidas = self.cotizaciones.vencer(hoy_usuario())
            for c in vencidas:
                self.auditoria.registrar(EventoAuditoria(
                    tipo_evento="COTIZACION_VENCIDA", severidad="INFO", id_sistema="M06_VENCIMIENTO_COTIZACIONES",
                    payload={"id_cotizacion": c["id_cotizacion"]}, id_periodo_contable=c["id_periodo_contable"],
                    id_referencia=c["id_cotizacion"]))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return len(vencidas)
