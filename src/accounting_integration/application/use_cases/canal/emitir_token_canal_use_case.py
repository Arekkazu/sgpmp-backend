# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-SSO02 / RF-101 Fase 2: token de canal para AgroFusion (GET_AUTHORIZATION) |
"""Emite el token de canal a nombre de un usuario de SGPMP (RF-SSO02, RF-101 Fase 2).

Las credenciales del cliente llegan solo en el cuerpo de esta llamada. El token no crea sesión: la
sesión web del usuario sigue viva (RFC-019 D-19.4)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

from src.accounting_integration.application.use_cases.canal.verificar_acceso_canal_use_case import Limitador, limitar_cliente
from src.accounting_integration.domain.entities.evento_integracion import EventoIntegracion
from src.accounting_integration.domain.repositories.cliente_externo_repository import ClienteExternoRepository
from src.accounting_integration.domain.repositories.usuario_canal_repository import UsuarioCanalRepository
from src.accounting_integration.domain.value_objects import secreto_cliente
from src.shared.errors import AppError, AuthenticationError, AuthorizationError, NotFoundError

EmisorToken = Callable[[int, int, int, str, int], tuple[str, int]]


class EmitirTokenCanalUseCase:
    def __init__(self, clientes: ClienteExternoRepository, usuarios: UsuarioCanalRepository, emitir: EmisorToken,
                 limitar: Limitador, auditar: Callable[[EventoIntegracion], None]):
        self.clientes = clientes
        self.usuarios = usuarios
        self.emitir = emitir
        self.limitar = limitar
        self.auditar = auditar

    def execute(self, client_id: str, client_secret: str, correo: str, ip: Optional[str]) -> tuple[str, int]:
        id_cliente = id_usuario = None
        try:
            cliente = self.clientes.obtener_por_identificador(client_id)
            credencial = self.clientes.credencial_activa(cliente.id_cliente_externo) if cliente else None
            if credencial is None or not secreto_cliente.coincide(client_secret, credencial.hash_secreto):
                raise AuthenticationError(code="CREDENCIALES_INVALIDAS", message="Las credenciales del sistema no son válidas.")
            id_cliente = cliente.id_cliente_externo
            if credencial.fecha_expiracion <= datetime.now(timezone.utc):
                raise AuthenticationError(code="CREDENCIAL_VENCIDA", message=(
                    "La credencial del sistema venció. El administrador del SGPMP debe renovarla."))
            if cliente.estado != "ACTIVO" or not cliente.ip_aceptada(ip) or not cliente.canales:
                raise AuthorizationError(code="CLIENTE_NO_AUTORIZADO", message=(
                    f"El sistema {cliente.nombre} no está autorizado. Contacte al administrador del SGPMP."))
            limitar_cliente(self.limitar, cliente, "TOKEN", max(cliente.canales.values()))
            usuario = self.usuarios.obtener_por_correo(correo)
            if usuario is None:
                raise NotFoundError(code="USUARIO_NO_ENCONTRADO", message=(
                    "No existe una cuenta del SGPMP con ese correo. Pida al administrador que la cree."))
            id_usuario = usuario.id_usuario
            if not usuario.es_activo:
                raise AuthorizationError(code="CUENTA_NO_ACTIVA", message="La cuenta del SGPMP con ese correo no está activa.")
            token, segundos = self.emitir(usuario.id_usuario, usuario.id_rol, id_cliente, cliente.codigo,
                                          cliente.ttl_token_canal_minutos)
        except AppError as exc:
            self.auditar(EventoIntegracion(
                tipo_evento="TOKEN_CANAL_RECHAZADO", severidad="WARNING", tipo_actor="CLIENTE_EXTERNO",
                id_cliente_externo=id_cliente, id_usuario=id_usuario, codigo_http=exc.status_code,
                codigo_resultado=exc.code, ip_origen=ip, endpoint="/integraciones/agrofusion/token", metodo_http="POST"))
            raise
        self.auditar(EventoIntegracion(
            tipo_evento="TOKEN_CANAL_EMITIDO", tipo_actor="CLIENTE_EXTERNO", id_cliente_externo=id_cliente,
            id_usuario=id_usuario, codigo_http=200, codigo_resultado="OK", ip_origen=ip,
            endpoint="/integraciones/agrofusion/token", metodo_http="POST", json_detalle={"vigencia_segundos": segundos}))
        return token, segundos
