# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | RF-66: el motor IA devuelve sus resultados al backend            |
# | 2026-10-30 | Arekkazu | RF-66: resuelve la patología base por código RF-64               |
# | 2026-10-31 | Arekkazu     | RFC-010 RF-69: versión por animal, estado SOMBRA y fuente de datos |
"""RF-66 — Registrar un resultado del motor IA (`motor-ia`) en ``modulo4.resultados_inferencia``.

Postcondición 1: el resultado queda persistido de forma inmutable y alimenta RF-67
(historial), RF-72 (retroalimentación) y el monitor. RF-73: ``INFERENCIA_EJECUTADA`` y,
si pasó de 2 s (CA-1), ``LATENCIA_EXCEDIDA``.

Solo se aceptan resultados en modo sombra: los modelos entregados (ET-02 v5, ET-03 v5)
son sintéticos y no autorizan alertas, y la Postcondición 2 (alerta en RF-57 con tipo
PREDICCION_PATOLOGIA) todavía no está conectada. Un resultado vinculante se rechaza en
vez de guardarse como si hubiera alertado.

Idempotente: el motor genera ``id_resultado_inferencia``; un reintento con el mismo id
devuelve el resultado ya guardado con ``duplicado=True`` (2xx, para que el motor no
reintente sin fin).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.prediction.domain.entities.resultado_inferencia import LATENCIA_MAXIMA_MS, ResultadoInferencia
from src.prediction.domain.repositories.activo_biologico_port import ActivoBiologicoPort
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.patologia_m04_repository import PatologiaM04Repository
from src.prediction.domain.repositories.resultado_inferencia_repository import ResultadoInferenciaRepository
from src.prediction.domain.repositories.version_modelo_port import VersionModeloPort
from src.prediction.infrastructure.dto.registrar_resultado_inferencia_dto import RegistrarResultadoInferenciaDTO
from src.shared.errors import BusinessRuleError, NotFoundError

logger = logging.getLogger(__name__)

ID_SISTEMA_MOTOR = "MOTOR_IA"
_ESTADOS_NO_UTILIZABLES = {"DEPRECADO", "RECHAZADO"}
#: RF-73 origen_dato (dónde ocurrió) a partir del modo_ejecucion de RF-66.
_ORIGEN_POR_MODO = {"EDGE": "EDGE", "SERVIDOR": "BACKEND", "HIBRIDO": "HIBRIDO"}


@dataclass(frozen=True)
class ResultadoRegistro:
    resultado: ResultadoInferencia
    duplicado: bool


class RegistrarResultadoInferenciaUseCase:
    def __init__(
        self,
        *,
        db: Session,
        repo: ResultadoInferenciaRepository,
        version_port: VersionModeloPort,
        activo_port: ActivoBiologicoPort,
        auditoria_repo: EventoAuditoriaM04Repository,
        patologia_repo: PatologiaM04Repository,
    ) -> None:
        self.db = db
        self.repo = repo
        self.version_port = version_port
        self.activo_port = activo_port
        self.auditoria_repo = auditoria_repo
        self.patologia_repo = patologia_repo

    def execute(self, dto: RegistrarResultadoInferenciaDTO) -> ResultadoRegistro:
        existente = self.repo.obtener(dto.id_resultado_inferencia)
        if existente is not None:
            return ResultadoRegistro(existente, duplicado=True)

        if not dto.modo_sombra:
            raise BusinessRuleError(
                code="INFERENCIA_VINCULANTE_NO_DISPONIBLE",
                message="Solo se registran resultados en modo sombra: la alerta de RF-57 para "
                        "resultados vinculantes aún no está conectada.",
                field="modo_sombra",
            )

        llave = self.version_port.obtener_llave(dto.id_version_modelo)
        if llave is None:
            raise NotFoundError(
                code="VERSION_MODELO_NO_ENCONTRADA",
                message=f"No existe la versión de modelo {dto.id_version_modelo} en RF-69.",
                field="id_version_modelo",
            )
        estado, tipo_modelo, _componente, id_activo_version = llave
        if estado in _ESTADOS_NO_UTILIZABLES:
            raise BusinessRuleError(
                code="VERSION_MODELO_NO_UTILIZABLE",
                message=f"La versión {dto.id_version_modelo} está {estado} y no puede producir resultados.",
                field="id_version_modelo",
            )
        if tipo_modelo != dto.tipo_modelo:
            raise BusinessRuleError(
                code="TIPO_MODELO_NO_COINCIDE",
                message=f"La versión {dto.id_version_modelo} es de {tipo_modelo}, no de {dto.tipo_modelo}.",
                field="tipo_modelo",
            )

        # RFC-010: el modelo INDIVIDUAL de un animal no produce resultados de otro.
        if id_activo_version is not None and id_activo_version != dto.id_activo_biologico:
            raise BusinessRuleError(
                code="VERSION_DE_OTRO_ACTIVO",
                message=(
                    f"La versión {dto.id_version_modelo} es del activo {id_activo_version}, "
                    f"no del {dto.id_activo_biologico}."
                ),
                field="id_activo_biologico",
            )

        id_especie = self.activo_port.obtener_especie(dto.id_activo_biologico)
        if id_especie is None:
            raise NotFoundError(
                code="ACTIVO_NO_ENCONTRADO",
                message=f"No existe el activo biológico {dto.id_activo_biologico}.",
                field="id_activo_biologico",
            )

        datos = dto.model_dump(exclude={"codigo_patologia_rf64"})
        if datos["id_patologia"] is None and dto.codigo_patologia_rf64 is not None:
            datos["id_patologia"] = self.patologia_repo.id_base_por_codigo_rf64(dto.codigo_patologia_rf64)
            if datos["id_patologia"] is None:
                # Las probabilidades conservan el diagnóstico: no se pierde el resultado por esto.
                logger.warning("RF-66: no hay patología base RF-64 con código %s; resultado %s sin patología.",
                               dto.codigo_patologia_rf64, dto.id_resultado_inferencia)
        resultado = ResultadoInferencia(**datos, id_especie=id_especie)
        try:
            self.repo.guardar(resultado)
            self._auditar(resultado)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return ResultadoRegistro(resultado, duplicado=False)

    def _auditar(self, r: ResultadoInferencia) -> None:
        comunes = dict(
            tipo_actor="SISTEMA", id_sistema=ID_SISTEMA_MOTOR,
            id_referencia=str(r.id_resultado_inferencia), entidad_referencia="resultado_inferencia",
            origen_dato=_ORIGEN_POR_MODO[r.modo_ejecucion], timestamp_evento=r.fecha_inferencia,
        )
        self.auditoria_repo.registrar(
            tipo_evento="INFERENCIA_EJECUTADA", severidad_evento="INFO", resultado_operacion="EXITOSO",
            payload_evento={
                "activo_biologico_id": r.id_activo_biologico,
                "especie": r.id_especie,
                "tipo_modelo": r.tipo_modelo,
                "version_modelo": r.id_version_modelo,
                "nivel_riesgo": r.nivel_riesgo,
                # Las claves de probabilidad_riesgo son los niveles 0-3; "3" es Riesgo Alto.
                "probabilidad_riesgo_alto": r.probabilidad_riesgo.get("3"),
                "enfermedad_estimada": r.id_patologia,
                "latencia_ms": r.latencia_ms,
                "contexto_incompleto": r.contexto_incompleto,
                "modo_sombra": r.modo_sombra,
            },
            **comunes,
        )
        if r.latencia_excedida:
            self.auditoria_repo.registrar(
                tipo_evento="LATENCIA_EXCEDIDA", severidad_evento="WARNING", resultado_operacion="EXITOSO",
                payload_evento={
                    "activo_biologico_id": r.id_activo_biologico,
                    "tipo_modelo": r.tipo_modelo,
                    "latencia_ms": r.latencia_ms,
                    "umbral_configurado_ms": LATENCIA_MAXIMA_MS,
                },
                **comunes,
            )
