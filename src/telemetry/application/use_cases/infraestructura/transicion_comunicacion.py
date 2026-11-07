# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-27 RF-60: comparte efectos de comunicacion    |
# | 2026-10-23 | Arekkazu | INTEG RFC-012..016 RF-57: conserva motivo_generacion de DEV-49 |
# | 2026-10-22 | Leandro | DEV-42 RF-60: recuperacion selectiva y heartbeat ausente |
"""Efectos de aplicación comunes al worker y al evaluador periódico, sin commits."""
from src.telemetry.domain.entities.alerta import Alerta
from src.telemetry.application.use_cases.alertas.actualizar_estado_alerta_use_case import ActualizarEstadoAlertaUseCase


def completar_transicion_comunicacion(estado, parametros, tiempo, ahora, alertas, periodos, origen):
    nuevo = estado.estado_actual
    if nuevo == 'EN_MANTENIMIENTO':
        return
    alertas.bloquear_dispositivo(estado.id_dispositivo_iot)
    if nuevo == 'ACTIVO':
        # El trigger abre períodos por transición; la reconexión por telemetría
        # también debe cerrarlos cuando no interviene el trigger de heartbeat.
        while (periodo := periodos.obtener_abierto_por_dispositivo(estado.id_dispositivo_iot)) is not None:
            periodo.cerrar(ahora)
            periodos.cerrar(periodo)
        for alerta in alertas.listar_conectividad_abierta(estado.id_dispositivo_iot):
            if alerta.tipo_variable == 'HEARTBEAT_AUSENTE' and (
                parametros.ultimo_heartbeat is None or not 0 <=
                (ahora-parametros.ultimo_heartbeat).total_seconds() <= 2*parametros.intervalo_heartbeat_seg
            ):
                continue  # La telemetría sola no prueba recuperación del heartbeat.
            ActualizarEstadoAlertaUseCase.resolver_conectividad(alerta, alertas, ahora)
        if parametros.heartbeat_ausente(ahora) and not alertas.buscar_tecnica_activa_dispositivo(
            estado.id_dispositivo_iot, 'HEARTBEAT_AUSENTE'):
            alertas.guardar(Alerta(
                tipo_alerta='TECNICA', severidad='LEVE', estado_alerta='ACTIVA',
                origen_evento=origen, tipo_variable='HEARTBEAT_AUSENTE',
                fecha_evento=ahora, fecha_generacion=ahora,
                id_dispositivo_ioit=estado.id_dispositivo_iot,
                id_infraestructura=parametros.id_infraestructura,
                metadato_evento={'ultimo_heartbeat': parametros.ultimo_heartbeat.isoformat() if parametros.ultimo_heartbeat else None,
                    'ultima_telemetria': parametros.ultima_telemetria.isoformat(),
                    'intervalo_heartbeat_seg': parametros.intervalo_heartbeat_seg},
            ))
    elif nuevo in ('SIN_SEÑAL', 'INACTIVO'):
        codigo = 'DISPOSITIVO_INACTIVO' if nuevo == 'INACTIVO' else 'DISPOSITIVO_SIN_SEÑAL'
        if not alertas.buscar_tecnica_activa_dispositivo(estado.id_dispositivo_iot, codigo):
            alertas.guardar(Alerta(
                tipo_alerta='TECNICA', severidad='CRITICO' if nuevo == 'INACTIVO' else 'LEVE',
                estado_alerta='ACTIVA', origen_evento=origen, tipo_variable=codigo,
                fecha_evento=ahora, fecha_generacion=ahora,
                id_dispositivo_ioit=estado.id_dispositivo_iot,
                id_infraestructura=parametros.id_infraestructura,
                # DEV-49: el trigger de RF-57 toma este motivo para el historial inicial.
                metadato_evento={'estado_operativo': nuevo, 'motivo_generacion': f'Dispositivo en estado {nuevo}',
                    'tiempo_sin_contacto_seg': tiempo,
                    'umbral_activo_seg': parametros.umbral_activo,
                    'umbral_sin_senal_seg': parametros.umbral_sin_senal,
                    'umbral_inactivo_seg': parametros.umbral_inactivo},
            ))
