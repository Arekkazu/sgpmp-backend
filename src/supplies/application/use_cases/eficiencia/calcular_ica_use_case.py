"""Caso de uso núcleo: calcular el ICA de un activo para un período (RF-74).

Reutilizado por el cálculo manual (Flujo A), el batch nocturno (Flujo C) y los
reintentos. Orquesta la recolección de insumos cross-module (consumo VALIDADO,
pesaje inicial/final) y delega el cálculo puro en :class:`CalculadoraICA`. Persiste
el resultado (desmarcando el vigente anterior) y, si la clasificación es ``CRITICA``,
genera la alerta correspondiente. ``commit()``/``rollback()`` viven aquí.

Un ``CA_NO_CALCULABLE`` por datos (sin peso, sin consumo…) **no es un error**: se
persiste y se retorna con HTTP 200. Solo los fallos técnicos re-lanzan (para que el
batch los reintente).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.shared.errors import BusinessRuleError, NotFoundError
from src.supplies.domain.entities.resultado_ica import ResultadoICA
from src.supplies.domain.repositories.activo_consulta_port import ActivoConsultaPort
from src.supplies.domain.repositories.alerta_ica_port import AlertaICAPort
from src.supplies.domain.repositories.ciclo_abierto_port import CicloAbiertoPort
from src.supplies.domain.repositories.consumo_ica_read_port import ConsumoICAReadPort
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
        calculadora: Optional[CalculadoraICA] = None,
    ) -> None:
        self.db = db
        self.resultado_repo = resultado_repo
        self.consumo_read_port = consumo_read_port
        self.pesaje_port = pesaje_port
        self.activo_port = activo_port
        self.ciclo_port = ciclo_port
        self.alerta_port = alerta_port
        self.calculadora = calculadora or CalculadoraICA()

    def execute(
        self,
        *,
        id_activo_biologico: int,
        periodo: PeriodoEvaluacion,
        tipo_calculo: TipoCalculo,
        id_usuario: Optional[int] = None,
        intento: int = 1,
    ) -> ResultadoICA:
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
                    f"No es posible calcular el ICA del activo {id_activo_biologico}: su estado "
                    f"actual es {activo.nombre_estado}. Solo se calcula sobre activos ACTIVO."
                ),
                field="id_activo_biologico",
            )

        # Resolver la ventana de fechas del período (POR_CICLO usa la fase abierta).
        hoy = datetime.now(timezone.utc).date()
        fecha_inicio_ciclo = activo.fecha_inicio_ciclo
        if periodo == PeriodoEvaluacion.POR_CICLO:
            ciclo = self.ciclo_port.obtener_abierto(id_activo_biologico)
            if ciclo is not None and ciclo.fecha_inicio is not None:
                fecha_inicio_ciclo = ciclo.fecha_inicio.date()
        periodo_calc = PeriodoCalculo.resolver(
            periodo, hoy=hoy, fecha_inicio_ciclo=fecha_inicio_ciclo
        )

        # Recolectar insumos.
        alimento_total = self.consumo_read_port.sumar_alimento_validado(
            id_activo_biologico, periodo_calc.fecha_inicio, periodo_calc.fecha_fin
        )
        peso_inicial = self.pesaje_port.obtener_peso_en_o_antes(
            id_activo_biologico, periodo_calc.fecha_inicio, activo.es_poblacional
        )
        peso_final = self.pesaje_port.obtener_peso_en_o_antes(
            id_activo_biologico, periodo_calc.fecha_fin, activo.es_poblacional
        )

        calculo = self.calculadora.calcular(
            alimento_total_kg=alimento_total,
            peso_inicial_kg=peso_inicial,
            peso_final_kg=peso_final,
            es_poblacional=activo.es_poblacional,
            cantidad_actual=activo.cantidad_actual,
        )

        resultado = ResultadoICA.desde_calculo(
            calculo=calculo,
            periodo=periodo_calc,
            id_activo_biologico=id_activo_biologico,
            tipo_calculo=tipo_calculo,
            intento=intento,
            id_usuario=id_usuario,
        )

        try:
            guardado = self.resultado_repo.guardar(resultado)
            if calculo.es_critica and calculo.ca_calculado is not None:
                origen = "BACKEND" if tipo_calculo in _TIPOS_MANUALES else "EVALUACION_PERIODICA"
                self.alerta_port.generar_alerta_critica(
                    id_activo_biologico=id_activo_biologico,
                    ca_calculado=calculo.ca_calculado,
                    periodo_evaluacion=periodo.value,
                    origen_evento=origen,
                    fecha_evento=datetime.now(timezone.utc),
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return guardado
