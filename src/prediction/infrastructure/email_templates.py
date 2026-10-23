# | Fecha      | Nombre       | Que se hizo                                           |
# |------------|--------------|-------------------------------------------------------|
# | 2026-10-23 | destroyerban | DEV-48 RF-69: avisos de carga externa y rechazo       |
# | 2026-10-23 | destroyerban | DEV-37 RF-73: reintentos, respaldo local y sincronización de la bitácora M04 |
"""Templates HTML de los correos del módulo de Predicción (RF-69 E1b y E3, DEV-48).

Avisos informativos, sin links al frontend. Usan la plantilla común de RF-14
(``src/shared/plantilla_correo.py``).
"""
from __future__ import annotations

from typing import Optional

from src.prediction.domain.entities.version_modelo import VersionModelo
from src.shared.plantilla_correo import renderizar_correo


def carga_modelo_externo_email(nombre: Optional[str], id_proceso_rf71: str, motivo: str) -> str:
    """RF-69 E1b: intento de registrar un modelo que no viene del reentrenamiento interno (RF-71)."""
    return renderizar_correo(
        titulo="Se bloqueó un intento de cargar un modelo de IA externo",
        nombre=nombre,
        parrafos=[
            "El sistema rechazó una solicitud para registrar una versión de modelo de IA que no "
            "provino del proceso interno de reentrenamiento (RF-71). No se registró ninguna versión.",
            "El intento quedó en la bitácora de auditoría de Predicción como "
            "INTENTO_CARGA_MODELO_EXTERNO, con severidad CRITICAL.",
        ],
        evento="Intento de carga de modelo externo",
        tono="critico",
        detalles=[
            ("Proceso declarado", id_proceso_rf71),
            ("Motivo del rechazo", motivo),
        ],
        nota=(
            "Si el intento se repite, solo se envía un aviso cada 5 minutos; "
            "todos los intentos quedan en la bitácora."
        ),
    )


def fallback_auditoria_activado_email(nombre: Optional[str], resumen: dict) -> str:
    """RF-73 E8: la bitácora de M04 estuvo caída y se sincronizó desde el respaldo local."""
    return renderizar_correo(
        titulo="La bitácora de auditoría de Predicción usó el respaldo local",
        nombre=nombre,
        parrafos=[
            "El repositorio de auditoría de Predicción (M04) no estuvo disponible y los eventos "
            "se guardaron en el respaldo local del servidor. El repositorio ya se recuperó y los "
            "eventos se sincronizaron en orden, con su fecha original y origen FALLBACK.",
            "Quedó registrado en la bitácora como AUDITORIA_FALLBACK_ACTIVADO, con severidad CRITICAL.",
        ],
        evento="Respaldo de auditoría activado",
        tono="critico",
        detalles=[
            ("Inicio de la contingencia", resumen["inicio_contingencia"]),
            ("Sincronizado", resumen["fin_contingencia"]),
            ("Eventos sincronizados", str(resumen["eventos_sincronizados"])),
            ("Fallas de persistencia", str(resumen["fallas_persistencia"])),
        ],
    )


def version_rechazada_email(nombre: Optional[str], version: VersionModelo) -> str:
    """RF-69 E3: una versión quedó RECHAZADO porque sus métricas no alcanzan los umbrales."""
    detalles = [
        ("Versión", version.nombre_version),
        ("Tipo de modelo", version.tipo_modelo),
    ]
    if version.componente:
        detalles.append(("Componente", version.componente))
    detalles.append(("Motivo", version.detalle_validacion or "Métricas bajo los umbrales mínimos"))
    return renderizar_correo(
        titulo="Una versión de modelo de IA quedó RECHAZADA",
        nombre=nombre,
        parrafos=[
            "Se registró una nueva versión de modelo con estado RECHAZADO: sus métricas no "
            "alcanzan los umbrales mínimos requeridos. La versión no se puede activar.",
            "Revísela en Versiones de modelos de Predicción.",
        ],
        evento="Versión de modelo rechazada",
        tono="atencion",
        detalles=detalles,
    )
