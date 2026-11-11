# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-91: verificación de la cadena de trazabilidad de las líneas de asiento |
# | 2026-11-09 | LuisfNarvaez01 | INC-M06-288-G32 RF-91: una cadena de período cerrado no aborta la verificación |
"""Caso de uso RF-91: verifica cada línea (CADENA_COMPLETA → VERIFICADO; si falta un eslabón →
PENDIENTE_TRAZABILIDAD). La re-verificación de una línea pendiente la lleva a VERIFICADO cuando el
eslabón se resolvió (FA-4). Las líneas de períodos cerrados no se tocan (R4).

INC-M06-288-G32: si la BD rechaza registrar la verificación de una línea, esa línea queda pendiente con
su motivo y las demás del período se verifican igual (antes: rollback total y HTTP 500)."""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria, LineaAsiento
from src.financial_valuation.domain.repositories.asiento_repository import AsientoRepository
from src.financial_valuation.domain.repositories.auditoria_financiera_repository import AuditoriaFinancieraRepository
from src.financial_valuation.domain.repositories.trazabilidad_repository import TrazabilidadRepository
from src.financial_valuation.domain.services.trazabilidad import verificar_cadena
from src.financial_valuation.domain.value_objects.nic41 import Severidad
from src.shared.errors import AppError, BusinessRuleError

logger = logging.getLogger(__name__)

MOTIVO_RECHAZO = ("No se pudo registrar la verificación de esta línea; las demás líneas del período sí se "
                  "verificaron. Revise su origen en la cadena de trazabilidad.")


class VerificadorTrazabilidad:
    """Servicio sin commit: lo usa el cierre (RF-87 paso 3) y el caso de uso de abajo."""

    def __init__(self, asientos: AsientoRepository, trazabilidad: TrazabilidadRepository,
                 auditoria: AuditoriaFinancieraRepository) -> None:
        self.asientos = asientos
        self.trazabilidad = trazabilidad
        self.auditoria = auditoria

    def evaluar(self, lineas: list[LineaAsiento]) -> list[dict]:
        """Simulación sin escribir: líneas que quedarían PENDIENTE_TRAZABILIDAD (prevalidación del cierre)."""
        pendientes = []
        for linea in lineas:
            if (linea.extra or {}).get("estado_trazabilidad") == "VERIFICADO":
                continue
            estado, faltantes, nivel = verificar_cadena(linea.tipo_evidencia, self.trazabilidad.eslabones(linea))
            if estado != "VERIFICADO":
                pendientes.append({"id_linea": linea.id_linea_asiento_nic41, "tipo_hecho": linea.tipo_hecho,
                                   "id_activo_biologico": linea.id_activo_biologico, "faltantes": faltantes,
                                   "nivel_fallo": nivel})
        return pendientes

    def verificar(self, lineas: list[LineaAsiento], id_usuario: Optional[int]) -> dict[str, list[dict]]:
        resultado: dict[str, list[dict]] = {"VERIFICADO": [], "PENDIENTE_TRAZABILIDAD": []}
        for linea in lineas:
            if (linea.extra or {}).get("estado_trazabilidad") == "VERIFICADO":
                resultado["VERIFICADO"].append({"id_linea": linea.id_linea_asiento_nic41})
                continue
            eslabones = self.trazabilidad.eslabones(linea)
            estado, faltantes, nivel = verificar_cadena(linea.tipo_evidencia, eslabones)
            eslabones.update({"faltantes": faltantes, "nivel_fallo": nivel})
            try:
                self.trazabilidad.registrar_verificacion(linea.id_linea_asiento_nic41, estado, linea.tipo_evidencia,
                                                         eslabones, id_usuario)
            except AppError:
                logger.exception("M06: la BD rechazó la verificación de la línea %s.", linea.id_linea_asiento_nic41)
                self._rechazada(linea, id_usuario, resultado)
                continue
            self.asientos.cambiar_trazabilidad(linea.id_linea_asiento_nic41, estado)
            self.auditoria.registrar(EventoAuditoria(
                tipo_evento="CADENA_TRAZABILIDAD_VERIFICADA",
                severidad=(Severidad.INFO if estado == "VERIFICADO" else Severidad.WARNING).value,
                payload={"resultado": "CADENA_COMPLETA" if estado == "VERIFICADO" else "CADENA_INCOMPLETA",
                         "tipo_evidencia": linea.tipo_evidencia, "faltantes": faltantes, "nivel_fallo": nivel},
                id_usuario=id_usuario, id_sistema=None if id_usuario else "M06_VERIFICADOR_TRAZABILIDAD",
                id_activo_biologico=linea.id_activo_biologico, id_periodo_contable=linea.id_periodo_contable,
                id_referencia=linea.id_linea_asiento_nic41,
            ))
            resultado[estado].append({"id_linea": linea.id_linea_asiento_nic41, "tipo_hecho": linea.tipo_hecho,
                                      "id_activo_biologico": linea.id_activo_biologico, "faltantes": faltantes,
                                      "nivel_fallo": nivel})
        return resultado

    def _rechazada(self, linea: LineaAsiento, id_usuario: Optional[int], resultado: dict) -> None:
        self.auditoria.registrar(EventoAuditoria(
            tipo_evento="CADENA_TRAZABILIDAD_VERIFICADA", severidad=Severidad.WARNING.value,
            payload={"resultado": "VERIFICACION_RECHAZADA", "tipo_evidencia": linea.tipo_evidencia,
                     "tabla_origen": linea.tabla_origen, "id_origen": linea.id_origen},
            id_usuario=id_usuario, id_sistema=None if id_usuario else "M06_VERIFICADOR_TRAZABILIDAD",
            id_activo_biologico=linea.id_activo_biologico, id_periodo_contable=linea.id_periodo_contable,
            id_referencia=linea.id_linea_asiento_nic41,
        ))
        resultado["PENDIENTE_TRAZABILIDAD"].append({
            "id_linea": linea.id_linea_asiento_nic41, "tipo_hecho": linea.tipo_hecho,
            "id_activo_biologico": linea.id_activo_biologico, "faltantes": [], "nivel_fallo": None,
            "motivo": MOTIVO_RECHAZO})


class VerificarTrazabilidadUseCase:
    def __init__(self, db: Session, asientos: AsientoRepository, verificador: VerificadorTrazabilidad,
                 periodos) -> None:
        self.db = db
        self.asientos = asientos
        self.verificador = verificador
        self.periodos = periodos

    def execute(self, id_periodo_contable: int, id_usuario: int) -> dict:
        periodo = self.periodos.obtener(id_periodo_contable)
        if periodo is None or not periodo.esta_abierto:
            raise BusinessRuleError(code="PERIODO_NO_ABIERTO",
                                    message="Solo se verifica la trazabilidad de períodos abiertos (la de un cerrado es inmutable).")
        try:
            resultado = self.verificador.verificar(self.asientos.del_periodo(id_periodo_contable), id_usuario)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"verificadas": len(resultado["VERIFICADO"]), "pendientes": resultado["PENDIENTE_TRAZABILIDAD"]}
