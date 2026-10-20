"""Crear una distribución OTA de un componente a varios nodos (DEV-15, RF-70, D6 de AIOT-DEV-03).

1. Valida la versión: debe estar ACTIVO y tener artefacto con SHA-256.
   AN-2 (¿ACTIVO o APROBADO?) no está definido; se distribuye solo ACTIVO porque
   ``trg_predicciones_version_modelo_activo`` rechaza (P0413) las predicciones de
   una versión que no lo está.
2. Valida los nodos: existen, están activos y no tienen otro despliegue vigente
   del mismo (tipo_modelo, componente) (regla de DB-04). Un nodo con DETECTOR v3 en
   curso sí puede recibir ANOMALIAS (D-05).
3. Crea la distribución y una fila PENDIENTE en ``despliegues_ota`` por nodo, con
   su fase del rollout (canary, parcial 20–30 %, total) y la versión que el nodo
   tiene instalada de ese componente (``id_version_modelo_anterior``).
4. Después del commit avisa ``ota/notify`` (BRK-08) solo a la fase CANARY, con la
   URL firmada y temporal, el SHA-256 y la firma del artefacto.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.prediction.application.use_cases.ota._aviso_fase import avisar_despliegues
from src.prediction.domain.entities.despliegue_ota import DespliegueOta
from src.prediction.domain.entities.distribucion_ota import FASE_CANARY, DistribucionOta, planificar_fases
from src.prediction.domain.repositories.despliegue_ota_repository import DespliegueOtaRepository
from src.prediction.domain.repositories.distribucion_ota_repository import DistribucionOtaRepository
from src.prediction.domain.repositories.ota_edge_port import AvisoOtaPort, NodoOtaPort, UrlDescargaPort
from src.prediction.domain.repositories.version_modelo_repository import VersionModeloRepository
from src.prediction.infrastructure.dto.ota_dto import CrearDistribucionOtaDTO
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, ServiceUnavailableError

ESTADO_VERSION_DISTRIBUIBLE = "ACTIVO"


@dataclass
class ResultadoDistribucionOta:
    distribucion: DistribucionOta
    despliegues: list[DespliegueOta]


class CrearDistribucionOtaUseCase:

    def __init__(
        self,
        *,
        db: Session,
        version_repo: VersionModeloRepository,
        distribucion_repo: DistribucionOtaRepository,
        despliegue_repo: DespliegueOtaRepository,
        nodo_port: NodoOtaPort,
        aviso_port: AvisoOtaPort,
        url_port: UrlDescargaPort,
    ) -> None:
        self._db = db
        self._version_repo = version_repo
        self._distribucion_repo = distribucion_repo
        self._despliegue_repo = despliegue_repo
        self._nodo_port = nodo_port
        self._aviso_port = aviso_port
        self._url_port = url_port

    def execute(self, dto: CrearDistribucionOtaDTO, id_usuario: int) -> ResultadoDistribucionOta:
        if not self._url_port.configurada():
            raise ServiceUnavailableError(
                code="OTA_NO_CONFIGURADA",
                message="La distribución OTA no está disponible: falta OTA_URL_SECRET u OTA_URL_BASE en este ambiente.",
            )

        version = self._version_repo.obtener_por_id(dto.id_version_modelo)
        if version is None:
            raise NotFoundError(
                code="VERSION_MODELO_NO_ENCONTRADA",
                message=f"No existe la versión de modelo con id {dto.id_version_modelo}.",
                field="id_version_modelo",
            )
        if version.estado_version != ESTADO_VERSION_DISTRIBUIBLE:
            raise BusinessRuleError(
                code="VERSION_NO_DISTRIBUIBLE",
                message=(
                    f"La versión {dto.id_version_modelo} está en estado '{version.estado_version}'. "
                    "Solo se distribuyen por OTA las versiones en estado ACTIVO."
                ),
                field="id_version_modelo",
            )
        if not version.ruta_artefacto or not version.hash_artefacto_sha256 or not version.tipo_modelo:
            raise BusinessRuleError(
                code="ARTEFACTO_NO_DISPONIBLE",
                message="La versión no tiene artefacto, SHA-256 o tipo_modelo registrados: no se puede distribuir.",
                field="id_version_modelo",
            )

        ids = dto.lista_dispositivos_objetivo
        seriales = self._nodo_port.obtener_seriales(ids)
        invalidos = [i for i in ids if i not in seriales]
        if invalidos:
            raise BusinessRuleError(
                code="DISPOSITIVO_OTA_INVALIDO",
                message=f"Los dispositivos {invalidos} no existen o están inactivos.",
                field="lista_dispositivos_objetivo",
            )
        vigentes = self._despliegue_repo.nodos_con_despliegue_vigente(ids, version.tipo_modelo, version.componente)
        if vigentes:
            raise ConflictError(
                code="DESPLIEGUE_OTA_VIGENTE",
                message=(
                    f"Los dispositivos {vigentes} ya tienen un despliegue en curso de "
                    f"{version.tipo_modelo}/{version.componente or 'modelo completo'}."
                ),
                field="lista_dispositivos_objetivo",
            )

        ahora = datetime.now(timezone.utc)
        try:
            distribucion = self._distribucion_repo.guardar(DistribucionOta(
                id_version_modelo=version.id_version_modelo,
                tipo_modelo=version.tipo_modelo,
                componente=version.componente,
                modo_distribucion=dto.modo_distribucion,
                ventana_inicio=dto.ventana_inicio,
                ventana_fin=dto.ventana_fin,
                nivel_bateria_minimo=dto.nivel_bateria_minimo,
                tamano_fragmento_bytes=dto.tamano_fragmento_bytes,
                max_reintentos_descarga=dto.max_reintentos_descarga,
                porcentaje_parcial=dto.porcentaje_parcial,
                id_usuario=id_usuario,
            ))
            despliegues = [
                self._despliegue_repo.crear(DespliegueOta(
                    id_despliegue_ota=0,
                    id_version_modelo=version.id_version_modelo,
                    id_dispositivo_iot=id_dispositivo,
                    tipo_modelo=version.tipo_modelo,
                    componente=version.componente,
                    modo_distribucion=dto.modo_distribucion,
                    estado_despliegue="PENDIENTE",
                    hash_modelo_sha256=version.hash_artefacto_sha256,
                    resultado_validacion_hash=None,
                    id_version_modelo_anterior=self._despliegue_repo.version_instalada(
                        id_dispositivo, version.tipo_modelo, version.componente
                    ),
                    rollback_ejecutado=False,
                    intentos_descarga=0,
                    max_reintentos=dto.max_reintentos_descarga,
                    tamano_modelo_bytes=version.tamanio_artefacto_bytes,
                    tamano_descargado_bytes=None,
                    duracion_proceso_ms=None,
                    ventana_inicio=dto.ventana_inicio,
                    ventana_fin=dto.ventana_fin,
                    nivel_bateria_al_inicio=None,
                    fecha_inicio=ahora,
                    fecha_fin=None,
                    motivo_fallo=None,
                    id_distribucion_ota=distribucion.id_distribucion_ota,
                    fase_rollout=fase,
                ))
                for id_dispositivo, fase in zip(ids, planificar_fases(len(ids), dto.porcentaje_parcial))
            ]
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        canary = [d for d in despliegues if d.fase_rollout == FASE_CANARY]
        try:
            avisados = avisar_despliegues(
                despliegues=canary, distribucion=distribucion, version=version,
                despliegue_repo=self._despliegue_repo, nodo_port=self._nodo_port,
                aviso_port=self._aviso_port, url_port=self._url_port, ahora=ahora,
            )
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        por_id = {d.id_despliegue_ota: d for d in avisados}
        return ResultadoDistribucionOta(
            distribucion=distribucion,
            despliegues=[por_id.get(d.id_despliegue_ota, d) for d in despliegues],
        )
