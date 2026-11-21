"""
Retest TC-M01-054 (2026-09-12)
Rechazo de un token que ya fue utilizado previamente en un restablecimiento
exitoso (uso unico) (HTTP 409)

Defecto original (2026-09-01/02): un token ya usado SI era rechazado (la regla
de seguridad de un solo uso funcionaba), pero con codigo HTTP 401
(TOKEN_INVALIDO) en vez del 409 Conflict exigido por la ficha -- el sistema no
distinguia "token ya usado" (conflicto de estado) de "token corrupto/inexistente"
(autenticacion invalida).

Este test prueba el use case RestablecerContrasenaUseCase directamente con
mocks, siguiendo el mismo patron ya usado y aprobado en TC-M01-038, TC-M01-044
y TC-M01-057, sin depender de un token real de recuperacion (cupo compartido
de RF-08 agotado durante esta sesion).

Punto exacto bajo prueba (restablecer_contrasena_use_case.py, paso 1.1):

    # 1.1 Token encontrado pero ya consumido en un restablecimiento anterior.
    if cuenta.token_usado:
        raise ConflictError(
            code="TOKEN_YA_UTILIZADO",
            message=(
                "Este token de recuperacion ya fue utilizado para restablecer la "
                "contrasena. Solicite un nuevo correo de recuperacion si necesita "
                "cambiarla de nuevo."
            ),
        )

Este paso ahora se evalua ANTES de la verificacion de bloqueo/expiracion, y es
distinto del caso "token no encontrado en absoluto" (cuenta is None), que sigue
respondiendo 401 TOKEN_INVALIDO como corresponde (ese es un caso distinto,
cubierto por otras fichas, y no debe verse afectado por este fix).

Ejecutar desde la raiz del repositorio:
    python -m pytest tests/Test_Testing/Test_Modulo1/RF-09/TC-M01-54/tc_m01_054_retest.py -v --html=reporte-TC-M01-054-v2.0.html --self-contained-html
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.identity_access.application.use_cases.contrasena.restablecer_contrasena_use_case import (
    RestablecerContrasenaUseCase,
)
from src.identity_access.infrastructure.dto.contrasena_dto import RestablecerContrasenaDTO
from src.shared.errors import AuthenticationError, ConflictError


def _build_use_case(token_usado: bool):
    """Arma el use case con mocks. `token_usado` controla si la cuenta
    encontrada por el token ya fue consumida en un restablecimiento anterior."""
    ahora = datetime.now(timezone.utc)

    cuenta = MagicMock()
    cuenta.token_usado = token_usado
    cuenta.bloqueado_hasta = None
    cuenta.fecha_cambio_estado = ahora - timedelta(minutes=2)
    cuenta.id_usuario = 53
    cuenta.id_cuenta_usuario = 53

    usuario = MagicMock()
    usuario.correo = "danielacastillovargas09@gmail.com"
    usuario.contrasena.verificar.return_value = False  # nueva contrasena distinta, no interfiere con este caso

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
        token="token-ya-usado-simulado-tc054",
        nueva_contrasena="OtraValida#99",
        confirmar_contrasena="OtraValida#99",
    )

    return use_case, dto, usuarios_repo, cuentas_repo, sesiones_repo, eventos_repo, db


class TestTCM01054TokenYaUtilizado:
    """TC-M01-054: reutilizar un token ya consumido debe responder 409, no 401."""

    def test_token_ya_usado_lanza_conflict_409_no_401(self):
        use_case, dto, usuarios_repo, cuentas_repo, sesiones_repo, eventos_repo, db = _build_use_case(
            token_usado=True
        )

        with pytest.raises(ConflictError) as exc_info:
            use_case.execute(dto, ip="127.0.0.1")

        exc = exc_info.value
        assert exc.status_code == 409, f"Se esperaba HTTP 409, se obtuvo {exc.status_code}"
        assert exc.code == "TOKEN_YA_UTILIZADO"

        # El rechazo debe ocurrir ANTES de tocar al usuario o aplicar cualquier
        # cambio -- no debe intentarse ni siquiera comparar la nueva contrasena.
        usuarios_repo.obtener_por_id.assert_not_called()
        usuarios_repo.cambiar_contrasena.assert_not_called()
        sesiones_repo.invalidar_todas_sesiones.assert_not_called()
        eventos_repo.registrar.assert_not_called()
        db.commit.assert_not_called()

    def test_token_no_usado_no_lanza_conflict_y_continua_el_flujo(self):
        """Caso de control: un token valido (no usado aun) no debe activar esta
        validacion y debe completar el restablecimiento con normalidad."""
        use_case, dto, usuarios_repo, cuentas_repo, sesiones_repo, eventos_repo, db = _build_use_case(
            token_usado=False
        )

        use_case.execute(dto, ip="127.0.0.1")

        usuarios_repo.cambiar_contrasena.assert_called_once()
        sesiones_repo.invalidar_todas_sesiones.assert_called_once()
        eventos_repo.registrar.assert_called_once()
        db.commit.assert_called_once()

    def test_token_inexistente_sigue_respondiendo_401_no_409(self):
        """Caso de control adicional: un token que no corresponde a NINGUNA
        cuenta (distinto de "ya usado") debe seguir respondiendo 401
        TOKEN_INVALIDO -- este fix no debe alterar ese comportamiento, que
        corresponde a un caso distinto (ver otras fichas de RF-09)."""
        cuentas_repo = MagicMock()
        cuentas_repo.obtener_por_hash_token.return_value = None

        usuarios_repo = MagicMock()
        sesiones_repo = MagicMock()
        eventos_repo = MagicMock()
        intentos_anonimos_repo = MagicMock()
        intentos_anonimos_repo.contar_por_ip.return_value = 1  # bien por debajo del limite de bloqueo
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
            token="token-que-no-existe-en-ninguna-cuenta",
            nueva_contrasena="OtraValida#99",
            confirmar_contrasena="OtraValida#99",
        )

        with pytest.raises(AuthenticationError) as exc_info:
            use_case.execute(dto, ip="127.0.0.1")

        exc = exc_info.value
        assert exc.status_code == 401
        assert exc.code == "TOKEN_INVALIDO"