# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-08 | —      | Primera evaluación: TC-M06-46/47 REQUIERE ACLARACIÓN (primera_evaluacion/). |
# | 2026-11-13 | —      | Ejecución negativa autorizada: APROBADO 2/2 (ultima_evaluacion/). |
"""TC-M06-G116 (RF-COT) — disponibilidad del activo, período y valoración para cotizaciones.

Alcance: TC-M06-46 y TC-M06-47.
Resultado vigente: APROBADO 2/2.

Evidencia vigente:
  tests/Test_Testing/Test_Modulo6/RF-COT/TC-M06-G116/resultados/ultima_evaluacion/

Este módulo no reejecuta los POST negativos ni genera nuevos estados contradictorios.
La evaluación inicial se conserva en resultados/primera_evaluacion/.
"""
from __future__ import annotations

from pathlib import Path

CARPETA = Path(__file__).resolve().parent
VIGENTE = CARPETA / "resultados" / "ultima_evaluacion" / "resumen_ejecucion_vigente_TC-M06-G116.json"


def main() -> int:
    print("TC-M06-G116 / TC-M06-46 + TC-M06-47 — APROBADO 2/2 (evidencia vigente).")
    print("No se reejecutan los POST. Consulte:", VIGENTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
