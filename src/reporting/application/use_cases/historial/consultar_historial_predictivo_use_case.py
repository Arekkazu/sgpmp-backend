# | Fecha      | Nombre   | Que se hizo                                                            |
# |------------|----------|------------------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-106: línea de tiempo de predicciones, eventos y retroalimentación |
# | 2026-11-19 | Arekkazu | M8-01 RF-106: marca las predicciones en modo sombra |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Caso de uso: historial clínico predictivo de un animal para el Veterinario (RF-106).

Une sobre un mismo eje de tiempo las predicciones guardadas de M04 (RF-67, nunca el motor en vivo), los eventos
sanitarios de M02 (RF-41) y las retroalimentaciones del Veterinario (RF-72). Calcula la TVCO, marca los conflictos,
las correspondencias predicción–evento (ventana configurable en M09) y las predicciones pendientes de evaluar.

Las tres fuentes se leen por separado: si una falla, la vista carga con las demás y dice cuál faltó (RNF-06).
Rango por defecto: los últimos 12 meses; máximo 24 (400 si se pide más). Solo animales activos o en tratamiento.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from src.reporting.application.use_cases.reportes.generacion import AbrirFuente, Solicitante
from src.reporting.domain.historial_predictivo import (
    RANGO_MAXIMO_DIAS,
    Marcador,
    agrupar_colisiones,
    calcular_tvco,
    correspondencias,
    pendientes,
    valoraciones_por_inferencia,
)
from src.shared.errors import AuthorizationError, BusinessRuleError, NotFoundError, ValidationError
from src.shared.fechas import fin_dia_usuario, hoy_usuario, inicio_dia_usuario

logger = logging.getLogger(__name__)

VENTANA_POR_DEFECTO = 12
POR_PAGINA = 20
_ESTADOS_VISIBLES = ("ACTIVO", "EN_TRATAMIENTO")
_FUENTES = {"inferencias": "Predicciones del modelo", "eventos": "Eventos sanitarios",
            "retroalimentaciones": "Retroalimentación clínica"}
SIN_INFERENCIAS = ("Este animal no tiene predicciones en el rango elegido. Prueba con otro rango de fechas; los "
                   "eventos sanitarios registrados sí se muestran.")


