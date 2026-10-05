from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.prediction.domain.entities.configuracion_motor_ia import ConfiguracionMotorIA
from src.prediction.domain.repositories.configuracion_motor_ia_repository import ConfiguracionMotorIARepository
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.nodo_edge_port import NodoEdgePort
from src.prediction.domain.repositories.version_modelo_port import VersionModeloPort
from src.prediction.infrastructure.dto.configurar_motor_dto import ConfigurarMotorDTO
from src.shared.errors import BusinessRuleError, NotFoundError, PreconditionFailedError
from src.shared.tipo_modelo import TIPOS_MODELO, es_poblacional

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
        por_paradigma = self._validar(dto)

        existente = self._repo.obtener_por_tipo(dto.tipo_modelo)
        snapshot_anterior = existente._snapshot() if existente else None

        if existente is None:
            entidad = ConfiguracionMotorIA.crear(
                tipo_modelo=dto.tipo_modelo,
                ventana_temporal_min=dto.ventana_temporal_min,
                modo_ejecucion=dto.modo_ejecucion,
                w_factor_sanitario=dto.w_factor_sanitario,
                w_factor_ambiental=dto.w_factor_ambiental,
                w_factor_densidad=dto.w_factor_densidad,
                id_usuario_responsable=id_usuario,
                temp_min_config=dto.temp_min_config,
                temp_max_config=dto.temp_max_config,
                hr_min_config=dto.hr_min_config,
                hr_max_config=dto.hr_max_config,
                densidad_maxima_config=dto.densidad_maxima_config,
                **por_paradigma,
            )
            es_nueva = True
        else:
            existente.actualizar(
                ventana_temporal_min=dto.ventana_temporal_min,
                modo_ejecucion=dto.modo_ejecucion,
                w_factor_sanitario=dto.w_factor_sanitario,
                w_factor_ambiental=dto.w_factor_ambiental,
                w_factor_densidad=dto.w_factor_densidad,
                id_usuario_responsable=id_usuario,
                temp_min_config=dto.temp_min_config,
                temp_max_config=dto.temp_max_config,
                hr_min_config=dto.hr_min_config,
                hr_max_config=dto.hr_max_config,
                densidad_maxima_config=dto.densidad_maxima_config,
                **por_paradigma,
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

    def _validar(self, dto: ConfigurarMotorDTO) -> dict:
        """Valida el DTO y devuelve los campos que dependen del paradigma (RFC-009).

        Los campos que no aplican al paradigma se descartan en vez de rechazarse,
        con el mismo criterio de campos no aplicables de RF-16.
        """
        if dto.tipo_modelo not in TIPOS_MODELO:
            raise BusinessRuleError(
                code="TIPO_MODELO_INVALIDO",
                message=f"tipo_modelo debe ser uno de: {sorted(TIPOS_MODELO)}.",
                field="tipo_modelo",
            )
        if dto.modo_ejecucion not in _MODOS_VALIDOS:
            raise BusinessRuleError(
                code="MODO_EJECUCION_INVALIDO",
                message=f"modo_ejecucion debe ser uno de: {sorted(_MODOS_VALIDOS)}.",
                field="modo_ejecucion",
            )

        self._validar_comunes(dto)
        if es_poblacional(dto.tipo_modelo):
            return self._validar_poblacional(dto)
        return self._validar_individual_o_meta(dto)

    def _validar_poblacional(self, dto: ConfigurarMotorDTO) -> dict:
        # RF-65 v2.0: un score de anomalía no tiene par, así que no hay orden que validar.
        umbral = dto.umbral_score_anomalia
        if umbral is None or not (Decimal("0") <= umbral <= Decimal("1")):
            raise BusinessRuleError(
                code="UMBRAL_SCORE_ANOMALIA_FUERA_RANGO",
                message="umbral_score_anomalia es obligatorio para modelos POBLACIONAL y debe estar entre 0 y 1.",
                field="umbral_score_anomalia",
            )
        versiones = dto.versiones_activas_por_componente or None
        for componente, id_version in (versiones or {}).items():
            self._validar_version(id_version, dto.tipo_modelo, componente, "versiones_activas_por_componente")
        return {
            "umbral_riesgo_alto": None,
            "umbral_alerta_critica": None,
            "umbral_score_anomalia": umbral,
            "id_version_modelo_activa": None,
            "versiones_activas_por_componente": versiones,
        }

    def _validar_individual_o_meta(self, dto: ConfigurarMotorDTO) -> dict:
        if dto.umbral_riesgo_alto is None or dto.umbral_alerta_critica is None:
            raise BusinessRuleError(
                code="UMBRALES_REQUERIDOS",
                message="umbral_riesgo_alto y umbral_alerta_critica son obligatorios para modelos INDIVIDUAL y META.",
                field="umbral_riesgo_alto" if dto.umbral_riesgo_alto is None else "umbral_alerta_critica",
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

        # FA-03: si se indica versión de modelo, debe existir, ser ACTIVO y del mismo tipo
        if dto.id_version_modelo_activa is not None:
            self._validar_version(dto.id_version_modelo_activa, dto.tipo_modelo, None, "id_version_modelo_activa")
        return {
            "umbral_riesgo_alto": dto.umbral_riesgo_alto,
            "umbral_alerta_critica": dto.umbral_alerta_critica,
            "umbral_score_anomalia": None,
            "id_version_modelo_activa": dto.id_version_modelo_activa,
            "versiones_activas_por_componente": None,
        }

    def _validar_version(self, id_version: int, tipo_modelo: str, componente: Optional[str], campo: str) -> None:
        """RF-65 4.e: la versión vinculada existe, está ACTIVO y su llave (tipo_modelo, componente) coincide."""
        llave = self._version_port.obtener_llave(id_version)
        if llave is None:
            raise NotFoundError(
                code="VERSION_MODELO_NO_ENCONTRADA",
                message=f"No existe la versión de modelo con id {id_version}.",
                field=campo,
            )
        estado, tipo_version, componente_version = llave
        if estado != _ESTADO_ACTIVO:
            raise PreconditionFailedError(
                code="MODELO_NO_ACTIVO",
                message=(
                    f"La versión {id_version} está en estado '{estado}'. "
                    "Solo se pueden vincular modelos en estado ACTIVO."
                ),
                field=campo,
            )
        if (tipo_version, componente_version) != (tipo_modelo, componente):
            raise BusinessRuleError(
                code="VERSION_MODELO_INCOMPATIBLE",
                message=(
                    f"La versión {id_version} es de ({tipo_version}, {componente_version}) y no corresponde "
                    f"a ({tipo_modelo}, {componente})."
                ),
                field=campo,
            )

    def _validar_comunes(self, dto: ConfigurarMotorDTO) -> None:
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
