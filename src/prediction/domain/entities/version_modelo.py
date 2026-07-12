from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from src.shared.errors import BusinessRuleError

_UMBRAL_F1 = Decimal("0.80")
_UMBRAL_RECALL = Decimal("0.85")
_MAX_BYTES = 500 * 1024 * 1024  # 500 MB


@dataclass(eq=False)
class VersionModelo:
    nombre_version: str
    tipo_modelo: str
    estado_version: str
    formato_artefacto: Optional[str]
    ruta_artefacto: Optional[str]
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
    id_usuario: Optional[int]
    esta_produccion: bool
    fecha_entrenamiento: Optional[datetime]
    fecha_registro: Optional[datetime]
    fecha_despliegue: Optional[datetime]

    id_version_modelo: Optional[int] = None

    @classmethod
    def crear(
        cls,
        *,
        tipo_modelo: str,
        formato_artefacto: str,
        ruta_artefacto: str,
        tamanio_artefacto_bytes: int,
        hash_artefacto_sha256: str,
        dataset_entrenamiento_hash: str,
        id_proceso_rf71: uuid.UUID,
        f1_score: Decimal,
        recall_clase_riesgo_alto: Decimal,
        precision_modelo: Decimal,
        accuracy: Decimal,
        roc_auc_score: Decimal,
        recall_por_clase: dict,
        matriz_confusion: dict,
        compatibilidad_variables: list,
        fecha_entrenamiento: datetime,
        version_referencia: Optional[int] = None,
    ) -> VersionModelo:
        nombre_version = (
            f"{tipo_modelo}_{fecha_entrenamiento.strftime('%Y%m%d')}_{str(id_proceso_rf71)[:8]}"
        )
        return cls(
            nombre_version=nombre_version,
            tipo_modelo=tipo_modelo,
            estado_version="EN_VALIDACION",
            formato_artefacto=formato_artefacto,
            ruta_artefacto=ruta_artefacto,
            tamanio_artefacto_bytes=tamanio_artefacto_bytes,
            hash_artefacto_sha256=hash_artefacto_sha256,
            dataset_entrenamiento_hash=dataset_entrenamiento_hash,
            id_proceso_rf71=id_proceso_rf71,
            version_referencia=version_referencia,
            f1_score=f1_score,
            recall_clase_riesgo_alto=recall_clase_riesgo_alto,
            precision_modelo=precision_modelo,
            accuracy=accuracy,
            roc_auc_score=roc_auc_score,
            recall_por_clase=recall_por_clase,
            matriz_confusion=matriz_confusion,
            compatibilidad_variables=compatibilidad_variables,
            notas_validacion=None,
            detalle_validacion=None,
            id_usuario=None,
            esta_produccion=False,
            fecha_entrenamiento=fecha_entrenamiento,
            fecha_registro=None,
            fecha_despliegue=None,
        )

    def validar_y_asignar_estado(self) -> None:
        """Evalúa métricas y asigna APROBADO o RECHAZADO. Llena detalle_validacion si RECHAZADO."""
        defectos = []
        if self.f1_score is None or self.f1_score < _UMBRAL_F1:
            defectos.append(
                f"f1_score_global={self.f1_score} < umbral requerido {_UMBRAL_F1}"
            )
        if self.recall_clase_riesgo_alto is None or self.recall_clase_riesgo_alto < _UMBRAL_RECALL:
            defectos.append(
                f"recall_clase_riesgo_alto={self.recall_clase_riesgo_alto} < umbral requerido {_UMBRAL_RECALL}"
            )
        if defectos:
            self.estado_version = "RECHAZADO"
            self.detalle_validacion = "; ".join(defectos)
        else:
            self.estado_version = "APROBADO"
            self.detalle_validacion = None

    def activar(self) -> None:
        """Transiciona a ACTIVO. Solo válido desde APROBADO y con notas_validacion."""
        if self.estado_version in ("DEPRECADO", "RECHAZADO"):
            raise BusinessRuleError(
                code="TRANSICION_ESTADO_INVALIDA",
                message=(
                    f"Los modelos en estado {self.estado_version} son terminales "
                    "y no pueden reactivarse."
                ),
            )
        if self.estado_version != "APROBADO":
            raise BusinessRuleError(
                code="VERSION_NO_APROBADA",
                message=(
                    f"Solo las versiones en estado APROBADO pueden activarse. "
                    f"Estado actual: {self.estado_version}."
                ),
            )
        if not self.notas_validacion or not self.notas_validacion.strip():
            raise BusinessRuleError(
                code="NOTAS_VALIDACION_REQUERIDAS",
                message=(
                    "Se requieren notas de validación clínica antes de activar la versión. "
                    "Use PATCH /prediccion/modelos/{id}/notas para registrarlas."
                ),
            )
        self.estado_version = "ACTIVO"
        self.esta_produccion = True
        self.fecha_despliegue = datetime.now(tz=timezone.utc)

    def deprecar(self) -> None:
        """Transiciona a DEPRECADO. Solo válido desde ACTIVO."""
        if self.estado_version != "ACTIVO":
            raise BusinessRuleError(
                code="TRANSICION_ESTADO_INVALIDA",
                message=(
                    f"Solo los modelos ACTIVOS pueden deprecarse. "
                    f"Estado actual: {self.estado_version}."
                ),
            )
        self.estado_version = "DEPRECADO"
        self.esta_produccion = False

    def registrar_notas(self, notas: str) -> None:
        if not notas or not notas.strip():
            raise BusinessRuleError(
                code="NOTAS_VACIAS",
                message="Las notas de validación no pueden estar vacías.",
                field="notas_validacion",
            )
        self.notas_validacion = notas.strip()

    def _snapshot(self) -> dict:
        return {
            "nombre_version": self.nombre_version,
            "tipo_modelo": self.tipo_modelo,
            "estado_version": self.estado_version,
            "formato_artefacto": self.formato_artefacto,
            "f1_score": str(self.f1_score) if self.f1_score is not None else None,
            "recall_clase_riesgo_alto": (
                str(self.recall_clase_riesgo_alto)
                if self.recall_clase_riesgo_alto is not None
                else None
            ),
            "precision_modelo": str(self.precision_modelo) if self.precision_modelo is not None else None,
            "accuracy": str(self.accuracy) if self.accuracy is not None else None,
            "roc_auc_score": str(self.roc_auc_score) if self.roc_auc_score is not None else None,
            "detalle_validacion": self.detalle_validacion,
            "notas_validacion": self.notas_validacion,
        }
