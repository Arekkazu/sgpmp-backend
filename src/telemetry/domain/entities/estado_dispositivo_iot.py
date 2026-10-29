# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-27 RF-60: algoritmo unico con umbrales dinamicos |
# | 2026-10-22 | Leandro | DEV-42 RF-60: restringe transiciones manuales       |
# | 2026-10-27 | Leandro | INC-M03-127-G27 RF-54/60: priorizar buffer confirmado y conservarlo hasta reporte de vaciado. |
# | 2026-10-29 | Arekkazu | INC-M03-134-G03 RF-60 CA-7/RF-53 E1: mantenimiento desde cualquier estado y lecturas rechazadas |
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from src.shared.errors import BusinessRuleError

@dataclass
class EstadoDispositivoIoT:
    id_estado_dispositivo_iot: Optional[int]
    id_dispositivo_iot: int
    estado_actual: str
    fecha_ultimo_contacto: Optional[datetime]
    id_ultimo_heartbeat: Optional[int]
    tiempo_sin_contacto: Optional[int]
    causa_primaria: Optional[str]
    causas_secundarias: Optional[Any]
    fecha_ultima_actualizacion: datetime
    id_usuario: Optional[int]

    def validar_transicion_manual(self, destino: str) -> None:
        # RF-60 CA-7: a mantenimiento desde cualquier estado; CA-8: solo de ahí vuelve a ACTIVO.
        a_mantenimiento = destino == 'EN_MANTENIMIENTO' and self.estado_actual != 'EN_MANTENIMIENTO'
        cierre = (self.estado_actual, destino) == ('EN_MANTENIMIENTO', 'ACTIVO')
        if not (a_mantenimiento or cierre):
            raise BusinessRuleError('TRANSICION_INVALIDA',
                f'No se permite la transición manual de {self.estado_actual} a {destino}.')

    def evaluar_transicion(
        self,
        tiempo_sin_contacto_seg: int,
        estado_local_buffer: Optional[str],
        umbral_activo: int,
        umbral_sin_senal: int,
        umbral_inactivo: int,
        *, datos_pendientes_buffer: Optional[int] = None,
    ) -> Optional[str]:
        """RF-60: prioridad de buffer confirmada para #682 sobre contacto reciente.
        Retorna el nuevo estado si hay transición, None si no cambia.
        No evalúa EN_MANTENIMIENTO (estado manual).
        """
        if self.estado_actual == 'EN_MANTENIMIENTO':
            return None

        if not 0 < umbral_activo < umbral_sin_senal < umbral_inactivo:
            raise ValueError('Los umbrales de comunicación deben ser positivos y estar ordenados.')
        # El contacto reciente acredita comunicación; no demuestra que se vació la cola.
        if datos_pendientes_buffer is None:
            buffer_activo = estado_local_buffer in ('A', 'L') or self.estado_actual == 'BUFFER_ACTIVO'
        else:
            buffer_activo = datos_pendientes_buffer > 0 and (
                estado_local_buffer in ('A', 'L') or self.estado_actual == 'BUFFER_ACTIVO')
        if buffer_activo:
            nuevo = 'BUFFER_ACTIVO'
        elif tiempo_sin_contacto_seg <= umbral_activo:
            nuevo = 'ACTIVO'
        elif tiempo_sin_contacto_seg > umbral_sin_senal:
            # Paso 4 refina el fallo del paso 3 al superar la inactividad:
            # intervalos excluyentes evitan volver INACTIVO inalcanzable.
            nuevo = 'INACTIVO' if tiempo_sin_contacto_seg > umbral_inactivo else 'SIN_SEÑAL'
        else:
            return None  # Durante la tolerancia se conserva el estado previo.

        return nuevo if nuevo != self.estado_actual else None

    def aplicar_transicion(
        self,
        nuevo_estado: str,
        causa: Optional[str],
        ahora: datetime,
        id_heartbeat: Optional[int] = None,
        id_usuario: Optional[int] = None,
    ) -> None:
        if nuevo_estado not in (
            'ACTIVO', 'SIN_SEÑAL', 'BUFFER_ACTIVO', 'INACTIVO', 'EN_MANTENIMIENTO', 'DESCONOCIDO'
        ):
            raise BusinessRuleError(
                code='ESTADO_DISPOSITIVO_INVALIDO',
                message=f'Estado de dispositivo no válido: {nuevo_estado}',
            )
        self.estado_actual = nuevo_estado
        self.causa_primaria = causa
        self.fecha_ultima_actualizacion = ahora
        if id_heartbeat is not None:
            self.id_ultimo_heartbeat = id_heartbeat
        # Una transición automática no se atribuye al último operador manual.
        self.id_usuario = id_usuario
