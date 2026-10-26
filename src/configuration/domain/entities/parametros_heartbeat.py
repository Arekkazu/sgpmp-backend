# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-27 RF-60: contrato de parametros persistidos  |
"""P-1 provisional: claves RF-60 en DEV-14, sin valores de respaldo en ejecución.

Los únicos defaults son los D expresos de RF-60/RF-56 para la siembra.
Los tiempos RF-60 son segundos; RF-18 conserva minutos en su contrato público.
"""
from decimal import Decimal

from src.configuration.domain.entities.parametro_mlops import numero_configurado
from src.shared.errors import ServiceUnavailableError

INTERVALO_CAMARA = 'intervalo_heartbeat_camara'
INTERVALOS_TIPO = 'intervalos_heartbeat_por_tipo'
MARGEN = 'margen_tolerancia'
INACTIVIDAD = 'tiempo_inactividad_extendida'
BATERIA_AVISO = 'umbral_bateria_aviso'
BATERIA_CRITICA = 'umbral_bateria_critica'
RSSI = 'umbral_rssi'
SNR = 'umbral_snr'
FIRMWARE = 'version_minima_firmware'
TEMPERATURA_MAXIMA = 'umbral_temperatura_maxima'
TEMPERATURA_CRITICA = 'umbral_temperatura_critica'
VENTANAS = 'ventanas_consecutivas_sin_deteccion'
COBERTURA = 'cobertura_minima_deteccion_valida'
DURACION = 'duracion_ventana_observacion'
LATENCIA = 'presupuesto_latencia_ventana'

LIMITES_HEARTBEAT = {
    INTERVALO_CAMARA: (30, 600), INTERVALOS_TIPO: (None, None),
    MARGEN: (0, None), INACTIVIDAD: (0, None),
    BATERIA_AVISO: (0, 100), BATERIA_CRITICA: (0, 100),
    RSSI: (None, None), SNR: (None, None), FIRMWARE: (None, None),
    TEMPERATURA_MAXIMA: (None, None), TEMPERATURA_CRITICA: (None, None),
    VENTANAS: (1, 20), COBERTURA: (Decimal('0.05'), Decimal('0.90')),
    DURACION: (10, 300), LATENCIA: (50, 95),
}
TEMPORALES = (INTERVALO_CAMARA, INTERVALOS_TIPO, MARGEN, INACTIVIDAD)
PREDETERMINADOS_HEARTBEAT = {
    INTERVALO_CAMARA: 120, VENTANAS: 3, COBERTURA: 0.30,
    DURACION: 60, LATENCIA: 80,
}


def _invalido(mensaje):
    raise ServiceUnavailableError('PARAMETRO_CONFIGURACION_INVALIDO', mensaje)


def intervalos_configurados(parametros):
    parametro = parametros.get(INTERVALOS_TIPO)
    if parametro is None:
        return {}
    valor = parametro.valor
    if not isinstance(valor, dict) or not valor:
        _invalido('intervalos_heartbeat_por_tipo debe ser un objeto no vacío de categorías e intervalos en segundos.')
    if any(not isinstance(tipo, str) or not tipo.strip() or tipo != tipo.strip().upper()
           or tipo == 'CAMARA' or type(segundos) is not int or segundos <= 0
           for tipo, segundos in valor.items()):
        _invalido('Los intervalos por tipo requieren categorías en mayúsculas e enteros positivos; CAMARA usa su clave canónica.')
    return dict(valor)


def validar_cadena(intervalos, frecuencia_seg, umbral_sin_senal_seg, margen_seg=None):
    """Una regla compartida para configuración RF-18 y consumidores RF-60."""
    if frecuencia_seg <= 0 or umbral_sin_senal_seg < frecuencia_seg:
        _invalido('Cadena canónica: frecuencia_muestreo debe ser positiva y no superar umbral_sin_senal.')
    for intervalo in intervalos:
        if intervalo <= 0 or 2 * intervalo > frecuencia_seg:
            _invalido('Cadena canónica: intervalo_heartbeat debe ser menor o igual a frecuencia_muestreo / 2.')
        if margen_seg is not None and margen_seg < max(intervalo, Decimal(str(frecuencia_seg)) / 2):
            _invalido('Restricción 12: margen_tolerancia debe ser al menos max(intervalo_heartbeat, frecuencia_muestreo / 2).')


def validar_heartbeat_configurado(parametros, frecuencia_min=None, umbral_min=None):
    """Valida claves presentes y relaciones disponibles; no completa ausencias."""
    valores = {}
    for nombre, (minimo, maximo) in LIMITES_HEARTBEAT.items():
        if nombre not in parametros or nombre in (INTERVALOS_TIPO, FIRMWARE):
            continue
        valores[nombre] = numero_configurado(
            parametros, nombre, minimo=minimo, maximo=maximo,
            entero=nombre in (INTERVALO_CAMARA, MARGEN, INACTIVIDAD, VENTANAS, DURACION),
            positivo=nombre in (INTERVALO_CAMARA, MARGEN, INACTIVIDAD, VENTANAS, DURACION),
        )
    intervalos = list(intervalos_configurados(parametros).values())
    if INTERVALO_CAMARA in valores:
        intervalos.append(valores[INTERVALO_CAMARA])
    if FIRMWARE in parametros:
        version = parametros[FIRMWARE].valor
        if not isinstance(version, str) or not version.strip() or len(version) > 50 or '\x00' in version:
            _invalido('La versión mínima de firmware debe ser un texto no vacío de hasta 50 caracteres.')
    if all(nombre in valores for nombre in (BATERIA_CRITICA, BATERIA_AVISO)):
        if valores[BATERIA_CRITICA] > valores[BATERIA_AVISO]:
            _invalido('El umbral crítico de batería no puede superar el umbral de aviso.')
    if all(nombre in valores for nombre in (TEMPERATURA_MAXIMA, TEMPERATURA_CRITICA)):
        if valores[TEMPERATURA_CRITICA] < valores[TEMPERATURA_MAXIMA]:
            _invalido('La temperatura crítica no puede ser inferior a la máxima operativa.')
    if frecuencia_min is not None and umbral_min is not None:
        validar_cadena(intervalos, frecuencia_min * 60, umbral_min * 60, valores.get(MARGEN))
    return valores
