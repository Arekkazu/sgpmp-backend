"""Comprueba la serialización JS contra el dominio Python real, sin red."""
import json
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

raiz = next(p for p in Path(__file__).resolve().parents if (p / 'src').is_dir())
sys.path.insert(0, str(raiz))
from src.financial_valuation.domain.services.nic41 import hash_sha256
from src.financial_valuation.domain.services.consolidacion import Comprobante

lineas = [
    {'cuenta_debito': 'Débito ñ', 'cuenta_credito': 'Crédito', 'valor': '123.40', 'detalle': {'zona': 'Peña', 'meses': [1, 2]}},
    {'cuenta_debito': '2', 'cuenta_credito': '3', 'valor': '-0.05'},
]
comprobante = Comprobante('NIC-Ñ-202611-AJUSTE-7', 'NIT-PRUEBA', 'AJUSTE', 7, date(2026, 11, 30), lineas, Decimal('123.35'), [1, 2])
codigos = [{'codigo': comprobante.codigo, 'hash': comprobante.hash_integridad, 'valor_total': str(comprobante.valor_total)}]
excluidos = [{'id_activo_biologico': 7, 'motivo': 'Peña ñ', 'detalle': {'razón': 'sin precio', 'meses': [2, 3]}}]
cierre = {'periodo': 220, 'comprobantes': codigos, 'excluidos': excluidos}
datos = [{'codigo': comprobante.codigo, 'fecha': str(comprobante.fecha_comprobante), 'lineas': lineas}, cierre]
script = "import {hashCanonico} from './g46.mjs'; let s=''; for await (const c of process.stdin) s+=c; console.log(JSON.stringify(JSON.parse(s).map(hashCanonico)));"
salida = subprocess.run(['node', '--input-type=module', '-e', script], input=json.dumps(datos, ensure_ascii=False), text=True, encoding='utf-8', capture_output=True, cwd=Path(__file__).resolve().parents[1], check=True)
calculados = json.loads(salida.stdout)
assert calculados == [comprobante.hash_integridad, hash_sha256(cierre)], (calculados, comprobante.hash_integridad, hash_sha256(cierre))
print('OK hash SHA-256 canónico JS = backend Python, con tildes, ñ, fechas, montos texto y listas anidadas')
