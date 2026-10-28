# | Fecha      | Nombre  | Que se hizo                                                |
# |------------|---------|------------------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-49 RF-57: historial por trigger y diagnostico de calidad |
# | 2026-10-21 | Leandro | DEV-41 RF-57: reutiliza consolidacion atomica e historial SQL |
# | 2026-10-28 | destroyerban | INC-M03-162-G68 RF-57: severidad por bandas de Fase 5, escalada THI y FALLO_AMBIENTAL técnica |
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.telemetry.domain.entities import reglas_base_rf57
from src.telemetry.domain.entities.alerta import (
    TIPO_ALERTA_TECNICA,
    Alerta,
    ConflictoResolucion,
    EstadoAlerta,
    OrigenEventoAlerta,
    ResultadoGeneracionAlerta,
    SeveridadAlerta,
    TipoAlerta,
)
from src.telemetry.domain.repositories.alerta_repository import AlertaRepository
from src.telemetry.domain.repositories.historico_estado_alerta_repository import HistoricoEstadoAlertaRepository
from src.telemetry.domain.repositories.parametros_alertas_port import ParametrosAlertasPort
from src.telemetry.domain.repositories.regla_alerta_repository import ReglaAlertaRepository
from src.telemetry.domain.repositories.variable_alerta_port import RangoFisicoVariable, VariableAlertaPort
from src.telemetry.domain.repositories.bitacora_auditoria_iot_repository import BitacoraAuditoriaIotRepository
from src.telemetry.domain.entities.evento_auditoria_iot import ComponenteOrigen, EntidadAfectadaTipo, SeveridadLog, TipoResultado
from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import RegistrarEventoAuditoriaIotUseCase
from src.telemetry.infrastructure.dto.procesar_evento_alerta_dto import ProcesarEventoAlertaDTO

# Mapa tipo_variable → tipo_alerta para reglas simples
_VARIABLE_A_TIPO_ALERTA: dict[str, str] = {
    "TEMPERATURA_AMBIENTAL": TipoAlerta.ESTRES_TERMICO,
    "HUMEDAD_RELATIVA": TipoAlerta.ESTRES_TERMICO,
    "NH3": TipoAlerta.SINDROME_RESPIRATORIO,
    "CO2": TipoAlerta.SINDROME_RESPIRATORIO,
    "TEMPERATURA_CORPORAL": TipoAlerta.FIEBRE,
    "TEMP_CORPORAL": TipoAlerta.FIEBRE,
    "FRECUENCIA_CARDIACA": TipoAlerta.FIEBRE,
    "FRECUENCIA_RESPIRATORIA": TipoAlerta.SINDROME_RESPIRATORIO,
    "ACTIVIDAD_MOVIMIENTO": TipoAlerta.INACTIVIDAD_ANORMAL,
    "ACTIVIDAD": TipoAlerta.INACTIVIDAD_ANORMAL,
    "PH_AGUA": TipoAlerta.RIESGO_HIDRICO,
    "OXIGENO_DISUELTO": TipoAlerta.RIESGO_HIDRICO,
    "TDS": TipoAlerta.RIESGO_HIDRICO,
    "CONDUCTIVIDAD_ELECTRICA": TipoAlerta.RIESGO_HIDRICO,
}


