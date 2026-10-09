"""RF-02: un usuario sin fila en `cuentas` no debe tumbar el login con un 500.

`verificar_estado_cuenta` recibía `None` y fallaba en `cuenta.esta_bloqueada()`.
Además el 500 distinguía "correo registrado" de "correo inexistente" (401).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.identity_access.application.use_cases.agrofusion.emitir_token_agrofusion_use_case import (
    EmitirTokenAgroFusionUseCase,
)
from src.identity_access.application.use_cases.sesiones.login_use_case import LoginUseCase
from src.identity_access.application.use_cases.sesiones.sso_login_use_case import SsoLoginUseCase
from src.identity_access.infrastructure.dto.usuario_dto import LoginDTO, SsoLoginDTO
from src.shared.errors import AuthenticationError, NotFoundError

_CORREO = "qa.sin.cuenta@example.com"


class _Usuarios:
    def __init__(self, existe: bool):
        self.existe = existe

    def obtener_por_correo(self, _email):
        return SimpleNamespace(id_usuario=7) if self.existe else None


class _SinCuenta:
    def obtener_por_usuario(self, _id_usuario):
        return None


def _login(existe: bool) -> LoginUseCase:
    return LoginUseCase(
        usuarios_repo=_Usuarios(existe), cuentas_repo=_SinCuenta(),
        sesiones_repo=None, eventos_repo=None, db=None,
    )


@pytest.mark.parametrize("existe", [True, False])
def test_login_responde_el_mismo_401_exista_o_no_el_usuario(existe: bool) -> None:
    dto = LoginDTO(correo_electronico=_CORREO, contrasena="x")
    with pytest.raises(AuthenticationError) as exc:
        _login(existe).execute(dto, ip="127.0.0.1", user_agent="test")
    assert exc.value.code == "CREDENCIALES_INVALIDAS"


def test_sso_con_usuario_sin_cuenta_responde_401() -> None:
    sso = SimpleNamespace(verificar=lambda _t: SimpleNamespace(email=_CORREO))
    use_case = SsoLoginUseCase(
        sso_provider=sso, usuarios_repo=_Usuarios(True), cuentas_repo=_SinCuenta(),
        sesiones_repo=None, eventos_repo=None, db=None,
    )
    with pytest.raises(AuthenticationError):
        use_case.execute(SsoLoginDTO(sso_token="t"), ip="127.0.0.1", user_agent="test")


def test_agrofusion_con_usuario_sin_cuenta_responde_404() -> None:
    use_case = EmitirTokenAgroFusionUseCase(
        usuarios_repo=_Usuarios(True), cuentas_repo=_SinCuenta(),
        sesiones_repo=None, eventos_repo=None, db=None,
    )
    with pytest.raises(NotFoundError) as exc:
        use_case.execute(_CORREO, ip="127.0.0.1", user_agent="test")
    assert exc.value.code == "USUARIO_NO_ENCONTRADO"
