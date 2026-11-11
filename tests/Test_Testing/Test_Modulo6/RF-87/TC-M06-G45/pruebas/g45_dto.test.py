"""Valida con Pydantic real los bodies literales enviados por G45; sin TEST."""
import ast
from pathlib import Path
import re
import sys

raiz = next(p for p in Path(__file__).resolve().parents if (p / "src").is_dir())
sys.path.insert(0, str(raiz))
from src.financial_valuation.infrastructure.dto.m06_dto import CostoDTO, RevertirReconocimientoDTO

fuente = (Path(__file__).resolve().parents[1] / "g45.mjs").read_text(encoding="utf-8")

def body(ruta):
    patron = r"req\('POST','" + re.escape(ruta) + r"',(\{[^{}]+\})\)"
    match = re.search(patron, fuente)
    assert match, f"Body no localizado: {ruta}"
    literal = re.sub(r"([,{])\s*([A-Za-z_][A-Za-z_0-9]*)\s*:", r"\1'\2':", match.group(1))
    return ast.literal_eval(literal)

costo = body("/finanzas/costos")
reversion = body("/finanzas/reconocimientos/949/reversion")
assert CostoDTO.model_validate(costo).monto_costo > 0
assert RevertirReconocimientoDTO.model_validate(reversion).motivo_reversion == reversion["motivo_reversion"]
print("OK DTO reales: costo y reversión; el simulador no genera respuestas con modelo Pydantic")
