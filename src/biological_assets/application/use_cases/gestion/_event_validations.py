from __future__ import annotations

from datetime import datetime, timezone

from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico
from src.biological_assets.domain.repositories.evento_activo_repository import EventoActivoRepository
from src.shared.errors import BusinessRuleError, ConflictError

# RF-39: estados que permiten registro de eventos
_ESTADOS_PERMITEN_EVENTOS = {1, 3, 4}  # ACTIVO, EN_TRATAMIENTO, AISLADO
_NOMBRES_ESTADO = {1: 'ACTIVO', 2: 'INACTIVO', 3: 'EN_TRATAMIENTO', 4: 'AISLADO', 5: 'CERRADO', 6: 'BAJA'}


def validar_estado_permite_eventos(activo: ActivoBiologico) -> None:
    if activo.id_estado not in _ESTADOS_PERMITEN_EVENTOS:
        estado_actual = _NOMBRES_ESTADO.get(activo.id_estado, str(activo.id_estado))
        raise ConflictError(
            code='ESTADO_NO_PERMITE_EVENTOS',
            message=(
                f'No es posible registrar eventos sobre este activo. El activo se encuentra '
                f'en estado {estado_actual}, el cual no permite nuevos registros de eventos. '
                f'Los estados que permiten registro de eventos son: ACTIVO, EN_TRATAMIENTO, AISLADO.'
            ),
        )


def validar_fecha_evento(
    fecha: datetime,
    activo: ActivoBiologico,
    evento_repo: EventoActivoRepository,
) -> None:
    ahora = datetime.now(timezone.utc)
    fecha_utc = fecha.astimezone(timezone.utc)

    if fecha_utc > ahora:
        raise BusinessRuleError(
            code='FECHA_FUTURA',
            message='La fecha del evento no puede ser posterior a la fecha actual.',
        )

    if activo.fecha_creacion:
        creacion_utc = activo.fecha_creacion.astimezone(timezone.utc)
        if fecha_utc < creacion_utc:
            raise BusinessRuleError(
                code='FECHA_ANTERIOR_REGISTRO',
                message='La fecha del evento es inválida o inconsistente con el historial.',
            )

    ultima = evento_repo.obtener_ultima_fecha(activo.id_activo_biologico)
    if ultima is not None:
        ultima_utc = ultima.astimezone(timezone.utc)
        if fecha_utc < ultima_utc:
            raise BusinessRuleError(
                code='FECHA_INCOHERENTE',
                message='La fecha del evento es inválida o inconsistente con el historial.',
            )
