# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | INC-M04-152-G083 RF-70/73: emite HASH_INVALIDO_DETECTADO |
# | 2026-10-27 | Leandro | INC-M04-158-G086 RF-73: conservar los minimos auditables del reporte de integridad OTA. |
"""Reporte de un nodo durante la OTA (DEV-15, RF-70/RF-73, D6 paso 5).

El broker reenvía cada ``ota/<evento>`` del nodo (BRK-08) con su token de servicio.
Cada evento actualiza el despliegue y, cuando corresponde, emite el evento RF-73:

| evento del nodo    | despliegue                                  | evento RF-73              |
|--------------------|---------------------------------------------|---------------------------|
| status             | EN_PROCESO; o PENDIENTE si ``pospuesto``    | DISTRIBUCION_POSPUESTA (si pospuesto) |
| download_progress  | EN_PROCESO, bytes descargados e intentos    | —                         |
| integrity_ok       | EN_PROCESO, hash válido                     | MODELO_DISTRIBUIDO_EDGE   |
| activated          | EXITOSO                                     | MODELO_ACTIVADO_EDGE      |
| rollback           | FALLIDO, rollback ejecutado                 | DISTRIBUCION_FALLIDA      |
| critical_failure   | FALLIDO                                     | DISTRIBUCION_FALLIDA      |

Si la falla trae ``detalle.causa`` HASH_INVALIDO o FIRMA_INVALIDA se registra
además HASH_INVALIDO_DETECTADO (RF-70 Fase 5 y E4), con su payload mínimo de RF-73.

Rollout: cuando el último nodo de la fase activa, la distribución pasa a la
siguiente fase y se avisa a sus nodos; sin más fases queda COMPLETADA. Un
``rollback`` o un ``critical_failure`` la DETIENEN: los nodos de las fases
siguientes no reciben el aviso.

Un reporte sobre un despliegue ya terminado no cambia nada (el nodo puede
repetir mensajes por QoS 1).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from sqlalchemy.orm import Session

from src.prediction.application.use_cases.ota._aviso_fase import avisar_despliegues
from src.prediction.domain.entities.despliegue_ota import DespliegueOta
from src.prediction.domain.entities.distribucion_ota import siguiente_fase
from src.prediction.domain.repositories.despliegue_ota_repository import DespliegueOtaRepository
from src.prediction.domain.repositories.distribucion_ota_repository import DistribucionOtaRepository
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.ota_edge_port import AvisoOtaPort, NodoOtaPort, UrlDescargaPort
from src.prediction.domain.repositories.version_modelo_repository import VersionModeloRepository
from src.prediction.infrastructure.dto.ota_dto import ReporteOtaDTO
from src.shared.errors import AuthorizationError, BusinessRuleError, NotFoundError

EVENTO_DISTRIBUIDO = "MODELO_DISTRIBUIDO_EDGE"
EVENTO_ACTIVADO = "MODELO_ACTIVADO_EDGE"
EVENTO_FALLIDA = "DISTRIBUCION_FALLIDA"
EVENTO_POSPUESTA = "DISTRIBUCION_POSPUESTA"
EVENTO_HASH_INVALIDO = "HASH_INVALIDO_DETECTADO"


@dataclass
class ResultadoReporteOta:
    despliegue: DespliegueOta
    evento_rf73: Optional[str]
    sin_cambios: bool = False
    fase_avanzada_a: Optional[str] = None


def _hash_invalido(dto: ReporteOtaDTO) -> bool:
    return dto.evento in ("rollback", "critical_failure") and str(
        dto.detalle.get("causa", "")).upper() in ("HASH_INVALIDO", "FIRMA_INVALIDA")


def _entero(valor: Any) -> Optional[int]:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def _decimal(valor: Any) -> Optional[Decimal]:
    if isinstance(valor, bool) or valor is None:
        return None
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return None


class RegistrarReporteOtaUseCase:

    def __init__(
        self,
        *,
        db: Session,
        despliegue_repo: DespliegueOtaRepository,
        distribucion_repo: DistribucionOtaRepository,
        version_repo: VersionModeloRepository,
        auditoria_repo: EventoAuditoriaM04Repository,
        nodo_port: NodoOtaPort,
        aviso_port: AvisoOtaPort,
        url_port: UrlDescargaPort,
    ) -> None:
        self._db = db
        self._despliegue_repo = despliegue_repo
        self._distribucion_repo = distribucion_repo
        self._version_repo = version_repo
        self._auditoria_repo = auditoria_repo
        self._nodo_port = nodo_port
        self._aviso_port = aviso_port
        self._url_port = url_port

    def execute(self, dto: ReporteOtaDTO) -> ResultadoReporteOta:
        ahora = datetime.now(timezone.utc)
        try:
            despliegue = self._despliegue_repo.obtener_por_id(dto.id_despliegue_ota, bloquear=True)
            if despliegue is None:
                raise NotFoundError(
                    code="DESPLIEGUE_OTA_NO_ENCONTRADO",
                    message=f"No existe el despliegue OTA {dto.id_despliegue_ota}.",
                )
            serial = self._nodo_port.obtener_seriales([despliegue.id_dispositivo_iot]).get(despliegue.id_dispositivo_iot)
            if serial != dto.serial:
                # Un nodo no puede reportar por el despliegue de otro.
                raise AuthorizationError(
                    code="DESPLIEGUE_OTA_DE_OTRO_NODO",
                    message="El despliegue OTA no corresponde al nodo que reporta.",
                )
            if dto.componente and despliegue.componente and dto.componente != despliegue.componente:
                raise BusinessRuleError(
                    code="COMPONENTE_OTA_INCORRECTO",
                    message=f"El despliegue es del componente {despliegue.componente}, no de {dto.componente}.",
                    field="componente",
                )
            if despliegue.esta_terminado:
                self._db.rollback()  # libera el bloqueo; no hubo cambios
                return ResultadoReporteOta(despliegue=despliegue, evento_rf73=None, sin_cambios=True)

            evento, severidad, resultado_op = self._aplicar(despliegue, dto, ahora)
            despliegue = self._despliegue_repo.actualizar(despliegue)
            if evento is not None:
                self._auditoria_repo.registrar(
                    tipo_evento=evento,
                    tipo_actor="DISPOSITIVO_EDGE",
                    id_sistema=dto.serial,
                    id_referencia=str(despliegue.id_despliegue_ota),
                    entidad_referencia="despliegue_ota",
                    severidad_evento=severidad,
                    resultado_operacion=resultado_op,
                    payload_evento={
                        "device_id": despliegue.id_dispositivo_iot,
                        "id_version": despliegue.id_version_modelo,
                        "hash_verificado": despliegue.resultado_validacion_hash,
                        "id_despliegue_ota": despliegue.id_despliegue_ota,
                        "id_distribucion_ota": despliegue.id_distribucion_ota,
                        "id_version_modelo": despliegue.id_version_modelo,
                        "id_version_modelo_anterior": despliegue.id_version_modelo_anterior,
                        "tipo_modelo": despliegue.tipo_modelo,
                        "componente": despliegue.componente,
                        "serial": dto.serial,
                        "fase_rollout": despliegue.fase_rollout,
                        "evento_nodo": dto.evento,
                        "estado_despliegue": despliegue.estado_despliegue,
                        "motivo": despliegue.motivo_fallo,
                        "detalle": dto.detalle,
                    },
                )
            if _hash_invalido(dto):
                self._auditoria_repo.registrar(
                    tipo_evento=EVENTO_HASH_INVALIDO,
                    tipo_actor="DISPOSITIVO_EDGE",
                    id_sistema=dto.serial,
                    id_referencia=str(despliegue.id_despliegue_ota),
                    entidad_referencia="despliegue_ota",
                    severidad_evento="CRITICAL",
                    resultado_operacion="FALLIDO",
                    codigo_error="HASH_MISMATCH",
                    payload_evento={
                        "device_id": despliegue.id_dispositivo_iot,
                        "tipo_modelo": despliegue.tipo_modelo,
                        "id_version": despliegue.id_version_modelo,
                        "hash_esperado": despliegue.hash_modelo_sha256,
                        "hash_recibido": dto.detalle.get("hash_recibido") or dto.detalle.get("hash_calculado"),
                        "id_despliegue_ota": despliegue.id_despliegue_ota,
                        "evento_nodo": dto.evento,
                    },
                )
            distribucion = None
            if despliegue.id_distribucion_ota is not None and despliegue.esta_terminado:
                distribucion = self._distribucion_repo.obtener_por_id(despliegue.id_distribucion_ota, bloquear=True)
                if distribucion is not None and distribucion.esta_en_curso:
                    if despliegue.estado_despliegue == "FALLIDO":
                        distribucion.detener(ahora)
                        distribucion = self._distribucion_repo.actualizar(distribucion)
                        distribucion = None  # detenida: no se avisa a nadie más
                    else:
                        distribucion = self._avanzar_si_fase_completa(distribucion, ahora)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        fase_nueva = None
        if distribucion is not None and distribucion.esta_en_curso and distribucion.fase_rollout != despliegue.fase_rollout:
            fase_nueva = distribucion.fase_rollout
            try:
                avisar_despliegues(
                    despliegues=self._despliegue_repo.listar_por_distribucion(distribucion.id_distribucion_ota, fase_nueva),
                    distribucion=distribucion,
                    version=self._version_repo.obtener_por_id(distribucion.id_version_modelo),
                    despliegue_repo=self._despliegue_repo, nodo_port=self._nodo_port,
                    aviso_port=self._aviso_port, url_port=self._url_port, ahora=ahora,
                )
                self._db.commit()
            except Exception:
                self._db.rollback()
                raise
        return ResultadoReporteOta(despliegue=despliegue, evento_rf73=evento, fase_avanzada_a=fase_nueva)

    @staticmethod
    def _aplicar(despliegue: DespliegueOta, dto: ReporteOtaDTO, ahora: datetime) -> tuple[Optional[str], str, str]:
        """Aplica el reporte al despliegue. Devuelve (evento RF-73, severidad, resultado)."""
        d = dto.detalle
        motivo = str(d.get("motivo") or d.get("mensaje") or "")
        if dto.evento == "status":
            if d.get("pospuesto") is True or str(d.get("estado", "")).upper() == "POSPUESTO":
                despliegue.posponer(motivo or "El nodo pospuso la instalación.")
                return EVENTO_POSPUESTA, "WARNING", "PARCIAL"
            despliegue.registrar_avance(nivel_bateria=_decimal(d.get("nivel_bateria")))
            return None, "INFO", "EXITOSO"
        if dto.evento == "download_progress":
            despliegue.registrar_avance(
                tamano_descargado_bytes=_entero(d.get("bytes_descargados")),
                intentos_descarga=_entero(d.get("intento")),
                nivel_bateria=_decimal(d.get("nivel_bateria")),
            )
            return None, "INFO", "EXITOSO"
        if dto.evento == "integrity_ok":
            despliegue.marcar_integridad_valida()
            return EVENTO_DISTRIBUIDO, "INFO", "EXITOSO"
        if dto.evento == "activated":
            despliegue.activar(ahora, _entero(d.get("duracion_proceso_ms")))
            return EVENTO_ACTIVADO, "INFO", "EXITOSO"
        if dto.evento == "rollback":
            despliegue.fallar(ahora, motivo or "El nodo revirtió a la versión anterior.", rollback=True,
                              hash_invalido=_hash_invalido(dto))
            return EVENTO_FALLIDA, "ERROR", "FALLIDO"
        # critical_failure
        despliegue.fallar(ahora, motivo or "Falla crítica del nodo durante la OTA.", rollback=False,
                          hash_invalido=_hash_invalido(dto))
        return EVENTO_FALLIDA, "CRITICAL", "FALLIDO"

    def _avanzar_si_fase_completa(self, distribucion, ahora):
        """Si todos los nodos de la fase actual activaron, pasa a la siguiente con nodos."""
        de_la_fase = self._despliegue_repo.listar_por_distribucion(
            distribucion.id_distribucion_ota, distribucion.fase_rollout
        )
        if any(d.estado_despliegue != "EXITOSO" for d in de_la_fase):
            return distribucion
        fase = siguiente_fase(distribucion.fase_rollout)
        while fase is not None and not self._despliegue_repo.listar_por_distribucion(distribucion.id_distribucion_ota, fase):
            fase = siguiente_fase(fase)
        distribucion.avanzar_a(fase, ahora)
        return self._distribucion_repo.actualizar(distribucion)
