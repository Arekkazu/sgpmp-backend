# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | #391 RF-16: densidad y biomasa máximas de la etapa con aviso preventivo |
"""Configurar la densidad máxima de una etapa (#391, RF-16). La aplica RF-36 al lote que está en esa fase."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.ciclo_biologico import CicloBiologico
from src.configuration.domain.repositories.auditoria_ciclo_repository import AuditoriaCicloRepository
from src.configuration.domain.repositories.ciclo_biologico_repository import CicloBiologicoRepository
from src.shared.errors import BusinessRuleError, NotFoundError, PreconditionFailedError

_CONCURRENCIA = "La etapa fue modificada por otro usuario. Recargue los datos e intente de nuevo."


def _snapshot(etapa: CicloBiologico) -> dict:
    return {
        "id_ciclo_biologico": etapa.id_ciclo_biologico,
        "densidad_maxima": str(etapa.densidad_maxima) if etapa.densidad_maxima is not None else None,
        "biomasa_maxima": str(etapa.biomasa_maxima) if etapa.biomasa_maxima is not None else None,
        "aviso_preventivo_pct": etapa.aviso_preventivo_pct,
    }


class ConfigurarDensidadEtapaUseCase:
    def __init__(self, db: Session, etapas: CicloBiologicoRepository, auditoria: AuditoriaCicloRepository) -> None:
        self.db, self.etapas, self.auditoria = db, etapas, auditoria

    def execute(self, id_ciclo_biologico: int, *, densidad_maxima: Decimal, biomasa_maxima: Optional[Decimal],
                aviso_preventivo_pct: int, fecha_actualizacion: Optional[datetime], id_usuario: int) -> CicloBiologico:
        etapa = self.etapas.obtener_por_id(id_ciclo_biologico, bloquear=True)
        if etapa is None:
            raise NotFoundError(code="ETAPA_NO_ENCONTRADA", message="La etapa no existe.")
        if not etapa.es_activo:
            raise BusinessRuleError(code="ETAPA_INACTIVA",
                                    message="No se puede configurar una etapa inactiva. Reactívela primero.")
        actual = etapa.fecha_actualizacion
        if actual is not None and fecha_actualizacion is not None:
            if actual.astimezone(timezone.utc) != fecha_actualizacion.astimezone(timezone.utc):
                raise PreconditionFailedError(code="CONFLICTO_CONCURRENCIA", message=_CONCURRENCIA)
        elif actual != fecha_actualizacion:  # None != None es False: una etapa nunca editada no exige fecha
            raise PreconditionFailedError(code="CONFLICTO_CONCURRENCIA", message=_CONCURRENCIA)
        anterior = _snapshot(etapa)
        etapa.configurar_densidad(densidad_maxima=densidad_maxima, biomasa_maxima=biomasa_maxima,
                                  aviso_preventivo_pct=aviso_preventivo_pct, fecha_actualizacion=datetime.now(timezone.utc))
        try:
            etapa = self.etapas.actualizar(etapa)
            self.auditoria.registrar(id_ciclo_biologico=id_ciclo_biologico, id_usuario=id_usuario,
                                     tipo_operacion="UPDATE", valores_nuevos=_snapshot(etapa), valores_anteriores=anterior)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return etapa
