# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-27 RF-60: comparte efectos de comunicacion    |
"""Efectos de aplicación comunes al worker y al evaluador periódico, sin commits."""
from src.telemetry.domain.entities.alerta import Alerta


def completar_transicion_comunicacion(estado, parametros, tiempo, ahora, alertas, periodos, origen):
    nuevo = estado.estado_actual
    if nuevo == 'ACTIVO':
        # El trigger abre períodos por transición; la reconexión por telemetría
        # también debe cerrarlos cuando no interviene el trigger de heartbeat.
        while (periodo := periodos.obtener_abierto_por_dispositivo(estado.id_dispositivo_iot)) is not None:
            periodo.cerrar(ahora)
            periodos.cerrar(periodo)
    elif nuevo in ('SIN_SEÑAL', 'INACTIVO'):
        codigo = 'DISPOSITIVO_INACTIVO' if nuevo == 'INACTIVO' else 'DISPOSITIVO_SIN_SEÑAL'
        if not alertas.buscar_tecnica_activa_dispositivo(estado.id_dispositivo_iot, codigo):
            alertas.guardar(Alerta(
                tipo_alerta='TECNICA', severidad='CRITICO' if nuevo == 'INACTIVO' else 'LEVE',
                estado_alerta='ACTIVA', origen_evento=origen, tipo_variable=codigo,
                fecha_evento=ahora, fecha_generacion=ahora,
                id_dispositivo_ioit=estado.id_dispositivo_iot,
                metadato_evento={'estado_operativo': nuevo, 'tiempo_sin_contacto_seg': tiempo,
                    'umbral_activo_seg': parametros.umbral_activo,
                    'umbral_sin_senal_seg': parametros.umbral_sin_senal,
                    'umbral_inactivo_seg': parametros.umbral_inactivo},
            ))
