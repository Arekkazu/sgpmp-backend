# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-89 FA-4/FA-5: avisos de precios próximos a vencer y vencidos |
# | 2026-11-05 | Arekkazu | M06 RF-89: la alerta nombra la especie y la vigencia del precio, no su id |
"""Caso de uso diario de RF-89: avisa al Contador los precios que vencen dentro de la ventana
configurada (7, 15 o 30 días) y los que vencieron hoy sin otro precio vigente para su especie."""
from __future__ import annotations

from datetime import timedelta

from src.financial_valuation.domain.repositories.configuracion_contable_repository import ConfiguracionContableRepository
from src.financial_valuation.domain.repositories.notificacion_financiera_port import NotificacionFinancieraPort
from src.financial_valuation.domain.repositories.precio_repository import PrecioRepository
from src.financial_valuation.domain.services.precios import precio_vigente
from src.shared.fechas import hoy_usuario



def _nombre(precio, especies: dict) -> str:
    """«Bovino (vigente desde 2026-10-01)»: el Contador reconoce el precio por su especie y su vigencia."""
    return f"{especies.get(precio.id_especie, 'la especie')} (vigente desde {precio.fecha_vigencia:%Y-%m-%d})"

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
        for precio in self.precios.por_vencer(hoy - timedelta(days=1), hoy + timedelta(days=ventana)):
            if precio.fecha_vencimiento < hoy:
                lista = self.precios.de_especie(precio.id_especie, precio.categoria, precio.id_metrica_produccion)
                if precio_vigente(lista, hoy) is not None:
                    continue
                nombre = _nombre(precio, especies)
                mensaje = (f"El precio de mercado de {nombre} venció sin reemplazo: los activos de esa especie "
                           "quedan sin precio vigente. Registre un precio nuevo o se medirán con el último como estimación.")
            elif (precio.fecha_vencimiento - hoy).days in (ventana, 15 if ventana > 15 else -1, 7, 0):
                mensaje = (f"El precio de mercado de {_nombre(precio, especies)} vence el {precio.fecha_vencimiento:%Y-%m-%d}. "
                           "Registre su reemplazo.")
            else:
                continue
            self.notificador.a_contadores("ALERTA_FINANCIERA_NIC41", mensaje, {"id_precio_mercado": precio.id_precio_mercado})
            avisos += 1
        return avisos
