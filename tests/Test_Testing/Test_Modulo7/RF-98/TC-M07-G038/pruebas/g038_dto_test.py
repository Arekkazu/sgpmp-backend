"""Validación local de los tres cuerpos de registro con el DTO real."""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[6]))
from src.accounting_integration.infrastructure.dto.m07_dto import RegistrarContratoDTO


def test_registros_g038():
    fecha = (date.today() + timedelta(days=400)).isoformat()
    for version, tipo, gracia in (("4.0", "MAJOR", 90), ("4.1", "MINOR", None), ("3.2", "MINOR", None)):
        body = dict(contrato_version=version, tipo_cambio=tipo, fecha_vigencia=fecha,
                    id_mapeo_anexo_aaef=2, mapeadores=["COMPRAS"])
        if gracia is not None:
            body["periodo_gracia_dias"] = gracia
        dto = RegistrarContratoDTO.model_validate(body)
        assert dto.contrato_version == version
        assert dto.tipo_cambio == tipo
        assert dto.periodo_gracia_dias == gracia
