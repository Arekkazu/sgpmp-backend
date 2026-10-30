# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-26 | Arekkazu | INC-M04-196-G026 RF-68: modelo de estimación de riesgo de contagio |
# | 2026-10-30 | Leandro | INC-M04-221-G032 RF-68: ejecutar MVP sin caché, conservar controles y registrar el aviso E10 con resultado válido. |
"""RF-68 — Ejecutar el modelo de riesgo de contagio de un lote.

Flujo: acceso al lote → configuración activa de RF-65 → caché/frecuencia (5.1) →
cálculo (``calcular_riesgo_contagio``) → persistencia (paso 9) → RF-73 → alerta
RIESGO_CONTAGIO hacia RF-57 si es Alto y la confianza no es baja (paso 8, CA-3, CA-6).

Fuera de alcance: la cola de concurrencia por lote (máx. 3 en curso, FIFO de 10) y la
agregación de 5 min del historial. Cada solicitud corre sola y la tasa por lote se
limita con el mínimo de 5 s entre ejecuciones.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from src.prediction.domain.entities.riesgo_contagio import (
    DatosContagioError,
    PESOS_POR_DEFECTO,
    LecturaAmbiental,
    ParametrosContagio,
    ResultadoRiesgoContagio,
    SalidaInferencia,
    calcular_riesgo_contagio,
)
from src.prediction.domain.repositories.activo_biologico_port import ActivoBiologicoPort
from src.prediction.domain.repositories.alerta_contagio_port import AlertaContagioPort
from src.prediction.domain.repositories.configuracion_motor_ia_repository import ConfiguracionMotorIARepository
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.resultado_riesgo_contagio_repository import (
    ResultadoRiesgoContagioRepository,
)
from src.prediction.infrastructure.dto.estimar_riesgo_contagio_dto import EstimarRiesgoContagioDTO
from src.shared.errors import BusinessRuleError, NotFoundError, TooManyRequestsError

TIPO_MODELO = "MODELO_RIESGO_CONTAGIO"
#: Restricciones: mínimo 5 s entre ejecuciones por lote (≤ 12/min); con las mismas
#: entradas dentro de esa ventana se reutiliza el resultado (5.1).
INTERVALO_MINIMO = timedelta(seconds=5)
#: E10: más de 5 ejecuciones consecutivas degradadas → ALERTA_CALIDAD_DATOS.
MAX_DEGRADADAS_CONSECUTIVAS = 5


class EstimarRiesgoContagioUseCase:

    def __init__(
        self,
        *,
        db: Session,
        config_repo: ConfiguracionMotorIARepository,
        resultado_repo: ResultadoRiesgoContagioRepository,
        activo_port: ActivoBiologicoPort,
        alerta_port: AlertaContagioPort,
        auditoria_repo: EventoAuditoriaM04Repository,
    ) -> None:
        self.db = db
        self.config_repo = config_repo
        self.resultado_repo = resultado_repo
        self.activo_port = activo_port
        self.alerta_port = alerta_port
        self.auditoria_repo = auditoria_repo

    def execute(self, dto: EstimarRiesgoContagioDTO, id_usuario: int, id_rol: int) -> ResultadoRiesgoContagio:
        if not self.activo_port.activo_existe_y_accesible(dto.id_lote, id_usuario, id_rol):
            raise NotFoundError(code="LOTE_NO_ENCONTRADO", message=f"No existe el lote {dto.id_lote}.", field="id_lote")
        config = self.config_repo.obtener_por_tipo(TIPO_MODELO)
        if config is None or not config.es_activa:
            raise BusinessRuleError(
                code="CONFIGURACION_CONTAGIO_NO_DEFINIDA",
                message="No hay una configuración activa de MODELO_RIESGO_CONTAGIO en RF-65 (pesos y rangos).",
            )

        perfil = getattr(config, "perfil_calculo_contagio", "ESTANDAR")
        es_mvp = perfil == "MVP"
        ahora = datetime.now(timezone.utc)
        huella = self._huella(dto, config.config_version)
        anteriores = self.resultado_repo.ultimos_por_lote(dto.id_lote, MAX_DEGRADADAS_CONSECUTIVAS + 1)
        if (not es_mvp and anteriores
                and getattr(anteriores[0], "perfil_calculo_contagio", "ESTANDAR") == perfil
                and ahora - anteriores[0].fecha_calculo < INTERVALO_MINIMO):
            if anteriores[0].huella_entradas == huella:
                anteriores[0].desde_cache = True
                return anteriores[0]
            espera = INTERVALO_MINIMO - (ahora - anteriores[0].fecha_calculo)
            raise TooManyRequestsError(
                code="EJECUCION_CONTAGIO_MUY_FRECUENTE",
                message="El modelo de contagio de este lote se ejecutó hace menos de 5 segundos.",
                headers={"Retry-After": str(max(1, int(espera.total_seconds()) + 1))},
            )

        try:
            resultado = calcular_riesgo_contagio(
                id_lote=dto.id_lote,
                parametros=ParametrosContagio(
                    w_fs=PESOS_POR_DEFECTO["fs"] if es_mvp else config.w_factor_sanitario,
                    w_fa=PESOS_POR_DEFECTO["fa"] if es_mvp else config.w_factor_ambiental,
                    w_fd=PESOS_POR_DEFECTO["fd"] if es_mvp else config.w_factor_densidad,
                    temp_min=config.temp_min_config, temp_max=config.temp_max_config,
                    hr_min=config.hr_min_config, hr_max=config.hr_max_config,
                    densidad_maxima=config.densidad_maxima_config,
                ),
                ahora=ahora,
                salidas_rf66=[SalidaInferencia(s.probabilidad_riesgo_alto, s.fecha_inferencia, s.id_activo_biologico)
                              for s in dto.salidas_rf66],
                total_activos_lote=dto.total_activos_lote,
                n_enfermos_detectados=dto.n_enfermos_detectados,
                score_anomalia=dto.score_anomalia,
                ambiente=LecturaAmbiental(**dto.variables_ambientales.model_dump()) if dto.variables_ambientales else None,
                densidad_poblacional=dto.densidad_poblacional,
                porcentaje_sensores_activos=dto.porcentaje_sensores_activos,
            )
        except DatosContagioError as exc:
            self._registrar_no_ejecutado(exc, dto, id_usuario, config.id_configuracion_motor, perfil)
            raise BusinessRuleError(code=exc.codigo, message=exc.mensaje) from exc

        resultado.perfil_calculo_contagio = perfil
        resultado.id_configuracion_motor = config.id_configuracion_motor
        resultado.config_version = config.config_version
        resultado.id_area_productiva = self.alerta_port.area_del_lote(dto.id_lote)
        resultado.huella_entradas = huella
        if dto.variables_ambientales:
            resultado.variables_ambientales = dto.variables_ambientales.model_dump(mode="json")

        degradadas = 0
        for anterior in anteriores:
            if not anterior.confianza_baja:
                break
            degradadas += 1
        try:
            self.resultado_repo.guardar(resultado)
            self._auditar("RIESGO_CONTAGIO_CALCULADO", resultado, id_usuario, "EXITOSO",
                          "WARNING" if resultado.confianza_baja else "INFO")
            calidad_suspendida = resultado.confianza_baja and degradadas + 1 > MAX_DEGRADADAS_CONSECUTIVAS
            if calidad_suspendida:
                self._auditar("ALERTA_CALIDAD_DATOS", resultado, id_usuario, "PARCIAL", "WARNING",
                              extra={"ejecuciones_degradadas_consecutivas": degradadas + 1})
            # CA-3 / CA-6 / E10: solo con confianza normal se alerta.
            if resultado.nivel_riesgo_contagio == 2 and not resultado.confianza_baja:
                resultado.alerta_id = self.alerta_port.emitir(resultado)
                self.resultado_repo.asociar_alerta(resultado.id_resultado_contagio, resultado.alerta_id)
                self._auditar("ALERTA_CONTAGIO_GENERADA", resultado, id_usuario, "EXITOSO", "WARNING",
                              extra={"id_alerta": resultado.alerta_id})
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return resultado

    @staticmethod
    def _huella(dto: EstimarRiesgoContagioDTO, config_version: int) -> str:
        """5.1: mismas entradas (Fs, ambiente, densidad) y misma configuración."""
        cuerpo = json.dumps({"dto": dto.model_dump(mode="json"), "config_version": config_version}, sort_keys=True)
        return hashlib.sha256(cuerpo.encode()).hexdigest()

    def _auditar(self, tipo_evento, resultado, id_usuario, resultado_operacion, severidad, extra=None) -> None:
        payload = {
            "id_lote": resultado.id_lote,
            "id_resultado_contagio": resultado.id_resultado_contagio,
            "probabilidad_contagio": str(resultado.probabilidad_contagio),
            "nivel_riesgo_contagio": resultado.nivel_texto,
            "confianza_baja": resultado.confianza_baja,
            "data_quality_score": str(resultado.data_quality_score),
            "factores_ausentes": resultado.factores_ausentes,
            "motivos_degradacion": resultado.motivos_degradacion,
            "config_version": resultado.config_version,
            "perfil_calculo_contagio": resultado.perfil_calculo_contagio,
            "pesos_aplicados": {k: str(v) for k, v in resultado.pesos_aplicados.items()},
            **(extra or {}),
        }
        self.auditoria_repo.registrar(
            tipo_evento=tipo_evento, tipo_actor="USUARIO", id_usuario=id_usuario,
            id_referencia=str(resultado.id_lote), entidad_referencia="lote",
            severidad_evento=severidad, resultado_operacion=resultado_operacion, payload_evento=payload,
        )

    def _registrar_no_ejecutado(self, exc: DatosContagioError, dto, id_usuario: int, id_configuracion: int,
                               perfil_calculo_contagio: str = "ESTANDAR") -> None:
        """E4/E8/CA-10 y sincronización: el intento queda en RF-73 aunque el modelo no corra."""
        tipo = exc.codigo if exc.codigo in ("ERROR_DATOS_INSUFICIENTES", "ERROR_DATOS_DESINCRONIZADOS") \
            else "RIESGO_CONTAGIO_CALCULADO"
        try:
            self.auditoria_repo.registrar(
                tipo_evento=tipo, tipo_actor="USUARIO", id_usuario=id_usuario,
                id_referencia=str(dto.id_lote), entidad_referencia="lote", severidad_evento="WARNING",
                resultado_operacion="FALLIDO", codigo_error=exc.codigo, descripcion_error=exc.mensaje,
                payload_evento={"id_lote": dto.id_lote, "id_configuracion_motor": id_configuracion,
                                "motivo": exc.mensaje, "perfil_calculo_contagio": perfil_calculo_contagio},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
