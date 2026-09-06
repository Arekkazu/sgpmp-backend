"""Unidad INC-M01-16-057: rechazo temprano de contraseña reutilizada en RF-09."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.identity_access.application.use_cases.contrasena.restablecer_contrasena_use_case import (
    RestablecerContrasenaUseCase,
)
from src.identity_access.infrastructure.dto.contrasena_dto import RestablecerContrasenaDTO
from src.shared.errors import ConflictError


def test_reutilizacion_se_rechaza_antes_de_cifrar_y_sin_efectos_colaterales() -> None:
    usuario = MagicMock()
    usuario.contrasena.verificar.return_value = True

    cuenta = MagicMock()
    cuenta.id_usuario = 74
    cuenta.bloqueado_hasta = None
    cuenta.fecha_cambio_estado = datetime.now(timezone.utc)

    usuarios = MagicMock()
    usuarios.obtener_por_id.return_value = usuario
    cuentas = MagicMock()
    cuentas.obtener_por_hash_token.return_value = cuenta
    sesiones = MagicMock()
    eventos = MagicMock()
    db = MagicMock()
    notificaciones = MagicMock()
    caso = RestablecerContrasenaUseCase(
        usuarios_repo=usuarios,
        cuentas_repo=cuentas,
        sesiones_repo=sesiones,
        eventos_repo=eventos,
        db=db,
        notificacion_service=notificaciones,
    )
    dto = RestablecerContrasenaDTO(
        token="token-rf09-reutilizacion",
        nueva_contrasena="Actual123!",
        confirmar_contrasena="Actual123!",
    )

    with patch(
        "src.identity_access.application.use_cases.contrasena."
        "restablecer_contrasena_use_case.Contrasena.cifrar"
    ) as cifrar, pytest.raises(ConflictError) as error:
        caso.execute(dto, ip="203.0.113.57")

    assert error.value.status_code == 409
    assert error.value.code == "CONTRASENA_REUTILIZADA"
    assert error.value.message == "La nueva contraseña no puede ser igual a la anterior."
    usuario.contrasena.verificar.assert_called_once_with("Actual123!")
    cifrar.assert_not_called()
    usuario.cambiar_contrasena.assert_not_called()
    usuarios.cambiar_contrasena.assert_not_called()
    cuenta.limpiar_token.assert_not_called()
    cuenta.resetear_cambio_contrasena.assert_not_called()
    cuentas.guardar.assert_not_called()
    sesiones.invalidar_todas_sesiones.assert_not_called()
    eventos.registrar.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    notificaciones.notificar.assert_not_called()
