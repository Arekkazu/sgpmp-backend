# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-90 + M05 RF-79: costos de M05 a M06 (CONSUMO_INVENTARIO / CONSUMO_INSUMO) |
# | 2026-11-05 | Arekkazu | M06 RF-90: justificación automática sin códigos de módulo |
"""Caso de uso de fondo: convierte cada provisión INCREMENTAL de M05 en un costo de RF-90.

- ALIMENTO y MEDICAMENTO: ``CONSUMO_INVENTARIO`` → línea ``CONSUMO_INSUMO`` (gasto contra el
  inventario de insumos ya comprado en la contabilidad externa). Nunca se capitalizan ni se restan
  del valor razonable (RF-84 R1, RF-90 5.1).
- SERVICIO_VETERINARIO e INSEMINACION: no salen de inventario y su factura ya está en SIGCON, así
  que cuentan como gasto del período (RF-93) pero no generan línea (D-3, contradicción C-6).
- Una corrección o anulación con costo negativo es un reverso: la línea invierte el par.
Las provisiones de activos aún sin reconocimiento esperan en la bandeja (RF-90 precondición)."""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from src.financial_valuation.application.services.contabilizador import ID_SISTEMA, Contabilizador, PeriodoEnCierreError
from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria, LineaAsiento
from src.financial_valuation.domain.repositories.activo_financiero_port import ActivoFinancieroPort
from src.financial_valuation.domain.repositories.costo_repository import CostoRepository
from src.financial_valuation.domain.value_objects.nic41 import (
    NaturalezaCosto,
    OrigenCosto,
    Sentido,
    Severidad,
    SubtipoCosto,
    TipoEvidencia,
    TipoHecho,
    VehiculoContable,
)
from src.shared.errors import AppError

logger = logging.getLogger(__name__)

_SUBTIPO = {"ALIMENTO": SubtipoCosto.ALIMENTO, "MEDICAMENTO": SubtipoCosto.MEDICAMENTO,
            "SERVICIO_VETERINARIO": SubtipoCosto.VETERINARIO, "INSEMINACION": SubtipoCosto.VETERINARIO}
_CON_INVENTARIO = ("ALIMENTO", "MEDICAMENTO")


_OPERACION = {"REGISTRO": "Consumo registrado", "CORRECCION": "Corrección de un consumo", "ANULACION": "Anulación de un consumo"}

