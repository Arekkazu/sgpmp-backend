from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import TypeVar

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import (
    BitacoraAuditoriaRepository,
)
from src.shared.errors import AppError


T = TypeVar('T')


def ejecutar_con_auditoria_de_rechazo(
    operacion: Callable[[], T],
    *,
    db: Session,
    bitacora_repo: BitacoraAuditoriaRepository | None,
    obtener_activo: Callable[[int], object | None] | None,
    id_activo: int | None,
    id_usuario: int,
    rf_origen: str,
    tipo_evento_rechazado: str,
    clasificacion_biologica: str,
    tipos_por_codigo: Mapping[str, str] | None = None,
) -> T:
    """Ejecuta una operación y registra sus rechazos de dominio para RF-52 CA-10.

    Los errores de infraestructura conservan el manejo de fallo que ya tiene cada
    caso de uso. La auditoría es de mejor esfuerzo: si RF-52 no está disponible,
    nunca reemplaza el error funcional que debe recibir el cliente.
    """

    try:
        return operacion()
    except AppError as exc:
        if exc.status_code >= 500 or bitacora_repo is None:
            raise

        # Separa cualquier trabajo pendiente del registro de rechazo. Así el
        # rollback funcional no puede deshacer la evidencia de auditoría.
        db.rollback()

        activo = None
        if obtener_activo is not None and id_activo is not None:
            try:
                activo = obtener_activo(id_activo)
            except Exception:
                # CA-10 exige conservar el rechazo aun si no puede enriquecerse
                # con los datos del activo solicitado.
                pass

        detalle = {
            'error_code': exc.code,
            'causa': exc.message,
        }
        if id_activo is not None:
            detalle['id_activo_solicitado'] = id_activo
        if exc.field is not None:
            detalle['campo'] = exc.field

        tipo_evento = (tipos_por_codigo or {}).get(exc.code, tipo_evento_rechazado)

        try:
            bitacora_repo.registrar(EventoAuditoria(
                rf_origen=rf_origen,
                tipo_evento=tipo_evento,
                clasificacion_biologica=clasificacion_biologica,
                resultado='RECHAZADO',
                severidad_log='WARNING',
                timestamp_evento=datetime.now(timezone.utc),
                id_activo_biologico=(id_activo if activo is not None else None),
                tipo_activo=getattr(activo, 'tipo', None),
                descripcion=f'Operación rechazada: {exc.code}',
                detalle_tecnico=detalle,
                id_usuario_responsable=id_usuario,
            ))
            db.commit()
        except Exception:
            db.rollback()

        raise
