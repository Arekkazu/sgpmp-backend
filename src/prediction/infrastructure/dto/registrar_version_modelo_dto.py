from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import File, Form, UploadFile
from pydantic import UUID4


class RegistrarVersionModeloDTO:
    """DTO para el endpoint interno POST /prediccion/modelos (multipart/form-data).

    Recibe el artefacto binario de RF-71 junto con sus metadatos.
    """

    def __init__(
        self,
        tipo_modelo: str = Form(...),
        hash_artefacto_sha256: str = Form(...),
        dataset_entrenamiento_hash: str = Form(...),
        metricas_validacion: str = Form(...),
        fecha_entrenamiento: datetime = Form(...),
        compatibilidad_variables: str = Form(...),
        id_proceso_rf71: uuid.UUID = Form(...),
        version_referencia: Optional[int] = Form(None),
        archivo_modelo: UploadFile = File(...),
    ) -> None:
        self.tipo_modelo = tipo_modelo
        self.hash_artefacto_sha256 = hash_artefacto_sha256
        self.dataset_entrenamiento_hash = dataset_entrenamiento_hash
        self.metricas_validacion: dict = json.loads(metricas_validacion)
        self.fecha_entrenamiento = fecha_entrenamiento
        self.compatibilidad_variables: list = json.loads(compatibilidad_variables)
        self.id_proceso_rf71 = id_proceso_rf71
        self.version_referencia = version_referencia
        self.archivo_modelo = archivo_modelo
