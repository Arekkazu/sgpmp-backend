from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.shared.errors import BusinessRuleError
from src.telemetry.domain.entities.telemetria import (
    EstadoCalidadBitacora,
    EstadoCalidadTelemetria,
    EstadoPaqueteInferencia,
    EventoEdgeComputing,
    PaqueteInferencia,
    TipoEventoEdge,
)
from src.telemetry.domain.repositories.motor_inferencia_port import MotorInferenciaPort
from src.telemetry.domain.repositories.paquete_inferencia_repository import PaqueteInferenciaRepository

# Variables mínimas por categoría para contexto completo
_MINIMOS_AMBIENTAL = {"TEMPERATURA_AMBIENTAL", "HUMEDAD_RELATIVA"}
_MINIMOS_ANIMAL = {"TEMPERATURA_CORPORAL", "TEMP_CORPORAL", "FRECUENCIA_CARDIACA"}
_MINIMOS_HIDRICA = {"PH_AGUA", "OXIGENO_DISUELTO"}

_CATEGORIA_VARIABLE: dict[str, str] = {
    "TEMPERATURA_AMBIENTAL": "AMBIENTAL",
    "HUMEDAD_RELATIVA": "AMBIENTAL",
    "NH3": "AMBIENTAL",
    "CO2": "AMBIENTAL",
    "TEMPERATURA_CORPORAL": "ANIMAL",
    "TEMP_CORPORAL": "ANIMAL",
    "FRECUENCIA_CARDIACA": "ANIMAL",
    "FRECUENCIA_RESPIRATORIA": "ANIMAL",
    "ACTIVIDAD_MOVIMIENTO": "ANIMAL",
    "ACTIVIDAD": "ANIMAL",
    "PH_AGUA": "HIDRICA",
    "OXIGENO_DISUELTO": "HIDRICA",
    "TDS": "HIDRICA",
    "CONDUCTIVIDAD_ELECTRICA": "HIDRICA",
}


def _evaluar_contexto(variables: list[dict]) -> tuple[dict, bool]:
    """Agrupa variables por categoría y determina si el contexto es completo."""
    por_categoria: dict[str, list[dict]] = {"AMBIENTAL": [], "ANIMAL": [], "HIDRICA": []}
    tipos_presentes: set[str] = set()

    for v in variables:
        tipo = v.get("tipo_variable", "")
        cat = _CATEGORIA_VARIABLE.get(tipo, "AMBIENTAL")
        por_categoria[cat].append(v)
        tipos_presentes.add(tipo)

    # Una categoría se considera completa si tiene sus variables mínimas
    categorias_activas = {cat for cat, vars in por_categoria.items() if vars}
    incompleto = False

    for cat in categorias_activas:
        if cat == "AMBIENTAL" and not (_MINIMOS_AMBIENTAL <= tipos_presentes):
            incompleto = True
        elif cat == "ANIMAL":
            tiene_temp = bool({"TEMPERATURA_CORPORAL", "TEMP_CORPORAL"} & tipos_presentes)
            tiene_fc = "FRECUENCIA_CARDIACA" in tipos_presentes
            if not (tiene_temp and tiene_fc):
                incompleto = True
        elif cat == "HIDRICA" and not (_MINIMOS_HIDRICA <= tipos_presentes):
            incompleto = True

    contexto = {cat: vars for cat, vars in por_categoria.items() if vars}
    return contexto, incompleto


