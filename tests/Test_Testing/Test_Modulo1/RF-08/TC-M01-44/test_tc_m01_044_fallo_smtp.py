"""
TC-M01-044 - Validar que un fallo del servicio SMTP mantenga el mensaje
generico hacia el usuario (HTTP 202) y disparar una alerta interna al
administrador.

RF relacionado: RF-08
Categoria: Manejo de errores (RESILIENCIA)

Criterio de aceptacion (segun la ficha, flujo alterno "Fallo critico en
el servicio de correo (SMTP)"):
    "El sistema intenta enviar el correo de recuperacion pero el servidor
    de mensajeria no responde tras los reintentos configurados. El
    sistema registra el fallo en los logs internos pero mantiene el
    mensaje generico hacia el usuario para no exponer vulnerabilidades.
    El sistema responde con: HTTP 202: Accepted (Mensaje Generico).
    Mensaje (Interfaz): 'Si el correo esta registrado, recibiras las
    instrucciones en unos minutos.'
    Nota interna de sistema: Se dispara una alerta al administrador
    debido al error 500 en el servicio de notificaciones."

Dato de prueba: correo de la cuenta QA "ana.martinez.qa1@sgpmp-test.com"
(la misma cuenta real usada en TC-M01-112 y TC-M01-042 para RF-08).

Por que local: send_email() (src/shared/email.py) ya implementa sus
propios 3 reintentos internos (_MAX_RETRIES=3) y, si todos fallan, lanza
ServiceUnavailableError con codigo EMAIL_NO_DISPONIBLE. Para esta prueba
solo hace falta simular ESE resultado final (reintentos ya agotados),
parcheando send_email en el punto donde lo usa el use case -- no hace
falta un servidor SMTP real caido ni coordinar con Implementacion.

Estado conocido al escribir este archivo:
src/identity_access/application/use_cases/contrasena/
solicitar_recuperacion_use_case.py llama a send_email(...) FUERA de
cualquier try/except (paso 5, "post-commit"). Si send_email agota sus
reintentos y lanza ServiceUnavailableError, esa excepcion se propaga sin
capturar fuera de execute(); el handler global la traduce a HTTP 503 (no
202), y el mensaje generico nunca llega al usuario. Tampoco existe en el
codigo ningun disparo de alerta al administrador para este caso. Por lo
tanto se espera que AMBAS pruebas de este archivo FALLEN hoy.

Como correrlo (desde la raiz del repo, con las env vars seteadas):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    python -m pytest <ruta>\\test_tc_m01_044_fallo_smtp.py -v \
        --html=reporte-TC-M01-044.html --self-contained-html
"""
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.identity_access.application.use_cases.contrasena.solicitar_recuperacion_use_case import (
    SolicitarRecuperacionUseCase,
)
from src.identity_access.infrastructure.dto.contrasena_dto import SolicitarRecuperacionDTO
from src.shared.errors import ServiceUnavailableError

CORREO_PRUEBA = "ana.martinez.qa1@sgpmp-test.com"
MENSAJE_GENERICO = (
    "Si el correo está registrado, recibirás instrucciones para recuperar "
    "tu contraseña en unos minutos."
)


def _falla_smtp_simulada() -> ServiceUnavailableError:
    """El mismo error que send_email() (src/shared/email.py) lanza cuando
    agota sus 3 reintentos internos contra un SMTP caido."""
    return ServiceUnavailableError(
        code="EMAIL_NO_DISPONIBLE",
        message=(
            "El servicio de notificaciones no está disponible. Tu token se "
            "enviará automáticamente en los próximos 10 minutos."
        ),
    )


def _construir_use_case():
    """Doble de prueba: cuenta activa, verificada, sin bloqueo por
    limite de solicitudes -- llega directo al paso de envio de correo."""
    usuario = MagicMock()
    usuario.id_usuario = 74
    usuario.nombre = "Ana Martinez"

    cuenta = MagicMock()
    cuenta.id_estado_cuenta = 2  # activa, distinta de ESTADO_ELIMINADO (5)
    cuenta.esta_pendiente.return_value = False

    usuarios_repo = MagicMock()
    usuarios_repo.obtener_por_correo.return_value = usuario

    cuentas_repo = MagicMock()
    cuentas_repo.obtener_por_usuario.return_value = cuenta

    eventos_repo = MagicMock()
    eventos_repo.contar_solicitudes_recuperacion_por_ip.return_value = 0

    db = MagicMock()

    use_case = SolicitarRecuperacionUseCase(
        usuarios_repo=usuarios_repo,
        cuentas_repo=cuentas_repo,
        eventos_repo=eventos_repo,
        db=db,
    )
    return use_case


