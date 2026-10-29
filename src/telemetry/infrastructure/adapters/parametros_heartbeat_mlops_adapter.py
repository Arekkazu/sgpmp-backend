# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-27 RF-60: adaptadores reales de politica M09  |
# | 2026-10-22 | Leandro | DEV-42 RF-60: consulta actividad valida y heartbeat real |
# | 2026-10-25 | Arekkazu | USAB-M03 M3-12 RF-60: firmware con prefijo v (v2.0.1) se compara como 2.0.1 |
# | 2026-10-26 | Arekkazu | FW-06 RF-60: firmware se compara con SemVer 2.0 (prerelease y +metadato) |
"""P-1 provisional: lectura dinámica DEV-14; ningún umbral se inventa al leer."""
import re

from sqlalchemy import text

from src.configuration.domain.entities.parametro_mlops import numero_configurado
from src.configuration.domain.entities.parametros_heartbeat import (
    BATERIA_AVISO, BATERIA_CRITICA, FIRMWARE, INACTIVIDAD, INTERVALO_CAMARA,
    INTERVALOS_TIPO, MARGEN, RSSI, SNR, TEMPERATURA_CRITICA,
    TEMPERATURA_MAXIMA, intervalos_configurados, validar_heartbeat_configurado,
)
from src.configuration.infrastructure.repositories.configuracion_global_repository import SqlAlchemyConfiguracionGlobalRepository
from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
from src.shared.db_error_translator import raise_from_db_error
from src.shared.errors import BusinessRuleError, NotFoundError, ServiceUnavailableError
from src.telemetry.domain.repositories.diagnostico_heartbeat_port import ComparacionFirmware, UmbralesTemperaturaDispositivo
from src.telemetry.domain.repositories.parametros_heartbeat_port import ParametrosComunicacionHeartbeat, ParametrosHeartbeat


class ParametrosHeartbeatMLOpsAdapter:
    def __init__(self, db):
        self.db = db
        self.parametros_repo = SqlAlchemyParametrosMLOpsRepository(db)
        self.configuracion_repo = SqlAlchemyConfiguracionGlobalRepository(db)

    def obtener(self):
        valores = self.parametros_repo.obtener((BATERIA_CRITICA, BATERIA_AVISO, RSSI, SNR))
        validar_heartbeat_configurado(valores)
        return ParametrosHeartbeat(
            numero_configurado(valores, BATERIA_CRITICA, minimo=0, maximo=100),
            numero_configurado(valores, BATERIA_AVISO, minimo=0, maximo=100),
            numero_configurado(valores, RSSI), numero_configurado(valores, SNR),
        )

    def obtener_comunicacion(self, id_dispositivo):
        try:
            dispositivo = self.db.execute(text('''
                SELECT t.categoria, d.id_infraestructura,
                  (SELECT max(h.fecha_recepcion) FROM modulo3.heartbeats h
                   WHERE h.id_dispositivo_iot=d.id_dispositivo_iot) AS ultimo_heartbeat,
                  (SELECT max(l.timestamp_procesamiento) FROM modulo3.telemetrias l
                   WHERE l.id_dispositivo_iot=d.id_dispositivo_iot
                     AND l.estado_calidad='LECTURA_VALIDA') AS ultima_telemetria,
                  (SELECT min(l.timestamp_procesamiento) FROM modulo3.telemetrias l
                   WHERE l.id_dispositivo_iot=d.id_dispositivo_iot
                     AND l.estado_calidad='LECTURA_VALIDA') AS primera_telemetria,
                  (SELECT h.estado_local_buffer::text FROM modulo3.heartbeats h
                   WHERE h.id_dispositivo_iot=d.id_dispositivo_iot
                   ORDER BY h.fecha_recepcion DESC,h.id_heartbeat DESC LIMIT 1) AS buffer
                FROM modulo9.dispositivos_iot d
                JOIN modulo9.tipos_dispositivo_iot t ON t.id_tipo_dispositivo=d.id_tipo_dispositivo
                WHERE d.id_dispositivo_iot=:id
            '''), {'id': id_dispositivo}).mappings().one_or_none()
        except Exception as exc:
            raise_from_db_error(exc)
        if dispositivo is None:
            raise NotFoundError('DISPOSITIVO_NO_ENCONTRADO', 'El dispositivo no existe en M09.')
        configuracion = self.configuracion_repo.obtener_activo()
        if configuracion is None:
            raise ServiceUnavailableError('CONFIGURACION_OPERATIVA_AUSENTE', 'No hay configuración RF-18 activa.')
        claves = (INTERVALO_CAMARA, MARGEN, INACTIVIDAD) if dispositivo['categoria'] == 'CAMARA' else (INTERVALOS_TIPO, MARGEN, INACTIVIDAD)
        valores = self.parametros_repo.obtener(claves)
        validar_heartbeat_configurado(valores, configuracion.frecuencia_muestreo.valor, configuracion.heartbeat.valor)
        if dispositivo['categoria'] == 'CAMARA':
            intervalo = numero_configurado(valores, INTERVALO_CAMARA, minimo=30, maximo=600, entero=True)
        else:
            intervalo = intervalos_configurados(valores).get(dispositivo['categoria'])
            if intervalo is None:
                raise ServiceUnavailableError('PARAMETRO_CONFIGURACION_AUSENTE', 'No está configurado el intervalo del tipo de dispositivo.')
        return ParametrosComunicacionHeartbeat(
            intervalo, configuracion.frecuencia_muestreo.valor * 60,
            numero_configurado(valores, MARGEN, entero=True, positivo=True),
            numero_configurado(valores, INACTIVIDAD, entero=True, positivo=True),
            dispositivo['buffer'],
            dispositivo['ultima_telemetria'], dispositivo['ultimo_heartbeat'],
            dispositivo['primera_telemetria'], dispositivo['id_infraestructura'],
        )


