# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82/RF-88 A: propuesta de reconocimiento inicial (NIC 41 ¶10, ¶12, ¶26-27, ¶30) |
# | 2026-11-05 | Arekkazu | M06: mensajes con rótulos legibles en vez de valores de enum |
# | 2026-11-08 | destroyerban | INC-M06-307-G11 RF-82: hecho menor a 0,01 se reconoce sin línea de asiento |
# | 2026-11-09 | LuisfNarvaez01 | INC-M06-302-G01 RF-82/RF-86: hecho RECONOCIMIENTO_DONACION |
"""Arma la propuesta de reconocimiento inicial de un activo (RF-82 pasos 2-6). No persiste.

La propuesta no se guarda hasta que el Contador la confirma: un activo sin reconocimiento
CONFIRMADO está, por definición, PENDIENTE_CONFIRMACION (RF-82 FA-4) y vuelve a la bandeja tras
una reversión (CA-14). Así no se acumulan propuestas obsoletas cuando cambia el precio.

Hechos que produce (RFC-018, catálogo cerrado de RF-86):
- NACIMIENTO → ``RECONOCIMIENTO_NACIMIENTO`` por el valor neto completo (¶27: la cría genera ganancia).
- COMPRA → la compra entra por su factura (RF-90 ``COMPRA_PROVEEDOR``); M06 solo registra
  ``RECONOCIMIENTO_DIFERENCIA = valor neto − costo`` (¶26-27; el RF cita ¶28, que es de productos).
- DONACION → ``RECONOCIMIENTO_DONACION`` (ingreso por donación, sin factura; cuenta propia en la matriz).
- TRANSFERENCIA_INTERNA → ``RECONOCIMIENTO_NACIMIENTO`` con sentido TRASLADO (activo contra la
  cuenta de traslado interno: no es un ingreso de la entidad).
Sin precio de mercado y con costo documentado se aplica el modelo de costo (¶30, RF-88 escenario A).

El valor de cada hecho se trunca a 2 decimales (RF-86); el que queda en 0,00 no genera línea, pero
el reconocimiento se registra con su valor de 4 decimales."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from src.financial_valuation.application.services.valorador import Valorador
from src.financial_valuation.domain.entities.activo_financiero import DatosActivo
from src.financial_valuation.domain.entities.valoracion import CalculoValor
from src.financial_valuation.domain.repositories.configuracion_contable_repository import (
    ConfiguracionContableRepository,
)
from src.financial_valuation.domain.services.nic41 import CERO, sentido_por_signo, truncar2
from src.financial_valuation.domain.services.precios import Precio
from src.financial_valuation.domain.value_objects.nic41 import IndicadorValoracion, Sentido, TipoHecho, estado_legible
from src.shared.fechas import hoy_usuario

RAZON_SIN_MERCADO = "Ausencia verificada de precio de mercado en el repositorio de precios"


@dataclass
class Propuesta:
    activo: DatosActivo
    fecha_reconocimiento: date
    es_apertura: bool
    clasificacion: Optional[str] = None
    indicador_valoracion: Optional[str] = None
    calculo: Optional[CalculoValor] = None
    precio: Optional[Precio] = None
    valor_inicial: Decimal = CERO
    costos_venta: Decimal = CERO
    hechos: list[tuple[str, str, Decimal]] = field(default_factory=list)  # (tipo_hecho, sentido, valor)
    bloqueos: list[dict] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)
    requiere_costos_manuales: bool = False
    vida_util_meses: Optional[int] = None

    @property
    def es_confirmable(self) -> bool:
        return not self.bloqueos

    def bloquear(self, codigo: str, mensaje: str) -> None:
        self.bloqueos.append({"codigo": codigo, "mensaje": mensaje})


def _hecho(tipo_hecho: str, sentido: str, valor: Decimal) -> list[tuple[str, str, Decimal]]:
    """Hecho con su valor de línea truncado; sin hecho si trunca a 0,00 (nada que asentar)."""
    linea = truncar2(valor)
    return [(tipo_hecho, sentido, linea)] if linea > 0 else []


class ProponedorReconocimiento:
    def __init__(self, valorador: Valorador, config: ConfiguracionContableRepository) -> None:
        self.valorador = valorador
        self.config = config

    def proponer(self, activo: DatosActivo, id_usuario: int, id_periodo: int = 0, *,
                 costos_manuales: Optional[dict] = None, justificacion: Optional[str] = None,
                 clasificacion: Optional[str] = None) -> Propuesta:
        configuracion = self.config.obtener()
        # Activos que ya estaban en M02 antes de M06: reconocimiento de apertura al precio del día en que
        # se reconocen (D-5); RF-82 R5 prohíbe valores retroactivos y no hay precio de su fecha de ingreso.
        es_apertura = activo.fecha_ingreso < configuracion.fecha_inicio_operacion
        dia = hoy_usuario() if es_apertura else activo.fecha_ingreso
        propuesta = Propuesta(activo, dia, es_apertura)
        parametro = self.config.parametro_especie(activo.id_especie)
        propuesta.clasificacion = clasificacion or (parametro.clasificacion if parametro else None)
        propuesta.vida_util_meses = parametro.vida_util_meses if parametro else None

        # ¶10: control (registrado y con finca titular), beneficio futuro (estado) y medición fiable.
        if not activo.es_valorable:
            propuesta.bloquear("ACTIVO_NO_VALORABLE", f"El activo está {estado_legible(activo.estado)}: solo se reconocen "
                                                      "los que están activos o en tratamiento.")
        if not activo.numero_id_tributaria:
            propuesta.bloquear("FINCA_SIN_TITULAR", f"La finca {activo.finca} no tiene titular tributario. "
                                                    "Complételo en Configuración → Fincas.")
        if not activo.origen_financiero:
            propuesta.bloquear("ORIGEN_FINANCIERO_NO_DEFINIDO", "Defina el origen financiero del activo en Activos "
                                                                "biológicos antes de reconocerlo.")
        if propuesta.clasificacion is None:
            propuesta.bloquear("CLASIFICACION_NO_CONFIGURADA", f"Configure la clasificación (producción o consumo) de la "
                                                               f"especie {activo.especie} en Configuración contable.")
        origen = (activo.origen_financiero or "").lower()
        if origen in ("compra", "donacion") and not activo.costo_adquisicion:
            propuesta.bloquear("COSTO_ADQUISICION_REQUERIDO", "El activo es de compra o donación y no tiene costo de "
                                                              "adquisición documentado en Activos biológicos.")

        resultado = self.valorador.valorar(activo, dia, id_periodo, id_usuario, costos_manuales=costos_manuales,
                                           justificacion=justificacion)
        if resultado.es_valido:
            propuesta.indicador_valoracion = IndicadorValoracion.VALOR_RAZONABLE.value
            propuesta.calculo, propuesta.precio = resultado.calculo, resultado.precio
            propuesta.valor_inicial = resultado.calculo.valor_neto
            propuesta.costos_venta = resultado.calculo.valor_razonable_bruto - resultado.calculo.valor_neto
            if resultado.calculo.tiene_valor_estimado:
                propuesta.advertencias.append("El precio de referencia es una estimación del Contador (fuente ESTIMADA).")
            propuesta.hechos = self._hechos_valor_razonable(origen, propuesta.valor_inicial, activo.costo_adquisicion)
        elif resultado.motivo == "SIN_COSTOS_VENTA":
            propuesta.requiere_costos_manuales = True
            propuesta.bloquear("COSTOS_VENTA_REQUERIDOS", resultado.mensaje)
        elif resultado.motivo == "SIN_PRECIO":
            precio_hoy, _ = self.valorador.precio_para(activo, hoy_usuario(), False)
            if precio_hoy is not None:  # hay mercado: ¶30 no permite refutar el valor razonable
                propuesta.bloquear("PRECIO_NO_VIGENTE_EN_FECHA", (
                    f"No hay precio de mercado vigente el {dia:%Y-%m-%d}, fecha de ingreso del activo. Registre el "
                    f"precio de la especie {activo.especie} con vigencia desde esa fecha."))
            else:
                self._modelo_costo(propuesta, origen)
        else:
            propuesta.bloquear(resultado.motivo, resultado.mensaje)
        return propuesta

    @staticmethod
    def _hechos_valor_razonable(origen: str, valor: Decimal, costo: Optional[Decimal]) -> list:
        if origen == "compra":
            signo = sentido_por_signo(valor - (costo or CERO))
            return [(TipoHecho.RECONOCIMIENTO_DIFERENCIA.value, signo[0].value, signo[1])] if signo else []
        if origen == "donacion":
            return [(TipoHecho.RECONOCIMIENTO_DONACION.value, Sentido.UNICO.value, valor)]
        sentido = Sentido.TRASLADO.value if origen == "transferencia_interna" else Sentido.UNICO.value
        return _hecho(TipoHecho.RECONOCIMIENTO_NACIMIENTO.value, sentido, valor)

    def _modelo_costo(self, propuesta: Propuesta, origen: str) -> None:
        """RF-82 paso 3 b / RF-88 escenario A (¶30): sin precio, el costo documentado es la medida."""
        activo = propuesta.activo
        if not activo.costo_adquisicion:
            propuesta.bloquear("RECONOCIMIENTO_BLOQUEADO_SIN_VALOR", (
                f"El activo {activo.identificador} (especie: {activo.especie}, origen: {origen or 'sin definir'}) no puede "
                "reconocerse: no hay precio de mercado ni costo de adquisición documentado. Registre un precio de "
                "mercado para la especie o el costo de adquisición del activo."))
            return
        if not propuesta.vida_util_meses:
            propuesta.bloquear("VIDA_UTIL_NO_CONFIGURADA", f"No se puede aplicar el método de costo: configure la vida "
                                                           f"útil de la especie {activo.especie} en Configuración contable.")
            return
        propuesta.indicador_valoracion = IndicadorValoracion.VALORACION_POR_COSTO.value
        propuesta.valor_inicial = Decimal(activo.costo_adquisicion)
        propuesta.advertencias.append(f"Valoración por costo por ausencia de precio de mercado para la especie "
                                      f"{activo.especie} (NIC 41 ¶30).")
        # La compra ya entra al activo por su factura; la donación y el traslado se asientan al costo.
        if origen == "donacion":
            propuesta.hechos = _hecho(TipoHecho.RECONOCIMIENTO_DONACION.value, Sentido.UNICO.value, propuesta.valor_inicial)
        elif origen == "transferencia_interna":
            propuesta.hechos = _hecho(TipoHecho.RECONOCIMIENTO_NACIMIENTO.value, Sentido.TRASLADO.value,
                                      propuesta.valor_inicial)
