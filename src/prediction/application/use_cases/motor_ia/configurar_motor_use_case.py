from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from src.prediction.domain.entities.configuracion_motor_ia import ConfiguracionMotorIA
from src.prediction.domain.repositories.configuracion_motor_ia_repository import ConfiguracionMotorIARepository
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.nodo_edge_port import NodoEdgePort
from src.prediction.domain.repositories.version_modelo_port import VersionModeloPort
from src.prediction.infrastructure.dto.configurar_motor_dto import ConfigurarMotorDTO
from src.shared.errors import BusinessRuleError, NotFoundError, PreconditionFailedError

_TIPOS_VALIDOS = {"ESPECIES_PEQUEÑAS", "ESPECIES_MEDIANAS", "ESPECIES_GRANDES", "CONTAGIO"}
_MODOS_VALIDOS = {"EDGE", "SERVIDOR", "HIBRIDO"}
_ESTADO_ACTIVO = "ACTIVO"


class ConfigurarMotorUseCase:
    def __init__(
        self,
        *,
        db: Session,
        repo: ConfiguracionMotorIARepository,
        auditoria_repo: EventoAuditoriaM04Repository,
        version_port: VersionModeloPort,
        nodo_edge_port: NodoEdgePort,
    ) -> None:
        self._db = db
        self._repo = repo
        self._auditoria_repo = auditoria_repo
        self._version_port = version_port
        self._nodo_edge_port = nodo_edge_port

    def execute(self, dto: ConfigurarMotorDTO, id_usuario: int) -> tuple[ConfiguracionMotorIA, bool]:
        """Devuelve (entidad, es_nueva) donde es_nueva=True si fue INSERT, False si fue UPDATE."""
        self._validar(dto)

        existente = self._repo.obtener_por_tipo(dto.tipo_modelo)
        snapshot_anterior = existente._snapshot() if existente else None

        if existente is None:
            entidad = ConfiguracionMotorIA.crear(
                tipo_modelo=dto.tipo_modelo,
                umbral_riesgo_alto=dto.umbral_riesgo_alto,
                umbral_alerta_critica=dto.umbral_alerta_critica,
                ventana_temporal_min=dto.ventana_temporal_min,
                modo_ejecucion=dto.modo_ejecucion,
                w_factor_sanitario=dto.w_factor_sanitario,
                w_factor_ambiental=dto.w_factor_ambiental,
                w_factor_densidad=dto.w_factor_densidad,
                id_usuario_responsable=id_usuario,
                id_version_modelo_activa=dto.id_version_modelo_activa,
                temp_min_config=dto.temp_min_config,
                temp_max_config=dto.temp_max_config,
                hr_min_config=dto.hr_min_config,
                hr_max_config=dto.hr_max_config,
                densidad_maxima_config=dto.densidad_maxima_config,
            )
            es_nueva = True
        else:
            existente.actualizar(
                umbral_riesgo_alto=dto.umbral_riesgo_alto,
                umbral_alerta_critica=dto.umbral_alerta_critica,
                ventana_temporal_min=dto.ventana_temporal_min,
                modo_ejecucion=dto.modo_ejecucion,
                w_factor_sanitario=dto.w_factor_sanitario,
                w_factor_ambiental=dto.w_factor_ambiental,
                w_factor_densidad=dto.w_factor_densidad,
                id_usuario_responsable=id_usuario,
                id_version_modelo_activa=dto.id_version_modelo_activa,
                temp_min_config=dto.temp_min_config,
                temp_max_config=dto.temp_max_config,
                hr_min_config=dto.hr_min_config,
                hr_max_config=dto.hr_max_config,
                densidad_maxima_config=dto.densidad_maxima_config,
            )
            entidad = existente
            es_nueva = False

        try:
            if es_nueva:
                entidad = self._repo.guardar(entidad)
            else:
                entidad = self._repo.actualizar(entidad)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        self._auditoria_repo.registrar(
            tipo_evento="CONFIGURACION_MOTOR_CAMBIADA",
            tipo_actor="USUARIO",
            id_usuario=id_usuario,
            id_referencia=str(entidad.id_configuracion_motor),
            entidad_referencia="configuracion_motor_ia",
            resultado_operacion="EXITOSO",
            payload_evento={
                "accion": "CREADA" if es_nueva else "ACTUALIZADA",
                "valores_anteriores": snapshot_anterior,
                "valores_nuevos": entidad._snapshot(),
            },
        )
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()

        return entidad, es_nueva

    def _validar(self, dto: ConfigurarMotorDTO) -> None:
        if dto.tipo_modelo not in _TIPOS_VALIDOS:
            raise BusinessRuleError(
                code="TIPO_MODELO_INVALIDO",
                message=f"tipo_modelo debe ser uno de: {sorted(_TIPOS_VALIDOS)}.",
                field="tipo_modelo",
            )
        if dto.modo_ejecucion not in _MODOS_VALIDOS:
            raise BusinessRuleError(
                code="MODO_EJECUCION_INVALIDO",
                message=f"modo_ejecucion debe ser uno de: {sorted(_MODOS_VALIDOS)}.",
                field="modo_ejecucion",
            )

        # FA-01: rangos de umbrales
        if not (Decimal("0.50") <= dto.umbral_riesgo_alto <= Decimal("0.95")):
            raise BusinessRuleError(
                code="UMBRAL_RIESGO_FUERA_RANGO",
                message="umbral_riesgo_alto debe estar entre 0.50 y 0.95.",
                field="umbral_riesgo_alto",
            )
        if not (Decimal("0.50") <= dto.umbral_alerta_critica <= Decimal("0.95")):
            raise BusinessRuleError(
                code="UMBRAL_CRITICA_FUERA_RANGO",
                message="umbral_alerta_critica debe estar entre 0.50 y 0.95.",
                field="umbral_alerta_critica",
            )

        # FA-02: umbral_alerta_critica ≥ umbral_riesgo_alto
        if dto.umbral_alerta_critica < dto.umbral_riesgo_alto:
            raise BusinessRuleError(
                code="UMBRAL_CRITICA_MENOR_QUE_RIESGO",
                message="umbral_alerta_critica debe ser mayor o igual a umbral_riesgo_alto.",
                field="umbral_alerta_critica",
            )

        # FA-01: ventana temporal
        if not (5 <= dto.ventana_temporal_min <= 15):
            raise BusinessRuleError(
                code="VENTANA_TEMPORAL_FUERA_RANGO",
                message="ventana_temporal_min debe estar entre 5 y 15 minutos.",
                field="ventana_temporal_min",
            )

        # Pesos de contagio: suma = 1.0 (tolerancia 0.001)
        suma = dto.w_factor_sanitario + dto.w_factor_ambiental + dto.w_factor_densidad
        if abs(suma - Decimal("1.000")) >= Decimal("0.001"):
            raise BusinessRuleError(
                code="PESOS_CONTAGIO_INVALIDOS",
                message="La suma de w_factor_sanitario + w_factor_ambiental + w_factor_densidad debe ser 1.0.",
                field="w_factor_sanitario",
            )

        # FA-03: si se indica versión de modelo, debe existir y ser ACTIVO
        if dto.id_version_modelo_activa is not None:
            estado = self._version_port.obtener_estado(dto.id_version_modelo_activa)
            if estado is None:
                raise NotFoundError(
                    code="VERSION_MODELO_NO_ENCONTRADA",
                    message=f"No existe la versión de modelo con id {dto.id_version_modelo_activa}.",
                    field="id_version_modelo_activa",
                )
            if estado != _ESTADO_ACTIVO:
                raise PreconditionFailedError(
                    code="MODELO_NO_ACTIVO",
                    message=(
                        f"La versión {dto.id_version_modelo_activa} está en estado '{estado}'. "
                        "Solo se pueden vincular modelos en estado ACTIVO."
                    ),
                    field="id_version_modelo_activa",
                )

        # FA-08: modo EDGE/HIBRIDO requiere nodos disponibles
        if dto.modo_ejecucion in ("EDGE", "HIBRIDO"):
            if not self._nodo_edge_port.hay_nodos_activos(dto.tipo_modelo):
                raise BusinessRuleError(
                    code="MODO_EDGE_SIN_NODOS",
                    message=(
                        "No hay nodos Edge activos disponibles para este tipo de modelo. "
                        "Complete la distribución OTA (RF-70) o seleccione modo SERVIDOR."
                    ),
                    field="modo_ejecucion",
                )
