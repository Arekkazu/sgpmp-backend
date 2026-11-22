# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-86/87/94: período del hecho, cuentas de la matriz y auditoría |
# | 2026-11-08 | destroyerban | INC-M06-312-G14 RF-83: evento en período cerrado queda pendiente y alerta |
# | 2026-11-10 | Arekkazu | INC-M06-342-G40 RF-86 FA-5: la línea sin cuenta avisa al Contador la combinación faltante |
"""Servicio de aplicación compartido: ubica el período de un hecho, crea su línea de asiento con
las cuentas de la matriz (RF-86 v2.0, RF-109) y registra la auditoría (RF-94). No hace commit."""
from __future__ import annotations

from datetime import date
from typing import Optional

from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria, LineaAsiento, Periodo
from src.financial_valuation.domain.repositories.activo_financiero_port import ActivoFinancieroPort
from src.financial_valuation.domain.repositories.asiento_repository import AsientoRepository
from src.financial_valuation.domain.repositories.auditoria_financiera_repository import AuditoriaFinancieraRepository
from src.financial_valuation.domain.repositories.configuracion_contable_repository import (
    ConfiguracionContableRepository,
)
from src.financial_valuation.domain.repositories.notificacion_financiera_port import NotificacionFinancieraPort
from src.financial_valuation.domain.repositories.periodo_repository import PeriodoRepository
from src.financial_valuation.domain.services.nic41 import periodo_siguiente, rango_periodo
from src.financial_valuation.domain.value_objects.nic41 import (
    ETIQUETA_HECHO,
    ETIQUETA_SENTIDO,
    ETIQUETA_SUBTIPO,
    EstadoPeriodo,
    Severidad,
    TipoHecho,
)
from src.shared.errors import BusinessRuleError, FlowError

ID_SISTEMA = "M06_PROCESO_AUTOMATICO"


class PeriodoEnCierreError(FlowError):
    """El hecho cae en un período EN_CIERRE: se encola para el período siguiente (RF-87 paso 1)."""


