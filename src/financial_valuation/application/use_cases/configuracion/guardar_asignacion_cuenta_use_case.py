# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-109/RF-86 FA-5: matriz contable y líneas pendientes de cuenta |
"""Caso de uso RF-109 (mínimo, D-2): par de cuentas débito/crédito por hecho, sentido, especie y
subtipo. Al completarse la matriz, las líneas PENDIENTE_CUENTA de períodos abiertos que ahora
tienen par quedan REGISTRADAS (RF-86 FA-5). Las líneas ya registradas no cambian: un cambio de
cuenta aplica a los hechos siguientes."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria
from src.financial_valuation.domain.repositories.asiento_repository import AsientoRepository
from src.financial_valuation.domain.repositories.auditoria_financiera_repository import AuditoriaFinancieraRepository
from src.financial_valuation.domain.repositories.configuracion_contable_repository import ConfiguracionContableRepository
from src.shared.errors import NotFoundError


class GuardarAsignacionCuentaUseCase:
    def __init__(self, db: Session, config: ConfiguracionContableRepository, asientos: AsientoRepository,
                 auditoria: AuditoriaFinancieraRepository) -> None:
        self.db = db
        self.config = config
        self.asientos = asientos
        self.auditoria = auditoria

    def execute(self, tipo_hecho: str, sentido: str, id_especie: Optional[int], subtipo_costo: Optional[str],
                cuenta_debito: str, cuenta_credito: str, id_usuario: int) -> dict:
        try:
            id_asignacion = self.config.guardar_asignacion(tipo_hecho, sentido, id_especie, subtipo_costo,
                                                           cuenta_debito, cuenta_credito, id_usuario)
            resueltas = self.resolver_pendientes()
            self.auditoria.registrar(EventoAuditoria(
                tipo_evento="MATRIZ_CONTABLE_ACTUALIZADA", severidad="INFO", id_usuario=id_usuario,
                payload={"tipo_hecho": tipo_hecho, "sentido": sentido, "id_especie": id_especie,
                         "subtipo_costo": subtipo_costo, "cuenta_debito": cuenta_debito, "cuenta_credito": cuenta_credito,
                         "lineas_resueltas": resueltas},
                id_referencia=id_asignacion,
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"id_asignacion_cuenta_contable": id_asignacion, "lineas_resueltas": resueltas}

    def desactivar(self, id_asignacion: int, id_usuario: int) -> None:
        try:
            if not self.config.desactivar_asignacion(id_asignacion):
                raise NotFoundError(code="ASIGNACION_NO_ENCONTRADA", message="La asignación no existe o ya está inactiva.")
            self.auditoria.registrar(EventoAuditoria(
                tipo_evento="MATRIZ_CONTABLE_ACTUALIZADA", severidad="INFO", id_usuario=id_usuario,
                payload={"desactivada": id_asignacion}, id_referencia=id_asignacion))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def resolver_pendientes(self) -> int:
        resueltas = 0
        for linea in self.asientos.pendientes_de_cuenta():
            asignacion = self.config.resolver_cuenta(linea.tipo_hecho_corregido or linea.tipo_hecho, linea.sentido,
                                                     linea.id_especie, linea.subtipo_costo)
            if asignacion is None:
                continue
            linea.asignar_cuentas(asignacion)
            self.asientos.registrar_cuentas(linea.id_linea_asiento_nic41, linea.cuenta_debito, linea.cuenta_credito)
            resueltas += 1
        return resueltas
