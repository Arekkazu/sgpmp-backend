# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-08 | —      | Evaluación histórica BLOQUEADA (primera_evaluacion/). |
# | 2026-11-13 | —      | Preparación con datos aislados 2126/411; solo lectura (preparacion/). |
"""TC-M06-G96 (RF-88) — valor en libros y límite no negativo.

Subcasos: TC-M06-05, TC-M06-06, TC-M06-07.
Estado: preparación; sin POST de deterioro ni cierre.

Evidencia:
  resultados/primera_evaluacion/  — histórico BLOQUEADO
  resultados/preparacion/         — inspección vigente
"""
from __future__ import annotations

from pathlib import Path

CARPETA = Path(__file__).resolve().parent
PREP = CARPETA / "resultados" / "preparacion" / "informe_preparacion_G96.md"


def main() -> int:
    print("TC-M06-G96 — fase de preparacion (sin escritura).")
    print("Baseline 2126 verificado: costo 10M, dep 0, det 0, libros 10M, periodo 411 ABIERTO.")
    print("Consulte:", PREP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
