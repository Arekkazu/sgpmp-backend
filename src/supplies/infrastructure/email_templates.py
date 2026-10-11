"""Templates HTML para los correos del módulo de suministros (RF-76 pasos 9 y 13).

No generan links al frontend (a diferencia de identity_access): son avisos
informativos sobre el período de retiro de un medicamento aplicado a un activo
biológico. Usan la plantilla común de ``src/shared/plantilla_correo.py``.
"""
from __future__ import annotations

from datetime import date

from src.shared.plantilla_correo import formatear_dia, renderizar_correo


def inicio_retiro_email(nombre: str, nombre_medicamento: str, fecha_fin_retiro: date) -> str:
    """Genera el HTML del correo de inicio de período de retiro (RF-76 paso 9).

    Args:
        nombre: Nombre del destinatario (Productor o Veterinario).
        nombre_medicamento: Medicamento aplicado que originó el retiro.
        fecha_fin_retiro: Fecha en que concluye el período de retiro vigente.

    Returns:
        String HTML listo para enviar por SMTP.
    """
    return renderizar_correo(
        titulo="Un activo entró en período de retiro",
        nombre=nombre,
        parrafos=[
            "Se aplicó un medicamento a uno de tus activos biológicos. Mientras dure el "
            "retiro, el activo queda en tratamiento y no debe destinarse a consumo humano "
            "ni a producción de leche o huevos.",
        ],
        evento="Inicio de período de retiro",
        tono="atencion",
        detalles=[
            ("Medicamento", nombre_medicamento),
            ("Retiro hasta", formatear_dia(fecha_fin_retiro)),
        ],
    )


def fin_retiro_email(nombre: str, fecha_fin_retiro: date) -> str:
    """Genera el HTML del correo de fin de período de retiro (RF-76 paso 13).

    Args:
        nombre: Nombre del destinatario (Productor).
        fecha_fin_retiro: Fecha de retiro vigente que acaba de concluir.

    Returns:
        String HTML listo para enviar por SMTP.
    """
    return renderizar_correo(
        titulo="Terminó el período de retiro",
        nombre=nombre,
        parrafos=[
            "El período de retiro de tu activo biológico concluyó y el activo volvió "
            "automáticamente al estado activo.",
        ],
        evento="Fin de período de retiro",
        detalles=[("Retiro vigente hasta", formatear_dia(fecha_fin_retiro))],
    )
