# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-74: E1/E5/E6 del RF y cálculo sin commit |
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""Caso de uso núcleo: calcular el ICA de un activo para un período (RF-74).

Reutilizado por el cálculo manual (Flujo A), el batch nocturno (Flujo C) y los
reintentos. Orquesta la recolección de insumos cross-module (consumo VALIDADO,
pesaje inicial/final) y delega el cálculo puro en :class:`CalculadoraICA`. Persiste
el resultado (desmarcando el vigente anterior) y, si la clasificación es ``CRITICA``,
genera la alerta correspondiente. ``commit()``/``rollback()`` viven aquí.

Un ``CA_NO_CALCULABLE`` por datos (sin peso, sin consumo…) **no es un error**: se
persiste y se retorna con HTTP 200. Los fallos técnicos re-lanzan para que el batch
los reintente; en el cálculo manual (E5) se revierte, se deja el fallo en
auditoría (paso, error) y se responde 500 con el mensaje del RF.

``calcular_sin_commit`` es el mismo cálculo sin ``commit``: lo usa el cierre de
ciclo (RF-38) para dejar el CA final dentro de su transacción.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.shared.errors import AppError, BusinessRuleError, InfrastructureError, NotFoundError
from src.shared.fechas import fecha_usuario, hoy_usuario
from src.supplies.domain.entities.resultado_ica import ResultadoICA
from src.supplies.domain.repositories.activo_consulta_port import ActivoConsultaPort
from src.supplies.domain.repositories.alerta_ica_port import AlertaICAPort
from src.supplies.domain.repositories.auditoria_suministro_port import (
    AuditoriaSuministroPort,
    EventoAuditoriaSuministro,
)
from src.supplies.domain.repositories.ciclo_abierto_port import CicloAbiertoPort
from src.supplies.domain.repositories.consumo_ica_read_port import ConsumoICAReadPort
from src.supplies.domain.repositories.notificacion_suministros_port import NotificacionSuministrosPort
from src.supplies.domain.repositories.pesaje_consulta_port import PesajeConsultaPort
from src.supplies.domain.repositories.resultado_ica_repository import ResultadoICARepository
from src.supplies.domain.services.calculadora_ica import CalculadoraICA
from src.supplies.domain.value_objects.eficiencia_enums import PeriodoEvaluacion, TipoCalculo
from src.supplies.domain.value_objects.periodo_calculo import PeriodoCalculo

# Tipos de cálculo iniciados por un usuario (alerta con origen BACKEND).
_TIPOS_MANUALES = {TipoCalculo.MANUAL, TipoCalculo.REINTENTO_MANUAL}


