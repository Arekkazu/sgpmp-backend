# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-89 FA-4/FA-5: avisos de precios próximos a vencer y vencidos |
# | 2026-11-05 | Arekkazu | M06 RF-89: la alerta nombra la especie y la vigencia del precio, no su id |
# | 2026-11-08 | Arekkazu | INC-M06-299-G81 RF-89: avisos de vencimiento sin duplicados tras reinicios (marca persistente) |
# | 2026-11-10 | —        | TC-M06-G109: el modo QA no avisa a Contadores que no estén en la lista |
# | 2026-11-10 | —        | TC-M06-G109: QA solo procesa precios autorizados; TEST no usa la vía general |
"""Caso de uso diario de RF-89: avisa al Contador los precios que vencen dentro de la ventana
configurada (a 30, 15 y 7 días, los que caben en ella, y el día del vencimiento) y los que vencieron
sin otro precio vigente para su especie.

Cada aviso se envía una sola vez: su marca (precio + umbral) queda en el detalle del evento de la
notificación y se consulta antes de enviar, así que un reinicio del proceso o un día sin ejecutar
no lo repite ni lo pierde (se envía el umbral más cercano alcanzado que no se haya enviado).

El proceso periódico de ``main.py`` entra solo por ``execute``. La vía general solo se abre
con ``SGPMP_ENTORNO=PROD`` y el interruptor QA apagado. En TEST, DEV, o si el entorno falta o
no se reconoce, no hay envío general. Con el interruptor encendido hacen falta las dos listas.
Un precio que no esté en la lista no llega a la lógica de umbral, evento ni marca."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from src.financial_valuation.domain.repositories.configuracion_contable_repository import ConfiguracionContableRepository
from src.financial_valuation.domain.repositories.notificacion_financiera_port import NotificacionFinancieraPort
from src.financial_valuation.domain.repositories.precio_repository import PrecioRepository
from src.financial_valuation.domain.services.precios import precio_vigente
from src.financial_valuation.infrastructure.configuracion_alertas import resolver_envio_alertas
from src.shared.fechas import hoy_usuario

logger = logging.getLogger(__name__)

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
        try:
            envio = resolver_envio_alertas()
        except Exception:
            logger.error("Alertas de vencimiento M06 detenidas: no se pudo leer la configuración.")
            return 0
        if not envio.permite_envio:
            logger.error("Alertas de vencimiento M06 detenidas.")
            return 0
        hoy = hoy_usuario()
        ventana = self.config.obtener().dias_alerta_vencimiento_precio
        avisos = 0
        especies = {e["id_especie"]: e["especie"] for e in self.config.listar_parametros_especie()}
        candidatos = self.precios.por_vencer(hoy - timedelta(days=_DIAS_ATRAS_VENCIDOS), hoy + timedelta(days=ventana))
        if envio.modo == "qa":
            permitidos = set(envio.precios)
            candidatos = [precio for precio in candidatos if precio.id_precio_mercado in permitidos]
        for precio in candidatos:
            aviso, mensaje = self._aviso(precio, hoy, ventana, especies)
            if aviso is None:
                continue
            marca = {"id_precio_mercado": precio.id_precio_mercado, "aviso": aviso}
            if self.notificador.ya_notificado(TIPO_AVISO, marca):
                continue
            if envio.modo == "qa":
                entregado = self.notificador.a_usuarios_autorizados(envio.destinatarios, TIPO_AVISO, mensaje, marca)
                if entregado is False:
                    continue
            else:
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
