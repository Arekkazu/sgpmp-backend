"""Helpers QA de TC-M09-G79. Solo lectura sobre TEST: descubrimiento y evidencia.

El descubrimiento se hace contra el TEST real por API (GET) para que el escenario
del harness use un dispositivo, un sensor, un area y un rango tecnico reales. La
ejecucion transaccional bajo fallo NO toca TEST: ocurre en el harness de Pytest.
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

BASE = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test'
FRONT = 'https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io'
RUN_ID = os.environ.get('G79_RUN_ID', 'run-local')
RAIZ = Path(__file__).resolve().parent
EVID = RAIZ / 'RESULTADOS' / RUN_ID

META = {
    'grupo': 'TC-M09-G79',
    'caso': 'TC-M09-150',
    'rf': 'RF-24',
    'cu': 'CU-05',
    'rol': 'Ingeniero de campo',
    'rama': 'qa/juan-esteban-m09',
    'frontendSHA': '966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56',
    'backendSHA': 'adc3932b9f0293a76ebec7e89ed877274791b6a1',
    'base': BASE,
}
_CTX = ssl.create_default_context()


class Token(str):
    """Su repr nunca revela el valor: pytest imprime los fixtures en los fallos."""

    def __repr__(self) -> str:  # noqa: D105
        return "'[JWT REDACTED]'"


def _peticion(metodo: str, ruta: str, token: str | None = None, cuerpo: str | None = None):
    req = urllib.request.Request(BASE + ruta, method=metodo)
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    datos = None
    if cuerpo is not None:
        datos = cuerpo.encode('utf-8')
        req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, data=datos, timeout=25, context=_CTX) as r:
            texto = r.read().decode('utf-8')
            return r.status, json.loads(texto) if texto else None
    except urllib.error.HTTPError as exc:
        texto = exc.read().decode('utf-8')
        return exc.code, json.loads(texto) if texto else None


def login() -> Token:
    cuerpo = json.dumps({
        'correo_electronico': os.environ['QA_EMAIL'],
        'contrasena': os.environ['QA_PASSWORD'],
    })
    status, body = _peticion('POST', '/sesiones/', cuerpo=cuerpo)
    if status != 200 or not body or not body.get('token'):
        raise RuntimeError(f'ENVIRONMENT_ERROR login HTTP {status}')
    return Token(body['token'])


def get(ruta: str, token: str):
    status, body = _peticion('GET', ruta, token=token)
    if status != 200:
        raise RuntimeError(f'GET {ruta} HTTP {status}')
    return body


def limpiar(texto: str) -> str:
    for secreto in (os.environ.get('QA_PASSWORD'), os.environ.get('QA_EMAIL')):
        if secreto:
            texto = texto.replace(secreto, '[REDACTED]')
    import re
    texto = re.sub(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', '[JWT REDACTED]', texto)
    return re.sub(r'Bearer\s+[A-Za-z0-9_.-]+', 'Bearer [REDACTED]', texto)


def guardar(nombre: str, valor: dict) -> Path:
    EVID.mkdir(parents=True, exist_ok=True)
    destino = EVID / nombre
    contenido = json.dumps({**META, 'fecha': datetime.now(timezone.utc).isoformat(), **valor},
                           indent=2, ensure_ascii=False, default=str)
    destino.write_text(limpiar(contenido), encoding='utf-8')
    return destino


def valor_interior(minimo: str, maximo: str) -> Decimal:
    """Punto interior del rango tecnico, con aritmetica decimal exacta."""
    return ((Decimal(str(minimo)) + Decimal(str(maximo))) / 2).quantize(Decimal('0.0001'))


def descubrir(token: str) -> dict:
    """Descubre por GET una calibracion completamente valida sobre datos reales."""
    permisos = get('/sesiones/me/permisos', token)['permisos']
    acciones = sorted({p['id_accion'] for p in permisos if p['id_recurso'] == 12})
    if 1 not in acciones:
        raise RuntimeError('BLOCKED: el actor no tiene permiso de creacion sobre el recurso 12')
    rangos = {r['categoria']: r for r in get('/configuracion/sensores/rangos-calibracion', token)['items']}
    dispositivos = get('/configuracion/dispositivos-iot', token)['items']
    candidatos = []
    for d in [x for x in dispositivos if x['es_activo']]:
        try:
            sensores = get(f"/configuracion/dispositivos-iot/{d['id_dispositivo_iot']}/sensores", token)['items']
        except RuntimeError:
            continue
        for s in [x for x in (sensores or []) if x['es_activo'] and x['categoria'] in rangos]:
            asociaciones = get(f"/configuracion/sensores/{s['id_sensores']}/asociaciones", token)['items']
            vigente = next((a for a in asociaciones if a['fecha_finalizacion'] is None), None)
            if vigente is None:
                continue
            historial = get(f"/configuracion/sensores/{s['id_sensores']}/calibraciones", token)
            candidatos.append((d, s, vigente, historial))
        # Se recorre un numero acotado de dispositivos: basta para hallar un sensor
        # con historial y evita barrer los 109 del catalogo.
        if len(candidatos) >= 6:
            break
    # Se prefiere un sensor CON calibraciones previas: asi la comprobacion de que
    # el rollback no destruye historicos es significativa y no vacia.
    candidatos.sort(key=lambda c: -c[3]['total'])
    for d, s, vigente, historial in candidatos:
            rango = rangos[s['categoria']]
            return {
                'permisosRecurso12': acciones,
                'dispositivo': {'id': d['id_dispositivo_iot'], 'serial': d['serial'], 'es_activo': d['es_activo']},
                'sensor': {'id': s['id_sensores'], 'nombre': s['nombre'], 'categoria': s['categoria'],
                           'es_activo': s['es_activo'], 'id_dispositivo_iot': s['id_dispositivo_iot']},
                'area': {'id_infraestructura': vigente['id_infraestructura'],
                         'punto_instalacion': vigente['punto_instalacion'],
                         'fecha_finalizacion': vigente['fecha_finalizacion']},
                'rangoTecnico': {'categoria': s['categoria'], 'min': str(rango['valor_min']),
                                 'max': str(rango['valor_max']),
                                 'fuente': 'GET /configuracion/sensores/rangos-calibracion'},
                'valor': str(valor_interior(rango['valor_min'], rango['valor_max'])),
                'historialTest': {'total': historial['total'],
                                  'items': [{'id_calibracion': c['id_calibracion'],
                                             'valor_referencia': c['valor_referencia'],
                                             'fecha_calibracion': c['fecha_calibracion'],
                                             'id_usuario': c['id_usuario']} for c in historial['items']]},
            }
    raise RuntimeError('BLOCKED: sin sensor activo con asociacion vigente y rango tecnico publicado')


def historial_test(token: str, id_sensor: int) -> dict:
    h = get(f'/configuracion/sensores/{id_sensor}/calibraciones', token)
    return {'total': h['total'], 'ids': [c['id_calibracion'] for c in h['items']],
            'items': [{'id_calibracion': c['id_calibracion'], 'valor_referencia': c['valor_referencia'],
                       'fecha_calibracion': c['fecha_calibracion']} for c in h['items']]}