class CalcularICAUseCase:
    def __init__(
        self,
        db: Session,
        resultado_repo: ResultadoICARepository,
        consumo_read_port: ConsumoICAReadPort,
        pesaje_port: PesajeConsultaPort,
        activo_port: ActivoConsultaPort,
        ciclo_port: CicloAbiertoPort,
        alerta_port: AlertaICAPort,
        auditoria_port: Optional[AuditoriaSuministroPort] = None,
        calculadora: Optional[CalculadoraICA] = None,
        notificador: Optional[NotificacionSuministrosPort] = None,
    ) -> None:
        self.db = db
        self.resultado_repo = resultado_repo
        self.consumo_read_port = consumo_read_port
        self.pesaje_port = pesaje_port
        self.activo_port = activo_port
        self.ciclo_port = ciclo_port
        self.alerta_port = alerta_port
        self.auditoria_port = auditoria_port
        self.calculadora = calculadora or CalculadoraICA()
        self.notificador = notificador

    def execute(
        self,
        *,
        id_activo_biologico: int,
        periodo: PeriodoEvaluacion,
        tipo_calculo: TipoCalculo,
        id_usuario: Optional[int] = None,
        intento: int = 1,
    ) -> ResultadoICA:
        paso = ["validar_activo"]
        try:
            guardado = self.calcular_sin_commit(
                id_activo_biologico=id_activo_biologico,
                periodo=periodo,
                tipo_calculo=tipo_calculo,
                id_usuario=id_usuario,
                intento=intento,
                paso=paso,
            )
            self.db.commit()
        except AppError:
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            if tipo_calculo not in _TIPOS_MANUALES:
                raise  # el batch reintenta (E5, política de reintentos automáticos)
            self._auditar_fallo(id_activo_biologico, periodo, paso[0], exc, id_usuario)
            raise InfrastructureError(
                code="ERROR_CALCULO_CA",
                message=(
                    f"Error interno al calcular el CA para el activo {id_activo_biologico}. "
                    "La operación fue revertida."
                ),
                original_error=exc,
            ) from exc
        self._avisar_si_critica(guardado)
        return guardado

    def _avisar_si_critica(self, resultado: ResultadoICA) -> None:
        """Paso 8 / CA-3: alerta de urgencia ALTA al Productor y al Veterinario del activo."""
        if self.notificador is None or not resultado.es_critica:
            return
        self.notificador.a_responsables_activo(
            resultado.id_activo_biologico,
            "ALERTA_CONVERSION_ALIMENTICIA",
            f"Urgencia ALTA: la conversión alimenticia del activo {resultado.id_activo_biologico} es CRÍTICA "
            f"(CA {resultado.ca_calculado}, período {resultado.periodo_evaluacion.value}). Revise dieta, calidad "
            "del alimento y estado sanitario.",
            {"id_activo_biologico": resultado.id_activo_biologico, "ca": str(resultado.ca_calculado)},
        )

    def calcular_sin_commit(
        self,
        *,
        id_activo_biologico: int,
        periodo: PeriodoEvaluacion,
        tipo_calculo: TipoCalculo,
        id_usuario: Optional[int] = None,
        intento: int = 1,
        paso: Optional[list[str]] = None,
        fecha_corte: Optional[date] = None,
    ) -> ResultadoICA:
        """``fecha_corte`` reemplaza a hoy como fin del período (CA final al cierre del ciclo, RF-38)."""
        paso = paso if paso is not None else ["validar_activo"]
        activo = self.activo_port.obtener(id_activo_biologico)
        if activo is None:
            raise NotFoundError(
                code="ACTIVO_NO_ENCONTRADO",
                message=f"El activo biológico con ID {id_activo_biologico} no existe.",
                field="id_activo_biologico",
            )
        if not activo.esta_activo:
            raise BusinessRuleError(
                code="ACTIVO_NO_ACTIVO",
                message=(
                    f"El activo biológico con ID {id_activo_biologico} no está en estado ACTIVO. "
                    "El cálculo del CA solo aplica a activos en producción."
                ),
                field="id_activo_biologico",
            )

        # Resolver la ventana de fechas del período (POR_CICLO usa la fase abierta).
        paso[0] = "resolver_periodo"
        hoy = fecha_corte or hoy_usuario()
        fecha_inicio_ciclo = activo.fecha_inicio_ciclo
        if periodo == PeriodoEvaluacion.POR_CICLO:
            ciclo = self.ciclo_port.obtener_abierto(id_activo_biologico)
            if ciclo is not None and ciclo.fecha_inicio is not None:
                fecha_inicio_ciclo = fecha_usuario(ciclo.fecha_inicio)
        periodo_calc = PeriodoCalculo.resolver(
            periodo, hoy=hoy, fecha_inicio_ciclo=fecha_inicio_ciclo
        )

        # Recolectar insumos (solo lectura, CA-4).
        paso[0] = "recolectar_insumos"
        alimento_total = self.consumo_read_port.sumar_alimento_validado(
            id_activo_biologico, periodo_calc.fecha_inicio, periodo_calc.fecha_fin
        )
        peso_inicial = self.pesaje_port.obtener_peso_en_o_antes(
            id_activo_biologico, periodo_calc.fecha_inicio, activo.es_poblacional
        )
        peso_final = self.pesaje_port.obtener_peso_en_o_antes(
            id_activo_biologico, periodo_calc.fecha_fin, activo.es_poblacional
        )
        # E6: si no hay pesaje válido pero sí uno fuera de rango, la causa es PESO_INVALIDO.
        descartado_inicial = (
            self.pesaje_port.obtener_peso_invalido_en_o_antes(
                id_activo_biologico, periodo_calc.fecha_inicio, activo.es_poblacional
            )
            if peso_inicial is None
            else None
        )
        descartado_final = (
            self.pesaje_port.obtener_peso_invalido_en_o_antes(
                id_activo_biologico, periodo_calc.fecha_fin, activo.es_poblacional
            )
            if peso_final is None
            else None
        )

        paso[0] = "calcular"
        calculo = self.calculadora.calcular(
            alimento_total_kg=alimento_total,
            peso_inicial_kg=peso_inicial,
            peso_final_kg=peso_final,
            es_poblacional=activo.es_poblacional,
            cantidad_actual=activo.cantidad_actual,
            peso_inicial_invalido=descartado_inicial is not None,
            peso_final_invalido=descartado_final is not None,
        )

        resultado = ResultadoICA.desde_calculo(
            calculo=calculo,
            periodo=periodo_calc,
            id_activo_biologico=id_activo_biologico,
            tipo_calculo=tipo_calculo,
            intento=intento,
            id_usuario=id_usuario,
            peso_inicial_kg=peso_inicial,
            peso_final_kg=peso_final,
            pesaje_descartado=descartado_inicial or descartado_final,
        )

        paso[0] = "persistir_resultado"
        guardado = self.resultado_repo.guardar(resultado)
        guardado.peso_inicial_kg = peso_inicial
        guardado.peso_final_kg = peso_final
        guardado.pesaje_descartado = resultado.pesaje_descartado
        if calculo.es_critica and calculo.ca_calculado is not None:
            paso[0] = "generar_alerta"
            origen = "BACKEND" if tipo_calculo in _TIPOS_MANUALES else "EVALUACION_PERIODICA"
            self.alerta_port.generar_alerta_critica(
                id_activo_biologico=id_activo_biologico,
                ca_calculado=calculo.ca_calculado,
                periodo_evaluacion=periodo.value,
                origen_evento=origen,
                fecha_evento=datetime.now(timezone.utc),
            )
        return guardado

    def _auditar_fallo(
        self, id_activo: int, periodo: PeriodoEvaluacion, paso: str, exc: Exception, id_usuario: Optional[int]
    ) -> None:
        """E5: deja el fallo del cálculo manual en la bitácora de M05, en su propia transacción."""
        if self.auditoria_port is None or id_usuario is None:
            return
        try:
            self.auditoria_port.registrar(
                EventoAuditoriaSuministro(
                    entidad_afectada="resultado_ica",
                    tipo_operacion="REGISTRO_FALLIDO",
                    id_usuario=id_usuario,
                    resultado="FALLIDO",
                    id_activo_biologico=id_activo,
                    detalle_causa=f"periodo={periodo.value}; paso_fallido={paso}; error={exc}"[:1000],
                    fecha_emision=datetime.now(timezone.utc),
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
