# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-89 paso 2: historial de precios con su estado efectivo |
"""Caso de uso RF-89 paso 2: historial por especie y categoría, del más reciente al más antiguo,
con su estado (vigente, programado, vencido, superado) calculado a la fecha de hoy."""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from src.financial_valuation.domain.repositories.precio_repository import PrecioRepository
from src.financial_valuation.domain.services.precios import estado_precio, precio_vigente
from src.shared.fechas import hoy_usuario


class ListarPreciosUseCase:
    def __init__(self, precios: PrecioRepository) -> None:
        self.precios = precios

    def execute(self, id_especie: Optional[int] = None) -> list[dict]:
        hoy = hoy_usuario()
        lista = self.precios.listar(id_especie)
        grupos = defaultdict(list)
        for p in lista:
            grupos[(p.id_especie, p.categoria, p.id_metrica_produccion, p.fuente)].append(p)
        vigentes = defaultdict(list)
        for (especie, categoria, metrica, _), precios in grupos.items():
            vigentes[(especie, categoria, metrica)].extend(precios)
        resultado = []
        for p in lista:
            aplicado = precio_vigente(vigentes[(p.id_especie, p.categoria, p.id_metrica_produccion)], hoy)
            resultado.append({**p.__dict__, "estado": estado_precio(p, grupos[(p.id_especie, p.categoria,
                                                                              p.id_metrica_produccion, p.fuente)], hoy),
                              "es_aplicado": aplicado is not None and aplicado.id_precio_mercado == p.id_precio_mercado})
        return resultado
