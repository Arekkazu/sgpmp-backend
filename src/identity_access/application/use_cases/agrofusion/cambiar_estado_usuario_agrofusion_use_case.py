# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | RF-SSO02: estado con los códigos de AgroFusion, usuario por id o correo e idempotente |
"""Caso de uso: cambio remoto de estado de cuenta (`CHANGE_USER_STATUS`).

Permite a un administrador de AgroFusion desactivar remotamente la cuenta
sgpmp de alguien que salió de la organización. Reutiliza el mismo patrón de
invalidación de sesión + transición de estado + evento que ya usa
``EditarPerfilUseCase`` para el cambio de estado hecho por un admin de sgpmp.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.agrofusion.comun import usuario_por_identificador
from src.identity_access.domain.repositories.cuenta_repository import CuentaRepository
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.sesion_repository import SesionRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.shared.errors import BusinessRuleError, NotFoundError

TIPO_EVENTO_CAMBIO_ESTADO_CUENTA = 10
# Códigos de AgroFusion (users_service.change_user_status) → estado de cuenta de SGPMP.
ESTADO_AGROFUSION = {1: 2, 2: 3, 3: 5}  # activo, inactivo, eliminado
NOMBRE_ESTADO = {1: "pendiente", 2: "activa", 3: "inactiva", 4: "bloqueada", 5: "eliminada", 6: "pendiente de datos"}
ESTADOS_QUE_INVALIDAN_SESION = {3, 4, 5}  # Inactivo, Bloqueado, Eliminado

TRANSICIONES_VALIDAS = {
    1: {2, 5},          # Pendiente → Activo, Eliminado
    2: {1, 3, 4, 5},    # Activo → Pendiente, Inactivo, Bloqueado, Eliminado
    3: {2, 5},          # Inactivo → Activo, Eliminado
    4: {2, 3, 5},       # Bloqueado → Activo, Inactivo, Eliminado
    6: {2, 5},          # Pendiente Datos → Activo, Eliminado
}


class CambiarEstadoUsuarioAgroFusionUseCase:
    """Orquesta el cambio de estado de cuenta solicitado por el Hub de AgroFusion."""

    def __init__(
        self,
        usuarios_repo: UsuarioRepository,
        cuentas_repo: CuentaRepository,
        sesiones_repo: SesionRepository,
        eventos_repo: EventoRepository,
        db: Session,
    ):
        self.usuarios_repo = usuarios_repo
        self.cuentas_repo = cuentas_repo
        self.sesiones_repo = sesiones_repo
        self.eventos_repo = eventos_repo
        self.db = db

    def execute(self, identificador: str, estado_agrofusion: int, motivo: Optional[str]) -> None:
        """Cambia el estado de cuenta del usuario (id de SGPMP o correo).

        Args:
            identificador: Id que AgroFusion pone en ``{user_id}`` o el correo.
            estado_agrofusion: Código de AgroFusion (1 activo, 2 inactivo, 3 eliminado).
            motivo: Justificación opcional, registrada en auditoría.

        Raises:
            NotFoundError: No existe usuario/cuenta. HTTP 404.
            BusinessRuleError: La transición de estado no está permitida. HTTP 422.
        """
        usuario = usuario_por_identificador(self.usuarios_repo, identificador)
        nuevo_estado = ESTADO_AGROFUSION[estado_agrofusion]
        cuenta = self.cuentas_repo.obtener_por_usuario(usuario.id_usuario)
        if cuenta is None:
            raise NotFoundError(
                code="CUENTA_NO_ENCONTRADA",
                message="El usuario no tiene una cuenta asociada.",
            )
        estado_actual = cuenta.id_estado_cuenta
        if estado_actual == nuevo_estado:  # AgroFusion reenvía el estado: ya está así
            return
        if nuevo_estado not in TRANSICIONES_VALIDAS.get(estado_actual, set()):
            raise BusinessRuleError(
                code="TRANSICION_INVALIDA",
                message=(
                    f"La cuenta está {NOMBRE_ESTADO.get(estado_actual, 'en otro estado')} y no puede pasar a "
                    f"{NOMBRE_ESTADO[nuevo_estado]}."
                ),
            )
        try:
            if nuevo_estado in ESTADOS_QUE_INVALIDAN_SESION:
                sesion_activa = self.sesiones_repo.buscar_sesion_activa(cuenta.id_cuenta_usuario)
                if sesion_activa is not None:
                    self.sesiones_repo.invalidar_sesion(sesion_activa)

            cuenta.cambiar_estado(nuevo_estado, motivo)
            self.cuentas_repo.guardar(cuenta)

            self.eventos_repo.registrar(
                tipo_evento=TIPO_EVENTO_CAMBIO_ESTADO_CUENTA,
                exitoso=True,
                id_usuario=usuario.id_usuario,
                detalle={
                    "mecanismo": "agrofusion_m2m",
                    "estado_anterior": estado_actual,
                    "estado_nuevo": nuevo_estado,
                    "motivo": motivo,
                },
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