class ConsultarHistorialPredictivoUseCase:
    """Consulta el historial de predicciones, eventos y retroalimentación de un activo."""

    def __init__(self, abrir_fuente: AbrirFuente) -> None:
        self.abrir_fuente = abrir_fuente

    def execute(self, id_activo: int, solicitante: Solicitante, *, fecha_inicio: Optional[date] = None,
                fecha_fin: Optional[date] = None, niveles: Optional[list[int]] = None,
                incluir_eventos: bool = True, incluir_retroalimentacion: bool = True, pagina: int = 1,
                ahora: Optional[datetime] = None) -> dict[str, Any]:
        """Devuelve la línea de tiempo predictiva del activo con su tasa de validación."""
        ahora = ahora or datetime.now(timezone.utc)
        with self.abrir_fuente(solicitante.id_usuario, solicitante.zona_horaria) as fuente:
            fin = fecha_fin or hoy_usuario()
            inicio = fecha_inicio or (fin - timedelta(days=365))
            if inicio > fin:
                raise ValidationError(code="VAL_ENTRADA", field="fecha_inicio",
                                      message="La fecha de inicio no puede ser posterior a la fecha de fin.")
            if (fin - inicio).days > RANGO_MAXIMO_DIAS:
                raise ValidationError(code="VAL_ENTRADA", field="fecha_inicio",
                                      message="El rango máximo es de 24 meses. Elige un rango más corto.")
            activo = fuente.ubicar("activo", id_activo)
            if activo is None:
                raise NotFoundError(code="ACTIVO_INEXISTENTE", message="El animal o lote no existe.",
                                    field="id_activo_biologico")
            if solicitante.fincas is not None and activo["id_finca"] not in solicitante.fincas:
                raise AuthorizationError(code="FINCA_NO_AUTORIZADA", message="No tienes permisos para esta finca.",
                                         field="id_activo_biologico")
            if activo.get("estado") and activo["estado"] not in _ESTADOS_VISIBLES:
                raise BusinessRuleError(code="ACTIVO_NO_VIGENTE", field="id_activo_biologico",
                                        message="El historial predictivo solo se muestra para animales activos o en "
                                                "tratamiento.")
            desde, hasta = inicio_dia_usuario(inicio), fin_dia_usuario(fin)
            no_disponibles: list[str] = []

            def leer(nombre: str, consulta) -> list[dict[str, Any]]:
                try:
                    return consulta()
                except Exception:
                    logger.exception("RF-106: falló la fuente %s del animal %s", nombre, id_activo)
                    no_disponibles.append(_FUENTES[nombre])
                    return []

            inferencias = leer("inferencias", lambda: fuente.inferencias(activo=id_activo, desde=desde, hasta=hasta))
            eventos = [e for e in leer("eventos", lambda: fuente.eventos_sanitarios_aislados(
                activo=id_activo, desde=desde, hasta=hasta)) if e["fuente"] == "M02"]
            retros = leer("retroalimentaciones",
                          lambda: fuente.retroalimentaciones(activo=id_activo, desde=desde, hasta=hasta))
            ventana = int(fuente.parametro("ventana_correspondencia_horas") or VENTANA_POR_DEFECTO)
            nombres = fuente.nombres_usuarios([r["id_usuario_veterinario"] for r in retros if r["id_usuario_veterinario"]]
                                              + [e["id_veterinario"] for e in eventos if e["id_veterinario"]])
            ficha = fuente.ficha(id_activo) or {}

        valoraciones = valoraciones_por_inferencia(retros)
        tvco = calcular_tvco([i["id_resultado_inferencia"] for i in inferencias], retros)
        visibles = [i for i in inferencias if niveles is None or (i["nivel_riesgo"] or 0) in niveles]
        m_pred = [Marcador("PREDICCION", i["fecha_inferencia"], {
            "id_resultado_inferencia": str(i["id_resultado_inferencia"]), "nivel_riesgo": i["nivel_riesgo"],
            "confianza": float(i["confianza_global"]) if i["confianza_global"] is not None else None,
            "condicion": i["condicion"] or "Condición no identificada", "modo_sombra": bool(i.get("modo_sombra")),
            "tiene_retroalimentacion": i["id_resultado_inferencia"] in valoraciones,
            "en_conflicto": len(valoraciones.get(i["id_resultado_inferencia"], ())) > 1}) for i in visibles]
        m_eventos = [Marcador("EVENTO_SANITARIO", e["fecha"], {
            "id_evento": e["id_evento"], "tipo": e["tipo"], "descripcion": e["descripcion"] or "Sin descripción",
            "veterinario": nombres.get(e["id_veterinario"]) or "Sin veterinario registrado"})
            for e in eventos] if incluir_eventos else []
        m_retros = [Marcador("RETROALIMENTACION", r["fecha_retroalimentacion"], {
            "id_resultado_inferencia": str(r["id_resultado_inferencia"]), "valoracion": r["valoracion"],
            "veterinario": nombres.get(r["id_usuario_veterinario"]) or "Sin veterinario registrado",
            "observaciones": r["observaciones"],
            "en_conflicto": len(valoraciones.get(r["id_resultado_inferencia"], ())) > 1})
            for r in retros] if incluir_retroalimentacion else []
        ventana_td = timedelta(hours=ventana)
        lista_pendientes = pendientes(inferencias, set(valoraciones), ahora)
        inicio_pagina = (pagina - 1) * POR_PAGINA

        def serial(m: Marcador) -> dict[str, Any]:
            return {"tipo": m.tipo, "fecha": m.fecha.isoformat(), **m.datos}

        return {
            "activo": {"id_activo_biologico": id_activo, "identificador": ficha.get("identificador"),
                       "especie": ficha.get("especie"), "finca": ficha.get("finca"), "estado": ficha.get("estado")},
            "rango_fechas_aplicado": {"fecha_inicio": inicio.isoformat(), "fecha_fin": fin.isoformat()},
            "ventana_correspondencia_horas": ventana,
            "predicciones": [serial(m) for m in m_pred],
            "eventos_sanitarios": [serial(m) for m in m_eventos],
            "retroalimentaciones": [serial(m) for m in m_retros],
            "grupos": [[serial(m) for m in g] for g in agrupar_colisiones(m_pred + m_eventos + m_retros) if len(g) > 1],
            "correspondencias": correspondencias(m_pred, m_eventos, ventana_td),
            "tvco": {"porcentaje": tvco.porcentaje, "texto": tvco.texto, "tvco_denominador": tvco.validadas,
                     "tvco_excluidas_conflicto": tvco.con_conflicto, "excluidas_sin_retroalimentacion":
                     tvco.sin_retroalimentacion, "tasa_error": tvco.tasa_error},
            "pendientes": {"total": len(lista_pendientes), "pagina": pagina, "por_pagina": POR_PAGINA, "items": [{
                "id_resultado_inferencia": str(p["id_resultado_inferencia"]), "fecha_inferencia":
                p["fecha_inferencia"].isoformat(), "nivel_riesgo": p["nivel_riesgo"],
                "condicion": p["condicion"] or "Condición no identificada"}
                for p in lista_pendientes[inicio_pagina:inicio_pagina + POR_PAGINA]]},
            "metadatos": {"total_inferencias": len(inferencias), "total_eventos_sanitarios": len(eventos),
                          "total_retroalimentaciones": len(retros), "total_pendientes": len(lista_pendientes),
                          "total_conflictos": tvco.con_conflicto},
            "fuentes_no_disponibles": no_disponibles,
            "mensaje": SIN_INFERENCIAS if not inferencias and "Predicciones del modelo" not in no_disponibles else None,
        }
