# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-26 | Arekkazu | INC-M04-204-G43/207-G46 RF-70: libera los despliegues PROGRAMADO al abrir su ventana |
"""Avisar ``ota/notify`` a los despliegues PROGRAMADO pospuestos cuando abre su ventana (RF-70 E1).

``CrearDistribucionOtaUseCase`` deja PENDIENTE con FUERA_VENTANA_ACTUALIZACION a los nodos
de una distribución PROGRAMADO creada antes de ``ventana_inicio``. Lo corre una tarea
periódica de ``main.py``; cada distribución va en su propia transacción.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.prediction.application.use_cases.ota._aviso_fase import MOTIVO_FUERA_VENTANA, avisar_despliegues
from src.prediction.domain.repositories.despliegue_ota_repository import DespliegueOtaRepository
from src.prediction.domain.repositories.distribucion_ota_repository import DistribucionOtaRepository
from src.prediction.domain.repositories.ota_edge_port import AvisoOtaPort, NodoOtaPort, UrlDescargaPort
from src.prediction.domain.repositories.version_modelo_repository import VersionModeloRepository

logger = logging.getLogger(__name__)


class LiberarDesplieguesProgramadosUseCase:

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

    def execute(self, ahora: Optional[datetime] = None) -> int:
        """Devuelve cuántos despliegues se avisaron."""
        ahora = ahora or datetime.now(timezone.utc)
        avisados = 0
        for distribucion in self._distribucion_repo.listar_programadas_en_ventana(ahora):
            pospuestos = [
                d for d in self._despliegue_repo.listar_por_distribucion(distribucion.id_distribucion_ota)
                if d.estado_despliegue == "PENDIENTE" and d.motivo_fallo == MOTIVO_FUERA_VENTANA
            ]
            if not pospuestos:
                continue
            try:
                resultado = avisar_despliegues(
                    despliegues=pospuestos, distribucion=distribucion,
                    version=self._version_repo.obtener_por_id(distribucion.id_version_modelo),
                    despliegue_repo=self._despliegue_repo, nodo_port=self._nodo_port,
                    aviso_port=self._aviso_port, url_port=self._url_port, ahora=ahora,
                )
                self._db.commit()
                avisados += sum(1 for d in resultado if d.id_mensaje_notify)
            except Exception:
                self._db.rollback()
                logger.exception("RF-70: no se pudo liberar la distribución OTA %s.", distribucion.id_distribucion_ota)
        return avisados
