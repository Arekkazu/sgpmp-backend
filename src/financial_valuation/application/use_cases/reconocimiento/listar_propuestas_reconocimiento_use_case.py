# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82 CA-1: bandeja de propuestas de reconocimiento inicial |
# | 2026-11-11 | Arekkazu | USAB-M06 M6-03 RF-82/87: razón social del período y listas filtradas por el titular del período |
"""Caso de uso RF-82 pasos 1-6: propuestas calculadas al vuelo para los activos sin reconocimiento."""
from __future__ import annotations

from typing import Optional

from src.financial_valuation.application.services.propuesta_reconocimiento import ProponedorReconocimiento, Propuesta
from src.financial_valuation.domain.repositories.activo_financiero_port import ActivoFinancieroPort
from src.shared.errors import NotFoundError


def serializar_propuesta(p: Propuesta) -> dict:
    a = p.activo
    return {
        "id_activo_biologico": a.id_activo_biologico, "identificador": a.identificador, "tipo": a.tipo,
        "especie": a.especie, "id_especie": a.id_especie, "finca": a.finca, "estado": a.estado,
        "origen_financiero": a.origen_financiero, "costo_adquisicion": a.costo_adquisicion,
        "soporte_documental": a.soporte_documental, "fecha_reconocimiento": p.fecha_reconocimiento,
        "es_apertura": p.es_apertura, "clasificacion": p.clasificacion, "indicador_valoracion": p.indicador_valoracion,
        "valor_inicial": p.valor_inicial, "costos_venta": p.costos_venta,
        "magnitud": p.calculo.magnitud if p.calculo else None, "unidad_magnitud": p.calculo.unidad_magnitud if p.calculo else None,
        "precio": ({"id_precio_mercado": p.precio.id_precio_mercado, "precio_unitario": p.precio.precio_unitario,
                    "unidad_medida": p.precio.unidad_medida, "fuente": p.precio.fuente,
                    "fecha_vigencia": p.precio.fecha_vigencia} if p.precio else None),
        "hechos": [{"tipo_hecho": t, "sentido": s, "valor": v} for t, s, v in p.hechos],
        "bloqueos": p.bloqueos, "advertencias": p.advertencias, "requiere_costos_manuales": p.requiere_costos_manuales,
        "es_confirmable": p.es_confirmable,
    }


class ListarPropuestasReconocimientoUseCase:
    def __init__(self, activos: ActivoFinancieroPort, proponedor: ProponedorReconocimiento) -> None:
        self.activos = activos
        self.proponedor = proponedor

    def execute(self, id_usuario: int, numero_id_tributaria: Optional[str] = None) -> list[dict]:
        return [serializar_propuesta(self.proponedor.proponer(a, id_usuario))
                for a in self.activos.listar_sin_reconocimiento(numero_id_tributaria)]

    def de_activo(self, id_activo_biologico: int, id_usuario: int, costos_manuales: Optional[dict] = None,
                  clasificacion: Optional[str] = None) -> dict:
        activo = self.activos.obtener(id_activo_biologico)
        if activo is None:
            raise NotFoundError(code="ACTIVO_NO_ENCONTRADO", message="El activo biológico no existe.")
        return serializar_propuesta(self.proponedor.proponer(activo, id_usuario, costos_manuales=costos_manuales,
                                                             clasificacion=clasificacion))
