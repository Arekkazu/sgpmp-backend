# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-08 | —      | Primera evaluación: BLOQUEADO → `_arch/primera_evaluacion/`. |
# | 2026-11-13 | —      | Preparación TC-51/52 (cot. 6/7) sin escritura → `_arch/preparacion/`. |
# | 2026-11-13 | —      | Cierre documental TC-52 APROBADO; TC-51 pendiente. |
# | 2026-11-15 | —      | Ejecución autorizada TC-51; dictamen G119 APROBADO. |
"""TC-M06-G119 (RF-COT / RF-94) — anulación y vencimiento automático.

Alcance: TC-M06-51 (cotización 6) y TC-M06-52 (cotización 7).
Resultado vigente: **APROBADO**.

Evidencia vigente:
  resultados/ultima_evaluacion/resumen_ejecucion_vigente_TC-M06-G119.json
  resultados/ejecucion_tc51_2026-11-15/
  resultados/ultima_evaluacion/evidencia_escenario_tc52_TC-M06-G119.json

Histórico intermedio: resultados/_arch/
No reejecuta anulación ni vencer() desde este entrypoint.
"""
from __future__ import annotations

from pathlib import Path

CARPETA = Path(__file__).resolve().parent
VIGENTE = CARPETA / "resultados" / "ultima_evaluacion" / "resumen_ejecucion_vigente_TC-M06-G119.json"


def main() -> int:
    print("TC-M06-G119 — APROBADO (TC-M06-51 + TC-M06-52).")
    print("Sin reejecución de escritura desde este script. Consulte:", VIGENTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
