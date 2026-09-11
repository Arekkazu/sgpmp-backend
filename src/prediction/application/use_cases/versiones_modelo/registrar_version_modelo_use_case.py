from __future__ import annotations

import hashlib
import os
import uuid
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy.orm import Session

from src.prediction.domain.entities.version_modelo import VersionModelo
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.variable_i3p1_port import VariableI3P1Port
from src.prediction.domain.repositories.version_modelo_repository import VersionModeloRepository
from src.prediction.infrastructure.dto.registrar_version_modelo_dto import RegistrarVersionModeloDTO
from src.shared.errors import AuthorizationError, BusinessRuleError

_TIPOS_VALIDOS = {"ESPECIES_PEQUEÑAS", "ESPECIES_MEDIANAS", "ESPECIES_GRANDES", "CONTAGIO"}
_FORMATOS_VALIDOS = {"ONNX", "TENSORFLOW_SAVED_MODEL"}
_MAX_BYTES = 500 * 1024 * 1024  # 500 MB
_METRICAS_REQUERIDAS = {
    "f1_score_global",
    "recall_clase_riesgo_alto",
    "precision_global",
    "accuracy",
    "roc_auc_score",
    "recall_por_clase",
    "matriz_confusion",
}
# Magic bytes para identificar el formato del artefacto
_ONNX_MAGIC = b"\x08"          # protobuf field tag 1 (model_ir_version)
_TF_SAVEDMODEL_MAGIC = b"\x0a" # protobuf field tag 1 (saved_model_schema_version)


