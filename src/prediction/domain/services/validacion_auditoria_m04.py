# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M04-158-G086 RF-73: validar catalogo, actor, referencia y payload antes de persistir. |
# | 2026-10-29 | Arekkazu | QA-M04-27-10 CU09 H-02/H-03 RF-73: NOTAS_REGISTRADAS e id_version_deprecada |
# | 2026-10-30 | Arekkazu | INC-M04-229-G070 RF-72/RF-73: VENTANA_RETROALIMENTACION_AMPLIADA |
"""RF-73 E1 y CA-13/15: contrato del evento sin dependencias de persistencia."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Optional
from uuid import UUID

from src.shared.tipo_modelo import POBLACIONAL, paradigma_de


class TipoEventoM04(StrEnum):
    CATALOGO_PATOLOGIA_AGREGADA = "CATALOGO_PATOLOGIA_AGREGADA"
    CATALOGO_PATOLOGIA_MODIFICADA = "CATALOGO_PATOLOGIA_MODIFICADA"
    CATALOGO_PATOLOGIA_INACTIVADA = "CATALOGO_PATOLOGIA_INACTIVADA"
    CONFIGURACION_MOTOR_CAMBIADA = "CONFIGURACION_MOTOR_CAMBIADA"
    INFERENCIA_EJECUTADA = "INFERENCIA_EJECUTADA"
    INFERENCIA_RECHAZADA = "INFERENCIA_RECHAZADA"
    LATENCIA_EXCEDIDA = "LATENCIA_EXCEDIDA"
    INFERENCIA_NO_DISPONIBLE = "INFERENCIA_NO_DISPONIBLE"
    ALERTA_PREDICCION_GENERADA = "ALERTA_PREDICCION_GENERADA"
    HISTORIAL_CONSULTADO = "HISTORIAL_CONSULTADO"
    EXPORTACION_GENERADA = "EXPORTACION_GENERADA"
    RIESGO_CONTAGIO_CALCULADO = "RIESGO_CONTAGIO_CALCULADO"
    ALERTA_CONTAGIO_GENERADA = "ALERTA_CONTAGIO_GENERADA"
    ERROR_DATOS_INSUFICIENTES = "ERROR_DATOS_INSUFICIENTES"
    ERROR_DATOS_DESINCRONIZADOS = "ERROR_DATOS_DESINCRONIZADOS"
    SOBRECARGA_MODELO_CONTAGIO = "SOBRECARGA_MODELO_CONTAGIO"
    ALERTA_CALIDAD_DATOS = "ALERTA_CALIDAD_DATOS"
    VERSION_REGISTRADA = "VERSION_REGISTRADA"
    VERSION_APROBADA = "VERSION_APROBADA"
    VERSION_RECHAZADA = "VERSION_RECHAZADA"
    VERSION_ACTIVADA = "VERSION_ACTIVADA"
    VERSION_DEPRECADA = "VERSION_DEPRECADA"
    NOTAS_REGISTRADAS = "NOTAS_REGISTRADAS"
    HASH_INVALIDO_DETECTADO = "HASH_INVALIDO_DETECTADO"
    INTENTO_CARGA_MODELO_EXTERNO = "INTENTO_CARGA_MODELO_EXTERNO"
    MODELO_DISTRIBUIDO_EDGE = "MODELO_DISTRIBUIDO_EDGE"
    MODELO_ACTIVADO_EDGE = "MODELO_ACTIVADO_EDGE"
    DISTRIBUCION_FALLIDA = "DISTRIBUCION_FALLIDA"
    DISTRIBUCION_POSPUESTA = "DISTRIBUCION_POSPUESTA"
    REENTRENAMIENTO_INICIADO = "REENTRENAMIENTO_INICIADO"
    REENTRENAMIENTO_COMPLETADO = "REENTRENAMIENTO_COMPLETADO"
    REENTRENAMIENTO_FALLIDO = "REENTRENAMIENTO_FALLIDO"
    REENTRENAMIENTO_ABORTADO = "REENTRENAMIENTO_ABORTADO"
    REENTRENAMIENTO_INTERRUMPIDO = "REENTRENAMIENTO_INTERRUMPIDO"
    REENTRENAMIENTO_PAUSADO_POR_PRIORIDAD = "REENTRENAMIENTO_PAUSADO_POR_PRIORIDAD"
    DEGRADACION_DETECTADA = "DEGRADACION_DETECTADA"
    RETROALIMENTACION_REGISTRADA = "RETROALIMENTACION_REGISTRADA"
    CONFLICTO_RETROALIMENTACION = "CONFLICTO_RETROALIMENTACION"
    VENTANA_RETROALIMENTACION_AMPLIADA = "VENTANA_RETROALIMENTACION_AMPLIADA"
    AUDITORIA_EVENTO_INVALIDO = "AUDITORIA_EVENTO_INVALIDO"
    AUDITORIA_FALLA_PERSISTENCIA = "AUDITORIA_FALLA_PERSISTENCIA"
    AUDITORIA_FALLBACK_ACTIVADO = "AUDITORIA_FALLBACK_ACTIVADO"
    TIMESTAMP_CORREGIDO = "TIMESTAMP_CORREGIDO"


@dataclass(frozen=True)
class ResultadoRegistroAuditoriaM04:
    """Aceptado en BD o contingencia; el rechazo E1 no interrumpe al emisor."""

    aceptado: bool
    id_evento: UUID
    codigo: Optional[str] = None
    campos_invalidos: tuple[str, ...] = ()


# Los tipos del catálogo sin esquema específico siguen exigiendo un objeto no vacío.
_PAYLOAD_REQUERIDO: dict[str, tuple[str, ...]] = {
    "INFERENCIA_EJECUTADA": ("activo_biologico_id", "especie", "tipo_modelo", "version_modelo", "nivel_riesgo", "probabilidad_riesgo_alto", "enfermedad_estimada", "latencia_ms", "contexto_incompleto"),
    "INFERENCIA_RECHAZADA": ("activo_biologico_id", "tipo_modelo", "version_modelo", "causa_rechazo"),
    "ALERTA_PREDICCION_GENERADA": ("activo_biologico_id", "tipo_alerta", "nivel_riesgo", "probabilidad", "version_modelo"),
    "LATENCIA_EXCEDIDA": ("activo_biologico_id", "tipo_modelo", "latencia_ms", "umbral_configurado_ms"),
    "VERSION_REGISTRADA": ("tipo_modelo", "id_version"),
    "VERSION_APROBADA": ("tipo_modelo", "id_version"),
    "VERSION_RECHAZADA": ("tipo_modelo", "id_version"),
    "VERSION_ACTIVADA": ("tipo_modelo", "id_version_nueva", "id_version_deprecada"),
    "VERSION_DEPRECADA": ("tipo_modelo", "id_version"),
    "NOTAS_REGISTRADAS": ("tipo_modelo", "id_version", "notas_validacion"),
    "MODELO_DISTRIBUIDO_EDGE": ("device_id", "tipo_modelo", "id_version", "hash_verificado"),
    "HASH_INVALIDO_DETECTADO": ("device_id", "tipo_modelo", "id_version", "hash_esperado", "hash_recibido"),
    "REENTRENAMIENTO_INICIADO": ("tipo_modelo", "trigger_reentrenamiento", "version_modelo_base"),
    "REENTRENAMIENTO_COMPLETADO": ("tipo_modelo", "id_version_generada", "roc_auc_score", "estado_resultado"),
    "DEGRADACION_DETECTADA": ("tipo_modelo", "version_modelo_activa", "umbral_minimo", "periodo_evaluado_dias"),
    "RETROALIMENTACION_REGISTRADA": ("id_resultado_inferencia", "estado_retroalimentacion", "id_usuario_veterinario"),
    "CONFLICTO_RETROALIMENTACION": ("id_resultado_inferencia", "numero_retroalimentaciones"),
    "VENTANA_RETROALIMENTACION_AMPLIADA": ("id_resultado_inferencia", "fecha_limite", "justificacion", "id_usuario_autorizador"),
    "CATALOGO_PATOLOGIA_AGREGADA": ("id_patologia", "nombre"),
    "CATALOGO_PATOLOGIA_MODIFICADA": ("id_patologia",),
    "CATALOGO_PATOLOGIA_INACTIVADA": ("id_patologia",),
    "CONFIGURACION_MOTOR_CAMBIADA": ("accion", "valores_anteriores", "valores_nuevos"),
}
_METRICAS_POBLACIONALES = ("calibracion_completada", "tasa_falsos_positivos_rutina", "tasa_deteccion_eventos_clinicos")
_METRICAS_SUPERVISADAS = ("f1_score_global", "recall_clase_riesgo_alto")


def campos_requeridos(tipo_evento: str, payload: dict) -> list[str]:
    TipoEventoM04(tipo_evento)  # Un tipo desconocido nunca equivale a un esquema vacío.
    requeridos = list(_PAYLOAD_REQUERIDO.get(tipo_evento, ()))
    tipo_modelo = payload.get("tipo_modelo")
    poblacional = isinstance(tipo_modelo, str) and paradigma_de(tipo_modelo) == POBLACIONAL
    if tipo_evento in {"VERSION_APROBADA", "VERSION_RECHAZADA", "REENTRENAMIENTO_COMPLETADO"}:
        requeridos += list(_METRICAS_POBLACIONALES if poblacional else _METRICAS_SUPERVISADAS)
    if tipo_evento == "DEGRADACION_DETECTADA":
        # RFC-009: métricas poblacionales equivalentes, sin exigir F1 a ese paradigma.
        requeridos += list(_METRICAS_POBLACIONALES if poblacional else ("f1_score_evaluado",))
    if tipo_evento == "REENTRENAMIENTO_INICIADO" and payload.get("trigger_reentrenamiento") == "MANUAL":
        requeridos.append("id_usuario_ejecucion")
    # RF-69 E3: hash inválido antes de crear versión/distribuir a un dispositivo.
    if tipo_evento == "HASH_INVALIDO_DETECTADO" and "id_proceso_rf71" in payload and "device_id" not in payload:
        requeridos = ["id_proceso_rf71", "hash_declarado", "hash_calculado"]
    return requeridos


def validar_evento(*, tipo_evento: str, tipo_actor: str, id_usuario: Optional[int],
                   id_sistema: Optional[str], id_referencia: Optional[str], payload_evento: object) -> tuple[str, ...]:
    errores: list[str] = []
    try:
        TipoEventoM04(tipo_evento)
    except (ValueError, TypeError):
        errores.append("tipo_evento")
    if id_referencia is None or not str(id_referencia).strip():
        errores.append("id_referencia")
    if tipo_actor == "USUARIO":
        if id_usuario is None or id_sistema is not None:
            errores.append("actor")
    elif isinstance(tipo_actor, str) and tipo_actor in {"SISTEMA", "DISPOSITIVO_EDGE"}:
        if not isinstance(id_sistema, str) or not id_sistema.strip() or id_usuario is not None:
            errores.append("actor")
    else:
        errores.append("tipo_actor")
    if not isinstance(payload_evento, dict) or not payload_evento:
        errores.append("payload_evento")
    elif "tipo_evento" not in errores:
        errores += ["payload_evento." + c for c in campos_requeridos(tipo_evento, payload_evento) if c not in payload_evento]
    return tuple(errores)
