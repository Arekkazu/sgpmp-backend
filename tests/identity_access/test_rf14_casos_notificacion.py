# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""RF-14: casos que deben notificar y contenido mínimo de cada aviso.

- Cada intento de login fallido notifica (el anti-spam deja uno cada 5 min).
- El bloqueo por 5 intentos es otro evento: aviso propio, sin anti-spam.
- Una edición administrativa de perfil notifica al usuario editado.
- Todo correo lleva tipo de evento, mensaje y fecha y hora, y escapa los datos.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.identity_access.application.use_cases.sesiones.login_use_case import LoginUseCase
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dto.usuario_dto import LoginDTO
from src.identity_access.infrastructure.email_templates import (
    activation_email,
    cambio_estado_cuenta_email,
    cuenta_bloqueada_email,
)
from src.shared import notificacion_service as service_module
from src.shared.errors import AuthenticationError, LockedError
from src.shared.notificacion_service import NotificacionService
from src.shared.plantilla_correo import formatear_fecha

from tests.identity_access.test_rf14_notificaciones import DbFake, PortServicioFake


class _Notificador:
    def __init__(self) -> None:
        self.llamadas: list[dict] = []

    def notificar(self, **datos) -> None:
        self.llamadas.append(datos)


class _Repo:
    def __getattr__(self, _nombre):
        return lambda *a, **k: None


class _DbNula:
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


def _login(intentos_previos: int) -> tuple[LoginUseCase, _Notificador]:
    usuario = SimpleNamespace(
        id_usuario=7,
        correo="ana@example.com",
        contrasena=SimpleNamespace(verificar=lambda _c: False),
    )
    cuenta = Cuenta(
        id_usuario=7,
        id_estado_cuenta=Cuenta.ESTADO_ACTIVO,
        tiene_correo_verificado=True,
        intentos_fallidos=intentos_previos,
        id_cuenta_usuario=3,
    )
    notificador = _Notificador()
    use_case = LoginUseCase(
        usuarios_repo=SimpleNamespace(obtener_por_correo=lambda _e: usuario),
        cuentas_repo=SimpleNamespace(obtener_por_usuario=lambda _i: cuenta, guardar=lambda _c: None),
        sesiones_repo=_Repo(),
        eventos_repo=_Repo(),
        db=_DbNula(),
        notificacion_service=notificador,
    )
    return use_case, notificador


_DTO = LoginDTO(correo_electronico="ana@example.com", contrasena="mala")


def test_primer_intento_fallido_notifica_con_anti_spam() -> None:
    use_case, notificador = _login(intentos_previos=0)

    with pytest.raises(AuthenticationError):
        use_case.execute(_DTO, ip="127.0.0.1", user_agent="test")

    assert notificador.llamadas == [
        {"tipo_evento": 4, "id_usuario": 7, "correo_destino": "ana@example.com"}
    ]


def test_bloqueo_notifica_su_propio_aviso_sin_anti_spam() -> None:
    use_case, notificador = _login(intentos_previos=4)

    with pytest.raises(LockedError):
        use_case.execute(_DTO, ip="127.0.0.1", user_agent="test")

    (aviso,) = notificador.llamadas
    assert aviso["tipo_evento"] == 4
    assert aviso["aplicar_anti_spam_email"] is False
    assert aviso["aplicar_anti_spam_interno"] is False
    assert aviso["titulo"] == "Cuenta bloqueada temporalmente"
    assert "Bloqueo de cuenta" in aviso["contenido_html_email"]


def test_bloqueo_llega_aunque_el_primer_intento_ya_ocupo_la_ventana(monkeypatch) -> None:
    port = PortServicioFake()
    correos: list[dict] = []
    monkeypatch.setattr(service_module, "send_email", lambda **d: correos.append(d))
    servicio = NotificacionService(port=port, db=DbFake())

    servicio.notificar(tipo_evento=4, id_usuario=7, correo_destino="ana@example.com")
    servicio.notificar(tipo_evento=4, id_usuario=7, correo_destino="ana@example.com")
    servicio.notificar(
        tipo_evento=4,
        id_usuario=7,
        correo_destino="ana@example.com",
        cuerpo="Tu cuenta se bloqueó.",
        asunto_email="Tu cuenta quedó bloqueada temporalmente",
        contenido_html_email="<p>bloqueo</p>",
        aplicar_anti_spam_email=False,
        aplicar_anti_spam_interno=False,
    )

    # El segundo intento cae en la ventana; el bloqueo pasa en ambos canales.
    assert [c["subject"] for c in correos] == [
        "Intento de acceso fallido",
        "Tu cuenta quedó bloqueada temporalmente",
    ]
    assert [r["mensaje"] for r in port.registros if r["id_canal"] == 2][-1] == "Tu cuenta se bloqueó."


def test_correo_por_defecto_cumple_la_constancia_de_rf14(monkeypatch) -> None:
    correos: list[dict] = []
    monkeypatch.setattr(service_module, "send_email", lambda **d: correos.append(d))

    NotificacionService(port=PortServicioFake(), db=DbFake()).notificar(
        tipo_evento=3, id_usuario=7, correo_destino="ana@example.com"
    )

    html = correos[0]["html_body"]
    assert "Inicio de sesión" in html  # tipo de evento
    assert "Se inició sesión en tu cuenta." in html  # mensaje
    assert "Fecha y hora" in html and " de 20" in html  # fecha y hora
    assert "SIGAB" in html


def test_las_plantillas_escapan_el_nombre() -> None:
    html = activation_email('<a href="x">Ana</a>', "tok")
    assert '<a href="x">' not in html
    assert "&lt;a href=&quot;x&quot;&gt;Ana&lt;/a&gt;" in html


def test_cambio_de_estado_dice_que_le_paso_a_la_cuenta() -> None:
    asunto, html = cambio_estado_cuenta_email("Ana", 3)
    assert asunto == "Tu cuenta fue desactivada"
    assert "Cambio de estado de la cuenta" in html


def test_fecha_en_hora_de_colombia(en_colombia) -> None:
    # 23:42 UTC son las 6:42 p. m. en Colombia (UTC-5, sin horario de verano).
    assert formatear_fecha(datetime(2026, 10, 10, 23, 42, tzinfo=timezone.utc)) == (
        "10 de octubre de 2026, 6:42 p. m. (UTC-05:00)"
    )
    assert "6:42 p. m. (UTC-05:00)" in cuenta_bloqueada_email(datetime(2026, 10, 10, 23, 42, tzinfo=timezone.utc))


def test_sin_zona_del_usuario_la_fecha_va_en_utc() -> None:
    assert formatear_fecha(datetime(2026, 10, 10, 23, 42, tzinfo=timezone.utc)) == (
        "10 de octubre de 2026, 11:42 p. m. (UTC)"
    )
