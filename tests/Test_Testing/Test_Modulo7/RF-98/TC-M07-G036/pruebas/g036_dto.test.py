"""DTO actual de RF-98: FA-3 se valida en caso de uso, no en Pydantic."""
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[6]))
from src.accounting_integration.infrastructure.dto.m07_dto import RegistrarContratoDTO, RegistrarAnexoDTO

fecha = (date.today() + timedelta(days=400)).isoformat()
base = dict(contrato_version="6.0", tipo_cambio="MAJOR", fecha_vigencia=fecha,
            id_mapeo_anexo_aaef=2, mapeadores=["COMPRAS"], periodo_gracia_dias=90)
for version, anexo in [("3.0", 2), ("6.0", 999999), ("6.0", 8), ("6.0", 2), ("6.1", 3), ("6.2", 2)]:
    assert RegistrarContratoDTO.model_validate({**base, "contrato_version": version,
                                                 "id_mapeo_anexo_aaef": anexo}).contrato_version == version
for mapeadores in ([], ["MAPPER_X"]):
    assert RegistrarContratoDTO.model_validate({**base, "mapeadores": mapeadores}).mapeadores == mapeadores
anexo = dict(codigo_anexo="QA-G036-V2", version_anexo="6.0",
             ruta_documento="docs/qa/QA-G036-V2.md",
             sha256_documento=sha256(b"QA-G036-V2").hexdigest())
assert RegistrarAnexoDTO.model_validate(anexo).codigo_anexo == "QA-G036-V2"
print("OK Pydantic: DTO acepta FA-3 para validación de caso de uso")

