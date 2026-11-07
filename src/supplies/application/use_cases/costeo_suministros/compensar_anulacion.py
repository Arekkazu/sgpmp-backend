# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-75/76/78: anulación revierte el ledger |
"""Compensación en el ledger de RF-78 al anular un consumo (RF-75) o medicamento (RF-76).

Un registro ANULADO queda excluido de los cálculos (RF-75 postcondición 4,
RF-77 R1). El ledger de RF-78 es append-only (R6): la anulación no borra la
fila acumulada, agrega una CORRECCION por ``-costo vigente`` (RNF-09), así el
acumulado, la provisión NIC-41 y el historial dejan de contar ese costo y la
traza queda completa.

Si la instancia de ciclo ya se cerró, su inversión está consolidada e
inmutable (RF-78 R2): la anulación se rechaza con 409 y el ajuste se hace con
una corrección del reporte consolidado (RF-79 E4).
"""
from __future__ import annotations

from typing import Optional
from uuid import uuid4

from src.shared.errors import ConflictError
from src.supplies.application.use_cases.costeo_suministros.movimiento_ledger import RegistradorMovimientoLedger
from src.supplies.domain.entities.registro_suministro_directo import RegistroSuministroDirecto
from src.supplies.domain.repositories.ciclo_abierto_port import CicloAbiertoPort
from src.supplies.domain.repositories.registro_suministro_repository import RegistroSuministroRepository

_MAX_MOTIVO = 500


class CompensadorAnulacion:
    def __init__(
        self,
        registro_repo: RegistroSuministroRepository,
        ciclo_port: CicloAbiertoPort,
        movimiento: RegistradorMovimientoLedger,
    ) -> None:
        self.registro_repo = registro_repo
        self.ciclo_port = ciclo_port
        self.movimiento = movimiento

    def validar(self, tipo_suministro: str, id_origen: int) -> Optional[RegistroSuministroDirecto]:
        """Devuelve la fila del ledger a compensar; 409 si su ciclo ya está cerrado."""
        ledger = self.registro_repo.obtener_por_origen(tipo_suministro, id_origen)
        if ledger is None or ledger.id_gestion_fases is None:
            return None
        fase = self.ciclo_port.obtener_por_id(ledger.id_gestion_fases)
        if fase is not None and not fase.es_activa:
            raise ConflictError(
                code="CICLO_CERRADO",
                message=(
                    "El ciclo productivo del registro está cerrado y su inversión ya fue consolidada "
                    "(RF-78). No es posible anularlo; solicite la corrección del reporte consolidado."
                ),
            )
        return ledger

    def compensar(self, ledger: RegistroSuministroDirecto, motivo: str, id_usuario: int) -> None:
        neto = self.registro_repo.costo_vigente(ledger.id_registro_suministro)
        if neto == 0:
            return
        correccion = RegistroSuministroDirecto.crear_compensacion(
            original=ledger,
            costo_compensatorio=-neto,
            motivo_correccion=motivo[:_MAX_MOTIVO],
            id_idempotencia=uuid4(),
        )
        guardada = self.registro_repo.guardar(correccion)
        self.movimiento.registrar(guardada, id_usuario=id_usuario, precio_manual=False)
