"""Valida los cuerpos V2 contra los DTO reales sin llamadas remotas."""
from pathlib import Path
import sys

raiz = next(p for p in Path(__file__).resolve().parents if (p / "src").is_dir())
sys.path.insert(0, str(raiz))
from src.financial_valuation.infrastructure.dto.m06_dto import (
    AjustePeriodoAnteriorDTO, CierreDTO, CostoDTO, RevertirReconocimientoDTO
)

fuente = (Path(__file__).resolve().parents[1] / "lib" / "flujo_v2.mjs").read_text(encoding="utf-8")
for ruta in (
    "/finanzas/costos", "/finanzas/reconocimientos/949/reversion",
    "/finanzas/lineas-asiento/2625/ajustes", "/cierre/cancelacion"
):
    assert ruta in fuente, ruta

assert CierreDTO.model_validate({}).autorizar_exclusiones is False
assert CierreDTO.model_validate({"autorizar_exclusiones": True}).autorizar_exclusiones is True
assert CostoDTO.model_validate({
    "subtipo_costo": "MANO_OBRA", "origen_costo": "MANO_OBRA_PROPIA",
    "monto_costo": "50.00", "fecha_costo": "2026-11-13",
    "id_activo_biologico": 3001, "naturaleza_costo": "MANTENIMIENTO",
}).monto_costo > 0
assert RevertirReconocimientoDTO.model_validate({
    "motivo_reversion": "Corrección contable de prueba autorizada"
}).motivo_reversion
assert AjustePeriodoAnteriorDTO.model_validate({
    "tipo_ajuste": "AUMENTAR", "valor": "10.00",
    "justificacion": "Ajuste QA autorizado por error del período anterior",
}).valor > 0
print("OK DTO reales V2")
