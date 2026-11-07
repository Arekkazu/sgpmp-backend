# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-SSO02: lectura del usuario que actúa por el canal |
"""Usuario del canal, leído como Sistema: el endpoint de token no tiene identidad declarada y la RLS
de ``modulo1`` lo dejaría ciego."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.accounting_integration.domain.repositories.usuario_canal_repository import UsuarioCanal, UsuarioCanalRepository
from src.financial_valuation.infrastructure.repositories.sql import fila
from src.shared.database import como_sistema

_ESTADO_CUENTA_ACTIVA = 2
_SELECT = f"""
    SELECT u.id_usuario, u.id_rol, r.nombre_rol, u.correo_electronico AS correo,
           COALESCE(c.id_estado_cuenta = {_ESTADO_CUENTA_ACTIVA}, false) AS es_activo
    FROM modulo1.usuarios u JOIN modulo1.roles r ON r.id_rol = u.id_rol
    LEFT JOIN modulo1.cuentas_usuarios c ON c.id_usuario = u.id_usuario
"""


class SqlAlchemyUsuarioCanalRepository(UsuarioCanalRepository):
    def __init__(self, db: Session):
        self.db = db

    def _uno(self, condicion: str, params: dict) -> Optional[UsuarioCanal]:
        with como_sistema(self.db):
            f = fila(self.db, f"{_SELECT} WHERE {condicion}", params)
        return UsuarioCanal(**f) if f else None

    def obtener_por_correo(self, correo: str) -> Optional[UsuarioCanal]:
        return self._uno("lower(u.correo_electronico) = lower(:correo)", {"correo": correo})

    def obtener(self, id_usuario: int) -> Optional[UsuarioCanal]:
        return self._uno("u.id_usuario = :id", {"id": id_usuario})
