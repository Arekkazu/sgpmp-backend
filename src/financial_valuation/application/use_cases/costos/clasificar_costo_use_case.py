# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-90 5.9/FA-3: resolver un costo PENDIENTE_CLASIFICACION |
"""Caso de uso RF-90: el Contador declara la naturaleza de un costo ``OTRO`` pendiente."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from src.financial_valuation.application.services.contabilizador import Contabilizador
from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria, LineaAsiento
from src.financial_valuation.domain.repositories.activo_financiero_port import ActivoFinancieroPort
from src.financial_valuation.domain.repositories.costo_repository import CostoRepository
from src.financial_valuation.domain.value_objects.nic41 import (
    NaturalezaCosto,
    OrigenCosto,
    Sentido,
    Severidad,
    TipoEvidencia,
    TipoHecho,
    VehiculoContable,
)
from src.shared.errors import BusinessRuleError, NotFoundError


class ClasificarCostoUseCase:
    def __init__(self, db: Session, costos: CostoRepository, activos: ActivoFinancieroPort,
                 contabilizador: Contabilizador) -> None:
        self.db = db
        self.costos = costos
        self.activos = activos
        self.contabilizador = contabilizador

    def execute(self, id_registro_costo: int, naturaleza: str, justificacion: str, id_usuario: int) -> dict:
        costo = self.costos.obtener(id_registro_costo)
        if costo is None:
            raise NotFoundError(code="COSTO_NO_ENCONTRADO", message="El costo no existe.")
        if costo["estado"] != "PENDIENTE_CLASIFICACION":
            raise BusinessRuleError(code="COSTO_YA_CLASIFICADO", message="El costo ya tiene naturaleza asignada.")
        if len((justificacion or "").strip()) < 10:
            raise BusinessRuleError(code="JUSTIFICACION_OBLIGATORIA", field="justificacion",
                                    message="La clasificación requiere una justificación (mínimo 10 caracteres).")
        con_proveedor = costo["origen_costo"] in (OrigenCosto.COMPRA_PROVEEDOR.value, OrigenCosto.SERVICIO_TERCERO.value)
        politica = None if naturaleza == NaturalezaCosto.VENTA.value else "GASTO"
        vehiculo = (VehiculoContable.NINGUNO if naturaleza == NaturalezaCosto.VENTA.value
                    else VehiculoContable.FACTURA_COMPRA if con_proveedor else VehiculoContable.ASIENTO_NIC41).value
        try:
            self.costos.clasificar(id_registro_costo, naturaleza, politica, vehiculo, costo["cuenta_debito"],
                                   costo["cuenta_credito"], justificacion.strip())
            if vehiculo == VehiculoContable.ASIENTO_NIC41.value:
                activo = self.activos.obtener(costo["id_activo_biologico"])
                self.contabilizador.asentar(LineaAsiento(
                    tipo_hecho=TipoHecho.MANO_OBRA_PROPIA.value, sentido=Sentido.UNICO.value,
                    valor=Decimal(costo["monto_costo"]).quantize(Decimal("0.01")), fecha_hecho=costo["fecha_costo"],
                    id_periodo_contable=costo["id_periodo_contable"], id_activo_biologico=activo.id_activo_biologico,
                    id_especie=activo.id_especie, id_finca=activo.id_finca, numero_id_tributaria=activo.numero_id_tributaria,
                    tabla_origen="registros_costos", id_origen=id_registro_costo,
                    tipo_evidencia=TipoEvidencia.REGISTRO_MANUAL.value, subtipo_costo=costo["subtipo_costo"],
                    id_usuario=id_usuario,
                ), id_usuario)
            self.contabilizador.auditar(EventoAuditoria(
                tipo_evento="COSTO_CLASIFICADO", severidad=Severidad.INFO.value, id_usuario=id_usuario,
                payload={"naturaleza": naturaleza, "vehiculo": vehiculo, "justificacion": justificacion.strip()},
                id_activo_biologico=costo["id_activo_biologico"], id_periodo_contable=costo["id_periodo_contable"],
                id_referencia=id_registro_costo, monto_afectado=costo["monto_costo"],
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"id_registro_costo": id_registro_costo, "naturaleza_costo": naturaleza, "vehiculo_contable": vehiculo}
