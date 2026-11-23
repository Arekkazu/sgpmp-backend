# | Fecha      | Nombre   | Que se hizo                                          |
# |------------|----------|------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: vista previa con las primeras 20 filas   |
# | 2026-11-19 | Arekkazu | M08 RF-104: parámetros, indicadores y autor en la vista previa |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Caso de uso: vista previa de un reporte (RF-104 Fase 2.2).

Valida igual que la generación y arma el contenido en la instantánea. Devuelve los totales, las primeras 20 filas
del cuerpo (o el resumen de las secciones), el número estimado de registros y si se generará en segundo plano. La
ficha del animal muestra solo identificación e historial productivo; el ejecutivo, sus 5 secciones con totales."""
from __future__ import annotations

from typing import Any, Optional

from src.reporting.application.use_cases.reportes.generacion import (
    SIN_DATOS,
    AbrirFuente,
    Solicitante,
    json_seguro,
    preparar,
)
from src.reporting.domain.reportes.catalogo import FILAS_VISTA_PREVIA, LIMITE_SINCRONO
from src.reporting.domain.reportes.contenido import Tabla


def tabla_previa(t: Tabla, limite: Optional[int] = FILAS_VISTA_PREVIA) -> dict[str, Any]:
    """Serializa una tabla para la vista previa, recortada a ``limite`` filas."""
    filas = t.filas if limite is None else t.filas[:limite]
    return {
        "titulo": t.titulo, "nota": t.nota, "total_filas": len(t.filas),
        "columnas": [{"clave": c.clave, "titulo": c.titulo, "tipo": c.tipo} for c in t.columnas],
        "filas": [{c.clave: json_seguro(f.get(c.clave)) for c in t.columnas} for f in filas],
    }


class PrevisualizarReporteUseCase:
    """Arma la vista previa de un reporte sin guardarlo."""

    def __init__(self, abrir_fuente: AbrirFuente) -> None:
        self.abrir_fuente = abrir_fuente

    def execute(self, tipo: str, filtros: Optional[dict[str, Any]], solicitante: Solicitante) -> dict[str, Any]:
        """Devuelve la vista previa del reporte con los filtros dados."""
        with self.abrir_fuente(solicitante.id_usuario, solicitante.zona_horaria) as fuente:
            preparado = preparar(fuente, tipo, filtros, solicitante)
        c = preparado.contenido
        secciones = c.secciones[:c.secciones_vista_previa] if c.secciones_vista_previa else c.secciones
        registros = c.numero_registros
        return {
            "tipo_reporte": tipo, "titulo": c.titulo, "encabezado": [{"dato": k, "valor": v} for k, v in c.encabezado],
            "numero_registros": registros, "en_segundo_plano": registros > LIMITE_SINCRONO,
            "sin_datos": not c.tiene_datos, "mensaje": None if c.tiene_datos else SIN_DATOS,
            "resumen": [tabla_previa(t) for t in c.resumen],
            "detalle": tabla_previa(c.detalle) if c.detalle else None,
            "secciones": [{"titulo": s.titulo, "textos": s.textos, "tablas": [tabla_previa(t) for t in s.tablas]}
                          for s in secciones],
            "finales": [tabla_previa(t) for t in c.finales],
            "advertencias": c.advertencias, "aclaraciones": c.aclaraciones,
            "generado_por": c.generado_por or None,
            "parametros": [{"dato": k, "valor": v} for k, v in c.parametros],
            "indicadores": [{"etiqueta": i.etiqueta, "valor": json_seguro(i.valor), "tipo": i.tipo}
                            for i in c.indicadores],
        }
