# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-91: eslabones obligatorios por tipo de evidencia |
"""Regla de RF-91 paso 2: qué eslabones exige cada tipo de evidencia. Python puro.

``eslabones`` trae ``True``/``False`` por eslabón comprobado; ``None`` = no aplica a esta línea.
"""
from __future__ import annotations

from src.financial_valuation.domain.value_objects.nic41 import TipoEvidencia

# Nivel de la cadena de cada eslabón (1 captura física, 2 vinculación biológica, 3 valoración, 4 registro).
NIVEL = {"lecturas_nic41": 1, "evento_m02": 2, "auditoria_m02": 2, "evento_sanitario": 2,
         "precio_documentado": 3, "cierre": 3, "origen": 4}

REQUERIDOS = {
    TipoEvidencia.IOT_DIRECTO.value: ("origen", "evento_m02", "lecturas_nic41", "precio_documentado"),
    TipoEvidencia.REGISTRO_MANUAL.value: ("origen", "evento_m02", "precio_documentado"),
    TipoEvidencia.VARIACION_PRECIO.value: ("origen", "precio_documentado"),
    TipoEvidencia.EVENTO_SANITARIO.value: ("origen", "evento_sanitario"),
    TipoEvidencia.CIERRE_PERIODO.value: ("origen", "cierre", "precio_documentado"),
}


def verificar_cadena(tipo_evidencia: str, eslabones: dict) -> tuple[str, list[str], int | None]:
    """(estado, eslabones faltantes, nivel del primer fallo). Un eslabón requerido que no aplica
    (``None``) no se exige: p. ej. un costo manual no tiene evento de M02 (RF-91 FA-3)."""
    faltantes = [e for e in REQUERIDOS[tipo_evidencia] if eslabones.get(e) is False]
    if not faltantes:
        return "VERIFICADO", [], None
    return "PENDIENTE_TRAZABILIDAD", faltantes, min(NIVEL[e] for e in faltantes)
