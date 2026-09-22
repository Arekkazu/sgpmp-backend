"""Regresión de los gaps de flujo alterno del Módulo 1.

Un caso por cada ❌ de `anotaciones/modulo_1/gaps_flujo_alterno_modulo1.md`:
el código de respuesta que el RF pide y que el módulo no devolvía.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.identity_access.application.use_cases.registro.crear_usuario_use_case import (
    CrearUsuarioUseCase,
)
from src.shared.errors import ServiceUnavailableError


class _DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class _NotificacionServiceFake:
    """Reproduce el contrato de ``NotificacionService.notificar``.

    Devuelve ``False`` cuando el canal EMAIL se intentó y el SMTP falló tras
    sus 3 reintentos internos.
    """

    def __init__(self, resultado_email) -> None:
        self.resultado_email = resultado_email
        self.llamadas: list[dict] = []

    def notificar(self, **datos):
        self.llamadas.append(datos)
        return self.resultado_email


def _ejecutar_registro(notificacion_service) -> _DbFake:
    usuario = SimpleNamespace(
        id_usuario=7,
        id_rol=2,
        correo="ana@example.com",
        nombre="Ana",
        es_mayor_de_edad=lambda: True,
    )
    db = _DbFake()

    use_case = CrearUsuarioUseCase(
        usuarios_repo=SimpleNamespace(guardar=lambda _u: usuario),
        cuentas_repo=SimpleNamespace(crear=lambda *_a, **_k: None),
        eventos_repo=SimpleNamespace(registrar=lambda **_k: None),
        captcha_verifier=SimpleNamespace(verificar=lambda *_a, **_k: True),
        db=db,
        notificacion_service=notificacion_service,
    )

    dto = SimpleNamespace(
        correo_electronico="ana@example.com",
        contrasena="Contrasena1!",
        confirmar_contrasena="Contrasena1!",
        nombre="Ana",
        apellidos="Pérez",
        fecha_nacimiento=None,
        genero=SimpleNamespace(value="F"),
        tipo_identificacion="CC",
        numero_identificacion="0012345678",
        telefono=None,
        direccion=None,
        captcha_token="captcha-valido",
    )

    use_case.execute(dto, "127.0.0.1", "pytest")
    return db


def test_rf01_smtp_agotado_responde_503_sin_perder_el_registro(monkeypatch) -> None:
    """RF-01: "Fallo crítico en el servicio de correo (SMTP)" → HTTP 503.

    El correo se envía dentro del request justamente para poder responderlo;
    con `BackgroundTasks` el 201 ya había salido y el caso era irreproducible.
    """
    from src.identity_access.application.use_cases.registro import (
        crear_usuario_use_case as modulo,
    )

    monkeypatch.setattr(modulo.Usuario, "registrar_nuevo", lambda **_d: SimpleNamespace(
        id_usuario=7,
        id_rol=2,
        correo="ana@example.com",
        nombre="Ana",
        es_mayor_de_edad=lambda: True,
    ))
    monkeypatch.setattr(modulo.Contrasena, "desde_texto_plano", lambda _t: object())

    servicio = _NotificacionServiceFake(resultado_email=False)

    with pytest.raises(ServiceUnavailableError) as error:
        _ejecutar_registro(servicio)

    assert error.value.status_code == 503
    assert error.value.code == "EMAIL_NO_DISPONIBLE"
    assert error.value.message.startswith("Registro exitoso")
    assert servicio.llamadas, "el correo debe intentarse dentro del request"


def test_rf01_registro_exitoso_no_lanza_cuando_el_correo_sale(monkeypatch) -> None:
    from src.identity_access.application.use_cases.registro import (
        crear_usuario_use_case as modulo,
    )

    monkeypatch.setattr(modulo.Usuario, "registrar_nuevo", lambda **_d: SimpleNamespace(
        id_usuario=7,
        id_rol=2,
        correo="ana@example.com",
        nombre="Ana",
        es_mayor_de_edad=lambda: True,
    ))
    monkeypatch.setattr(modulo.Contrasena, "desde_texto_plano", lambda _t: object())

    db = _ejecutar_registro(_NotificacionServiceFake(resultado_email=True))

    assert db.commits == 1
    assert db.rollbacks == 0