class GenararAlertaUseCase:

    def __init__(
        self,
        db: Session,
        alerta_repo: AlertaRepository,
        historico_repo: HistoricoEstadoAlertaRepository,
        regla_repo: ReglaAlertaRepository,
        parametros_port: ParametrosAlertasPort,
        auditoria_repo: BitacoraAuditoriaIotRepository | None = None,
        variable_port: VariableAlertaPort | None = None,
    ) -> None:
        self.db = db
        self.alerta_repo = alerta_repo
        # Compatibilidad con ensambladores actuales; no se escribe historial aquí.
        self.historico_repo = historico_repo
        self.regla_repo = regla_repo
        self.parametros_port = parametros_port
        self.auditoria_repo = auditoria_repo
        # G68: con el catálogo de M09 se evalúa el evento externo contra RF-57 Fase 5
        # (bandas base, THI y FALLO_AMBIENTAL) en vez de copiar la severidad declarada.
        self.variable_port = variable_port

    def execute(
        self,
        dto: ProcesarEventoAlertaDTO,
        id_activo_biologico: Optional[int] = None,
        contexto_activo_biologico: Optional[dict] = None,
        id_dispositivo_ioit: Optional[int] = None,
        id_infraestructura: Optional[int] = None,
    ) -> ResultadoGeneracionAlerta:
        ahora = datetime.now(timezone.utc)
        ids = dict(id_activo_biologico=id_activo_biologico, id_dispositivo_ioit=id_dispositivo_ioit,
                   id_infraestructura=id_infraestructura)
        rango = self.variable_port.obtener_rango_fisico(dto.tipo_variable) if self.variable_port else None
        causa_fallo = self._causa_fallo_ambiental(dto, rango)

        # Fase 2: Validar estado_dato (FA-01/E1/E2/CA-3)
        if dto.estado_dato != "LECTURA_VALIDA":
            if self.auditoria_repo is not None:
                # RF-63 admite tipos de evento de texto libre. Se conservan solo
                # campos de diagnóstico conocidos, nunca metadata arbitraria.
                RegistrarEventoAuditoriaIotUseCase(self.db, self.auditoria_repo).execute(
                    tipo_evento="LECTURA_EXCLUIDA_RF57",
                    resultado=TipoResultado.RECHAZADO,
                    componente_origen=ComponenteOrigen.RF57,
                    severidad_log=SeveridadLog.WARNING,
                    descripcion="Lectura excluida de alertas operativas por su calidad.",
                    entidad_afectada_tipo=EntidadAfectadaTipo.LECTURA if dto.id_telemetria is not None else EntidadAfectadaTipo.DISPOSITIVO,
                    entidad_afectada_id=str(dto.id_telemetria if dto.id_telemetria is not None else dto.device_id),
                    accion_detallada={
                        "estado_dato": dto.estado_dato, "id_sensor": dto.sensor_id,
                        "id_dispositivo_iot": dto.device_id, "tipo_variable": dto.tipo_variable,
                        "valor": str(dto.valor), "unidad": dto.unidad,
                        "timestamp_evento": dto.timestamp_evento.isoformat(),
                        "id_telemetria": dto.id_telemetria,
                        "id_evento_edge_computing": dto.id_evento_edge_computing,
                        "id_paquete_inferencia": dto.id_paquete_inferencia,
                    },
                )
            if causa_fallo:
                return self._fallo_ambiental(dto, rango, causa_fallo, ahora, ids)
            return ResultadoGeneracionAlerta(
                es_duplicado=False,
                motivo_descarte=f"estado_dato={dto.estado_dato} no genera alerta operativa",
            )
        if causa_fallo:
            # Una lectura imposible no es una condición del animal ni del ambiente.
            return self._fallo_ambiental(dto, rango, causa_fallo, ahora, ids)

        # Fase 5 (CA-1, Restricción 7): la severidad sale del valor, no de la declarada.
        severidad_reportada = dto.severidad_edge
        evaluacion = None
        if self.variable_port is not None and dto.origen_evento != OrigenEventoAlerta.IA:
            evaluacion = reglas_base_rf57.evaluar_evento(dto.tipo_variable, dto.valor, dto.correlacion_variables)
            if evaluacion.evaluable and evaluacion.severidad is None:
                self._auditar_sin_desviacion(dto, evaluacion.detalle)
                return ResultadoGeneracionAlerta(
                    es_duplicado=False,
                    motivo_descarte=f"{dto.tipo_variable}={dto.valor} está en la banda NORMAL de RF-57: no genera alerta",
                )
            if evaluacion.evaluable:
                dto = dto.model_copy(update={"severidad_edge": evaluacion.severidad})

        # Fase 3: Contexto de activo biológico (FA-03/E6/CA-7)
        tiene_contexto_incompleto = (id_activo_biologico is None)

        # Fase 4: Deduplicación (FA-02/E4/CA-4/CA-5)
        self.alerta_repo.bloquear_condicion(dto.sensor_id, dto.tipo_variable)
        alerta_existente = self.alerta_repo.buscar_activa_duplicada(
            id_sensor=dto.sensor_id,
            tipo_variable=dto.tipo_variable,
            ventana_min=30,
        )
        if alerta_existente:
            nueva_sev = dto.severidad_edge
            if self._severidad_mayor(nueva_sev, alerta_existente.severidad):
                self.alerta_repo.actualizar_deduplicacion(
                    id_alerta=alerta_existente.id_alerta,
                    ultima_ocurrencia=ahora,
                    nueva_severidad=nueva_sev,
                )
            else:
                self.alerta_repo.actualizar_deduplicacion(
                    id_alerta=alerta_existente.id_alerta,
                    ultima_ocurrencia=ahora,
                )
            self.db.commit()
            return ResultadoGeneracionAlerta(
                es_duplicado=True,
                id_alerta=alerta_existente.id_alerta,
                tipo_alerta=alerta_existente.tipo_alerta,
                severidad=alerta_existente.severidad,
                alerta_existente_id=alerta_existente.id_alerta,
            )

        # Fase 5/6: Clasificar tipo y severidad
        tipo_alerta, severidad_final, conflicto_resolucion = self._clasificar(dto)

        # Fase 7: Construir alerta
        alerta = Alerta(
            tipo_alerta=tipo_alerta,
            severidad=severidad_final,
            estado_alerta=EstadoAlerta.ACTIVA,
            origen_evento=dto.origen_evento,
            tipo_variable=dto.tipo_variable,
            fecha_evento=dto.timestamp_evento,
            fecha_generacion=ahora,
            reglas_activas=dto.reglas_activadas,
            valor=dto.valor,
            unidad=dto.unidad,
            contexto_activo_biologico=contexto_activo_biologico,
            metadato_evento=self._metadato_con_evaluacion(dto, evaluacion, severidad_reportada),
            tiene_inferencia_no_disponible=(dto.probabilidad_ia is None and dto.origen_evento == OrigenEventoAlerta.EDGE),
            tiene_contexto_incompleto=tiene_contexto_incompleto,
            conflicto_resolucion=conflicto_resolucion,
            severidad_edge_original=(dto.severidad_edge if conflicto_resolucion
                                     else severidad_reportada if severidad_reportada != dto.severidad_edge else None),
            severidad_ia=dto.severidad_ia if conflicto_resolucion else None,
            id_evento_edge_computing=dto.id_evento_edge_computing,
            id_telemetria=dto.id_telemetria,
            id_paquete_inferencia=dto.id_paquete_inferencia,
            id_sensor=dto.sensor_id,
            id_dispositivo_ioit=id_dispositivo_ioit,
            id_activo_biologico=id_activo_biologico,
            id_infraestructura=id_infraestructura,
        )
        alerta.fecha_vencimiento = alerta.calcular_fecha_vencimiento()

        try:
            alerta_guardada = self.alerta_repo.guardar(alerta)
            # trg_rf57_02_historico_inicial registra la creación en esta transacción.
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return ResultadoGeneracionAlerta(
            es_duplicado=False,
            id_alerta=alerta_guardada.id_alerta,
            tipo_alerta=alerta_guardada.tipo_alerta,
            severidad=alerta_guardada.severidad,
        )

    def _causa_fallo_ambiental(self, dto: ProcesarEventoAlertaDTO,
                               rango: Optional[RangoFisicoVariable]) -> Optional[str]:
        """RF-57 FALLO_AMBIENTAL: error de calibración o valor fuera del rango absoluto del sensor."""
        if self.variable_port is None:
            return None
        if dto.estado_dato == "ERROR_CALIBRACION":
            return "ERROR_CALIBRACION"
        if rango and reglas_base_rf57.fuera_de_rango_fisico(dto.valor, rango.valor_fisico_min, rango.valor_fisico_max):
            return "VALOR_FUERA_DE_RANGO_ABSOLUTO"
        return None

    def _fallo_ambiental(self, dto, rango, causa, ahora, ids) -> ResultadoGeneracionAlerta:
        """Alerta técnica para el ingeniero de campo (no operativa): MODERADO, CRITICO si la variable es crítica."""
        severidad = SeveridadAlerta.CRITICO if rango and rango.es_critica else SeveridadAlerta.MODERADO
        motivo = f"FALLO_AMBIENTAL ({causa}): no genera alerta operativa; alerta técnica para el ingeniero de campo"
        try:
            self.alerta_repo.bloquear_condicion(dto.sensor_id, TipoAlerta.FALLO_AMBIENTAL)
            existente = self.alerta_repo.buscar_activa_duplicada(
                id_sensor=dto.sensor_id, tipo_variable=TipoAlerta.FALLO_AMBIENTAL, ventana_min=30)
            if existente:
                self.alerta_repo.actualizar_deduplicacion(id_alerta=existente.id_alerta, ultima_ocurrencia=ahora)
                self.db.commit()
                return ResultadoGeneracionAlerta(
                    es_duplicado=True, id_alerta=existente.id_alerta, tipo_alerta=existente.tipo_alerta,
                    severidad=existente.severidad, alerta_existente_id=existente.id_alerta, motivo_descarte=motivo)
            alerta = Alerta(
                tipo_alerta=TIPO_ALERTA_TECNICA,
                severidad=severidad,
                estado_alerta=EstadoAlerta.ACTIVA,
                origen_evento=dto.origen_evento,
                tipo_variable=TipoAlerta.FALLO_AMBIENTAL,
                fecha_evento=dto.timestamp_evento,
                fecha_generacion=ahora,
                reglas_activas=dto.reglas_activadas,
                valor=dto.valor,
                unidad=dto.unidad,
                metadato_evento={
                    **(dto.metadata_evento or {}),
                    "componente_origen": "RF57", "alerta": TipoAlerta.FALLO_AMBIENTAL.value, "causa": causa,
                    "tipo_variable": dto.tipo_variable, "estado_dato": dto.estado_dato,
                    "severidad_reportada": dto.severidad_edge,
                    "rango_fisico": {"min": str(rango.valor_fisico_min) if rango else None,
                                     "max": str(rango.valor_fisico_max) if rango else None,
                                     "variable_critica": bool(rango and rango.es_critica)},
                },
                diagnostico=causa,
                id_evento_edge_computing=dto.id_evento_edge_computing,
                id_telemetria=dto.id_telemetria,
                id_paquete_inferencia=dto.id_paquete_inferencia,
                id_sensor=dto.sensor_id,
                **ids,
            )
            alerta.fecha_vencimiento = alerta.calcular_fecha_vencimiento()
            guardada = self.alerta_repo.guardar(alerta)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return ResultadoGeneracionAlerta(es_duplicado=False, id_alerta=guardada.id_alerta,
                                         tipo_alerta=guardada.tipo_alerta, severidad=guardada.severidad,
                                         motivo_descarte=motivo)

    def _auditar_sin_desviacion(self, dto: ProcesarEventoAlertaDTO, detalle: dict) -> None:
        if self.auditoria_repo is None:
            return
        RegistrarEventoAuditoriaIotUseCase(self.db, self.auditoria_repo).execute(
            tipo_evento="EVENTO_SIN_DESVIACION_RF57",
            resultado=TipoResultado.RECHAZADO,
            componente_origen=ComponenteOrigen.RF57,
            severidad_log=SeveridadLog.WARNING,
            descripcion="Evento con severidad declarada pero valor en la banda NORMAL de RF-57.",
            entidad_afectada_tipo=EntidadAfectadaTipo.DISPOSITIVO,
            entidad_afectada_id=str(dto.device_id),
            accion_detallada={"id_sensor": dto.sensor_id, "tipo_variable": dto.tipo_variable,
                              "valor": str(dto.valor), "severidad_reportada": dto.severidad_edge, **detalle},
        )

    @staticmethod
    def _metadato_con_evaluacion(dto, evaluacion, severidad_reportada) -> Optional[dict]:
        if evaluacion is None or not evaluacion.evaluable:
            return dto.metadata_evento
        return {**(dto.metadata_evento or {}),
                "evaluacion_rf57": {"severidad_reportada": severidad_reportada, **evaluacion.detalle}}

    def _clasificar(self, dto: ProcesarEventoAlertaDTO) -> tuple[str, str, Optional[str]]:
        """Determina tipo_alerta, severidad final y conflicto_resolucion (E12/E13)."""
        tipo_edge = self._inferir_tipo_alerta(dto)
        tipo_ia = dto.tipo_alerta_ia
        sev_edge = dto.severidad_edge
        sev_ia = dto.severidad_ia
        prob_ia = dto.probabilidad_ia

        # Sin IA disponible (E3/CA-6)
        if prob_ia is None or sev_ia is None:
            if dto.origen_evento == OrigenEventoAlerta.IA:
                tipo_final = tipo_ia or tipo_edge
                sev_final = self._severidad_por_probabilidad(prob_ia) if prob_ia else sev_edge
                return tipo_final, sev_final, None
            return tipo_edge, sev_edge, None

        # PREDICCION_PATOLOGIA pura de IA
        if dto.origen_evento == OrigenEventoAlerta.IA and tipo_ia == TipoAlerta.PREDICCION_PATOLOGIA:
            sev_final = self._severidad_por_probabilidad(prob_ia)
            return TipoAlerta.PREDICCION_PATOLOGIA, sev_final, None

        if (not tipo_ia or tipo_ia == tipo_edge) and sev_ia == sev_edge:
            return tipo_edge, sev_edge, None
        umbral_confianza = self.parametros_port.obtener_confianza_edge_ia()

        # E13: Conflicto de tipo entre Edge e IA
        conflicto_tipo: Optional[str] = None
        if tipo_ia and tipo_ia != tipo_edge:
            if prob_ia >= umbral_confianza:
                tipo_final = tipo_ia
                conflicto_tipo = ConflictoResolucion.IA_PREVALECE
            else:
                tipo_final = tipo_edge
                conflicto_tipo = ConflictoResolucion.EDGE_PREVALECE
        else:
            tipo_final = tipo_edge

        # E12: Conflicto de severidad entre Edge e IA
        if sev_ia != sev_edge:
            if prob_ia < umbral_confianza and sev_ia == SeveridadAlerta.CRITICO and sev_edge == SeveridadAlerta.LEVE:
                # Excepción de compromiso
                return tipo_final, SeveridadAlerta.MODERADO, ConflictoResolucion.SEVERIDAD_COMPROMISO
            # Regla general: severidad máxima
            sev_final = sev_ia if self._severidad_mayor(sev_ia, sev_edge) else sev_edge
            return tipo_final, sev_final, conflicto_tipo or ConflictoResolucion.SEVERIDAD_MAXIMA

        return tipo_final, sev_edge, conflicto_tipo

    def _inferir_tipo_alerta(self, dto: ProcesarEventoAlertaDTO) -> str:
        return _VARIABLE_A_TIPO_ALERTA.get(dto.tipo_variable.upper(), TipoAlerta.FALLO_AMBIENTAL)

    @staticmethod
    def _severidad_mayor(sev_a: str, sev_b: str) -> bool:
        orden = {SeveridadAlerta.LEVE: 0, SeveridadAlerta.MODERADO: 1, SeveridadAlerta.CRITICO: 2}
        return orden.get(sev_a, 0) > orden.get(sev_b, 0)

    @staticmethod
    def _severidad_por_probabilidad(prob: Optional[Decimal]) -> str:
        # Bandas de severidad propias del RF; no son la confianza de conflicto E12/E13.
        if prob is None:
            return SeveridadAlerta.LEVE
        if prob >= Decimal("0.95"):
            return SeveridadAlerta.CRITICO
        if prob >= Decimal("0.85"):
            return SeveridadAlerta.MODERADO
        return SeveridadAlerta.LEVE
