# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-101 Fase 1: registro de un cliente externo con su credencial |
"""Registra un cliente externo (RF-101 Fase 1). El secreto se muestra una sola vez.

Se puede generar (256 bits) o recibir uno ya existente: AgroFusion usa una credencial fija para
todos sus proyectos y no puede adoptar una generada por SGPMP sin cambiar su código."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.accounting_integration.domain.entities.cliente_externo import ClienteExterno, Credencial
from src.accounting_integration.domain.entities.evento_integracion import EventoIntegracion
from src.accounting_integration.domain.repositories.auditoria_integracion_repository import AuditoriaIntegracionRepository
from src.accounting_integration.domain.repositories.cliente_externo_repository import ClienteExternoRepository
from src.accounting_integration.domain.value_objects import secreto_cliente
from src.shared.errors import ConflictError, ValidationError


@dataclass(frozen=True)
class SolicitudCliente:
    codigo: str
    nombre: str
    identificador_publico: str
    fecha_vencimiento: date
    canales: dict[str, int] = field(default_factory=dict)
    ip_permitida: Optional[str] = None
    ttl_token_canal_minutos: int = 15
    secreto: Optional[str] = None


def expiracion(fecha_vencimiento: date) -> datetime:
    """La credencial vale hasta el final del día de vencimiento (UTC)."""
    limite = datetime.combine(fecha_vencimiento + timedelta(days=1), time.min, tzinfo=timezone.utc)
    if limite <= datetime.now(timezone.utc):
        raise ValidationError(code="FECHA_VENCIMIENTO_INVALIDA", field="fecha_vencimiento",
                              message="La fecha de vencimiento de la credencial debe ser posterior a hoy.")
    return limite


class RegistrarClienteExternoUseCase:
    def __init__(self, clientes: ClienteExternoRepository, auditoria: AuditoriaIntegracionRepository, db: Session):
        self.clientes = clientes
        self.auditoria = auditoria
        self.db = db

    def execute(self, s: SolicitudCliente, id_usuario: int) -> tuple[ClienteExterno, str]:
        if self.clientes.obtener_por_identificador(s.identificador_publico):
            raise ConflictError(code="CLIENTE_DUPLICADO", field="identificador_publico",
                                message="Ya existe un cliente externo con ese identificador.")
        secreto = s.secreto or secreto_cliente.generar()
        credencial = Credencial(None, secreto_cliente.hashear(secreto), datetime.now(timezone.utc),
                                expiracion(s.fecha_vencimiento))
        try:
            cliente = self.clientes.guardar(ClienteExterno(
                None, s.codigo, s.nombre, s.identificador_publico, ip_permitida=s.ip_permitida,
                ttl_token_canal_minutos=s.ttl_token_canal_minutos, canales=dict(s.canales)))
            self.clientes.reemplazar_credencial(cliente.id_cliente_externo, credencial)
            self.auditoria.registrar(EventoIntegracion(
                tipo_evento="CLIENTE_REGISTRADO", tipo_actor="USUARIO", id_usuario=id_usuario,
                id_cliente_externo=cliente.id_cliente_externo, codigo_resultado="OK",
                json_detalle={**cliente.snapshot(), "secreto_provisto": s.secreto is not None,
                              "fecha_vencimiento": s.fecha_vencimiento.isoformat()}))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return cliente, secreto