class RegistrarVersionModeloUseCase:

    def __init__(
        self,
        *,
        db: Session,
        repo: VersionModeloRepository,
        auditoria_repo: EventoAuditoriaM04Repository,
        variable_port: VariableI3P1Port,
    ) -> None:
        self._db = db
        self._repo = repo
        self._auditoria_repo = auditoria_repo
        self._variable_port = variable_port

    def execute(self, dto: RegistrarVersionModeloDTO, internal_key: Optional[str]) -> VersionModelo:
        # FA-02: verificar clave interna
        self._verificar_clave_interna(internal_key, dto.id_proceso_rf71)

        # Leer bytes del archivo
        archivo_bytes = dto.archivo_modelo.file.read()

        # FA-03: tamaño
        self._validar_tamano(archivo_bytes)

        # FA-01: formato por magic bytes
        formato = self._detectar_formato(archivo_bytes)

        # FA-04/FA-05: integridad de hashes
        self._validar_hash_sha256_campo(dto.hash_artefacto_sha256, "hash_artefacto_sha256")
        self._validar_hash_sha256_campo(dto.dataset_entrenamiento_hash, "dataset_entrenamiento_hash")
        self._verificar_hash_artefacto(archivo_bytes, dto.hash_artefacto_sha256, dto.id_proceso_rf71)

        # FA-04: métricas
        metricas = self._validar_metricas(dto.metricas_validacion)

        # FA-04: tipo_modelo
        if dto.tipo_modelo not in _TIPOS_VALIDOS:
            raise BusinessRuleError(
                code="TIPO_MODELO_INVALIDO",
                message=f"tipo_modelo debe ser uno de: {sorted(_TIPOS_VALIDOS)}.",
                field="tipo_modelo",
            )

        # Validar compatibilidad_variables contra catálogo I3P-1
        self._validar_variables(dto.compatibilidad_variables)

        # Guardar artefacto en disco
        ext = "onnx" if formato == "ONNX" else "pb"
        ruta = self._guardar_artefacto(archivo_bytes, dto.id_proceso_rf71, dto.tipo_modelo, ext)

        # Crear entidad
        entidad = VersionModelo.crear(
            tipo_modelo=dto.tipo_modelo,
            formato_artefacto=formato,
            ruta_artefacto=ruta,
            tamanio_artefacto_bytes=len(archivo_bytes),
            hash_artefacto_sha256=dto.hash_artefacto_sha256,
            dataset_entrenamiento_hash=dto.dataset_entrenamiento_hash,
            id_proceso_rf71=dto.id_proceso_rf71,
            f1_score=metricas["f1_score_global"],
            recall_clase_riesgo_alto=metricas["recall_clase_riesgo_alto"],
            precision_modelo=metricas["precision_global"],
            accuracy=metricas["accuracy"],
            roc_auc_score=metricas["roc_auc_score"],
            recall_por_clase=metricas["recall_por_clase"],
            matriz_confusion=metricas["matriz_confusion"],
            compatibilidad_variables=dto.compatibilidad_variables,
            fecha_entrenamiento=dto.fecha_entrenamiento,
            version_referencia=dto.version_referencia,
        )

        # Evaluación automática de métricas (Fase 3)
        entidad.validar_y_asignar_estado()

        estado_final = entidad.estado_version

        try:
            entidad = self._repo.guardar(entidad)
            self._repo.registrar_historial(
                id_version_modelo=entidad.id_version_modelo,
                estado_anterior=None,
                estado_nuevo="EN_VALIDACION",
                tipo_actor="SISTEMA",
                id_sistema=str(dto.id_proceso_rf71),
                id_proceso_rf71=dto.id_proceso_rf71,
                motivo="Registro automático desde RF-71",
            )
            self._repo.registrar_historial(
                id_version_modelo=entidad.id_version_modelo,
                estado_anterior="EN_VALIDACION",
                estado_nuevo=estado_final,
                tipo_actor="SISTEMA",
                id_sistema=str(dto.id_proceso_rf71),
                id_proceso_rf71=dto.id_proceso_rf71,
                motivo=entidad.detalle_validacion or "Evaluación automática de métricas",
            )
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        tipo_evento_resultado = "VERSION_APROBADA" if estado_final == "APROBADO" else "VERSION_RECHAZADA"
        for tipo_ev in ("VERSION_REGISTRADA", tipo_evento_resultado):
            self._auditoria_repo.registrar(
                tipo_evento=tipo_ev,
                tipo_actor="SISTEMA",
                id_sistema=str(dto.id_proceso_rf71),
                id_referencia=str(entidad.id_version_modelo),
                entidad_referencia="version_modelo",
                resultado_operacion="EXITOSO",
                severidad_evento="INFO",
                payload_evento={
                    "id_proceso_rf71": str(dto.id_proceso_rf71),
                    **entidad._snapshot(),
                },
            )
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()

        return entidad

    # ------------------------------------------------------------------
    # Validaciones privadas
    # ------------------------------------------------------------------

    def _verificar_clave_interna(self, clave: Optional[str], id_proceso: uuid.UUID) -> None:
        esperada = os.environ.get("RF71_INTERNAL_KEY", "")
        if not clave or clave != esperada:
            self._auditoria_repo.registrar(
                tipo_evento="INTENTO_CARGA_MODELO_EXTERNO",
                tipo_actor="SISTEMA",
                id_sistema="DESCONOCIDO",
                resultado_operacion="FALLIDO",
                severidad_evento="CRITICAL",
                payload_evento={
                    "motivo": "X-RF71-Internal-Key ausente o incorrecta",
                    "id_proceso_rf71": str(id_proceso),
                },
            )
            try:
                self._db.commit()
            except Exception:
                self._db.rollback()
            raise AuthorizationError(
                code="REGISTRO_INTERNO_REQUERIDO",
                message=(
                    "El registro de versiones de modelo solo puede ser invocado "
                    "internamente por el proceso de reentrenamiento RF-71."
                ),
            )

    def _validar_tamano(self, archivo_bytes: bytes) -> None:
        if len(archivo_bytes) > _MAX_BYTES:
            raise BusinessRuleError(
                code="ARTEFACTO_SUPERA_TAMANO_MAXIMO",
                message=(
                    f"El artefacto del modelo supera el tamaño máximo permitido "
                    f"(500 MB). Tamaño recibido: {len(archivo_bytes) / 1024 / 1024:.1f} MB."
                ),
                field="archivo_modelo",
            )

    def _detectar_formato(self, archivo_bytes: bytes) -> str:
        if len(archivo_bytes) < 2:
            raise BusinessRuleError(
                code="FORMATO_ARTEFACTO_INVALIDO",
                message="El artefacto es demasiado pequeño para ser un modelo válido.",
                field="archivo_modelo",
            )
        # ONNX: protobuf ModelProto comienza con field_number=1 (model_ir_version, varint)
        # bytes 0x08 = field 1, wire_type 0 (varint)
        if archivo_bytes[0:1] == b"\x08":
            return "ONNX"
        # TF SavedModel.pb: protobuf SavedModel comienza con field_number=1 (saved_model_schema_version)
        # bytes 0x0a = field 1, wire_type 2 (length-delimited)
        if archivo_bytes[0:1] == b"\x0a":
            return "TENSORFLOW_SAVED_MODEL"
        raise BusinessRuleError(
            code="FORMATO_ARTEFACTO_INVALIDO",
            message=(
                "El formato del artefacto no es compatible. "
                "Solo se aceptan ONNX y TensorFlow SavedModel."
            ),
            field="archivo_modelo",
        )

    def _validar_hash_sha256_campo(self, valor: str, campo: str) -> None:
        import re
        if not valor or not re.fullmatch(r"[0-9a-fA-F]{64}", valor):
            raise BusinessRuleError(
                code="HASH_SHA256_INVALIDO",
                message=f"{campo} debe ser un hash SHA-256 de 64 caracteres hexadecimales.",
                field=campo,
            )

    def _verificar_hash_artefacto(
        self, archivo_bytes: bytes, hash_declarado: str, id_proceso: uuid.UUID
    ) -> None:
        hash_calculado = hashlib.sha256(archivo_bytes).hexdigest()
        if hash_calculado.lower() != hash_declarado.lower():
            self._auditoria_repo.registrar(
                tipo_evento="HASH_INVALIDO_DETECTADO",
                tipo_actor="SISTEMA",
                id_sistema=str(id_proceso),
                resultado_operacion="FALLIDO",
                severidad_evento="CRITICAL",
                payload_evento={
                    "hash_declarado": hash_declarado,
                    "hash_calculado": hash_calculado,
                    "id_proceso_rf71": str(id_proceso),
                },
            )
            try:
                self._db.commit()
            except Exception:
                self._db.rollback()
            raise BusinessRuleError(
                code="HASH_ARTEFACTO_NO_COINCIDE",
                message="El hash del artefacto no coincide con el contenido del archivo.",
                field="hash_artefacto_sha256",
            )

    def _validar_metricas(self, metricas: dict) -> dict[str, object]:
        faltantes = _METRICAS_REQUERIDAS - set(metricas.keys())
        if faltantes:
            raise BusinessRuleError(
                code="METRICAS_INCOMPLETAS",
                message=f"Los metadatos del modelo son inválidos o incompletos: faltan {sorted(faltantes)}.",
                field="metricas_validacion",
            )
        escalares = ("f1_score_global", "recall_clase_riesgo_alto", "precision_global", "accuracy", "roc_auc_score")
        resultado: dict = {}
        for campo in escalares:
            try:
                val = Decimal(str(metricas[campo]))
            except (InvalidOperation, TypeError):
                raise BusinessRuleError(
                    code="METRICA_INVALIDA",
                    message=f"El campo {campo} tiene un valor no numérico.",
                    field="metricas_validacion",
                )
            if not (Decimal("0.0") <= val <= Decimal("1.0")):
                raise BusinessRuleError(
                    code="METRICA_FUERA_DE_RANGO",
                    message=f"El campo {campo}={val} debe estar en el rango [0.0, 1.0].",
                    field="metricas_validacion",
                )
            resultado[campo] = val
        resultado["recall_por_clase"] = metricas["recall_por_clase"]
        resultado["matriz_confusion"] = metricas["matriz_confusion"]
        return resultado

    def _validar_variables(self, variables: list) -> None:
        if not variables:
            return
        try:
            ids = [int(v) for v in variables]
        except (ValueError, TypeError):
            raise BusinessRuleError(
                code="VARIABLE_I3P1_INVALIDA",
                message="Los identificadores de compatibilidad_variables deben ser enteros.",
                field="compatibilidad_variables",
            )
        activos = self._variable_port.obtener_ids_activos(ids)
        faltantes = set(ids) - set(activos)
        if faltantes:
            raise BusinessRuleError(
                code="VARIABLE_I3P1_NO_ENCONTRADA",
                message=f"Las siguientes variables no existen en el catálogo I3P-1: {sorted(faltantes)}.",
                field="compatibilidad_variables",
            )

    def _guardar_artefacto(
        self, archivo_bytes: bytes, id_proceso: uuid.UUID, tipo_modelo: str, ext: str
    ) -> str:
        storage = os.environ.get("MODELOS_STORAGE_PATH", "/tmp/sgpmp_modelos")
        os.makedirs(storage, exist_ok=True)
        nombre_archivo = f"{str(id_proceso)}_{tipo_modelo}.{ext}"
        ruta = os.path.join(storage, nombre_archivo)
        with open(ruta, "wb") as f:
            f.write(archivo_bytes)
        return ruta
