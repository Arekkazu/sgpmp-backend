# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-08 | —      | Primera evaluación: BLOQUEADO → `_arch/primera_evaluacion_bloqueada_2026-11-08/`. |
# | 2026-11-15 | —      | TC-M06-40 APROBADO (ejecucion_tc40). G112 global INCOMPLETO. |
# | 2026-11-15 | —      | TC-M06-39 APROBADO + cierre documental G112 APROBADO (RF-90/RF-94). |
"""TC-M06-G112 (RF-90 / RF-109 / RF-94) — capitalización vs gasto de inversión directa.

Subcasos: TC-M06-39 (CAPITALIZAR), TC-M06-40 (GASTO).
RF-93: relacionado, PENDIENTE_CASO_INDEPENDIENTE (no condiciona aprobación del grupo).

Dictamen grupo: **APROBADO**.
Evidencias:
  - resultados/ejecucion_tc39_2026-11-15/
  - resultados/ejecucion_tc40_2026-11-15/

No reejecuta escrituras desde este entrypoint.
"""
from __future__ import annotations

from pathlib import Path

CARPETA = Path(__file__).resolve().parent
OFICIAL = CARPETA / "resultados" / "estado_oficial_G112.json"


def main() -> int:
    print("TC-M06-G112 — APROBADO (TC-M06-39 + TC-M06-40). RF-93 = PENDIENTE_CASO_INDEPENDIENTE.")
    print("Consulte:", OFICIAL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
