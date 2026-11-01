# | Fecha      | Nombre       | Que se hizo                                           |
# |------------|--------------|-------------------------------------------------------|
# | 2026-10-23 | destroyerban | DEV-48 RF-69: avisos de carga externa y rechazo       |
# | 2026-10-27 | Leandro | INC-M04-158-G086 RF-73: referenciar los procesos reales en incidentes previos al registro. |
# | 2026-10-29 | Arekkazu | INC-M04-213/214 RF-69: SavedModel por estructura protobuf, fecha futura y tipo vacío 422 |
# | 2026-10-31 | Arekkazu     | RFC-010 RF-69: versión por animal, estado SOMBRA y fuente de datos |
from __future__ import annotations

import hashlib
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy.orm import Session

from src.prediction.domain.entities.version_modelo import FUENTES_DATOS, VersionModelo
from src.prediction.domain.repositories.aviso_version_modelo_port import AvisoVersionModeloPort
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.variable_i3p1_port import VariableI3P1Port
from src.prediction.domain.repositories.version_modelo_repository import VersionModeloRepository
from src.prediction.infrastructure.dto.registrar_version_modelo_dto import RegistrarVersionModeloDTO
from src.shared.errors import AuthorizationError, BusinessRuleError
from src.shared.tipo_modelo import COMPONENTES_POBLACIONAL, INDIVIDUAL, TIPOS_MODELO, es_poblacional, paradigma_de

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
# RF-69 v2.0 (RFC-009): un modelo no supervisado no produce F1/recall; se valida
# con la calibración en sitio y sus tasas de falsos positivos y de detección.
_TASAS_POBLACIONALES = ("tasa_falsos_positivos_rutina", "tasa_deteccion_eventos_clinicos")
# RF-69 E1b (DEV-48): un aviso al Administrador por ventana, aunque el intento se repita;
# misma ventana anti-spam de RF-14. Todos los intentos quedan en la bitácora.
_VENTANA_AVISO_CARGA_EXTERNA = timedelta(minutes=5)
_MOTIVO_CARGA_EXTERNA = "X-RF71-Internal-Key ausente o incorrecta"

logger = logging.getLogger(__name__)


def _campos_protobuf(datos: bytes) -> list[tuple[int, int, bytes]] | None:
    """Campos de primer nivel de un mensaje protobuf (número, wire type, payload); None si no parsea."""

    def varint(i: int) -> tuple[int, int]:
        valor = desplazamiento = 0
        while i < len(datos) and desplazamiento < 64:
            byte = datos[i]
            valor |= (byte & 0x7F) << desplazamiento
            i += 1
            if not byte & 0x80:
                return valor, i
            desplazamiento += 7
        raise ValueError

    campos, i = [], 0
    try:
        while i < len(datos):
            clave, i = varint(i)
            numero, tipo = clave >> 3, clave & 0x07
            if tipo == 0:
                inicio = i
                _, i = varint(i)
            elif tipo == 1:
                inicio, i = i, i + 8
            elif tipo == 2:
                largo, inicio = varint(i)
                i = inicio + largo
            elif tipo == 5:
                inicio, i = i, i + 4
            else:
                return None
            if numero == 0 or i > len(datos):
                return None
            campos.append((numero, tipo, datos[inicio:i] if tipo == 2 else b""))
    except ValueError:
        return None
    return campos


def _es_saved_model(datos: bytes) -> bool:
    campos = _campos_protobuf(datos)
    if not campos or any(numero not in (1, 2) for numero, _, _ in campos):
        return False
    meta_graphs = [payload for numero, tipo, payload in campos if numero == 2 and tipo == 2]
    return bool(meta_graphs) and meta_graphs[0][:1] == b"\x0a"


