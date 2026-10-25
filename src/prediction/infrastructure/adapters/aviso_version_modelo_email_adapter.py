# | Fecha      | Nombre       | Que se hizo                                           |
# |------------|--------------|-------------------------------------------------------|
# | 2026-10-23 | destroyerban | DEV-48 RF-69: avisos de carga externa y rechazo       |
# | 2026-10-23 | Arekkazu     | DEV-48 RF-69 E1b: el aviso al Administrador usa E sobre auditoria_m04 (DB-08 le dio R al Veterinario) |
"""Avisos por correo del ciclo de vida de versiones de modelo (RF-69 E1b y E3, DEV-48).

Reusa el canal de correo de RF-14 (``send_email`` con la plantilla común) con el
mismo patrón que ``notificacion_medicamento_email_adapter.py`` de suministros.

Los destinatarios se resuelven por permiso en ``modulo1.permisos``, no por un
``id_rol`` fijo, igual que ``UsuarioRepository.listar_ids_con_permiso``:

- E1b (Administrador): quien puede exportar la auditoría de M04 (recurso 46, E). Desde
  DB-08 el Veterinario también la lee (R), así que R ya no distingue al Administrador;
  es el mismo criterio del aviso de respaldo de RF-73 (DEV-37).
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
from src.prediction.domain.repositories.aviso_version_modelo_port import AvisoVersionModeloPort
from src.prediction.infrastructure.email_templates import carga_modelo_externo_email, version_rechazada_email
from src.shared.database import CORREO_USUARIO_SERVICIO, como_sistema
from src.shared.email import send_email

logger = logging.getLogger(__name__)

RECURSO_AUDITORIA_M04 = 46
RECURSO_VERSION_MODELO = 43
ACCION_ACTUALIZAR = 3
ACCION_EJECUTAR = 5

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


class AvisoVersionModeloEmailAdapter(AvisoVersionModeloPort):
    def __init__(self, db: Session) -> None:
        self.db = db

    def avisar_carga_externa(self, *, id_proceso_rf71: str, motivo: str) -> None:
        for nombre, correo in self._destinatarios(RECURSO_AUDITORIA_M04, ACCION_EJECUTAR):
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

    def _destinatarios(self, id_recurso: int, id_accion: int) -> list[tuple[Optional[str], str]]:
        try:
            # modulo1 tiene RLS forzada y estos avisos corren sin usuario en sesión (RF-71
            # interno o un intento externo): sin la identidad de servicio no habría filas.
            with como_sistema(self.db):
                filas = self.db.execute(
                    _SQL_DESTINATARIOS,
                    {"id_recurso": id_recurso, "id_accion": id_accion, "correo_servicio": CORREO_USUARIO_SERVICIO},
                ).fetchall()
        except Exception as exc:  # best-effort: sin destinatarios no hay aviso, el flujo sigue
            self.db.rollback()
            logger.warning("No se pudieron resolver los destinatarios (%s, %s): %s", id_recurso, id_accion, exc)
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
