"""Valida localmente los cuerpos que G43 envía; no requiere TEST."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

GROUP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GROUP.parents[4]))
from src.identity_access.infrastructure.dto.usuario_dto import LoginDTO
from src.financial_valuation.infrastructure.dto.m06_dto import PrecioDTO, CierreDTO, AsignacionCuentaDTO

class DtoTest(unittest.TestCase):
    def test_todos_los_cuerpos(self):
        LoginDTO.model_validate({"correo_electronico":"qa@example.com","contrasena":"local"})
        hoy=datetime.now(timezone(timedelta(hours=-5))).date()  # America/Bogota en el entorno local sin tzdata
        cuerpos=[
            {"id_especie":39,"categoria":"POR_CABEZA","id_metrica_produccion":None,"precio_unitario":"4410000","fecha_vigencia":hoy.isoformat(),"fuente":"MERCADO_ACTIVO","evidencia_documental":"QA local precio nuevo","confirmar_desviacion":False},
            *[{"id_especie":e,"categoria":"POR_CABEZA","id_metrica_produccion":None,"precio_unitario":"4000000","fecha_vigencia":(hoy-timedelta(days=7)).isoformat(),"fecha_vencimiento":(hoy-timedelta(days=1)).isoformat(),"fuente":"MERCADO_ACTIVO","evidencia_documental":"QA local precio vencido","confirmar_desviacion":False} for e in (422,423)],
        ]
        for body in cuerpos: PrecioDTO.model_validate(body)
        for body in ({},{"autorizar_exclusiones":True,"incluir_activos_sin_precio":False},{"incluir_activos_sin_precio":True,"autorizar_exclusiones":False}):
            CierreDTO.model_validate(body)
        for tipo, sentido in (("DEPRECIACION_ACTIVO_COSTO", "UNICO"), ("VARIACION_VR_PM", "GANANCIA"), ("VARIACION_VR_TB", "GANANCIA"), ("VARIACION_VR_TB", "PERDIDA")):
            AsignacionCuentaDTO.model_validate({"tipo_hecho":tipo,"sentido":sentido,"id_especie":None,"subtipo_costo":None,"cuenta_debito":"516005","cuenta_credito":"159205"})

if __name__=='__main__': unittest.main()
