# | Fecha      | Nombre       | Que se hizo                                           |
# |------------|--------------|-------------------------------------------------------|
# | 2026-10-23 | destroyerban | DEV-34 RF-69: códigos HTTP de E2, E3 y E4             |
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
# | 2026-10-29 | Arekkazu | INC-M04-214 RF-69: tipo_modelo vacío llega al caso de uso (422 con los tipos admitidos) |
from __future__ import annotations

import json
import uuid
from typing import Optional

from fastapi import File, Form, UploadFile
from pydantic import UUID4

from src.shared.errors import BusinessRuleError
from src.shared.fechas import FechaHoraUtc


def _json_de_formulario(valor: str, campo: str, tipo: type, descripcion: str):
    """RF-69 E2 (DEV-34): un campo JSON del formulario que no parsea o no es del tipo esperado es 422."""
    try:
        resultado = json.loads(valor)
    except (json.JSONDecodeError, TypeError):
        resultado = None
    if not isinstance(resultado, tipo):
        raise BusinessRuleError(
            code="METADATOS_JSON_INVALIDO",
            message=f"Los metadatos del modelo son inválidos o incompletos: {campo} debe ser {descripcion} JSON válido.",
            field=campo,
        )
    return resultado


class RegistrarVersionModeloDTO:
    """DTO para el endpoint interno POST /prediccion/modelos (multipart/form-data).

    Recibe el artefacto binario de RF-71 junto con sus metadatos.
    """

    def __init__(
        self,
        # Vacío u omitido lo rechaza el caso de uso con la lista de tipos admitidos.
        tipo_modelo: Optional[str] = Form(None),
        hash_artefacto_sha256: str = Form(...),
        dataset_entrenamiento_hash: str = Form(...),
        metricas_validacion: str = Form(...),
        fecha_entrenamiento: FechaHoraUtc = Form(...),
        compatibilidad_variables: str = Form(...),
        id_proceso_rf71: uuid.UUID = Form(...),
        version_referencia: Optional[int] = Form(None),
        archivo_modelo: UploadFile = File(...),
        # RF-69 v2.0 (RFC-009): obligatorio para modelos POBLACIONAL.
        componente: Optional[str] = Form(None),
    ) -> None:
        self.tipo_modelo = tipo_modelo
        self.hash_artefacto_sha256 = hash_artefacto_sha256
        self.dataset_entrenamiento_hash = dataset_entrenamiento_hash
        self.metricas_validacion: dict = _json_de_formulario(metricas_validacion, "metricas_validacion", dict, "un objeto")
        self.fecha_entrenamiento = fecha_entrenamiento
        self.compatibilidad_variables: list = _json_de_formulario(
            compatibilidad_variables, "compatibilidad_variables", list, "una lista"
        )
        self.id_proceso_rf71 = id_proceso_rf71
        self.version_referencia = version_referencia
        self.archivo_modelo = archivo_modelo
        self.componente = componente
