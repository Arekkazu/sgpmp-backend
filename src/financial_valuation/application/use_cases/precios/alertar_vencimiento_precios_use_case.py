# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-89 FA-4/FA-5: avisos de precios próximos a vencer y vencidos |
# | 2026-11-05 | Arekkazu | M06 RF-89: la alerta nombra la especie y la vigencia del precio, no su id |
# | 2026-11-08 | Arekkazu | INC-M06-299-G81 RF-89: avisos de vencimiento sin duplicados tras reinicios (marca persistente) |
"""Caso de uso diario de RF-89: avisa al Contador los precios que vencen dentro de la ventana
configurada (a 30, 15 y 7 días, los que caben en ella, y el día del vencimiento) y los que vencieron
sin otro precio vigente para su especie.

Cada aviso se envía una sola vez: su marca (precio + umbral) queda en el detalle del evento de la
notificación y se consulta antes de enviar, así que un reinicio del proceso o un día sin ejecutar
no lo repite ni lo pierde (se envía el umbral más cercano alcanzado que no se haya enviado)."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from src.financial_valuation.domain.repositories.configuracion_contable_repository import ConfiguracionContableRepository
from src.financial_valuation.domain.repositories.notificacion_financiera_port import NotificacionFinancieraPort
from src.financial_valuation.domain.repositories.precio_repository import PrecioRepository
from src.financial_valuation.domain.services.precios import precio_vigente
from src.shared.fechas import hoy_usuario

TIPO_AVISO = "ALERTA_FINANCIERA_NIC41"
_UMBRALES_FIJOS = (15, 7, 0)
# Un precio vencido sin reemplazo se avisa aunque el proceso no haya corrido el día siguiente.
_DIAS_ATRAS_VENCIDOS = 7


def _nombre(precio, especies: dict) -> str:
    """«Bovino (vigente desde 2026-10-01)»: el Contador reconoce el precio por su especie y su vigencia."""
    return f"{especies.get(precio.id_especie, 'la especie')} (vigente desde {precio.fecha_vigencia:%Y-%m-%d})"


def umbral_alcanzado(dias_restantes: int, ventana: int) -> Optional[int]:
    """Umbral más cercano ya alcanzado (``ventana`` y los de 15, 7 y 0 días que caben en ella)."""
    umbrales = sorted({ventana, *(u for u in _UMBRALES_FIJOS if u <= ventana)})
    return next((u for u in umbrales if dias_restantes <= u), None)


class AlertarVencimientoPreciosUseCase:
    def __init__(self, precios: PrecioRepository, config: ConfiguracionContableRepository,
                 notificador: NotificacionFinancieraPort) -> None:
        self.precios = precios
        self.config = config
        self.notificador = notificador

    def execute(self) -> int:
        hoy = hoy_usuario()
        ventana = self.config.obtener().dias_alerta_vencimiento_precio
        avisos = 0
        especies = {e["id_especie"]: e["especie"] for e in self.config.listar_parametros_especie()}
        for precio in self.precios.por_vencer(hoy - timedelta(days=_DIAS_ATRAS_VENCIDOS), hoy + timedelta(days=ventana)):
            aviso, mensaje = self._aviso(precio, hoy, ventana, especies)
            if aviso is None:
                continue
            marca = {"id_precio_mercado": precio.id_precio_mercado, "aviso": aviso}
            if self.notificador.ya_notificado(TIPO_AVISO, marca):
                continue
            self.notificador.a_contadores(TIPO_AVISO, mensaje, marca)
            avisos += 1
        return avisos

    def _aviso(self, precio, hoy: date, ventana: int, especies: dict) -> tuple[Optional[str], Optional[str]]:
        if precio.fecha_vencimiento < hoy:
            lista = self.precios.de_especie(precio.id_especie, precio.categoria, precio.id_metrica_produccion)
            if precio_vigente(lista, hoy) is not None:
                return None, None
            return "VENCIDO", (f"El precio de mercado de {_nombre(precio, especies)} venció sin reemplazo: los activos "
                               "de esa especie quedan sin precio vigente. Registre un precio nuevo o se medirán con el "
                               "último como estimación.")
        umbral = umbral_alcanzado((precio.fecha_vencimiento - hoy).days, ventana)
        if umbral is None:
            return None, None
        return f"{umbral}_DIAS", (f"El precio de mercado de {_nombre(precio, especies)} vence el "
                                  f"{precio.fecha_vencimiento:%Y-%m-%d}. Registre su reemplazo.")
