# | Fecha      | Nombre       | Que se hizo                                           |
# |------------|--------------|-------------------------------------------------------|
# | 2026-10-23 | destroyerban | DEV-48 RF-69: avisos de carga externa y rechazo       |
# | 2026-10-23 | Arekkazu     | DEV-37 RF-73 E8 / DEV-48: Administrador por fn_rol_protegido y aviso de respaldo |
"""Avisos por correo del ciclo de vida de versiones de modelo (RF-69 E1b y E3, DEV-48).

Reusa el canal de correo de RF-14 (``send_email`` con la plantilla común) con el
mismo patrón que ``notificacion_medicamento_email_adapter.py`` de suministros.

Los destinatarios se resuelven por permiso en ``modulo1.permisos``, no por un
``id_rol`` fijo, igual que ``UsuarioRepository.listar_ids_con_permiso``:

- E1b y RF-73 E8 (Administrador): ``modulo1.fn_rol_protegido`` (el Veterinario
  también lee la auditoría de M04 desde DB-08, así que R sobre el recurso 46 ya no
  distingue al Administrador).
- E3 (Veterinario): quien revisa las versiones, es decir, quien puede registrar
  sus notas de validación (recurso 43, U).

La búsqueda corre con la identidad de servicio (``como_sistema``) porque
``modulo1`` tiene RLS forzada y no hay usuario en sesión; el propio usuario de
servicio (rol Administrador) se excluye.

Envío *best-effort*: cada correo va en su propio ``try/except`` con log; nunca
propaga.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.prediction.domain.entities.version_modelo import VersionModelo
from src.prediction.domain.repositories.aviso_version_modelo_port import AvisoFallbackAuditoriaPort, AvisoVersionModeloPort
from src.prediction.infrastructure.email_templates import (
    carga_modelo_externo_email,
    fallback_auditoria_activado_email,
    version_rechazada_email,
)
from src.shared.database import CORREO_USUARIO_SERVICIO, como_sistema
from src.shared.email import send_email

logger = logging.getLogger(__name__)

RECURSO_VERSION_MODELO = 43
ACCION_ACTUALIZAR = 3

# RF-14: "El sistema NO reintenta automáticamente (para evitar duplicidad)".
_INTENTOS_EMAIL = 1

_SQL_DESTINATARIOS = text(
    "SELECT DISTINCT u.id_usuario, u.nombre, u.apellidos, u.correo_electronico "
    "FROM modulo1.usuarios u "
    "JOIN modulo1.permisos p ON p.id_rol = u.id_rol "
    "JOIN modulo1.cuentas_usuarios c ON c.id_usuario = u.id_usuario "
    "JOIN modulo1.estados_cuentas e ON e.id_estado_cuenta = c.id_estado_cuenta "
    "WHERE p.id_recurso = :id_recurso AND p.id_accion = :id_accion AND p.es_activo "
    "AND lower(e.nombre) = 'activo' AND u.correo_electronico <> :correo_servicio "
    "ORDER BY u.id_usuario"
)


_SQL_ADMINISTRADORES = text(
    "SELECT DISTINCT u.id_usuario, u.nombre, u.apellidos, u.correo_electronico "
    "FROM modulo1.usuarios u "
    "JOIN modulo1.cuentas_usuarios c ON c.id_usuario = u.id_usuario "
    "JOIN modulo1.estados_cuentas e ON e.id_estado_cuenta = c.id_estado_cuenta "
    "WHERE modulo1.fn_rol_protegido(u.id_rol) AND lower(e.nombre) = 'activo' "
    "AND u.correo_electronico <> :correo_servicio "
    "ORDER BY u.id_usuario"
)


class AvisoVersionModeloEmailAdapter(AvisoVersionModeloPort, AvisoFallbackAuditoriaPort):
    def __init__(self, db: Session) -> None:
        self.db = db

    def avisar_carga_externa(self, *, id_proceso_rf71: str, motivo: str) -> None:
        for nombre, correo in self._administradores():
            self._enviar(
                correo,
                "Intento de carga de un modelo de IA externo",
                carga_modelo_externo_email(nombre, id_proceso_rf71, motivo),
            )

    def avisar_version_rechazada(self, version: VersionModelo) -> None:
        for nombre, correo in self._destinatarios(RECURSO_VERSION_MODELO, ACCION_ACTUALIZAR):
            self._enviar(
                correo,
                f"Versión de modelo rechazada: {version.nombre_version}",
                version_rechazada_email(nombre, version),
            )

    def avisar_fallback_activado(self, *, inicio_contingencia: Optional[str], eventos: int) -> None:
        for nombre, correo in self._administradores():
            self._enviar(
                correo,
                "Auditoría de Predicción: se activó el respaldo local",
                fallback_auditoria_activado_email(nombre, inicio_contingencia, eventos),
            )

    def _administradores(self) -> list[tuple[Optional[str], str]]:
        return self._consultar(_SQL_ADMINISTRADORES, {"correo_servicio": CORREO_USUARIO_SERVICIO})

    def _destinatarios(self, id_recurso: int, id_accion: int) -> list[tuple[Optional[str], str]]:
        return self._consultar(
            _SQL_DESTINATARIOS,
            {"id_recurso": id_recurso, "id_accion": id_accion, "correo_servicio": CORREO_USUARIO_SERVICIO},
        )

    def _consultar(self, sql, parametros: dict) -> list[tuple[Optional[str], str]]:
        try:
            # modulo1 tiene RLS forzada y estos avisos corren sin usuario en sesión (RF-71
            # interno o un intento externo): sin la identidad de servicio no habría filas.
            with como_sistema(self.db):
                filas = self.db.execute(sql, parametros).fetchall()
        except Exception as exc:  # best-effort: sin destinatarios no hay aviso, el flujo sigue
            self.db.rollback()
            logger.warning("No se pudieron resolver los destinatarios del aviso de M04: %s", exc)
            return []
        return [
            (f"{fila.nombre or ''} {fila.apellidos or ''}".strip() or None, fila.correo_electronico)
            for fila in filas
            if fila.correo_electronico
        ]

    @staticmethod
    def _enviar(correo: str, asunto: str, html: str) -> None:
        try:
            send_email(to=correo, subject=asunto, html_body=html, intentos=_INTENTOS_EMAIL)
        except Exception as exc:  # best-effort: nunca interrumpe el flujo de negocio
            logger.warning("No se pudo enviar el aviso de versiones de modelo a %s: %s", correo, exc)
