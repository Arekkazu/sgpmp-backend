from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import _calcular_hash
from src.telemetry.domain.entities.evento_auditoria_iot import (
    ComponenteOrigen,
    EntidadAfectadaTipo,
    EventoAuditoriaIot,
    SeveridadLog,
    TipoResultado,
)
from src.telemetry.domain.repositories.bitacora_auditoria_iot_repository import BitacoraAuditoriaIotRepository


@dataclass
class ResultadoVerificacion:
    total_verificados: int
    comprometidos: int
    ids_comprometidos: list[str]


class VerificarIntegridadBitacoraUseCase:
    """RF-63 FA-11: Re-calcula SHA-256 de cada registro y detecta alteraciones."""

    def __init__(self, db: Session, auditoria_repo: BitacoraAuditoriaIotRepository) -> None:
        self.db = db
        self.auditoria_repo = auditoria_repo

    def execute(
        self,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
    ) -> ResultadoVerificacion:
        eventos = self.auditoria_repo.listar_todos_para_verificacion(fecha_desde, fecha_hasta)
        comprometidos: list[str] = []

        for evento in eventos:
            hash_esperado = _calcular_hash(evento)
            if hash_esperado != evento.hash_integridad:
                comprometidos.append(str(evento.id_evento))

        if comprometidos:
            self._registrar_incidente(comprometidos)

        return ResultadoVerificacion(
            total_verificados=len(eventos),
            comprometidos=len(comprometidos),
            ids_comprometidos=comprometidos,
        )

    def _registrar_incidente(self, ids_comprometidos: list[str]) -> None:
        try:
            from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import RegistrarEventoAuditoriaIotUseCase
            svc = RegistrarEventoAuditoriaIotUseCase(db=self.db, auditoria_repo=self.auditoria_repo)
            svc.execute(
                tipo_evento='INTEGRIDAD_COMPROMETIDA',
                resultado=TipoResultado.FALLIDO,
                componente_origen=ComponenteOrigen.RF62,
                severidad_log=SeveridadLog.CRITICAL,
                descripcion=f'Integridad comprometida en {len(ids_comprometidos)} registro(s).',
                entidad_afectada_tipo=EntidadAfectadaTipo.CALIDAD_DATO,
                accion_detallada={'ids_comprometidos': ids_comprometidos},
            )
        except Exception:
            pass