class TestTCM01044FalloSMTP:
    """Suite de pruebas para TC-M01-044."""

    @patch(
        "src.identity_access.application.use_cases.contrasena."
        "solicitar_recuperacion_use_case.send_email"
    )
    def test_fallo_smtp_debe_mantener_el_mensaje_generico_sin_lanzar_excepcion(
        self, mock_send_email
    ):
        """
        RF-08: si el envio de correo agota sus reintentos y falla, el use
        case debe devolver igualmente el mensaje generico -- no debe
        propagar la excepcion del servicio de correo hacia el llamador.
        """
        mock_send_email.side_effect = _falla_smtp_simulada()
        use_case = _construir_use_case()
        dto = SolicitarRecuperacionDTO(correo_electronico=CORREO_PRUEBA)

        resultado = None
        excepcion_lanzada = None
        try:
            resultado = use_case.execute(dto, ip="203.0.113.10")
        except Exception as exc:
            excepcion_lanzada = exc

        assert excepcion_lanzada is None, (
            f"RF-08 exige que un fallo del servicio SMTP NO impida "
            f"responder al usuario con el mensaje generico; el use case "
            f"propago {type(excepcion_lanzada).__name__ if excepcion_lanzada else ''}"
            f": {excepcion_lanzada}"
        )
        assert resultado == MENSAJE_GENERICO, (
            f"Se esperaba el mensaje generico {MENSAJE_GENERICO!r}, se "
            f"obtuvo {resultado!r}"
        )

    @patch(
        "src.identity_access.application.use_cases.contrasena."
        "solicitar_recuperacion_use_case.send_email"
    )
    def test_endpoint_responde_202_cuando_smtp_falla(self, mock_send_email):
        """
        RF-08: POST /contrasena/recuperar debe responder HTTP 202 con el
        mensaje generico incluso si el SMTP esta caido tras agotar
        reintentos, no un error 5xx.
        """
        from src.identity_access.infrastructure.repositories.cuenta_repository import (
            SqlAlchemyCuentaRepository,
        )
        from src.identity_access.infrastructure.repositories.evento_repository import (
            SqlAlchemyEventoRepository,
        )
        from src.identity_access.infrastructure.repositories.usuario_repository import (
            SqlAlchemyUsuarioRepository,
        )
        from src.identity_access.infrastructure.routers.contrasena_routers import (
            router as contrasena_router,
        )
        from src.shared.database import get_db
        from src.shared.error_handlers import register_error_handlers

        mock_send_email.side_effect = _falla_smtp_simulada()

        usuario = MagicMock()
        usuario.id_usuario = 74
        usuario.nombre = "Ana Martinez"
        cuenta = MagicMock()
        cuenta.id_estado_cuenta = 2
        cuenta.esta_pendiente.return_value = False

        app = FastAPI()
        register_error_handlers(app)
        app.include_router(contrasena_router)

        def _fake_db():
            yield MagicMock()

        app.dependency_overrides[get_db] = _fake_db

        with (
            patch.object(SqlAlchemyUsuarioRepository, "obtener_por_correo", return_value=usuario),
            patch.object(SqlAlchemyCuentaRepository, "obtener_por_usuario", return_value=cuenta),
            patch.object(
                SqlAlchemyEventoRepository,
                "contar_solicitudes_recuperacion_por_ip",
                return_value=0,
            ),
            patch.object(SqlAlchemyEventoRepository, "registrar", return_value=None),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/contrasena/recuperar",
                json={"correo_electronico": CORREO_PRUEBA},
            )

        assert response.status_code == 202, (
            f"RF-08 exige HTTP 202 con mensaje generico aunque el SMTP "
            f"este caido tras agotar reintentos; el endpoint respondio "
            f"{response.status_code}. Cuerpo: {response.text}"
        )
        if response.status_code == 202:
            assert response.json().get("message") == MENSAJE_GENERICO
