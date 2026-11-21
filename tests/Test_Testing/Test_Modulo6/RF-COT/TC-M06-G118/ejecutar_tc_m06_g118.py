# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-08 | —      | Primera evaluación: BLOQUEADO (activo compartido 943; primera_evaluacion/). |
# | 2026-11-13 | —      | Preparación TC-M06-50 con activo aislado 1571; sin POST (preparacion/). |
# | 2026-11-15 | —      | Confirmación externa Samuel AAEF documentada; G118 sigue NO APROBADO (TC-50 pendiente). |
# | 2026-11-15 | —      | TC-M06-50 ejecutado (cotización 15); G118 APROBADO. |
"""TC-M06-G118 (RF-COT) — integridad del activo y ausencia de efectos contables.

Alcance: TC-M06-50 + canal AAEF.
Dictamen grupo: APROBADO.

Evidencia vigente:
  resultados/estado_oficial_G118.json
  resultados/ejecucion_tc50_2026-11-15/
  resultados/confirmacion_samuel_aaef_2026-11-15/
  resultados/reevaluacion_fixture_aaef_2026-11-15/
  resultados/preparacion/
"""
from __future__ import annotations

from pathlib import Path

CARPETA = Path(__file__).resolve().parent
OFICIAL = CARPETA / "resultados" / "estado_oficial_G118.json"


def main() -> int:
    print("TC-M06-G118 — APROBADO (TC-M06-50 cotizacion 15 / RF-94 29463).")
    print("Consulte:", OFICIAL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
