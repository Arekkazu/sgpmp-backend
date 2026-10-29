"""Templates HTML para los correos del módulo de identidad y acceso.

Los links generados apuntan al frontend (`FRONTEND_URL`), no al backend.
El frontend extrae el token del query param y llama el endpoint correspondiente.
Todos usan la plantilla común de ``src/shared/plantilla_correo.py``.
"""
import os
from datetime import datetime

from dotenv import load_dotenv

from src.shared.plantilla_correo import Accion, formatear_hora, renderizar_correo

load_dotenv()

_FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

_NOTA_NO_FUISTE_TU = (
    "Si no reconoces esta actividad, cambia tu contraseña de inmediato desde "
    "«¿Olvidaste tu contraseña?» en la pantalla de inicio de sesión."
)


def recovery_email(nombre: str, token: str) -> str:
    """Genera el HTML del correo de recuperación de contraseña.

    Args:
        nombre: Nombre del usuario destinatario.
        token: Token de recuperación (válido 15 min) que se incluye en el link.

    Returns:
        String HTML listo para enviar por SMTP.
    """
    return renderizar_correo(
        titulo="Restablece tu contraseña",
        nombre=nombre,
        parrafos=[
            "Recibimos una solicitud para restablecer la contraseña de tu cuenta. "
            "Usa el botón para elegir una nueva.",
        ],
        evento="Solicitud de recuperación de contraseña",
        detalles=[("Enlace válido por", "15 minutos")],
        accion=Accion("Restablecer contraseña", f"{_FRONTEND_URL}/restablecer-contrasena?token={token}"),
        nota="Si no solicitaste este cambio, ignora este correo: tu contraseña sigue igual.",
    )


def activation_email(nombre: str, token: str) -> str:
    """Genera el HTML del correo de activación de cuenta.

    Args:
        nombre: Nombre del usuario destinatario.
        token: Token de activación (válido 24 h) que se incluye en el link.

    Returns:
        String HTML listo para enviar por SMTP.
    """
    return renderizar_correo(
        titulo="Activa tu cuenta en SIGAB",
        nombre=nombre,
        parrafos=[
            "Tu registro quedó listo. Activa la cuenta para poder iniciar sesión.",
        ],
        evento="Registro de usuario",
        detalles=[("Enlace válido por", "24 horas")],
        accion=Accion("Activar mi cuenta", f"{_FRONTEND_URL}/activar?token={token}"),
        nota="Si no te registraste en SIGAB, ignora este correo.",
    )


def verificar_correo_email(nombre: str, token: str) -> str:
    """HTML del correo que confirma un correo nuevo tras editar el perfil (RF-05).

    Usa el mismo enlace de activación: cambiar el correo devuelve la cuenta a
    pendiente hasta confirmarlo.
    """
    return renderizar_correo(
        titulo="Confirma tu nuevo correo",
        nombre=nombre,
        parrafos=[
            "Se cambió el correo de tu cuenta a esta dirección. Confírmalo para "
            "volver a iniciar sesión.",
        ],
        evento="Cambio de correo electrónico",
        detalles=[("Enlace válido por", "24 horas")],
        accion=Accion("Confirmar correo", f"{_FRONTEND_URL}/activar?token={token}"),
        nota="Si no pediste este cambio, contacta al administrador de SIGAB.",
    )


def cuenta_bloqueada_email(bloqueado_hasta: datetime) -> str:
    """HTML del aviso de bloqueo por intentos fallidos (RF-02 / RF-14)."""
    hora = formatear_hora(bloqueado_hasta)
    return renderizar_correo(
        titulo="Tu cuenta quedó bloqueada temporalmente",
        parrafos=[
            "Hubo 5 intentos seguidos de iniciar sesión con una contraseña incorrecta, "
            "así que la cuenta se bloqueó por seguridad.",
            f"A partir de las {hora} podrás volver a intentarlo.",
        ],
        evento="Bloqueo de cuenta",
        tono="critico",
        detalles=[("Disponible desde", hora)],
        nota=_NOTA_NO_FUISTE_TU,
    )


# RF-06: estado nuevo → (título, párrafo, tono). Los ids son modulo1.estados_cuentas.
_CAMBIOS_ESTADO = {
    2: (
        "Tu cuenta fue reactivada",
        "Un administrador reactivó tu cuenta. Ya puedes iniciar sesión.",
        "info",
    ),
    3: (
        "Tu cuenta fue desactivada",
        "Un administrador desactivó tu cuenta. No podrás iniciar sesión hasta que la reactive.",
        "atencion",
    ),
    4: (
        "Tu cuenta fue bloqueada",
        "Un administrador bloqueó tu cuenta. No podrás iniciar sesión hasta que la desbloquee.",
        "critico",
    ),
    5: (
        "Tu cuenta fue eliminada",
        "Un administrador eliminó tu cuenta. Ya no podrás iniciar sesión en SIGAB.",
        "critico",
    ),
}


def cambio_estado_cuenta_email(nombre: str, id_estado_nuevo: int) -> tuple[str, str]:
    """Asunto y HTML del aviso de cambio de estado por un administrador (RF-06)."""
    titulo, parrafo, tono = _CAMBIOS_ESTADO.get(
        id_estado_nuevo,
        ("El estado de tu cuenta cambió", "Un administrador modificó el estado de tu cuenta.", "atencion"),
    )
    return titulo, renderizar_correo(
        titulo=titulo,
        nombre=nombre,
        parrafos=[parrafo],
        evento="Cambio de estado de la cuenta",
        tono=tono,
        nota="Si crees que es un error, contacta al administrador de SIGAB.",
    )
