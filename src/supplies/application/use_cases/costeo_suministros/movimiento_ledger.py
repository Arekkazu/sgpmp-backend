# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-78/79/80: efectos de cada movimiento   |
"""Efectos de un movimiento del ledger de RF-78, comunes a todos los caminos.

Cada fila nueva de ``registro_suministro`` — un consumo (RF-75) o medicamento
(RF-76) que el trigger acumula, un suministro directo, una corrección o la
compensación de una anulación — produce lo mismo:

- RF-80: ``SUMINISTRO_REGISTRADO`` o ``SUMINISTRO_CORREGIDO``,
  ``PRECIO_MANUAL_INGRESADO`` cuando el usuario digitó el precio (Fase 5) y
  ``ACUMULADO_ACTUALIZADO`` con el costo que movió el acumulado.
- RF-79 Fase 1: el evento INCREMENTAL con el acumulado actualizado, escrito en el
  outbox dentro de la misma transacción (lo entrega el despachador).

No hace ``commit``: corre dentro de la transacción del caso de uso que movió el
ledger, así el movimiento y sus eventos se confirman o se revierten juntos.
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.supplies.domain.entities.evento_provision_m06 import EventoProvisionM06
from src.supplies.domain.entities.registro_suministro_directo import RegistroSuministroDirecto
from src.supplies.domain.repositories.acumulado_ciclo_repository import AcumuladoCicloRepository
from src.supplies.domain.repositories.auditoria_suministro_port import (
    AuditoriaSuministroPort,
    EventoAuditoriaSuministro,
)
from src.supplies.domain.repositories.outbox_provision_m06_repository import OutboxProvisionM06Repository
from src.supplies.domain.value_objects.eventos_auditoria_suministro_enums import (
    ResultadoAuditoriaSuministro,
    TipoEventoAuditoriaSuministro,
)


class RegistradorMovimientoLedger:
    def __init__(
        self,
        acumulado_repo: AcumuladoCicloRepository,
        auditoria_port: AuditoriaSuministroPort,
        outbox_repo: OutboxProvisionM06Repository,
    ) -> None:
        self.acumulado_repo = acumulado_repo
        self.auditoria_port = auditoria_port
        self.outbox_repo = outbox_repo

    def registrar(self, registro: RegistroSuministroDirecto, *, id_usuario: int, precio_manual: bool) -> None:
        ahora = datetime.now(timezone.utc)
        es_correccion = registro.tipo_operacion == "CORRECCION"
        self._auditar(
            registro, id_usuario, ahora,
            TipoEventoAuditoriaSuministro.SUMINISTRO_CORREGIDO if es_correccion
            else TipoEventoAuditoriaSuministro.SUMINISTRO_REGISTRADO,
            origen_precio=registro.origen_precio,
        )
        if precio_manual:
            self._auditar(
                registro, id_usuario, ahora, TipoEventoAuditoriaSuministro.PRECIO_MANUAL_INGRESADO,
                origen_precio="MANUAL",
            )

        acumulado = self.acumulado_repo.obtener(registro.id_gestion_fases) if registro.id_gestion_fases else None
        if acumulado is None:
            return  # el trigger no acumula filas sin instancia de ciclo
        self._auditar(registro, id_usuario, ahora, TipoEventoAuditoriaSuministro.ACUMULADO_ACTUALIZADO)
        self.outbox_repo.encolar(
            EventoProvisionM06.incremental(
                id_activo_biologico=registro.id_activo_biologico,
                id_ciclo_productivo=registro.id_ciclo_productivo,
                id_gestion_fases=registro.id_gestion_fases,
                id_registro_suministro=registro.id_registro_suministro,
                tipo_suministro=registro.tipo_suministro,
                tipo_operacion=registro.tipo_operacion,
                costo_registro=registro.costo_registro,
                acumulado_total_ciclo=acumulado.acumulado_total_ciclo,
                acumulado_por_categoria=acumulado.acumulado_por_categoria,
                ahora=ahora,
            )
        )

    def _auditar(
        self,
        registro: RegistroSuministroDirecto,
        id_usuario: int,
        ahora: datetime,
        tipo: TipoEventoAuditoriaSuministro,
        origen_precio: str | None = None,
    ) -> None:
        self.auditoria_port.registrar(
            EventoAuditoriaSuministro(
                entidad_afectada="registro_suministro",
                tipo_operacion=tipo.value,
                id_usuario=id_usuario,
                resultado=ResultadoAuditoriaSuministro.EXITOSO.value,
                id_activo_biologico=registro.id_activo_biologico,
                id_ciclo_productivo=registro.id_ciclo_productivo,
                id_gestion_fases=registro.id_gestion_fases,
                costo_afectado=registro.costo_registro,
                origen_precio=origen_precio,
                fecha_emision=ahora,
            )
        )
