"""Valida el body literal de cierre contra el DTO real, sin TEST."""
import sys
from pathlib import Path

raiz = next(p for p in Path(__file__).resolve().parents if (p / 'src').is_dir())
sys.path.insert(0, str(raiz))
from src.financial_valuation.infrastructure.dto.m06_dto import CierreDTO

fuente = (Path(__file__).resolve().parents[1] / 'g46.mjs').read_text(encoding='utf-8')
assert "req('POST','/finanzas/periodos/220/cierre',{})" in fuente
dto = CierreDTO.model_validate({})
assert not dto.autorizar_exclusiones
print('OK CierreDTO real: body {} sin autorización de exclusiones')
