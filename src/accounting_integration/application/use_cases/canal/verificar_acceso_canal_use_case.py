# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-101 Fase 3 / RF-95 5.3 a-b: acceso por token de canal en cada solicitud |
"""Verifica una solicitud con token de canal (RF-101 Fase 3, RF-95 5.3 a y b).

No hay lista negra: el cliente se relee en cada solicitud, así que suspenderlo o revocarlo corta sus
tokens vigentes en la siguiente llamada (RF-101 5.4, CA-4)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from src.accounting_integration.domain.entities.cliente_externo import ClienteExterno
from src.accounting_integration.domain.repositories.cliente_externo_repository import ClienteExternoRepository
from src.accounting_integration.domain.repositories.usuario_canal_repository import UsuarioCanal, UsuarioCanalRepository
from src.shared.errors import AuthenticationError, AuthorizationError, TooManyRequestsError

Limitador = Callable[[str, int, float], None]


@dataclass(frozen=True)
class AccesoCanal:
    cliente: ClienteExterno
    usuario: UsuarioCanal


def limitar_cliente(limitar: Limitador, cliente: ClienteExterno, uso: str, limite: int) -> None:
    """RF-101 5.9: ventana deslizante de un minuto por cliente y uso; 429 ``LIMITE_EXCEDIDO`` con ``Retry-After``."""
    try:
        limitar(f"m07:{cliente.id_cliente_externo}:{uso}", limite, 60)
    except TooManyRequestsError as exc:
        raise TooManyRequestsError(code="LIMITE_EXCEDIDO", headers=exc.headers, message=(
            "Se superó el número de consultas permitidas por minuto. Intente de nuevo en unos momentos.")) from exc


class VerificarAccesoCanalUseCase:
    def __init__(self, clientes: ClienteExternoRepository, usuarios: UsuarioCanalRepository,
                 verificar_token: Callable[[str], dict], limitar: Limitador):
        self.clientes = clientes
        self.usuarios = usuarios
        self.verificar_token = verificar_token
        self.limitar = limitar

    def execute(self, token: Optional[str], canal: str, ip: Optional[str]) -> AccesoCanal:
        if not token:
            raise AuthenticationError(code="NO_AUTENTICADO", message="Falta la credencial de acceso del canal.")
        payload = self.verificar_token(token)
        cliente = self.clientes.obtener(int(payload["cli"]))
        if cliente is None or cliente.codigo != payload["canal"]:
            raise AuthenticationError(code="NO_AUTENTICADO", message="La credencial de acceso no es válida.")
        if cliente.estado != "ACTIVO" or canal not in cliente.canales or not cliente.ip_aceptada(ip):
            raise AuthorizationError(code="CLIENTE_NO_AUTORIZADO", message=(
                f"El sistema {cliente.nombre} no está autorizado para esta consulta. Contacte al administrador del SGPMP."))
        limitar_cliente(self.limitar, cliente, canal, cliente.canales[canal])
        usuario = self.usuarios.obtener(int(payload["sub"]))
        if usuario is None or not usuario.es_activo:
            raise AuthorizationError(code="PERMISO_INSUFICIENTE",
                                     message="Su usuario del SGPMP no está activo. Contacte al administrador.")
        return AccesoCanal(cliente, usuario)
