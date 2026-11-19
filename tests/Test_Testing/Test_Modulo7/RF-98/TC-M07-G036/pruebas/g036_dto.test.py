"""Validación local de todos los cuerpos G036 con los DTO reales; no decide veredictos TEST."""
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path
import sys
from pydantic import ValidationError
sys.path.insert(0, str(Path(__file__).resolve().parents[6]))
from src.accounting_integration.infrastructure.dto.m07_dto import RegistrarContratoDTO, RegistrarAnexoDTO

fecha = (date.today() + timedelta(days=400)).isoformat()
base = dict(contrato_version="4.0", tipo_cambio="MAJOR", fecha_vigencia=fecha,
            id_mapeo_anexo_aaef=2, mapeadores=["COMPRAS"], periodo_gracia_dias=90)
for version, anexo in [("2.1", 2), ("4.0", 999999), ("4.0", 4), ("4.0", 2), ("4.1", 3), ("4.2", 2)]:
    dto = RegistrarContratoDTO.model_validate({**base, "contrato_version": version, "id_mapeo_anexo_aaef": anexo})
    assert dto.contrato_version == version
for mappers in ([], ["MAPPER_X"]):
    try:
        RegistrarContratoDTO.model_validate({**base, "mapeadores": mappers})
    except ValidationError as exc:
        assert any("mapeadores" in str(e["loc"]) for e in exc.errors())
    else:
        raise AssertionError(f"DTO aceptó {mappers}")
anexo = dict(codigo_anexo="QA-G036-BORRADOR", version_anexo="4.0",
             ruta_documento="docs/qa/QA-G036-BORRADOR.md",
             sha256_documento=sha256(b"QA-G036-BORRADOR").hexdigest())
assert RegistrarAnexoDTO.model_validate(anexo).codigo_anexo == "QA-G036-BORRADOR"
print("OK Pydantic: cuerpos válidos aceptados; [] y [MAPPER_X] rechazados por DTO")
