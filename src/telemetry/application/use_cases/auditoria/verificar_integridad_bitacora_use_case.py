# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-47 RF-63: incidentes inmutables idempotentes y avisos recuperables |
"""E6: el marcador de compromiso es externo al registro protegido por DB-11."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from dataclasses import replace
import logging
from typing import Optional

from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import _calcular_hash
from src.telemetry.application.use_cases.auditoria.evidencia_iot import registrar_evidencia
from src.telemetry.domain.entities.evento_auditoria_iot import SeveridadLog, TipoResultado
from src.telemetry.domain.repositories.aviso_integridad_port import AvisoIntegridadPort

logger = logging.getLogger(__name__)


@dataclass
class ResultadoVerificacion:
    total_verificados: int
    comprometidos: int
    ids_comprometidos: list[str]
    ids_sin_hash: list[str] = field(default_factory=list)
    ids_incompletos: list[str] = field(default_factory=list)
    incidentes_creados: int = 0
    notificaciones_pendientes: int = 0


def hash_coincide(evento):
    # TIMESTAMPTZ conserva el instante, no el offset original. Los productores
    # HTTP usan UTC; SQL puede devolver la zona de la sesión.
    return evento.hash_integridad in {
        _calcular_hash(evento),
        _calcular_hash(replace(evento, fecha_hora=evento.fecha_hora.astimezone(timezone.utc))),
    }


class VerificarIntegridadBitacoraUseCase:
    def __init__(self, db, auditoria_repo, avisos: Optional[AvisoIntegridadPort] = None):
        self.db, self.auditoria_repo, self.avisos = db, auditoria_repo, avisos

    def execute(self, fecha_desde: Optional[datetime] = None, fecha_hasta: Optional[datetime] = None):
        eventos = self.auditoria_repo.listar_todos_para_verificacion(fecha_desde, fecha_hasta)
        resultado = ResultadoVerificacion(len(eventos), 0, [])
        for evento in sorted(eventos, key=lambda e: str(e.id_evento)):
            identificador = str(evento.id_evento)
            if evento.registro_incompleto:
                resultado.ids_incompletos.append(identificador)
            if not evento.hash_integridad:
                resultado.ids_sin_hash.append(identificador)
                continue
            if hash_coincide(evento):
                continue
            self.auditoria_repo.bloquear_integridad(evento.id_evento)
            # La evidencia es append-only; confirmar nuevamente dentro del lock.
            actual = self.auditoria_repo.obtener(evento.id_evento)
            esperado = _calcular_hash(replace(actual, fecha_hora=actual.fecha_hora.astimezone(timezone.utc)))
            if hash_coincide(actual):
                continue
            clave = {'id_evento': identificador, 'hash_almacenado': actual.hash_integridad,
                     'hash_calculado': esperado}
            incidente = self.auditoria_repo.buscar_incidente(clave)
            if incidente is None:
                try:
                    incidente = registrar_evidencia(self.auditoria_repo, 'INTEGRIDAD_COMPROMETIDA', None,
                        resultado=TipoResultado.FALLIDO, severidad=SeveridadLog.CRITICAL,
                        descripcion='Hash de auditoría IoT alterado; evidencia original preservada.',
                        detalle={'compromiso': clave, 'estado_integridad': 'COMPROMETIDO',
                                 'notificacion': 'PENDIENTE'})
                    self.db.commit()
                    resultado.incidentes_creados += 1
                except Exception:
                    self.db.rollback()
                    raise
            resultado.ids_comprometidos.append(identificador)
            # El incidente ya está confirmado: una falla de RF-14 no lo revierte.
            if not self._notificar(incidente, identificador):
                resultado.notificaciones_pendientes += 1
        resultado.comprometidos = len(resultado.ids_comprometidos)
        return resultado

    def _notificar(self, incidente, identificador):
        try:
            self.auditoria_repo.bloquear_integridad(incidente.id_evento)
            if self.auditoria_repo.aviso_confirmado(incidente.id_evento):
                self.db.commit()
                return True
            if self.avisos is None:
                self.db.rollback()
                return False
            cantidad = self.avisos.notificar(str(incidente.id_evento), [identificador])
            if cantidad <= 0:
                self.db.rollback()
                return False
            registrar_evidencia(self.auditoria_repo, 'INTEGRIDAD_COMPROMETIDA', None,
                detalle={'aviso_incidente': str(incidente.id_evento),
                         'notificacion': 'REGISTRADA_RF14', 'destinatarios': cantidad})
            self.db.commit()
            return True
        except Exception as exc:
            self.db.rollback()
            logger.warning('RF-63: aviso pendiente incidente=%s error=%s',
                           incidente.id_evento, getattr(exc, 'code', type(exc).__name__))
            return False
