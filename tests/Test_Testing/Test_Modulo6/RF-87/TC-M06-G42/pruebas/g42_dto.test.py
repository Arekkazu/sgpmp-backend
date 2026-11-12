"""Cuerpos locales G42 validados con los DTO reales; no accede a TEST."""
import json
import sys
import unittest
from datetime import date
from pathlib import Path

GROUP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GROUP.parents[4]))

from src.identity_access.infrastructure.dto.usuario_dto import LoginDTO
from src.financial_valuation.infrastructure.dto.m06_dto import PrecioDTO, AsignacionCuentaDTO, CierreDTO, CostoDTO
from src.biological_assets.infrastructure.dto.registrar_evento_crecimiento_dto import RegistrarEventoCrecimientoDTO

DTOS = {x.__name__: x for x in (LoginDTO, PrecioDTO, AsignacionCuentaDTO, CierreDTO, CostoDTO, RegistrarEventoCrecimientoDTO)}
TODAY = date.today().isoformat()
BASE = {"subtipo_costo":"ALIMENTO","origen_costo":"COMPRA_PROVEEDOR","monto_costo":"100.00","fecha_costo":TODAY,
        "id_activo_biologico":1569,"naturaleza_costo":"MANTENIMIENTO","tercero_nit":"900000123","tercero_dv":"4",
        "tercero_razon_social":"Proveedor local","factura_numero":"QA-LOCAL-1","fecha_factura":TODAY,"fecha_vencimiento_factura":TODAY}
SAMPLES = {
    "LoginDTO":[{"correo_electronico":"qa@example.com","contrasena":"local"}],
    "PrecioDTO":[{"id_especie":39,"categoria":"POR_CABEZA","precio_unitario":"10.05","fecha_vigencia":TODAY,"fuente":"MERCADO_ACTIVO","evidencia_documental":"QA local","confirmar_desviacion":False}],
    "AsignacionCuentaDTO":[{"tipo_hecho":t,"sentido":s,"id_especie":None,"subtipo_costo":None,"cuenta_debito":a,"cuenta_credito":b} for t,s,a,b in
                           (("VARIACION_VR_TB","PERDIDA","539505","158405"),("VARIACION_VR_PM","GANANCIA","158405","424805"),("DEPRECIACION_ACTIVO_COSTO","UNICO","539505","158405"))],
    "CierreDTO":[{"autorizar_exclusiones":True,"incluir_activos_sin_precio":False},{"autorizar_exclusiones":False,"incluir_activos_sin_precio":False}],
    "CostoDTO":[{**BASE,"subtipo_costo":t,"factura_numero":f"QA-LOCAL-{i}"} for i,t in enumerate(("ALIMENTO","MEDICAMENTO","VETERINARIO"),1)] +
               [{"subtipo_costo":"MANO_OBRA","origen_costo":"MANO_OBRA_PROPIA","monto_costo":"100.00","fecha_costo":TODAY,"id_activo_biologico":1569,"naturaleza_costo":"MANTENIMIENTO"}],
    "RegistrarEventoCrecimientoDTO":[{"tipo_medicion":"PESO","valor_medicion":x,"unidad_medida":"kg","descripcion":"QA local"} for x in ("250.00","240.00")],
}

class DtoTest(unittest.TestCase):
    def test_cuerpos(self):
        contract=json.loads((GROUP/'pruebas'/'contrato_g42.json').read_text(encoding='utf-8'))
        rows=[x for x in contract['rutas'] if x.get('dto')]
        self.assertEqual({x['dto'] for x in rows},set(DTOS))
        for row in rows:
            dto=DTOS[row['dto']]
            self.assertTrue(set(row['cuerpo']) <= set(dto.model_fields),row['ruta'])
            for body in SAMPLES[row['dto']]:
                self.assertTrue(set(body) <= set(row['cuerpo']),row['ruta'])
                dto.model_validate(body)

if __name__=='__main__':unittest.main()
