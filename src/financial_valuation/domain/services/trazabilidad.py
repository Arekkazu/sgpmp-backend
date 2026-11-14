# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-91: eslabones obligatorios por tipo de evidencia |
# | 2026-11-13 | Leandro | TC-M06-G52 RF-91: exigir evidencia de las bitácoras fuente. |
"""Regla de RF-91 paso 2: qué eslabones exige cada tipo de evidencia. Python puro.

``eslabones`` trae ``True``/``False`` por eslabón comprobado; ``None`` = no aplica a esta línea.
"""
from __future__ import annotations

from src.financial_valuation.domain.value_objects.nic41 import TipoEvidencia

# Nivel de la cadena de cada eslabón (1 captura física, 2 vinculación biológica, 3 valoración, 4 registro).
NIVEL = {"lecturas_nic41": 1, "evento_m02": 2, "auditoria_m02": 2, "evento_sanitario": 2,
         "auditoria_m03": 1, "auditoria_m04": 2,
         "precio_documentado": 3, "cierre": 3, "origen": 4}

AUDITORIAS_REQUERIDAS = {
    TipoEvidencia.IOT_DIRECTO.value: ("auditoria_m02", "auditoria_m03"),
    TipoEvidencia.REGISTRO_MANUAL.value: ("auditoria_m02",),
    TipoEvidencia.EVENTO_SANITARIO.value: ("auditoria_m04",),
}

REQUERIDOS = {
    TipoEvidencia.IOT_DIRECTO.value: ("origen", "evento_m02", "lecturas_nic41", "precio_documentado"),
    TipoEvidencia.REGISTRO_MANUAL.value: ("origen", "evento_m02", "precio_documentado"),
    TipoEvidencia.VARIACION_PRECIO.value: ("origen", "precio_documentado"),
    TipoEvidencia.EVENTO_SANITARIO.value: ("origen", "evento_sanitario"),
    TipoEvidencia.CIERRE_PERIODO.value: ("origen", "cierre", "precio_documentado"),
}


def verificar_cadena(tipo_evidencia: str, eslabones: dict) -> tuple[str, list[str], int | None]:
    """Devuelve estado, eslabones faltantes y nivel del primer fallo.

    Las auditorías requeridas por el tipo de evidencia necesitan una comprobación positiva.
    Los demás eslabones conservan el significado de ``None`` como «no aplica».
    """
    auditorias = AUDITORIAS_REQUERIDAS.get(tipo_evidencia, ())
    indisponibles = eslabones.get("fuentes_no_disponibles", [])
    if indisponibles:
        return "VERIFICACION_PENDIENTE", indisponibles, min(NIVEL[e] for e in indisponibles)
    faltantes = [e for e in REQUERIDOS[tipo_evidencia] if eslabones.get(e) is False]
    faltantes.extend(e for e in auditorias if eslabones.get(e) is not True)
    if not faltantes:
        return "VERIFICADO", [], None
    return "PENDIENTE_TRAZABILIDAD", faltantes, min(NIVEL[e] for e in faltantes)
