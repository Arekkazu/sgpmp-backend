# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-83/86: medición posterior, variaciones y líneas de asiento |
# | 2026-11-08 | destroyerban | INC-M06-307-G11 RF-83: una variación menor a 0,01 se mide sin asiento |
# | 2026-11-08 | destroyerban | INC-M06-308-G12 RF-83: alerta MEDICION_PENDIENTE al Contador si la medición es estimada |
# | 2026-11-08 | destroyerban | INC-M06-310-G12 RF-83: motivo de la estimación y precio usado |
# | 2026-11-08 | destroyerban | INC-M06-312-G14 RF-83: evento en período cerrado queda pendiente y alerta |
# | 2026-11-13 | Arekkazu | INC-M06-91-G43-03 RF-83/87: la medición estimada sin variación se registra, marcada y con alerta |
"""Servicio de aplicación: medición posterior de un activo (RF-83) y su registro en resultados
(RF-86). Lo usan el procesador de eventos de M02 y el cierre del período (RF-87). No hace commit.

Sin precio vigente (medición estimada o pendiente) RF-83 exige alertar al Contador (restricción 3,
salida 4). Como el medidor no confirma la transacción, deja la alerta en cola y el caso de uso la
envía con ``tomar_alertas`` después de su ``commit()``; si revierte, la descarta.

La variación se mide contra el último cálculo registrado del activo, no contra el valor al inicio
del período: así el cierre no vuelve a registrar lo que ya registraron los eventos (contradicción
C-3 de RF-87 pasos 4-5).

El cálculo y la medición guardan 4 decimales; la variación y su línea, 2 (RF-86 trunca). Un
componente que trunca a 0,00 no tiene nada que asentar y se omite solo (CA-14), pero la medición
se registra igual: sin eso el valor vigente no avanza y nunca acumula los cambios pequeños. Una
medición estimada se registra aunque no varíe: la marca de estimación y su alerta (RF-83 v1.2) no
dependen del monto."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from src.financial_valuation.application.services.contabilizador import ID_SISTEMA, Contabilizador
from src.financial_valuation.application.services.valorador import Valorador
from src.financial_valuation.domain.entities.activo_financiero import DatosActivo
from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria, LineaAsiento, Periodo
from src.financial_valuation.domain.entities.valoracion import CalculoValor, Medicion, VariacionRegistro
from src.financial_valuation.domain.repositories.valoracion_repository import ValoracionRepository
from src.financial_valuation.domain.services.nic41 import CERO, descomponer_variacion, sentido_por_signo
from src.financial_valuation.domain.services.precios import Precio, motivo_estimacion
from src.financial_valuation.domain.value_objects.nic41 import Sentido, Severidad, TipoEvidencia, TipoHecho


_DESCRIPCION_MOTIVO = {
    "SIN_PRECIO_VIGENTE": ("No había precio de mercado vigente para la especie {especie} el {dia:%Y-%m-%d}: se usó "
                           "el último precio conocido, vigente desde el {vigencia:%Y-%m-%d}."),
    "FUENTE_ESTIMADA": "El precio vigente de la especie {especie} es una estimación registrada por el Contador.",
}


def _motivo_estimacion(precio: Precio, dia: date, especie: str) -> dict:
    """RF-83 FA-1: por qué la medición es estimada y con qué precio, para el evento de RF-94."""
    motivo = motivo_estimacion(precio, dia) or "FUENTE_ESTIMADA"
    return {
        "motivo_estimacion": motivo,
        "descripcion_motivo": _DESCRIPCION_MOTIVO[motivo].format(especie=especie, dia=dia, vigencia=precio.fecha_vigencia),
        "precio_usado": {
            "id_precio_mercado": precio.id_precio_mercado, "precio_unitario": str(precio.precio_unitario),
            "unidad_medida": precio.unidad_medida, "fuente": precio.fuente,
            "fecha_vigencia": precio.fecha_vigencia.isoformat(),
            "fecha_vencimiento": precio.fecha_vencimiento.isoformat() if precio.fecha_vencimiento else None,
        },
    }


@dataclass(frozen=True)
class AlertaMedicion:
    mensaje: str
    detalle: dict
    id_finca: Optional[int]


@dataclass(frozen=True)
class ResultadoMedicion:
    estado: str  # MEDIDO | SIN_VARIACION | PENDIENTE
    motivo: Optional[str] = None
    mensaje: Optional[str] = None
    calculo: Optional[CalculoValor] = None
    id_medicion: Optional[int] = None
    variacion_total: Decimal = CERO


class Medidor:
    def __init__(self, valorador: Valorador, valoraciones: ValoracionRepository, contabilizador: Contabilizador) -> None:
        self.valorador = valorador
        self.valoraciones = valoraciones
        self.contabilizador = contabilizador
        self._alertas: list[AlertaMedicion] = []

    def tomar_alertas(self) -> list[AlertaMedicion]:
        """Alertas para el Contador acumuladas desde la última llamada (se vacía la cola)."""
        alertas, self._alertas = self._alertas, []
        return alertas

    def medir(
        self,
        activo: DatosActivo,
        periodo: Periodo,
        dia: date,
        *,
        origen: str,
        id_usuario: int,
        id_usuario_auditoria: Optional[int],
        id_evento: Optional[int] = None,
        id_cierre: Optional[int] = None,
        hubo_evento: bool = True,
        permitir_estimado: bool = True,
        precio_congelado: Optional[Precio] = None,
        tipo_evidencia_tb: str = TipoEvidencia.REGISTRO_MANUAL.value,
        tipo_evidencia_pm: str = TipoEvidencia.VARIACION_PRECIO.value,
        tipo_hecho_tb: str = TipoHecho.VARIACION_VR_TB.value,
    ) -> ResultadoMedicion:
        anterior = self.valoraciones.ultimo_calculo(activo.id_activo_biologico)
        if anterior is None:
            return self._pendiente(activo, periodo, id_evento, id_usuario_auditoria, "SIN_BASE",
                                   "El activo no tiene una valoración base registrada.")
        resultado = self.valorador.valorar(activo, dia, periodo.id_periodo_contable, id_usuario,
                                           permitir_estimado=permitir_estimado, precio_congelado=precio_congelado)
        if not resultado.es_valido:
            return self._pendiente(activo, periodo, id_evento, id_usuario_auditoria, resultado.motivo, resultado.mensaje)
        nuevo = resultado.calculo
        comparable = anterior.unidad_magnitud == nuevo.unidad_magnitud
        variacion = descomponer_variacion(anterior.valor_neto, nuevo.valor_neto,
                                          anterior.magnitud if comparable else None, nuevo.magnitud,
                                          hubo_evento_biologico=hubo_evento)
        tb, pm = sentido_por_signo(variacion.transformacion), sentido_por_signo(variacion.precio)
        if variacion.transformacion == CERO and variacion.precio == CERO and not nuevo.tiene_valor_estimado:
            self.contabilizador.auditar(EventoAuditoria(
                tipo_evento="MEDICION_SIN_VARIACION", severidad=Severidad.INFO.value,
                payload={"valor_neto": str(nuevo.valor_neto), "id_evento": id_evento, "origen": origen},
                id_usuario=id_usuario_auditoria, id_sistema=None if id_usuario_auditoria else ID_SISTEMA,
                id_activo_biologico=activo.id_activo_biologico, id_periodo_contable=periodo.id_periodo_contable,
                id_referencia=id_evento or id_cierre,
            ))
            return ResultadoMedicion("SIN_VARIACION", calculo=anterior)

        nuevo.id_calculo_valor_razonable = self.valoraciones.agregar_calculo(nuevo)
        medicion = Medicion(
            id_activo_biologico=activo.id_activo_biologico, id_calculo_actual=nuevo.id_calculo_valor_razonable,
            id_calculo_anterior=anterior.id_calculo_valor_razonable, origen_medicion=origen,
            valor_razonable_anterior=anterior.valor_neto, valor_razonable_actual=nuevo.valor_neto,
            ganancia_perdida_transformacion=variacion.transformacion, ganancia_perdida_precio_mercado=variacion.precio,
            tiene_valor_estimado=nuevo.tiene_valor_estimado, id_periodo_contable=periodo.id_periodo_contable,
            id_evento=id_evento,
            supuestos_aplicados={"precio_unitario": str(nuevo.precio_unitario), "fuente": resultado.precio.fuente,
                                 "magnitud": str(nuevo.magnitud), "unidad": nuevo.unidad_magnitud,
                                 "costos_venta": str(nuevo.valor_razonable_bruto - nuevo.valor_neto),
                                 "estimado": nuevo.tiene_valor_estimado},
        )
        medicion.id_medicion_posterior = self.valoraciones.agregar_medicion(medicion)
        componentes = (
            (tb, variacion.transformacion, "TRANSFORMACION_BIOLOGICA", tipo_hecho_tb, tipo_evidencia_tb),
            (pm, variacion.precio, "PRECIO_MERCADO", TipoHecho.VARIACION_VR_PM.value, tipo_evidencia_pm),
        )
        sin_asiento = []
        for signo, monto, nombre, tipo_hecho, evidencia in componentes:
            if signo is None:
                if monto != CERO:
                    sin_asiento.append({"componente": nombre, "monto": str(monto)})
                continue
            sentido, valor = signo
            es_tb = nombre == "TRANSFORMACION_BIOLOGICA"
            registro = VariacionRegistro(
                id_activo_biologico=activo.id_activo_biologico, tipo=f"{sentido.value}_{nombre}",
                variacion_transformacion=monto if es_tb else CERO, variacion_precio_mercado=CERO if es_tb else monto,
                valor_razonable_anterior=anterior.valor_neto, valor_razonable_nuevo=nuevo.valor_neto,
                id_periodo_contable=periodo.id_periodo_contable, id_usuario=id_usuario,
                tiene_estimacion=nuevo.tiene_valor_estimado, id_medicion_posterior=medicion.id_medicion_posterior,
                id_evento=id_evento, id_precio_mercado=nuevo.id_precio_mercado, id_cierre=id_cierre,
            )
            registro.id_variacion_valor_razonable = self.valoraciones.agregar_variacion(registro)
            # El nacimiento en un POBLACIONAL es reconocimiento inicial de las crías (NIC 41 ¶27).
            sentido_linea = Sentido.UNICO.value if tipo_hecho == TipoHecho.RECONOCIMIENTO_NACIMIENTO.value else sentido.value
            self.contabilizador.asentar(LineaAsiento(
                tipo_hecho=tipo_hecho, sentido=sentido_linea, valor=valor, fecha_hecho=dia,
                id_periodo_contable=periodo.id_periodo_contable, id_activo_biologico=activo.id_activo_biologico,
                id_especie=activo.id_especie, id_finca=activo.id_finca,
                numero_id_tributaria=activo.numero_id_tributaria, tabla_origen="variaciones_valor_razonable",
                id_origen=registro.id_variacion_valor_razonable, tipo_evidencia=evidencia,
                es_estimacion=nuevo.tiene_valor_estimado, id_usuario=id_usuario_auditoria,
            ), id_usuario_auditoria)
            self.contabilizador.auditar(EventoAuditoria(
                tipo_evento="VARIACION_REGISTRADA", severidad=Severidad.INFO.value,
                payload={"tipo": registro.tipo, "monto": str(monto), "id_evento": id_evento, "id_cierre": id_cierre},
                id_usuario=id_usuario_auditoria, id_sistema=None if id_usuario_auditoria else ID_SISTEMA,
                id_activo_biologico=activo.id_activo_biologico, id_periodo_contable=periodo.id_periodo_contable,
                id_referencia=registro.id_variacion_valor_razonable, monto_afectado=monto,
            ))
        self.contabilizador.auditar(EventoAuditoria(
            tipo_evento="MEDICION_CON_ESTIMACION" if nuevo.tiene_valor_estimado else "MEDICION_POSTERIOR",
            severidad=Severidad.WARNING.value if nuevo.tiene_valor_estimado else Severidad.INFO.value,
            payload={"origen": origen, "valor_anterior": str(anterior.valor_neto), "valor_actual": str(nuevo.valor_neto),
                     "transformacion": str(variacion.transformacion), "precio": str(variacion.precio),
                     "componentes_sin_asiento": sin_asiento,
                     **(_motivo_estimacion(resultado.precio, dia, activo.especie) if nuevo.tiene_valor_estimado else {})},
            id_usuario=id_usuario_auditoria, id_sistema=None if id_usuario_auditoria else ID_SISTEMA,
            id_activo_biologico=activo.id_activo_biologico, id_periodo_contable=periodo.id_periodo_contable,
            id_referencia=medicion.id_medicion_posterior, monto_afectado=variacion.total,
        ))
        if nuevo.tiene_valor_estimado:  # RF-83 restricción 3 y salida 4
            self.alertar_pendiente(activo, periodo, dia, id_evento, id_usuario_auditoria, "PRECIO_ESTIMADO", (
                f"El activo {activo.identificador} se midió el {dia:%Y-%m-%d} con un precio estimado porque la especie "
                f"{activo.especie} no tiene precio de mercado vigente. Revise la medición y registre el precio vigente."),
                id_medicion=medicion.id_medicion_posterior)
        return ResultadoMedicion("MEDIDO", calculo=nuevo, id_medicion=medicion.id_medicion_posterior,
                                 variacion_total=variacion.total)

    def _pendiente(self, activo, periodo, id_evento, id_usuario_auditoria, motivo, mensaje) -> ResultadoMedicion:
        """RF-86 FA-3 / RF-83 FA-2: la medición queda pendiente y se alerta al Contador."""
        self.alertar_pendiente(activo, periodo, None, id_evento, id_usuario_auditoria, motivo, (
            f"La medición del activo {activo.identificador} quedó pendiente: {mensaje}"), detalle_auditoria=mensaje)
        return ResultadoMedicion("PENDIENTE", motivo=motivo, mensaje=mensaje)

    def alertar_pendiente(self, activo, periodo, dia, id_evento, id_usuario_auditoria, motivo, mensaje, *,
                           id_medicion=None, detalle_auditoria=None) -> None:
        """Evento ``MEDICION_PENDIENTE`` en RF-94 y alerta en cola para el Contador de la finca."""
        self.contabilizador.auditar(EventoAuditoria(
            tipo_evento="MEDICION_PENDIENTE", severidad=Severidad.WARNING.value,
            payload={"motivo": motivo, "mensaje": detalle_auditoria or mensaje, "id_evento": id_evento,
                     "id_medicion": id_medicion},
            id_usuario=id_usuario_auditoria, id_sistema=None if id_usuario_auditoria else ID_SISTEMA,
            id_activo_biologico=activo.id_activo_biologico, id_periodo_contable=periodo.id_periodo_contable,
            id_referencia=id_medicion or id_evento,
        ))
        self._alertas.append(AlertaMedicion(mensaje, {
            "motivo": motivo, "id_activo_biologico": activo.id_activo_biologico, "id_evento": id_evento,
            "id_medicion": id_medicion, "id_periodo_contable": periodo.id_periodo_contable,
            "fecha": dia.isoformat() if dia else None,
        }, activo.id_finca))
