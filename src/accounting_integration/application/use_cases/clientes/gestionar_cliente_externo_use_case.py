# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-101 Fase 4: editar, suspender, reactivar, revocar y rotar el secreto |
"""Operaciones administrativas sobre un cliente externo (RF-101 Fase 4). Efecto inmediato: cada
solicitud con token relee el cliente. La auditoría va en la misma transacción (RF-102 4.1)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.accounting_integration.application.use_cases.clientes.registrar_cliente_externo_use_case import expiracion
from src.accounting_integration.domain.entities.cliente_externo import ClienteExterno, Credencial
from src.accounting_integration.domain.entities.evento_integracion import EventoIntegracion
from src.accounting_integration.domain.repositories.auditoria_integracion_repository import AuditoriaIntegracionRepository
from src.accounting_integration.domain.repositories.cliente_externo_repository import ClienteExternoRepository
from src.accounting_integration.domain.value_objects import secreto_cliente
from src.shared.errors import NotFoundError, PreconditionFailedError, ValidationError

_EVENTO = {"suspender": "CLIENTE_SUSPENDIDO", "reactivar": "CLIENTE_REACTIVADO", "revocar": "CLIENTE_REVOCADO"}


class GestionarClienteExternoUseCase:
    def __init__(self, clientes: ClienteExternoRepository, auditoria: AuditoriaIntegracionRepository, db: Session):
        self.clientes = clientes
        self.auditoria = auditoria
        self.db = db

    def _cliente(self, id_cliente_externo: int) -> ClienteExterno:
        cliente = self.clientes.obtener(id_cliente_externo)
        if cliente is None:
            raise NotFoundError(code="CLIENTE_NO_ENCONTRADO", message="El cliente externo no existe.")
        return cliente

    def _confirmar(self, evento: EventoIntegracion) -> None:
        try:
            self.auditoria.registrar(evento)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def editar(self, id_cliente_externo: int, canales: dict[str, int], ip_permitida: Optional[str],
               ttl_token_canal_minutos: int, fecha_actualizacion: Optional[datetime], id_usuario: int) -> ClienteExterno:
        cliente = self._cliente(id_cliente_externo)
        if cliente.fecha_actualizacion is None or fecha_actualizacion is None or (
                cliente.fecha_actualizacion.astimezone(timezone.utc) != fecha_actualizacion.astimezone(timezone.utc)):
            raise PreconditionFailedError(code="CONFLICTO_CONCURRENCIA",
                                          message="El registro fue modificado por otro usuario. Recarga y reintenta.")
        anterior = cliente.snapshot()
        cliente.canales, cliente.ip_permitida, cliente.ttl_token_canal_minutos = dict(canales), ip_permitida, ttl_token_canal_minutos
        cliente = self.clientes.guardar(cliente)
        self._confirmar(EventoIntegracion(
            tipo_evento="CLIENTE_EDITADO", tipo_actor="USUARIO", id_usuario=id_usuario,
            id_cliente_externo=id_cliente_externo, codigo_resultado="OK",
            json_detalle={"valores_anteriores": anterior, "valores_nuevos": cliente.snapshot()}))
        return cliente

    def cambiar_estado(self, id_cliente_externo: int, accion: str, motivo: Optional[str], id_usuario: int) -> ClienteExterno:
        if accion != "reactivar" and not (motivo or "").strip():
            raise ValidationError(code="MOTIVO_REQUERIDO", field="motivo", message="Indique el motivo del cambio.")
        cliente = self._cliente(id_cliente_externo)
        anterior = cliente.estado
        getattr(cliente, accion)()  # suspender | reactivar | revocar (FA-7: un revocado no vuelve)
        cliente = self.clientes.guardar(cliente)
        self._confirmar(EventoIntegracion(
            tipo_evento=_EVENTO[accion], severidad="WARNING" if accion != "reactivar" else "INFO", tipo_actor="USUARIO",
            id_usuario=id_usuario, id_cliente_externo=id_cliente_externo, codigo_resultado="OK",
            json_detalle={"estado_anterior": anterior, "estado_nuevo": cliente.estado, "motivo": motivo}))
        return cliente

    def rotar(self, id_cliente_externo: int, motivo: str, fecha_vencimiento: date, secreto: Optional[str],
              id_usuario: int) -> str:
        """RF-101 5.7: el secreto anterior deja de servir de inmediato. Devuelve el nuevo, que no se vuelve a mostrar."""
        if not (motivo or "").strip():
            raise ValidationError(code="MOTIVO_REQUERIDO", field="motivo", message="Indique el motivo de la rotación.")
        cliente = self._cliente(id_cliente_externo)
        cliente.exigir_no_revocado("rotar su secreto")
        nuevo = secreto or secreto_cliente.generar()
        self.clientes.reemplazar_credencial(id_cliente_externo, Credencial(
            None, secreto_cliente.hashear(nuevo), datetime.now(timezone.utc), expiracion(fecha_vencimiento)))
        self._confirmar(EventoIntegracion(
            tipo_evento="SECRETO_ROTADO", severidad="WARNING", tipo_actor="USUARIO", id_usuario=id_usuario,
            id_cliente_externo=id_cliente_externo, codigo_resultado="OK",
            json_detalle={"motivo": motivo, "secreto_provisto": secreto is not None,
                          "fecha_vencimiento": fecha_vencimiento.isoformat()}))
        return nuevo
