"""
Retest TC-M01-057 (2026-09-12)
Rechazo al intentar establecer una nueva contrasena identica a la anterior (HTTP 409)

Este test prueba el use case RestablecerContrasenaUseCase directamente con mocks,
sin depender de un token real de recuperacion (el cupo compartido de RF-08 esta
agotado, ver TC-M01-041/049). Se sigue el mismo patron ya usado y aprobado por
Daniela en TC-M01-038 y TC-M01-044: probar la logica de negocio contra el codigo
real del use case (sincronizado desde origin/test), mockeando solo los
repositorios/infraestructura externos.

Punto exacto bajo prueba (restablecer_contrasena_use_case.py, paso 5):

    if usuario.contrasena.verificar(dto.nueva_contrasena):
        raise ConflictError(
            code="CONTRASENA_REUTILIZADA",
            message="La nueva contrasena no puede ser igual a la anterior.",
        )

Ejecutar desde la raiz del repositorio:
    python -m pytest tests/Test_Testing/Test_Modulo1/RF-09/TC-M01-057/tc_m01_057_retest.py -v --html=reporte-TC-M01-057-retest.html --self-contained-html

(ajustar la ruta del archivo segun donde lo coloques; debe ejecutarse desde la
raiz del repo para que "from src..." resuelva correctamente)
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.identity_access.application.use_cases.contrasena.restablecer_contrasena_use_case import (
    RestablecerContrasenaUseCase,
)
from src.identity_access.infrastructure.dto.contrasena_dto import RestablecerContrasenaDTO
from src.shared.errors import ConflictError


def _build_use_case_y_cuenta(contrasena_repetida: bool):
    """Arma el use case con mocks y una cuenta/usuario validos para llegar al paso 5."""
    ahora = datetime.now(timezone.utc)

    cuenta = MagicMock()
    cuenta.token_usado = False
    cuenta.bloqueado_hasta = None
    cuenta.fecha_cambio_estado = ahora - timedelta(minutes=2)  # token generado hace 2 min, no expirado
    cuenta.id_usuario = 53
    cuenta.id_cuenta_usuario = 53

    usuario = MagicMock()
    usuario.correo = "danielacastillovargas09@gmail.com"
    usuario.contrasena.verificar.return_value = contrasena_repetida

    usuarios_repo = MagicMock()
    usuarios_repo.obtener_por_id.return_value = usuario

    cuentas_repo = MagicMock()
    cuentas_repo.obtener_por_hash_token.return_value = cuenta

    sesiones_repo = MagicMock()
    eventos_repo = MagicMock()
    intentos_anonimos_repo = MagicMock()
    db = MagicMock()

    use_case = RestablecerContrasenaUseCase(
        usuarios_repo=usuarios_repo,
        cuentas_repo=cuentas_repo,
        sesiones_repo=sesiones_repo,
        eventos_repo=eventos_repo,
        intentos_anonimos_repo=intentos_anonimos_repo,
        db=db,
        notificacion_service=None,
    )

    dto = RestablecerContrasenaDTO(
        token="token-valido-simulado-tc057",
        nueva_contrasena="Verificada#45",
        confirmar_contrasena="Verificada#45",
    )

    return use_case, dto, usuario, usuarios_repo, sesiones_repo, eventos_repo, db


class TestTCM01057ContrasenaRepetida:
    """TC-M01-057: la nueva contrasena es identica a la anterior -> debe rechazarse con 409."""

    def test_nueva_contrasena_igual_a_la_anterior_lanza_conflict_409(self):
        use_case, dto, usuario, usuarios_repo, sesiones_repo, eventos_repo, db = _build_use_case_y_cuenta(
            contrasena_repetida=True
        )

        with pytest.raises(ConflictError) as exc_info:
            use_case.execute(dto, ip="127.0.0.1")

        exc = exc_info.value
        assert exc.status_code == 409, f"Se esperaba HTTP 409, se obtuvo {exc.status_code}"
        assert exc.code == "CONTRASENA_REUTILIZADA"

        # No debe haberse aplicado ningun cambio: ni cambio de contrasena, ni
        # consumo de token, ni invalidacion de sesiones, ni commit.
        usuarios_repo.cambiar_contrasena.assert_not_called()
        sesiones_repo.invalidar_todas_sesiones.assert_not_called()
        eventos_repo.registrar.assert_not_called()
        db.commit.assert_not_called()

    def test_nueva_contrasena_diferente_no_lanza_error_y_continua_el_flujo(self):
        """Caso de control: si la contrasena SI es diferente, no debe lanzarse
        ConflictError y el flujo normal (cambio de contrasena, invalidacion de
        sesiones, commit) debe completarse."""
        use_case, dto, usuario, usuarios_repo, sesiones_repo, eventos_repo, db = _build_use_case_y_cuenta(
            contrasena_repetida=False
        )

        use_case.execute(dto, ip="127.0.0.1")

        usuarios_repo.cambiar_contrasena.assert_called_once()
        sesiones_repo.invalidar_todas_sesiones.assert_called_once()
        eventos_repo.registrar.assert_called_once()
        db.commit.assert_called_once()
        db.rollback.assert_not_called()