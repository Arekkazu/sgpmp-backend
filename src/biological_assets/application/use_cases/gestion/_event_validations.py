from __future__ import annotations

from datetime import datetime, timezone

from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico
from src.biological_assets.domain.repositories.evento_activo_repository import EventoActivoRepository
from src.biological_assets.domain.repositories.historico_estado_repository import HistoricoEstadoRepository
from src.shared.errors import BusinessRuleError, ConflictError, ValidationError

# RF-39: estados que permiten registro de eventos
_ESTADOS_PERMITEN_EVENTOS = {1, 3, 4}  # ACTIVO, EN_TRATAMIENTO, AISLADO
_NOMBRES_ESTADO = {1: 'ACTIVO', 2: 'INACTIVO', 3: 'EN_TRATAMIENTO', 4: 'AISLADO', 5: 'CERRADO', 6: 'BAJA'}

# RF-35 (tarea Taiga "RBAC Veterinario, validar eventos pendientes,
# concurrencia optimista" -- issue histórico #30): estados que reflejan un
# evento sanitario abierto (sin cerrar) sobre el activo.
_ESTADOS_EVENTO_PENDIENTE = {3, 4}  # EN_TRATAMIENTO, AISLADO


def validar_sin_eventos_pendientes(activo: ActivoBiologico) -> None:
    """RF-35: rechaza la edición si el activo tiene un evento pendiente sin cerrar.

    El modelo de eventos no tiene un flag propio de "abierto/cerrado" — el
    estado del activo es la única señal persistente de que un evento
    sanitario sigue abierto: `RegistrarEventoSanitarioUseCase` transiciona a
    EN_TRATAMIENTO/AISLADO al registrar el evento, y solo `CambiarEstadoUseCase`
    (RF-44) lo "cierra" de vuelta a ACTIVO/INACTIVO/CERRADO.

    409, no 422 (INC-M02-G22): el activo está bloqueado por su estado actual,
    igual que ESTADO_NO_PERMITE_EVENTOS; la petición en sí es válida.
    """
    if activo.id_estado in _ESTADOS_EVENTO_PENDIENTE:
        estado_actual = _NOMBRES_ESTADO.get(activo.id_estado, str(activo.id_estado))
        raise ConflictError(
            code='EVENTO_PENDIENTE_SIN_CERRAR',
            message=(
                f'No se puede editar el activo mientras tenga un evento sanitario pendiente sin cerrar '
                f'(estado actual: {estado_actual}). Cambie el estado de vuelta a ACTIVO, INACTIVO o CERRADO '
                f'antes de editar sus datos.'
            ),
        )


def validar_historial_consistente(activo: ActivoBiologico, historico_repo: HistoricoEstadoRepository) -> None:
    """RF-35: rechaza la edición si el histórico de estados es inconsistente con el estado actual.

    `CambiarEstadoUseCase` es el único punto que muta `id_estado` y siempre
    inserta el histórico correspondiente en la misma transacción. Si el
    último registro no coincide con el estado actual del activo, algo lo
    mutó fuera de ese flujo — una inconsistencia de datos que debe bloquear
    la edición hasta investigarse.
    """
    ultimo = historico_repo.obtener_ultimo_cambio(activo.id_activo_biologico)
    if ultimo is not None and ultimo.id_estado_nuevo != activo.id_estado:
        raise BusinessRuleError(
            code='HISTORIAL_INCONSISTENTE',
            message=(
                'El histórico de estados del activo es inconsistente con su estado actual. '
                'Contacte a soporte antes de continuar con la edición.'
            ),
        )


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
    # RF-39/40/41/42 clasifican "Fecha inválida" como HTTP 400, no como regla de
    # negocio: ValidationError, no BusinessRuleError. RF-43 no pasa por aquí, pide
    # 422 para su propio caso de fecha.
    ahora = datetime.now(timezone.utc)
    fecha_utc = fecha.astimezone(timezone.utc)

    if fecha_utc > ahora:
        raise ValidationError(
            code='FECHA_FUTURA',
            message='La fecha del evento no puede ser posterior a la fecha actual.',
        )

    if activo.fecha_creacion:
        creacion_utc = activo.fecha_creacion.astimezone(timezone.utc)
        if fecha_utc < creacion_utc:
            raise ValidationError(
                code='FECHA_ANTERIOR_REGISTRO',
                message='La fecha del evento es inválida o inconsistente con el historial.',
            )

    ultima = evento_repo.obtener_ultima_fecha(activo.id_activo_biologico)
    if ultima is not None:
        ultima_utc = ultima.astimezone(timezone.utc)
        if fecha_utc < ultima_utc:
            raise ValidationError(
                code='FECHA_INCOHERENTE',
                message='La fecha del evento es inválida o inconsistente con el historial.',
            )
