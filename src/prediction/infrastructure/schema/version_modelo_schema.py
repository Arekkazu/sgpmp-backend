from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from src.prediction.domain.entities.version_modelo import VersionModelo


class VersionModeloResponse(BaseModel):
    id_version_modelo: int
    nombre_version: str
    tipo_modelo: Optional[str]
    estado_version: str
    formato_artefacto: Optional[str]
    tamanio_artefacto_bytes: Optional[int]
    hash_artefacto_sha256: Optional[str]
    dataset_entrenamiento_hash: Optional[str]
    id_proceso_rf71: Optional[uuid.UUID]
    version_referencia: Optional[int]
    f1_score: Optional[Decimal]
    recall_clase_riesgo_alto: Optional[Decimal]
    precision_modelo: Optional[Decimal]
    accuracy: Optional[Decimal]
    roc_auc_score: Optional[Decimal]
    recall_por_clase: Optional[dict]
    matriz_confusion: Optional[dict]
    compatibilidad_variables: Optional[list]
    notas_validacion: Optional[str]
    detalle_validacion: Optional[str]
    esta_produccion: bool
    fecha_entrenamiento: Optional[datetime]
    fecha_registro: Optional[datetime]
    fecha_despliegue: Optional[datetime]

    @classmethod
    def from_entity(cls, e: VersionModelo) -> VersionModeloResponse:
        return cls(
            id_version_modelo=e.id_version_modelo,
            nombre_version=e.nombre_version,
            tipo_modelo=e.tipo_modelo,
            estado_version=e.estado_version,
            formato_artefacto=e.formato_artefacto,
            tamanio_artefacto_bytes=e.tamanio_artefacto_bytes,
            hash_artefacto_sha256=e.hash_artefacto_sha256,
            dataset_entrenamiento_hash=e.dataset_entrenamiento_hash,
            id_proceso_rf71=e.id_proceso_rf71,
            version_referencia=e.version_referencia,
            f1_score=e.f1_score,
            recall_clase_riesgo_alto=e.recall_clase_riesgo_alto,
            precision_modelo=e.precision_modelo,
            accuracy=e.accuracy,
            roc_auc_score=e.roc_auc_score,
            recall_por_clase=e.recall_por_clase,
            matriz_confusion=e.matriz_confusion,
            compatibilidad_variables=e.compatibilidad_variables,
            notas_validacion=e.notas_validacion,
            detalle_validacion=e.detalle_validacion,
            esta_produccion=e.esta_produccion,
            fecha_entrenamiento=e.fecha_entrenamiento,
            fecha_registro=e.fecha_registro,
            fecha_despliegue=e.fecha_despliegue,
        )


class VersionModeloListResponse(BaseModel):
    total: int
    items: list[VersionModeloResponse]