class Contabilizador:
    def __init__(self, config: ConfiguracionContableRepository, periodos: PeriodoRepository,
                 asientos: AsientoRepository, auditoria: AuditoriaFinancieraRepository,
                 notificador: Optional[NotificacionFinancieraPort] = None,
                 activos: Optional[ActivoFinancieroPort] = None) -> None:
        self.config = config
        self.periodos = periodos
        self.asientos = asientos
        self.auditoria = auditoria
        self.notificador = notificador
        self.activos = activos

    # --- Períodos ------------------------------------------------------------------------------

    def periodo_para(self, numero_id_tributaria: Optional[str], dia: date, id_usuario: int) -> Periodo:
        """Período ABIERTO al que va un hecho del ``dia``.

        Un hecho de un período ya CERRADO entra al primer período abierto posterior (corrección sin
        reapertura, RF-87 v1.1). Sin titular tributario no hay cierre posible (RF-19 v1.1)."""
        if not numero_id_tributaria:
            raise BusinessRuleError(
                code="FINCA_SIN_TITULAR",
                message="La finca del activo no tiene titular tributario. Complételo en Configuración → Fincas.",
            )
        tipo = self.config.obtener().tipo_cierre
        periodo = self.periodos.que_contiene(numero_id_tributaria, dia)
        if periodo is not None and periodo.esta_abierto:
            return periodo
        if periodo is not None and periodo.estado == EstadoPeriodo.EN_CIERRE.value:
            raise PeriodoEnCierreError(
                code="PERIODO_EN_CIERRE",
                message=f"El período {periodo.fecha_inicio:%Y-%m} está en cierre. El registro se procesará en el período siguiente.",
            )
        if periodo is None and not self.periodos.hay_posteriores(numero_id_tributaria, dia):
            inicio, fin = rango_periodo(dia, tipo)
            return self.periodos.crear(numero_id_tributaria, tipo, inicio, fin, id_usuario)
        desde = periodo.fecha_fin if periodo is not None else dia
        abierto = self.periodos.primero_abierto_desde(numero_id_tributaria, desde)
        if abierto is not None:
            return abierto
        inicio, fin = periodo_siguiente(desde, tipo)
        return self.periodos.crear(numero_id_tributaria, tipo, inicio, fin, id_usuario)

    def periodo_cerrado_en(self, numero_id_tributaria: Optional[str], dia: date) -> Optional[Periodo]:
        """Período CERRADO que contiene ``dia``, si lo hay (RF-83 restricción 2, RF-86 paso 1 c)."""
        if not numero_id_tributaria:
            return None
        periodo = self.periodos.que_contiene(numero_id_tributaria, dia)
        return periodo if periodo is not None and periodo.estado == EstadoPeriodo.CERRADO.value else None

    # --- Líneas --------------------------------------------------------------------------------

    def asentar(self, linea: LineaAsiento, id_usuario: Optional[int]) -> LineaAsiento:
        """Resuelve el par de cuentas vigente y persiste la línea. Sin par, queda PENDIENTE_CUENTA,
        se alerta al Contador y el período no podrá cerrarse (RF-86 FA-5, CA-21)."""
        tipo = linea.tipo_hecho_corregido or linea.tipo_hecho
        if linea.estado != "REGISTRADA":
            linea.asignar_cuentas(self.config.resolver_cuenta(tipo, linea.sentido, linea.id_especie, linea.subtipo_costo))
        guardada = self.asientos.agregar(linea)
        if guardada.estado == "PENDIENTE_CUENTA":
            self.auditar(EventoAuditoria(
                tipo_evento="LINEA_ASIENTO_PENDIENTE_CUENTA", severidad=Severidad.WARNING.value,
                payload={"tipo_hecho": tipo, "sentido": linea.sentido, "id_especie": linea.id_especie,
                         "subtipo_costo": linea.subtipo_costo, "valor": str(linea.valor)},
                id_usuario=id_usuario, id_sistema=None if id_usuario else ID_SISTEMA,
                id_activo_biologico=linea.id_activo_biologico, id_periodo_contable=linea.id_periodo_contable,
                id_referencia=guardada.id_linea_asiento_nic41, monto_afectado=linea.valor,
            ))
            self._avisar_sin_cuenta(linea, tipo)
        return guardada

    def _avisar_sin_cuenta(self, linea: LineaAsiento, tipo: str) -> None:
        """FA-5: un aviso por combinación y período. El adaptador usa su propia sesión: si la transacción
        del hecho se revierte, el aviso queda igual, y sigue siendo cierto (la matriz no tiene ese par)."""
        if self.notificador is None:
            return
        clave = {"tipo_hecho": tipo, "sentido": linea.sentido, "id_especie": linea.id_especie,
                 "subtipo_costo": linea.subtipo_costo, "id_periodo_contable": linea.id_periodo_contable}
        if self.notificador.ya_notificado("ALERTA_FINANCIERA_NIC41", clave):
            return
        especie = ((self.activos.especie(linea.id_especie) if self.activos and linea.id_especie else None) or {}).get(
            "nombre", "todas las especies")
        subtipo = f" de {ETIQUETA_SUBTIPO.get(linea.subtipo_costo, 'otro costo')}" if linea.subtipo_costo else ""
        self.notificador.a_contadores("ALERTA_FINANCIERA_NIC41", (
            f"Falta la cuenta contable de {ETIQUETA_HECHO.get(tipo, 'un hecho contable')}{subtipo} "
            f"({ETIQUETA_SENTIDO.get(linea.sentido, linea.sentido.lower())}) para {especie}. El registro quedó pendiente "
            "de cuenta y el período no podrá cerrarse hasta configurarla en Configuración contable."),
            clave, id_finca=linea.id_finca)

    def revertir_lineas(self, lineas: list[LineaAsiento], periodo: Periodo, fecha: date, tabla_origen: str,
                        id_origen: int, justificacion: str, id_usuario: Optional[int]) -> list[LineaAsiento]:
        """Líneas espejo con el par invertido. Si la original es de un período cerrado, la
        corrección es ``AJUSTE_PERIODO_ANTERIOR`` en el período abierto (RF-87 v1.1)."""
        nuevas = []
        for original in lineas:
            de_periodo_cerrado = original.id_periodo_contable != periodo.id_periodo_contable
            espejo = LineaAsiento(
                tipo_hecho=TipoHecho.AJUSTE_PERIODO_ANTERIOR.value if de_periodo_cerrado else original.tipo_hecho,
                tipo_hecho_corregido=original.tipo_hecho if de_periodo_cerrado else None,
                sentido=original.sentido, valor=original.valor, fecha_hecho=fecha,
                id_periodo_contable=periodo.id_periodo_contable, id_activo_biologico=original.id_activo_biologico,
                id_especie=original.id_especie, id_finca=original.id_finca,
                numero_id_tributaria=original.numero_id_tributaria, tabla_origen=tabla_origen, id_origen=id_origen,
                tipo_evidencia=original.tipo_evidencia, subtipo_costo=original.subtipo_costo,
                es_estimacion=original.es_estimacion, es_reverso=not original.es_reverso,
                id_linea_corregida=original.id_linea_asiento_nic41, justificacion=justificacion, id_usuario=id_usuario,
            )
            if original.estado == "REGISTRADA":  # mismo par de la original, invertido
                espejo.cuenta_debito, espejo.cuenta_credito = original.cuenta_credito, original.cuenta_debito
                espejo.estado = "REGISTRADA"
            nuevas.append(self.asentar(espejo, id_usuario))
        return nuevas

    def auditar(self, evento: EventoAuditoria) -> None:
        self.auditoria.registrar(evento)