class ConsolidarEnviarPaqueteUseCase:

    def __init__(
        self,
        db: Session,
        paquete_repo: PaqueteInferenciaRepository,
        motor_inferencia_port: MotorInferenciaPort,
    ) -> None:
        self.db = db
        self.paquete_repo = paquete_repo
        self.motor_inferencia_port = motor_inferencia_port

    def execute(self, evento: EventoEdgeComputing) -> Optional[PaqueteInferencia]:
        """
        RF-56 pasos 7-10: consolidar paquete multivariable y enviar a M04.
        Solo se ejecuta si clasificacion_rf55 != NORMAL.
        Devuelve None si no hay nada que enviar.
        """
        if evento.clasificacion_rf55 == TipoEventoEdge.NORMAL:
            return None

        variables = evento.variables_involucradas
        if not variables:
            raise BusinessRuleError(
                code="PAQUETE_INCONSISTENTE",
                message="El evento Edge no contiene variables para consolidar.",
            )

        # FA-03: validar que el evento tiene al menos una variable con valor
        variable_principal = variables[0]
        tipo_variable = variable_principal.get("tipo_variable")
        valor_raw = variable_principal.get("valor")
        if not tipo_variable or valor_raw is None:
            raise BusinessRuleError(
                code="PAQUETE_INCONSISTENTE",
                message="La variable principal del evento no tiene tipo_variable o valor.",
            )

        # Paso 7: Consolidar contexto multivariable
        contexto_ambiental, contexto_incompleto = _evaluar_contexto(variables)

        # Paso 8: Validar consistencia (FA-03)
        self._validar_timestamps(variables)

        valor_numerico = Decimal(str(valor_raw))
        unidad = variable_principal.get("unidad")

        metadatos = {
            "timestamp_captura": evento.fecha_captura.isoformat(),
            "timestamp_procesamiento_edge": evento.fecha_procesamiento.isoformat(),
            "clasificacion_rf55": evento.clasificacion_rf55,
        }

        paquete = PaqueteInferencia(
            id_sensor=evento.id_sensor,
            id_dispositivo_iot=evento.id_dispositivo_iot,
            id_evento_edge_computing=evento.id_evento_edge_computing,
            tipo_variable=tipo_variable,
            valor_numerico=valor_numerico,
            unidad=unidad,
            estado_calidad=EstadoCalidadTelemetria.LECTURA_VALIDA,
            estado_desviacion=evento.clasificacion_rf55,
            severidad=evento.severidad,
            origen=evento.origen_dato,
            contexto_ambiental=contexto_ambiental,
            contexto_incompleto=contexto_incompleto,
            metadatos=metadatos,
            fecha_envio=datetime.now(timezone.utc),
            estado_paquete=EstadoPaqueteInferencia.PENDIENTE,
            intento_envios=0,
        )

        try:
            paquete_guardado = self.paquete_repo.guardar(paquete)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        # Paso 9: Intentar envío a M04 (un intento síncrono; backoff diferido fuera de alcance)
        try:
            exito = self.motor_inferencia_port.enviar_paquete(paquete_guardado)
        except Exception:
            exito = False

        nuevo_estado = EstadoPaqueteInferencia.ENVIADO if exito else EstadoPaqueteInferencia.FALLIDO
        try:
            self.paquete_repo.actualizar_estado(
                paquete_guardado.id_paquetes_inferencia,
                nuevo_estado,
                1,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        paquete_guardado.estado_paquete = nuevo_estado
        paquete_guardado.intento_envios = 1
        return paquete_guardado

    @staticmethod
    def _validar_timestamps(variables: list[dict]) -> None:
        """FA-03: diferencia máxima entre timestamps de variables del mismo contexto ≤ 5 s."""
        timestamps = [
            v["timestamp_captura"]
            for v in variables
            if v.get("timestamp_captura") is not None
        ]
        if len(timestamps) < 2:
            return
        ts_sorted = sorted(timestamps)
        delta = (ts_sorted[-1] - ts_sorted[0]).total_seconds() if hasattr(ts_sorted[0], 'total_seconds') else 0
        # timestamps son datetime objects
        if isinstance(ts_sorted[0], str):
            return  # no se pueden comparar strings aquí
        from datetime import datetime as dt
        if all(isinstance(t, dt) for t in ts_sorted):
            delta = (ts_sorted[-1] - ts_sorted[0]).total_seconds()
            if delta > 5:
                raise BusinessRuleError(
                    code="PAQUETE_INCONSISTENTE",
                    message="La diferencia entre timestamps de variables supera los 5 segundos permitidos.",
                )