# FW-06 (acordado con Edge el 2026-10-25): SemVer 2.0 con "v" opcional; el
# metadato "+..." no cuenta al comparar. Se mantienen núcleos cortos (1.0).
_SEMVER = re.compile(r'[vV]?([0-9]+(?:\.[0-9]+)*)'
                     r'(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?'
                     r'(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?')


def _semver(version):
    """(núcleo, prerelease) o None si la cadena no sigue FW-06."""
    coincidencia = _SEMVER.fullmatch(version) if isinstance(version, str) else None
    if coincidencia is None:
        return None
    nucleo, prerelease = coincidencia.groups()
    # SemVer §11: los identificadores numéricos se comparan por valor y van antes que los alfanuméricos.
    identificadores = tuple((0, int(i), '') if i.isdigit() else (1, 0, i)
                            for i in prerelease.split('.')) if prerelease else None
    return tuple(int(parte) for parte in nucleo.split('.')), identificadores


def _clave_semver(nucleo, prerelease, ancho):
    # Sin prerelease va después de cualquier prerelease del mismo núcleo (1.0.0-rc.1 < 1.0.0).
    return nucleo + (0,) * (ancho - len(nucleo)), prerelease is None, prerelease or ()


class DiagnosticoHeartbeatMLOpsAdapter:
    def __init__(self, db):
        self.parametros_repo = SqlAlchemyParametrosMLOpsRepository(db)

    def obtener_umbrales_temperatura(self, id_dispositivo):
        valores = self.parametros_repo.obtener((TEMPERATURA_MAXIMA, TEMPERATURA_CRITICA))
        validar_heartbeat_configurado(valores)
        return UmbralesTemperaturaDispositivo(
            numero_configurado(valores, TEMPERATURA_MAXIMA),
            numero_configurado(valores, TEMPERATURA_CRITICA),
        )

    def comparar_firmware(self, id_dispositivo, version_instalada):
        valores = self.parametros_repo.obtener((FIRMWARE,))
        if FIRMWARE not in valores:
            raise ServiceUnavailableError('PARAMETRO_CONFIGURACION_AUSENTE', 'No se ha configurado la versión mínima de firmware.')
        validar_heartbeat_configurado(valores)
        minima = valores[FIRMWARE].valor.strip()
        if version_instalada == minima:
            return ComparacionFirmware(minima, False)
        # Nunca orden lexicográfico: lo que no sigue FW-06 no se compara.
        partes = [_semver(version) for version in (minima, version_instalada)]
        if None in partes:
            raise BusinessRuleError('VERSION_FIRMWARE_NO_COMPARABLE',
                                    'La versión de firmware requiere una convención de comparación compatible.')
        ancho = max(len(nucleo) for nucleo, _ in partes)
        requerida, instalada = (_clave_semver(nucleo, prerelease, ancho) for nucleo, prerelease in partes)
        return ComparacionFirmware(minima, instalada < requerida)
