# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-08 | —      | Primera evaluación: BLOQUEADO por timeout de login en TEST (primera_evaluacion/). |
# | 2026-11-13 | —      | Preparación de re-prueba TC-M06-48/49; sin POST de cotizaciones (preparacion/). |
# | 2026-11-13 | —      | Ejecución autorizada 48a/48b/49a: RECHAZADO 1/3 (ultima_evaluacion/). |
"""TC-M06-G117 (RF-COT) — valores propuestos y fechas de vencimiento.

Alcance ejecutado: TC-M06-48a, TC-M06-48b, TC-M06-49a (sin 49b).
Resultado vigente: RECHAZADO (DISC-G117-01 confirmada en 48a/48b; 49a APROBADO).

Evidencia vigente:
  tests/Test_Testing/Test_Modulo6/RF-COT/TC-M06-G117/resultados/ultima_evaluacion/

Este módulo no reejecuta los POST. La evaluación inicial se conserva en
resultados/primera_evaluacion/ y la preparación en resultados/preparacion/.
"""
from __future__ import annotations

from pathlib import Path

CARPETA = Path(__file__).resolve().parent
VIGENTE = CARPETA / "resultados" / "ultima_evaluacion" / "resumen_ejecucion_vigente_TC-M06-G117.json"


def main() -> int:
    print("TC-M06-G117 / TC-M06-48 + TC-M06-49 — RECHAZADO (evidencia vigente).")
    print("48a/48b: RECHAZADO (400 VAL_ENTRADA vs matriz 422). 49a: APROBADO. 49b: no ejecutado.")
    print("Consulte:", VIGENTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
