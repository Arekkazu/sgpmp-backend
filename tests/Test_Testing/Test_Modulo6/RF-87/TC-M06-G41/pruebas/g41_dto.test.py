"""Verificación local de los cuerpos G41 con los DTO Pydantic del backend."""
import json
import sys
import unittest
from datetime import date
from pathlib import Path

GROUP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GROUP.parents[4]))

from src.identity_access.infrastructure.dto.usuario_dto import LoginDTO
from src.biological_assets.infrastructure.dto.cambiar_estado_dto import CambiarEstadoDTO
from src.biological_assets.infrastructure.dto.registrar_evento_baja_dto import RegistrarEventoBajaDTO
from src.financial_valuation.infrastructure.dto.m06_dto import (
    PrecioDTO, AsignacionCuentaDTO, CierreDTO,
)

DTOS = {c.__name__: c for c in (
    LoginDTO, CambiarEstadoDTO, RegistrarEventoBajaDTO, PrecioDTO,
    AsignacionCuentaDTO, CierreDTO,
)}
TODAY = date.today().isoformat()
SAMPLES = {
    "LoginDTO": [{"correo_electronico": "qa@example.com", "contrasena": "local"}],
    "CambiarEstadoDTO": [{"estado_nuevo": "EN_TRATAMIENTO", "fecha_cambio_estado": TODAY,
                          "motivo_cambio": "QA local"}],
    "RegistrarEventoBajaDTO": [{"tipo_baja": "venta", "fecha_baja": TODAY,
                                "motivo_baja": "QA local"}],
    "PrecioDTO": [
        {"id_especie": 39, "categoria": category, "precio_unitario": "10.05",
         "fecha_vigencia": TODAY, "fuente": source, "evidencia_documental": "QA local",
         **({"justificacion_estimacion": "QA local"} if source == "ESTIMADA" else {}),
         "confirmar_desviacion": source == "ESTIMADA"}
        for category, source in (("POR_CABEZA", "MERCADO_ACTIVO"), ("PESO_KG", "ESTIMADA"))
    ],
    "AsignacionCuentaDTO": [
        {"tipo_hecho": kind, "sentido": sense, "id_especie": None,
         "subtipo_costo": None, "cuenta_debito": debit, "cuenta_credito": credit}
        for kind, sense, debit, credit in (
            ("VARIACION_VR_TB", "PERDIDA", "539505", "158405"),
            ("VARIACION_VR_PM", "GANANCIA", "158405", "424805"),
            ("DEPRECIACION_ACTIVO_COSTO", "UNICO", "539505", "158405"),
        )
    ],
    "CierreDTO": [{"autorizar_exclusiones": False, "incluir_activos_sin_precio": False}],
}


class ContratoDtoTest(unittest.TestCase):
    def test_cuerpos(self):
        contract = json.loads((GROUP / "pruebas" / "contrato_g41.json").read_text(encoding="utf-8"))
        items = [item for item in contract["rutas"] if item.get("dto")]
        self.assertEqual({item["dto"] for item in items}, set(DTOS))
        for item in items:
            dto = DTOS[item["dto"]]
            declared = set(item["cuerpo"])
            self.assertTrue(declared <= set(dto.model_fields), item["dto"])
            for body in SAMPLES[item["dto"]]:
                self.assertTrue(set(body) <= declared, item["dto"])
                dto.model_validate(body)


if __name__ == "__main__":
    unittest.main()
