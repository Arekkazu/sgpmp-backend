# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-21 | Arekkazu | DEV-32 RF-57: notificación de alertas, tormenta (E8), contexto incompleto (E6) y fallos con reintento (E7) |
# | 2026-10-28 | destroyerban | INC-M03-170-G77 RF-57 E6: el aviso de contexto incompleto no se pierde por anti-spam; uno por sensor cada 24 h |
"""Caso de uso: notificar las alertas nuevas (RF-57 Fase 8, E6, E7, E8).

Corre cada pocos segundos fuera del request del broker:

1. Toma las alertas operativas sin notificar y las marca (``fecha_notificacion``).
2. **E8 tormenta:** si en el último minuto se generaron más alertas que el umbral del
   sistema o de una unidad productiva, CRITICO se sigue notificando una por una y
   LEVE/MODERADO se agrupan en un resumen por destinatario; además se crea una sola
   alerta ``TORMENTA_DE_ALERTAS`` para el Administrador por ventana de 10 minutos.
3. **Destinatarios:** usuarios de la finca del área con permiso de lectura sobre
   ``alertas_operativas`` (por permisos, sin roles quemados).
4. **E6:** una alerta sin contexto de activo avisa al Administrador para que complete
   la asociación del sensor (RF-22).
5. **E7:** un correo que no sale queda ``fallido`` y en la bitácora RF-63 como
   ``NOTIFICACION_FALLIDA``; se reintenta con backoff en las siguientes vueltas.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import (
    RegistrarEventoAuditoriaIotUseCase,
)
from src.telemetry.domain.entities.alerta import (
    Alerta,
    EstadoAlerta,
    OrigenEventoAlerta,
    SeveridadAlerta,
    TipoAlerta,
)
from src.telemetry.domain.entities.evento_auditoria_iot import (
    ComponenteOrigen,
    EntidadAfectadaTipo,
    SeveridadLog,
    TipoResultado,
)
from src.telemetry.domain.repositories.alerta_repository import AlertaRepository
from src.telemetry.domain.repositories.bitacora_auditoria_iot_repository import BitacoraAuditoriaIotRepository
from src.telemetry.domain.repositories.notificacion_alerta_port import NotificacionAlertaPort
from src.telemetry.domain.repositories.parametros_alertas_port import ParametrosAlertasPort

logger = logging.getLogger(__name__)

VENTANA_TORMENTA = timedelta(minutes=1)
REPOSO_TORMENTA = timedelta(minutes=10)  # una alerta de tormenta por ventana, no una por vuelta
# G77 (E6): un aviso por sensor sin asociación cada 24 h; el RF no fija la frecuencia.
VENTANA_AVISO_CONTEXTO = timedelta(hours=24)


def _titulo(alerta: Alerta) -> str:
    return f"Alerta {alerta.severidad}: {alerta.tipo_alerta.replace('_', ' ').lower()}"


def _cuerpo(alerta: Alerta) -> str:
    valor = f" Valor {alerta.valor} {alerta.unidad or ''}." if alerta.valor is not None else ""
    area = f" Área {alerta.id_infraestructura}." if alerta.id_infraestructura else ""
    return f"{_titulo(alerta)} en {alerta.tipo_variable}.{valor}{area} Alerta #{alerta.id_alerta}."


class NotificarAlertasUseCase:

    def __init__(
        self,
        db: Session,
        alerta_repo: AlertaRepository,
        notificacion_port: NotificacionAlertaPort,
        parametros_port: ParametrosAlertasPort,
        auditoria_repo: BitacoraAuditoriaIotRepository,
    ) -> None:
        self.db = db
        self.alerta_repo = alerta_repo
        self.notificacion = notificacion_port
        self.parametros = parametros_port
        self.auditoria = RegistrarEventoAuditoriaIotUseCase(db, auditoria_repo)

    def execute(self, ahora: Optional[datetime] = None) -> int:
        """Devuelve cuántas alertas se procesaron."""
        ahora = ahora or datetime.now(timezone.utc)
        try:
            pendientes = self.alerta_repo.reclamar_pendientes_notificacion(ahora)
            tormenta = self._crear_tormenta_si_aplica(ahora) if pendientes else None
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        if tormenta is not None:
            self._a_administradores(tormenta, _titulo(tormenta), self._cuerpo_tormenta(tormenta), agrupable=False)

        agrupadas: dict[int, list[Alerta]] = defaultdict(list)
        sensores_avisados: set[int] = set()
        for alerta in pendientes:
            if alerta.tipo_alerta == TipoAlerta.TORMENTA_DE_ALERTAS.value:
                continue
            critica = alerta.severidad == SeveridadAlerta.CRITICO.value
            for id_usuario in self.notificacion.destinatarios(alerta.id_infraestructura, escalamiento=False):
                if tormenta is not None and not critica:
                    agrupadas[id_usuario].append(alerta)
                else:
                    self._enviar(id_usuario, alerta, _titulo(alerta), _cuerpo(alerta), agrupable=not critica)
            if alerta.tiene_contexto_incompleto and self._avisar_contexto(alerta, ahora, sensores_avisados):
                # G77: sin anti-spam. El anti-spam es por tipo de evento (32) y una notificación de otra
                # alerta en los últimos 5 min descartaba este aviso en silencio.
                self._a_administradores(
                    alerta, "Alerta sin contexto de activo biológico",
                    f"La alerta #{alerta.id_alerta} ({alerta.tipo_variable}) se generó sin activo asociado. "
                    f"Complete la asociación del sensor {alerta.id_sensor} a su unidad productiva (RF-22).",
                    agrupable=False,
                )

        for id_usuario, alertas in agrupadas.items():
            resumen = ", ".join(f"#{a.id_alerta} {a.severidad}" for a in alertas[:20])
            self._enviar(id_usuario, alertas[0], f"Resumen de {len(alertas)} alertas",
                         f"Tormenta de alertas: {len(alertas)} alertas LEVE/MODERADO agrupadas ({resumen}).",
                         agrupable=False)

        self.notificacion.reintentar_fallidas(ahora)
        return len(pendientes)

    def _avisar_contexto(self, alerta: Alerta, ahora: datetime, sensores_avisados: set[int]) -> bool:
        """Un aviso por sensor: ni dos en la misma vuelta ni otro si ya se avisó en las últimas 24 h."""
        if alerta.id_sensor is None:
            return True
        if alerta.id_sensor in sensores_avisados:
            return False
        sensores_avisados.add(alerta.id_sensor)
        return not self.alerta_repo.contexto_incompleto_avisado_desde(
            alerta.id_sensor, ahora - VENTANA_AVISO_CONTEXTO, ahora)

    def _crear_tormenta_si_aplica(self, ahora: datetime) -> Optional[Alerta]:
        umbrales = self.parametros.obtener_umbrales_tormenta()
        if umbrales is None:
            return None
        umbral_sistema, umbral_unidad = umbrales
        total, por_area = self.alerta_repo.contar_generadas_desde(ahora - VENTANA_TORMENTA)
        areas = sorted(area for area, n in por_area.items() if n > umbral_unidad)
        if total <= umbral_sistema and not areas:
            return None
        if self.alerta_repo.existe_tormenta_desde(ahora - REPOSO_TORMENTA):
            # Ya se avisó en esta ventana: se sigue agrupando, sin otra alerta de tormenta.
            return Alerta(tipo_alerta=TipoAlerta.TORMENTA_DE_ALERTAS.value, severidad=SeveridadAlerta.MODERADO.value,
                          estado_alerta=EstadoAlerta.ACTIVA.value, origen_evento=OrigenEventoAlerta.BACKEND.value,
                          tipo_variable=TipoAlerta.TORMENTA_DE_ALERTAS.value, fecha_evento=ahora, fecha_generacion=ahora,
                          metadato_evento={"ya_notificada": True})
        tormenta = Alerta(
            tipo_alerta=TipoAlerta.TORMENTA_DE_ALERTAS.value,
            severidad=SeveridadAlerta.MODERADO.value,
            estado_alerta=EstadoAlerta.ACTIVA.value,
            origen_evento=OrigenEventoAlerta.BACKEND.value,
            tipo_variable=TipoAlerta.TORMENTA_DE_ALERTAS.value,
            fecha_evento=ahora,
            fecha_generacion=ahora,
            metadato_evento={"alertas_ultimo_minuto": total, "areas_sobre_umbral": areas,
                             "umbral_sistema": umbral_sistema, "umbral_unidad": umbral_unidad},
        )
        tormenta.fecha_vencimiento = tormenta.calcular_fecha_vencimiento()
        return self.alerta_repo.guardar(tormenta)

    @staticmethod
    def _cuerpo_tormenta(tormenta: Alerta) -> str:
        meta = tormenta.metadato_evento or {}
        return (f"Tormenta de alertas: {meta.get('alertas_ultimo_minuto')} alertas en el último minuto "
                f"(áreas sobre el umbral: {meta.get('areas_sobre_umbral') or 'ninguna'}). Las alertas LEVE y "
                "MODERADO se notifican agrupadas; las CRITICO, una por una.")

    def _a_administradores(self, alerta: Alerta, titulo: str, cuerpo: str, *, agrupable: bool) -> None:
        if (alerta.metadato_evento or {}).get("ya_notificada"):
            return
        for id_usuario in self.notificacion.administradores():
            self._enviar(id_usuario, alerta, titulo, cuerpo, agrupable=agrupable)

    def _enviar(self, id_usuario: int, alerta: Alerta, titulo: str, cuerpo: str, *, agrupable: bool) -> None:
        if self.notificacion.enviar(id_usuario, titulo, cuerpo, agrupable=agrupable) is False:
            self.auditoria.execute(
                tipo_evento="NOTIFICACION_FALLIDA",
                resultado=TipoResultado.FALLIDO,
                componente_origen=ComponenteOrigen.RF57,
                severidad_log=SeveridadLog.ERROR,
                descripcion="No se pudo entregar la notificación de la alerta; se reintenta con backoff.",
                entidad_afectada_tipo=EntidadAfectadaTipo.ALERTA,
                entidad_afectada_id=str(alerta.id_alerta) if alerta.id_alerta else None,
                accion_detallada={"id_usuario_destinatario": id_usuario, "titulo": titulo},
            )
