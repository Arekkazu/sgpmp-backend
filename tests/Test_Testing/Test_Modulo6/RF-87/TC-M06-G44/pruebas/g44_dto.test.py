"""Validación local de los tres DTO usados por G44; no accede a TEST."""
from pathlib import Path
import sys
import ast
from typing import Optional

from pydantic import ValidationError

raiz = next(p for p in Path(__file__).resolve().parents if (p / "src").is_dir())
sys.path.insert(0, str(raiz))
from src.financial_valuation.infrastructure.dto.m06_dto import CierreDTO, CostoDTO
from src.shared.base_dto import BaseDTO

# El router importa la conexión de producción al cargarse. Se compila solo el
# nodo del DTO real para validar sus campos sin inicializar infraestructura.
router = raiz / "src/configuration/infrastructure/routers/finca_router.py"
arbol = ast.parse(router.read_text(encoding="utf-8"))
nodo = next(x for x in arbol.body if isinstance(x, ast.ClassDef) and x.name == "TitularFincaDTO")
namespace = {"BaseDTO": BaseDTO, "Optional": Optional}
exec(compile(ast.Module(body=[nodo], type_ignores=[]), str(router), "exec"), namespace)
TitularFincaDTO = namespace["TitularFincaDTO"]

assert CierreDTO.model_validate({}).autorizar_exclusiones is False
assert CierreDTO.model_validate({}).incluir_activos_sin_precio is False
costo = CostoDTO.model_validate({
    "subtipo_costo": "MANO_OBRA",
    "origen_costo": "MANO_OBRA_PROPIA",
    "monto_costo": "103.00",
    "fecha_costo": "2026-11-10",
    "id_activo_biologico": 1569,
    "naturaleza_costo": "MANTENIMIENTO",
})
assert costo.id_activo_biologico == 1569
assert TitularFincaDTO.model_validate({
    "tipo_id_tributaria": None,
    "numero_id_tributaria": None,
    "dv": None,
    "razon_social": None,
}).tipo_id_tributaria is None
try:
    CostoDTO.model_validate({"subtipo_costo": "MANO_OBRA", "origen_costo": "MANO_OBRA_PROPIA", "monto_costo": 0, "fecha_costo": "2026-11-10"})
    raise AssertionError("Costo cero aceptado")
except ValidationError:
    pass
print("OK DTO: CierreDTO, CostoDTO y TitularFincaDTO")
