"""Templates HTML para los correos del módulo de suministros (RF-76 pasos 9 y 13).

No generan links al frontend (a diferencia de identity_access): son avisos
informativos sobre el período de retiro de un medicamento aplicado a un activo
biológico.
"""
from __future__ import annotations

from datetime import date


def inicio_retiro_email(nombre: str, nombre_medicamento: str, fecha_fin_retiro: date) -> str:
    """Genera el HTML del correo de inicio de período de retiro (RF-76 paso 9).

    Args:
        nombre: Nombre del destinatario (Productor o Veterinario).
        nombre_medicamento: Medicamento aplicado que originó el retiro.
        fecha_fin_retiro: Fecha en que concluye el período de retiro vigente.

    Returns:
        String HTML listo para enviar por SMTP.
    """
    return f"""
    <h2>Hola, {nombre}</h2>
    <p>Se aplicó el medicamento <strong>{nombre_medicamento}</strong> a uno de tus activos
    biológicos, lo que inicia un período de retiro.</p>
    <p>El activo permanecerá en estado <strong>EN_TRATAMIENTO</strong> hasta el
    <strong>{fecha_fin_retiro.isoformat()}</strong>. Durante este período no debe destinarse a
    consumo humano ni a producción de leche/huevos.</p>
    """


def fin_retiro_email(nombre: str, fecha_fin_retiro: date) -> str:
    """Genera el HTML del correo de fin de período de retiro (RF-76 paso 13).

    Args:
        nombre: Nombre del destinatario (Productor).
        fecha_fin_retiro: Fecha de retiro vigente que acaba de concluir.

    Returns:
        String HTML listo para enviar por SMTP.
    """
    return f"""
    <h2>Hola, {nombre}</h2>
    <p>El período de retiro vigente hasta el <strong>{fecha_fin_retiro.isoformat()}</strong>
    ha concluido.</p>
    <p>El activo volvió automáticamente al estado <strong>ACTIVO</strong>.</p>
    """
