import os

from dotenv import load_dotenv

load_dotenv()

_FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


def activation_email(nombre: str, token: str) -> str:
    link = f"{_FRONTEND_URL}/activar-cuenta?token={token}"
    return f"""
    <h2>Hola, {nombre}</h2>
    <p>Para activar tu cuenta haz clic en el siguiente enlace:</p>
    <p><a href="{link}">Activar mi cuenta</a></p>
    <p>Este enlace es válido por <strong>24 horas</strong>.</p>
    <p>Si no realizaste este registro, ignora este correo.</p>
    """
