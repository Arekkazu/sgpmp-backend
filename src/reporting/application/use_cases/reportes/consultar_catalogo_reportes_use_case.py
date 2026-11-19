# | Fecha      | Nombre   | Que se hizo                                              |
# |------------|----------|----------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: reportes que el rol puede generar y sus filtros |
"""Caso de uso: catálogo de reportes que el usuario puede generar, con sus filtros (RF-104 Fase 1).

Solo aparecen los tipos para los que el rol tiene el permiso Ejecutar en ``modulo1.permisos``: el front no ofrece
lo que después respondería 403 (CA-6 a CA-9)."""
from __future__ import annotations

from typing import Any

from src.reporting.application.use_cases.reportes.generacion import Solicitante
from src.reporting.domain.reportes.catalogo import CATALOGO, ETIQUETAS, LIMITE_SINCRONO


class ConsultarCatalogoReportesUseCase:

    def execute(self, solicitante: Solicitante) -> list[dict[str, Any]]:
        return [{
            "tipo_reporte": d.tipo, "titulo": d.titulo, "periodo_cerrado": d.periodo_cerrado,
            "compara_periodos": d.compara_periodos, "limite_sincrono": LIMITE_SINCRONO,
            "filtros": [{"nombre": f.nombre, "etiqueta": ETIQUETAS[f.nombre], "tipo": f.tipo,
                         "obligatorio": f.obligatorio, "valores": list(f.valores)} for f in d.filtros],
        } for d in CATALOGO.values() if d.tipo in solicitante.permitidos]
