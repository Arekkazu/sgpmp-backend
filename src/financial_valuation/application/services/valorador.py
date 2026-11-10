# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-84/89: valor razonable menos costos de venta de un activo |
# | 2026-11-08 | destroyerban | INC-M06-310-G12 RF-83: el precio congelado vencido también es estimación |
# | 2026-11-08 | destroyerban | INC-M06-316-G16 RF-84: referencia documental de los costos manuales |
"""Servicio de aplicación: valor razonable menos costos de venta de un activo en una fecha (RF-84).

Toma el precio vigente de RF-89 por la regla de prioridad, la magnitud física de M02 y los costos
de venta de M09. No persiste nada: devuelve el cálculo listo para guardar o el motivo por el que
no se puede valorar."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from src.financial_valuation.domain.entities.activo_financiero import DatosActivo
from src.financial_valuation.domain.entities.valoracion import CalculoValor
from src.financial_valuation.domain.repositories.configuracion_contable_repository import (
    ConfiguracionContableRepository,
)
from src.financial_valuation.domain.repositories.precio_repository import PrecioRepository
from src.financial_valuation.domain.services.nic41 import costos_venta, valor_neto
from src.financial_valuation.domain.services.precios import Precio, motivo_estimacion, precio_vigente, ultimo_precio_conocido
from src.financial_valuation.domain.value_objects.nic41 import CategoriaPrecio, FuentePrecio

MOTIVOS = {
    "SIN_PRECIO": "No hay precio de mercado vigente para la especie {especie}. Registre uno en Precios de mercado.",
    "SIN_MAGNITUD": "El activo {activo} no tiene un pesaje registrado: no se puede medir su valor por kilogramo.",
    "SIN_COSTOS_VENTA": "No hay costos de venta configurados para la especie {especie}: ingréselos manualmente "
                        "o configúrelos en Configuración contable.",
    "VALOR_NETO_NO_POSITIVO": "Los costos de venta igualan o superan el valor de mercado del activo {activo}. "
                              "Revise los parámetros o valide el resultado con una justificación.",
}


@dataclass(frozen=True)
class ResultadoValoracion:
    calculo: Optional[CalculoValor]
    precio: Optional[Precio]
    motivo: Optional[str] = None
    mensaje: Optional[str] = None

    @property
    def es_valido(self) -> bool:
        return self.motivo is None


class Valorador:
    def __init__(self, precios: PrecioRepository, config: ConfiguracionContableRepository) -> None:
        self.precios = precios
        self.config = config

    def categoria(self, id_especie: int) -> str:
        parametro = self.config.parametro_especie(id_especie)
        return parametro.categoria_precio if parametro else CategoriaPrecio.PESO_KG.value

    def precio_para(self, activo: DatosActivo, dia: date, permitir_estimado: bool) -> tuple[Optional[Precio], bool]:
        """Precio vigente; sin él y si se permite, el último conocido como estimación (RF-83 FA-1)."""
        lista = self.precios.de_especie(activo.id_especie, self.categoria(activo.id_especie))
        precio = precio_vigente(lista, dia)
        if precio is not None:
            return precio, precio.fuente == FuentePrecio.ESTIMADA.value
        if permitir_estimado:
            ultimo = ultimo_precio_conocido(lista, dia)
            if ultimo is not None:
                return ultimo, True
        return None, False

    def valorar(
        self,
        activo: DatosActivo,
        dia: date,
        id_periodo_contable: int,
        id_usuario: int,
        *,
        permitir_estimado: bool = False,
        precio_congelado: Optional[Precio] = None,
        costos_manuales: Optional[dict] = None,
        justificacion: Optional[str] = None,
        aceptar_no_positivo: bool = False,
        referencia_documental: Optional[str] = None,
    ) -> ResultadoValoracion:
        textos = {"especie": activo.especie, "activo": activo.identificador}
        if precio_congelado is not None:
            # El cierre congela el último precio conocido si se incluyen activos sin precio vigente (RF-87 FA-2).
            precio, estimado = precio_congelado, motivo_estimacion(precio_congelado, dia) is not None
        else:
            precio, estimado = self.precio_para(activo, dia, permitir_estimado)
        if precio is None:
            return ResultadoValoracion(None, None, "SIN_PRECIO", MOTIVOS["SIN_PRECIO"].format(**textos))
        magnitud, unidad = activo.magnitud(precio.categoria)
        if not magnitud or magnitud <= 0:
            return ResultadoValoracion(None, precio, "SIN_MAGNITUD", MOTIVOS["SIN_MAGNITUD"].format(**textos))
        parametro = self.config.costos_venta_vigentes(activo.id_especie)
        if parametro is None and not costos_manuales:
            return ResultadoValoracion(None, precio, "SIN_COSTOS_VENTA", MOTIVOS["SIN_COSTOS_VENTA"].format(**textos))
        bruto = magnitud * precio.precio_unitario
        costos = costos_venta(
            bruto,
            parametro.pct_transporte if parametro else None,
            parametro.pct_comisiones if parametro else None,
            parametro.pct_impuestos if parametro else None,
            costos_manuales,
        )
        vn = valor_neto(magnitud, precio.precio_unitario, costos)
        if vn.requiere_revision and not aceptar_no_positivo:
            return ResultadoValoracion(None, precio, "VALOR_NETO_NO_POSITIVO",
                                       MOTIVOS["VALOR_NETO_NO_POSITIVO"].format(**textos))
        calculo = CalculoValor(
            id_activo_biologico=activo.id_activo_biologico, id_precio_mercado=precio.id_precio_mercado,
            id_periodo_contable=id_periodo_contable, magnitud=magnitud, unidad_magnitud=unidad,
            precio_unitario=precio.precio_unitario, valor_razonable_bruto=vn.bruto,
            costo_transporte=costos.transporte, costo_comisiones=costos.comisiones,
            costo_impuestos_transaccion=costos.impuestos, otros_costos_disposicion=costos.otros,
            valor_neto=vn.neto, metodo_costo=costos.metodo_global,
            json_metodo_costo={**costos.metodos, "categoria": precio.categoria, "fuente_precio": precio.fuente,
                               "cabezas": activo.cabezas,
                               **({"referencia_documental": referencia_documental} if costos.tiene_manuales else {})},
            id_usuario=id_usuario, estado="REVISION_REQUERIDA" if vn.requiere_revision else "CALCULADO",
            justificacion=justificacion if costos.tiene_manuales or vn.requiere_revision else None,
            id_parametro_costo_venta=parametro.id_parametro_costo_venta if parametro else None,
            id_evento_magnitud=activo.id_evento_peso if precio.categoria == CategoriaPrecio.PESO_KG.value else None,
            tiene_valor_estimado=estimado,
        )
        return ResultadoValoracion(calculo, precio)
