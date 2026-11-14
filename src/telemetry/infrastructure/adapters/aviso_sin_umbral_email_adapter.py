# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-39 RF-58: vista por permiso, GRIS sin umbral y anomalías visibles |
"""Aviso de RF-58 E7 al Administrador: una variable recibe datos sin umbral en M09.

- Canal: correo de RF-14 (``send_email`` + plantilla común, sin reintentos), como los
  avisos de M04 (DEV-48). No hay un ``tipo_evento`` de RF-14 para este caso y crearlo
  pide migración; por eso no se usa la bandeja interna.
- Destinatarios: los Administradores (rol protegido, el mismo criterio de
  ``AvisoIntegridadM01Adapter``), leídos con la identidad de servicio porque
  ``modulo1`` tiene RLS forzada y quien mira el dashboard puede ser un Productor.
- Sin repetición: el aviso de un sensor queda en la bitácora de RF-63
  (``VARIABLE_SIN_UMBRAL``) y no se repite en 24 h, aunque el dashboard se refresque.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.database import CORREO_USUARIO_SERVICIO, como_sistema
from src.shared.email import send_email
from src.shared.plantilla_correo import renderizar_correo
from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import (
    RegistrarEventoAuditoriaIotUseCase,
)
from src.telemetry.domain.entities.evento_auditoria_iot import (
    ComponenteOrigen,
    EntidadAfectadaTipo,
    SeveridadLog,
    TipoResultado,
)
from src.telemetry.domain.entities.monitoreo import EstadoSensorActual
from src.telemetry.domain.repositories.aviso_sin_umbral_port import AvisoSinUmbralPort
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import (
    SqlAlchemyBitacoraAuditoriaIotRepository,
)

logger = logging.getLogger(__name__)

TIPO_EVENTO = 'VARIABLE_SIN_UMBRAL'
_INTENTOS_EMAIL = 1  # RF-14: sin reintentos

_SQL_YA_AVISADOS = text(
    "SELECT DISTINCT entidad_afectada_id FROM modulo3.bitacora_auditoria_iot "
    "WHERE tipo_evento = :tipo AND fecha_hora > now() - interval '24 hours' "
    "AND entidad_afectada_id = ANY(:ids)"
)
_SQL_ADMINISTRADORES = text(
    "SELECT DISTINCT u.id_usuario, u.nombre, u.apellidos, u.correo_electronico "
    "FROM modulo1.usuarios u "
    "JOIN modulo1.cuentas_usuarios c ON c.id_usuario = u.id_usuario "
    "JOIN modulo1.estados_cuentas e ON e.id_estado_cuenta = c.id_estado_cuenta "
    "WHERE modulo1.fn_rol_protegido(u.id_rol) AND lower(e.nombre) = 'activo' "
    "AND u.correo_electronico <> :correo_servicio "
    "ORDER BY u.id_usuario"
)


class AvisoSinUmbralEmailAdapter(AvisoSinUmbralPort):
    def __init__(self, db: Session) -> None:
        self.db = db

    def avisar(self, sensores: list[EstadoSensorActual]) -> int:
        try:
            pendientes = self._sin_avisar(sensores)
            if not pendientes:
                return 0
            with como_sistema(self.db):
                admins = self.db.execute(
                    _SQL_ADMINISTRADORES, {'correo_servicio': CORREO_USUARIO_SERVICIO}
                ).fetchall()
            auditoria = RegistrarEventoAuditoriaIotUseCase(self.db, SqlAlchemyBitacoraAuditoriaIotRepository(self.db))
            for sensor in pendientes:
                auditoria.execute(
                    tipo_evento=TIPO_EVENTO,
                    resultado=TipoResultado.ADVERTENCIA,
                    componente_origen=ComponenteOrigen.RF58,
                    severidad_log=SeveridadLog.WARNING,
                    descripcion=f'La variable {sensor.tipo_variable} del sensor {sensor.nombre_sensor} '
                                'recibe datos sin umbral configurado.',
                    entidad_afectada_tipo=EntidadAfectadaTipo.UMBRAL,
                    entidad_afectada_id=str(sensor.id_sensor),
                    accion_detallada={
                        'id_sensor': sensor.id_sensor,
                        'tipo_variable': sensor.tipo_variable,
                        'id_infraestructura': sensor.id_infraestructura,
                        'infraestructura': sensor.nombre_infraestructura,
                        'finca': sensor.nombre_finca,
                        'administradores_avisados': len(admins),
                    },
                )
                for admin in admins:
                    self._enviar(admin, sensor)
            return len(pendientes)
        except Exception:  # best-effort: el dashboard es una lectura
            self.db.rollback()
            logger.exception('RF-58 E7: no se pudo avisar de las variables sin umbral')
            return 0

    def _sin_avisar(self, sensores: list[EstadoSensorActual]) -> list[EstadoSensorActual]:
        ids = [str(s.id_sensor) for s in sensores]
        avisados = set(self.db.execute(_SQL_YA_AVISADOS, {'tipo': TIPO_EVENTO, 'ids': ids}).scalars())
        return [s for s in sensores if str(s.id_sensor) not in avisados]

    @staticmethod
    def _enviar(admin, sensor: EstadoSensorActual) -> None:
        if not admin.correo_electronico:
            return
        nombre: Optional[str] = f'{admin.nombre or ""} {admin.apellidos or ""}'.strip() or None
        html = renderizar_correo(
            titulo='Una variable monitoreada no tiene umbral configurado',
            nombre=nombre,
            parrafos=[
                'El dashboard de monitoreo muestra esta variable en GRIS, con la etiqueta '
                '"Sin umbral configurado": recibe datos, pero ninguna especie del área tiene '
                'rangos operativos para ella en M09.',
                'Configure el umbral ambiental de la variable para las especies del área.',
            ],
            evento='Variable sin umbral configurado',
            tono='atencion',
            detalles=[
                ('Variable', sensor.tipo_variable),
                ('Sensor', sensor.nombre_sensor),
                ('Área', sensor.nombre_infraestructura or '—'),
                ('Finca', sensor.nombre_finca or '—'),
            ],
        )
        try:
            send_email(to=admin.correo_electronico, subject=f'Variable sin umbral: {sensor.tipo_variable}',
                       html_body=html, intentos=_INTENTOS_EMAIL)
        except Exception as exc:  # best-effort
            logger.warning('RF-58 E7: no se pudo enviar el aviso a %s: %s', admin.correo_electronico, exc)
