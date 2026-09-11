"""Templates HTML para los correos del módulo de identidad y acceso.

Los links generados apuntan al frontend (`FRONTEND_URL`), no al backend.
El frontend extrae el token del query param y llama el endpoint correspondiente.
"""
import os

from dotenv import load_dotenv

load_dotenv()

_FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


def recovery_email(nombre: str, token: str) -> str:
    """Genera el HTML del correo de recuperación de contraseña.

    Args:
        nombre: Nombre del usuario destinatario.
        token: Token de recuperación (válido 15 min) que se incluye en el link.

    Returns:
        String HTML listo para enviar por SMTP.
    """
    link = f"{_FRONTEND_URL}/restablecer-contrasena?token={token}"
    return f"""
    <h2>Hola, {nombre}</h2>
    <p>Recibimos una solicitud para restablecer la contraseña de tu cuenta.</p>
    <p>Haz clic en el siguiente enlace para continuar:</p>
    <p><a href="{link}">Restablecer mi contraseña</a></p>
    <p>Este enlace es válido por <strong>15 minutos</strong>. Si no lo usas a tiempo, deberás solicitar uno nuevo.</p>
    <p>Si no solicitaste este cambio, ignora este correo. Tu contraseña no será modificada.</p>
    """


def activation_email(nombre: str, token: str) -> str:
    """Genera el HTML del correo de activación de cuenta.

    Args:
        nombre: Nombre del usuario destinatario.
        token: Token de activación (válido 24 h) que se incluye en el link.

    Returns:
        String HTML listo para enviar por SMTP.
    """
    link = f"{_FRONTEND_URL}/activar?token={token}"
    return f"""
    <h2>Hola, {nombre}</h2>
    <p>Para activar tu cuenta haz clic en el siguiente enlace:</p>
    <p><a href="{link}">Activar mi cuenta</a></p>
    <p>Este enlace es válido por <strong>24 horas</strong>.</p>
    <p>Si no realizaste este registro, ignora este correo.</p>
    """