class RegistrarVersionModeloUseCase:

    def __init__(
        self,
        *,
        db: Session,
        repo: VersionModeloRepository,
        auditoria_repo: EventoAuditoriaM04Repository,
        variable_port: VariableI3P1Port,
        aviso_port: AvisoVersionModeloPort,
    ) -> None:
        self._db = db
        self._repo = repo
        self._auditoria_repo = auditoria_repo
        self._variable_port = variable_port
        self._aviso_port = aviso_port

    def execute(self, dto: RegistrarVersionModeloDTO, internal_key: Optional[str]) -> VersionModelo:
        # FA-02: verificar clave interna
        self._verificar_clave_interna(internal_key, dto.id_proceso_rf71)

        # Antes de leer o guardar el artefacto: el trigger P0408 llegaba como 500 y el
        # archivo ya estaba en disco (INC-M04-214).
        self._validar_fecha_entrenamiento(dto.fecha_entrenamiento)

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

        # FA-04: tipo_modelo (antes que las métricas: el paradigma decide cuáles se exigen)
        if not dto.tipo_modelo or dto.tipo_modelo not in TIPOS_MODELO:
            raise BusinessRuleError(
                code="TIPO_MODELO_INVALIDO",
                message=f"tipo_modelo es obligatorio y debe ser uno de: {sorted(TIPOS_MODELO)}.",
                field="tipo_modelo",
            )

        # FA-04: métricas y componente por paradigma
        if es_poblacional(dto.tipo_modelo):
            componente = self._validar_componente(dto.componente)
            metricas_poblacionales = self._validar_metricas_poblacionales(dto.metricas_validacion)
            metricas = dict.fromkeys(_METRICAS_REQUERIDAS)
        else:
            componente, metricas_poblacionales = None, None  # no aplican a INDIVIDUAL/META
            metricas = self._validar_metricas(dto.metricas_validacion)

        id_activo = self._validar_activo_biologico(dto.tipo_modelo, dto.id_activo_biologico)
        if dto.fuente_datos not in FUENTES_DATOS:
            raise BusinessRuleError(
                code="FUENTE_DATOS_INVALIDA",
                message=f"fuente_datos debe ser uno de: {sorted(FUENTES_DATOS)}.",
                field="fuente_datos",
            )

        # Validar compatibilidad_variables contra catálogo I3P-1
        self._validar_variables(dto.compatibilidad_variables)

        # Guardar artefacto en disco
        ext = "onnx" if formato == "ONNX" else "pb"
        # RFC-010: un proceso RF-71 registra un artefacto por animal; el nombre no puede chocar.
        sufijo = componente or (str(id_activo) if id_activo is not None else None)
        ruta = self._guardar_artefacto(
            archivo_bytes, dto.id_proceso_rf71, f"{dto.tipo_modelo}_{sufijo}" if sufijo else dto.tipo_modelo, ext
        )

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
            componente=componente,
            metricas_poblacionales=metricas_poblacionales,
            id_activo_biologico=id_activo,
            fuente_datos=dto.fuente_datos,
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
            self._borrar_artefacto(ruta)
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

        # RF-69 E3 (DEV-48): el Veterinario revisa la versión rechazada; aviso después del commit.
        if estado_final == "RECHAZADO":
            try:
                self._aviso_port.avisar_version_rechazada(entidad)
            except Exception:  # la versión ya quedó registrada aunque el aviso falle
                logger.exception("No se pudo avisar la versión rechazada %s", entidad.id_version_modelo)

        return entidad

    def _avisar_carga_externa(self, id_proceso: uuid.UUID) -> None:
        """RF-69 E1b (DEV-48): avisa al Administrador, como mucho una vez por ventana."""
        try:
            desde = datetime.now(timezone.utc) - _VENTANA_AVISO_CARGA_EXTERNA
            _, intentos = self._auditoria_repo.consultar(
                tipo_evento="INTENTO_CARGA_MODELO_EXTERNO", fecha_desde=desde, por_pagina=1
            )
            # El intento actual ya está registrado: más de uno significa que ya se avisó.
            if intentos > 1:
                return
            self._aviso_port.avisar_carga_externa(id_proceso_rf71=str(id_proceso), motivo=_MOTIVO_CARGA_EXTERNA)
        except Exception:  # el 403 sale igual aunque el aviso falle
            self._db.rollback()
            logger.exception("No se pudo avisar el intento de carga de modelo externo")

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
                id_referencia=str(id_proceso),
                entidad_referencia="proceso_rf71",
                resultado_operacion="FALLIDO",
                severidad_evento="CRITICAL",
                payload_evento={
                    "motivo": _MOTIVO_CARGA_EXTERNA,
                    "id_proceso_rf71": str(id_proceso),
                },
            )
            try:
                self._db.commit()
            except Exception:
                self._db.rollback()
            self._avisar_carga_externa(id_proceso)
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
        """Formato por la estructura protobuf del archivo, no por su extensión (TC-M04-119).

        ONNX (ModelProto) y SavedModel empiezan los dos con 0x08 (campo 1 varint), así que
        el primer byte no distingue: SavedModel solo tiene los campos 1 y 2, y el 2
        (meta_graphs) es un MetaGraphDef que empieza por meta_info_def (0x0a).
        """
        if len(archivo_bytes) < 2:
            raise BusinessRuleError(
                code="FORMATO_ARTEFACTO_INVALIDO",
                message="El artefacto es demasiado pequeño para ser un modelo válido.",
                field="archivo_modelo",
            )
        if _es_saved_model(archivo_bytes):
            return "TENSORFLOW_SAVED_MODEL"
        if archivo_bytes[0:1] == b"\x08":
            return "ONNX"
        raise BusinessRuleError(
            code="FORMATO_ARTEFACTO_INVALIDO",
            message=(
                "El formato del artefacto no es compatible. "
                "Solo se aceptan ONNX y TensorFlow SavedModel."
            ),
            field="archivo_modelo",
        )

    def _validar_fecha_entrenamiento(self, fecha: datetime) -> None:
        if fecha > datetime.now(timezone.utc):
            raise BusinessRuleError(
                code="FECHA_ENTRENAMIENTO_FUTURA",
                message="La fecha_entrenamiento no puede ser una fecha futura.",
                field="fecha_entrenamiento",
            )

    @staticmethod
    def _borrar_artefacto(ruta: str) -> None:
        try:
            os.remove(ruta)
        except OSError:
            logger.warning("No se pudo borrar el artefacto de un registro fallido: %s", ruta)

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
                id_referencia=str(id_proceso),
                entidad_referencia="proceso_rf71",
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

    def _validar_componente(self, componente: Optional[str]) -> str:
        if componente not in COMPONENTES_POBLACIONAL:
            raise BusinessRuleError(
                code="COMPONENTE_INVALIDO",
                message=(
                    "Los modelos POBLACIONAL se versionan por componente: componente debe ser uno de "
                    f"{sorted(COMPONENTES_POBLACIONAL)}."
                ),
                field="componente",
            )
        return componente

    def _validar_activo_biologico(self, tipo_modelo: str, id_activo: Optional[int]) -> Optional[int]:
        """RFC-010: un INDIVIDUAL es de un animal; POBLACIONAL y META no lo son.

        Que el animal exista lo valida la FK (400 REFERENCIA_INVALIDA).
        """
        if paradigma_de(tipo_modelo) == INDIVIDUAL:
            if id_activo is None:
                raise BusinessRuleError(
                    code="ACTIVO_BIOLOGICO_REQUERIDO",
                    message="Los modelos INDIVIDUAL se versionan por animal: id_activo_biologico es obligatorio.",
                    field="id_activo_biologico",
                )
            return id_activo
        if id_activo is not None:
            raise BusinessRuleError(
                code="ACTIVO_BIOLOGICO_NO_APLICA",
                message=f"Los modelos {paradigma_de(tipo_modelo)} no son de un animal: no envíe id_activo_biologico.",
                field="id_activo_biologico",
            )
        return None

    def _validar_metricas_poblacionales(self, metricas: dict) -> dict:
        faltantes = {"calibracion_completada", *_TASAS_POBLACIONALES} - set(metricas.keys())
        if faltantes:
            raise BusinessRuleError(
                code="METRICAS_INCOMPLETAS",
                message=f"Los metadatos del modelo son inválidos o incompletos: faltan {sorted(faltantes)}.",
                field="metricas_validacion",
            )
        if not isinstance(metricas["calibracion_completada"], bool):
            raise BusinessRuleError(
                code="METRICA_INVALIDA",
                message="El campo calibracion_completada debe ser booleano.",
                field="metricas_validacion",
            )
        resultado: dict = {"calibracion_completada": metricas["calibracion_completada"]}
        for campo in _TASAS_POBLACIONALES:
            valor = metricas[campo]
            if isinstance(valor, bool) or not isinstance(valor, (int, float)):
                raise BusinessRuleError(
                    code="METRICA_INVALIDA",
                    message=f"El campo {campo} tiene un valor no numérico.",
                    field="metricas_validacion",
                )
            if not (0.0 <= valor <= 1.0):
                raise BusinessRuleError(
                    code="METRICA_FUERA_DE_RANGO",
                    message=f"El campo {campo}={valor} debe estar en el rango [0.0, 1.0].",
                    field="metricas_validacion",
                )
            resultado[campo] = valor
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