class ProcesarProvisionesM05UseCase:
    def __init__(self, db: Session, costos: CostoRepository, activos: ActivoFinancieroPort,
                 contabilizador: Contabilizador, id_usuario_servicio: int) -> None:
        self.db = db
        self.costos = costos
        self.activos = activos
        self.contabilizador = contabilizador
        self.id_servicio = id_usuario_servicio

    def execute(self, limite: int = 500) -> dict:
        conteo: dict[str, int] = {}
        for id_recepcion, recepcion in self.costos.recepciones_pendientes(limite):
            try:
                resultado = self._procesar(recepcion)
                if resultado is not None:
                    self.costos.marcar_recepcion(id_recepcion, resultado)
                self.db.commit()
            except Exception:
                self.db.rollback()
                logger.exception("M06: no se pudo procesar la provisión %s de M05.", recepcion.id_evento_provision)
                resultado = "ERROR"
            conteo[resultado or "EN_ESPERA"] = conteo.get(resultado or "EN_ESPERA", 0) + 1
        return conteo

    def _procesar(self, recepcion) -> str | None:
        """Devuelve el resultado a marcar, o ``None`` para dejarla en espera (período en cierre o sin titular)."""
        if recepcion.modalidad == "CONSOLIDADO":
            return "CONSOLIDADO_RECIBIDO"
        contenido = recepcion.contenido or {}
        tipo = (contenido.get("id_tipo_suministro") or contenido.get("tipo_suministro") or "").upper()
        try:
            monto = Decimal(str(contenido.get("costo_registro")))
        except (InvalidOperation, TypeError):
            return "SIN_MONTO"
        if tipo not in _SUBTIPO or monto == 0:
            return "SIN_EFECTO"
        activo = self.activos.obtener(recepcion.id_activo_biologico)
        if activo is None:
            return "ACTIVO_NO_ENCONTRADO"
        fecha = self._fecha(contenido, recepcion)
        try:
            periodo = self.contabilizador.periodo_para(activo.numero_id_tributaria, fecha, self.id_servicio)
        except (PeriodoEnCierreError, AppError):
            return None
        subtipo = _SUBTIPO[tipo].value
        con_linea = tipo in _CON_INVENTARIO
        cuenta = self.contabilizador.config.resolver_cuenta(TipoHecho.CONSUMO_INSUMO.value, Sentido.UNICO.value,
                                                            activo.id_especie, subtipo)
        es_reverso = monto < 0
        id_costo = self.costos.agregar({
            "naturaleza_costo": NaturalezaCosto.MANTENIMIENTO.value, "subtipo_costo": subtipo,
            "id_activo_biologico": activo.id_activo_biologico, "monto_costo": abs(monto),
            "politica_capitalizacion": "GASTO", "id_periodo_contable": periodo.id_periodo_contable,
            "id_usuario": self.id_servicio, "origen_costo": OrigenCosto.CONSUMO_INVENTARIO.value,
            "vehiculo_contable": (VehiculoContable.ASIENTO_NIC41 if con_linea else VehiculoContable.NINGUNO).value,
            "fecha_costo": fecha, "id_origen_m05": recepcion.id_evento_provision, "es_reverso": es_reverso,
            # El registro de Suministros queda en id_origen_m05; la justificación es texto para el Contador.
            "justificacion": f"{_OPERACION.get(contenido.get('tipo_operacion'), _OPERACION['REGISTRO'])} en Suministros",
            "cuenta_debito": cuenta.cuenta_debito if cuenta else None,
            "cuenta_credito": cuenta.cuenta_credito if cuenta else None,
        })
        if con_linea:
            self.contabilizador.asentar(LineaAsiento(
                tipo_hecho=TipoHecho.CONSUMO_INSUMO.value, sentido=Sentido.UNICO.value, valor=abs(monto).quantize(Decimal("0.01")),
                fecha_hecho=fecha, id_periodo_contable=periodo.id_periodo_contable,
                id_activo_biologico=activo.id_activo_biologico, id_especie=activo.id_especie, id_finca=activo.id_finca,
                numero_id_tributaria=activo.numero_id_tributaria, tabla_origen="registros_costos", id_origen=id_costo,
                tipo_evidencia=TipoEvidencia.REGISTRO_MANUAL.value, subtipo_costo=subtipo, es_reverso=es_reverso,
            ), None)
        self.contabilizador.auditar(EventoAuditoria(
            tipo_evento="COSTO_REGISTRADO", severidad=Severidad.INFO.value, id_sistema=ID_SISTEMA,
            payload={"origen_costo": OrigenCosto.CONSUMO_INVENTARIO.value, "subtipo_costo": subtipo,
                     "vehiculo_contable": "ASIENTO_NIC41" if con_linea else "NINGUNO", "monto": str(monto),
                     "id_evento_provision": str(recepcion.id_evento_provision), "tipo_suministro": tipo},
            id_activo_biologico=activo.id_activo_biologico, id_periodo_contable=periodo.id_periodo_contable,
            id_referencia=id_costo, monto_afectado=abs(monto),
        ))
        return "PROCESADO"

    def _fecha(self, contenido: dict, recepcion) -> date:
        """La fecha del consumo, no la de recepción (M5-2): del evento o, en eventos anteriores, de M05."""
        if contenido.get("fecha_aplicacion"):
            return date.fromisoformat(str(contenido["fecha_aplicacion"])[:10])
        if contenido.get("id_registro_suministro"):
            fecha = self.costos.fecha_aplicacion_m05(str(contenido["id_registro_suministro"]))
            if fecha:
                return fecha
        return recepcion.fecha_recepcion.date()
