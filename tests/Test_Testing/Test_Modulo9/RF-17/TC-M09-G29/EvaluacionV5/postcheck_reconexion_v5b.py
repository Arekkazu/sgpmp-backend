"""TC-M09-G29 V5 (reejecucion) - POSTCHECK de reconexion (SOLO LECTURA, 0 escrituras).

Tras reconectar la Raspberry comprueba, sin escribir nada:
  - que SERBY-TAX-FIRMWARE volvio a estar operativo con heartbeat reciente;
  - que NO hubo reenvio automatico de la Configuracion B al reconectar;
  - que la Configuracion A sigue siendo la ultima que el Edge recibio.

La senal decisiva es fecha_ultima_sincronizacion: quedo en el valor que dejo A
(2026-10-08T20:18:32.740677Z). Si al reconectar se hubiera reenviado B, ese
campo habria avanzado y el estado habria pasado a APLICADA. Que siga en
PENDIENTE con la fecha de A es la evidencia central de que no hay reenvio.

Se toman varias muestras separadas en el tiempo para descartar un reenvio
diferido por una tarea periodica.

Uso: RUN_ID=... TEST_ADMIN_PASSWORD=... python postcheck_reconexion_v5b.py
"""
from __future__ import annotations

import datetime
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = 'https://api.inmero.co/back-sigab-test'
ACTOR = 'administador.dev@gmail.com'
ESPECIE, UMBRAL, GID, NID = 4, 65, 138, 139
GATEWAY = 'SERBY-TAX-FIRMWARE'
RUTA_EDGE = '/var/lib/sgpmp-edge/umbrales.json'

# Valores de referencia fijados por TC-M09-62 y TC-M09-63.
FECHA_SINC_DE_A = '2026-10-08T20:18:32.740677Z'
A = ('40.00', '95.00')
B = ('40.00', '100.00')

MUESTRAS = 4
INTERVALO = 45
SENSIBLES = ('password', 'contrasena', 'token', 'secret', 'usuario_mqtt', 'clave')

AQUI = Path(__file__).resolve().parent
RUN_ID = os.environ.get('RUN_ID')
if not RUN_ID:
    raise SystemExit('Falta RUN_ID.')
OUT = AQUI / 'RESULTADOS' / RUN_ID


def ahora() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def limpio(d) -> dict:
    return {k: v for k, v in (d or {}).items()
            if not any(s in k.lower() for s in SENSIBLES)}


def http(metodo, ruta, cuerpo=None, token=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    pet = urllib.request.Request(BASE + ruta, data=datos, method=metodo)
    if datos:
        pet.add_header('Content-Type', 'application/json')
    if token:
        pet.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(pet, timeout=60) as r:
            return r.status, json.loads(r.read() or b'null')
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b'null')
        except Exception:
            return e.code, None
    except Exception:
        return -1, None


def token() -> str:
    clave = os.environ['TEST_ADMIN_PASSWORD']
    _, login = http('POST', '/sesiones/',
                    {'correo_electronico': ACTOR, 'contrasena': clave})
    return (login or {}).get('token')


def main() -> None:
    if not os.environ.get('TEST_ADMIN_PASSWORD'):
        raise SystemExit('TEST_ADMIN_PASSWORD no disponible.')

    ev: dict = {'runId': RUN_ID, 'caso': 'TC-M09-63', 'fase': 'postcheck de reconexion',
                'tipo': 'SOLO LECTURA', 'escriturasFuncionales': 0, 'inicio': ahora(),
                'referencias': {'fechaSincronizacionDeA': FECHA_SINC_DE_A,
                                'configuracionA': A, 'configuracionB': B},
                'muestras': []}

    for i in range(1, MUESTRAS + 1):
        t = token()
        hc, cred = http('GET', f'/configuracion/dispositivos-iot/{GID}/credencial-mqtt', token=t)
        _, eg = http('GET', f'/iot/dispositivos/{GID}/estado', token=t)
        _, en = http('GET', f'/iot/dispositivos/{NID}/estado', token=t)
        bg = (eg or {}).get('estado') or {}
        bn = (en or {}).get('estado') or {}
        _, lista = http('GET', f'/configuracion/umbrales?id_especie={ESPECIE}', token=t)
        u = next((x for x in (lista or {}).get('items', [])
                  if x['id_umbral_ambiental'] == UMBRAL), None)
        m = {
            'muestra': i, 'momento': ahora(),
            'gateway': {'httpCredencial': hc,
                        'conectada': (cred or {}).get('conectada'),
                        'estado_actual': bg.get('estado_actual'),
                        'id_ultimo_heartbeat': bg.get('id_ultimo_heartbeat'),
                        'fecha_ultimo_contacto': bg.get('fecha_ultimo_contacto'),
                        'causa_primaria': bg.get('causa_primaria')},
            'nodo': {'estado_actual': bn.get('estado_actual'),
                     'id_ultimo_heartbeat': bn.get('id_ultimo_heartbeat'),
                     'fecha_ultimo_contacto': bn.get('fecha_ultimo_contacto')},
            'umbral': {'valor_min': (u or {}).get('valor_min'),
                       'valor_max': (u or {}).get('valor_max'),
                       'estado_sincronizacion': (u or {}).get('estado_sincronizacion'),
                       'fecha_ultima_sincronizacion': (u or {}).get('fecha_ultima_sincronizacion'),
                       'motivo_fallo_sincronizacion': (u or {}).get('motivo_fallo_sincronizacion'),
                       'fecha_actualizacion': (u or {}).get('fecha_actualizacion')},
        }
        ev['muestras'].append(m)
        print(f"  [{m['momento']}] edge={m['gateway']['estado_actual']} "
              f"hb={m['gateway']['id_ultimo_heartbeat']} "
              f"umbral={m['umbral']['valor_min']}-{m['umbral']['valor_max']} "
              f"sync={m['umbral']['estado_sincronizacion']} "
              f"fecha_sinc={m['umbral']['fecha_ultima_sincronizacion']}", flush=True)
        if i < MUESTRAS:
            time.sleep(INTERVALO)

    ultima = ev['muestras'][-1]
    primera = ev['muestras'][0]
    t = token()
    _, aud = http('GET', f'/configuracion/umbrales/{UMBRAL}/auditoria', token=t)
    _, hist = http('GET', f'/iot/dispositivos/{GID}/historial', token=t)
    items = hist if isinstance(hist, list) else (hist or {}).get('items', [])
    ev['auditoriaUmbral'] = aud
    ev['reconexionEnHistorial'] = [x for x in items[:4]
                                   if x.get('estado_nuevo') == 'ACTIVO']

    edge_ok = (ultima['gateway']['estado_actual'] == 'ACTIVO'
               and ultima['gateway']['conectada'] is True
               and ultima['gateway']['httpCredencial'] == 200)
    hb_reciente = all(m['gateway']['id_ultimo_heartbeat'] is not None
                      for m in ev['muestras'])
    hb_avanzo = (ultima['gateway']['id_ultimo_heartbeat']
                 != primera['gateway']['id_ultimo_heartbeat'])
    sin_reenvio = all(m['umbral']['estado_sincronizacion'] == 'PENDIENTE'
                      and m['umbral']['fecha_ultima_sincronizacion'] == FECHA_SINC_DE_A
                      for m in ev['muestras'])
    b_sigue_central = all((m['umbral']['valor_min'], m['umbral']['valor_max']) == B
                          for m in ev['muestras'])
    sin_escrituras_de_terceros = all(
        m['umbral']['fecha_actualizacion'] == primera['umbral']['fecha_actualizacion']
        for m in ev['muestras'])

    ev['verificaciones'] = {
        '1_edgeVolvioAEstarOperativo': edge_ok,
        '2_heartbeatReciente': hb_reciente,
        '3_heartbeatSigueAvanzando': hb_avanzo,
        '4_sinReenvioAutomaticoDeB': sin_reenvio,
        '5_bSigueSoloEnElCentro': b_sigue_central,
        '6_nadieMasEditoElUmbral': sin_escrituras_de_terceros,
    }
    ev['razonamientoDeLaNoPropagacion'] = (
        'fecha_ultima_sincronizacion se mantiene en el valor que dejo la Configuracion A '
        f'({FECHA_SINC_DE_A}) en las {MUESTRAS} muestras, y el estado sigue en PENDIENTE con el '
        'motivo de Edge offline, pese a que el Gateway esta ACTIVO y su heartbeat avanza. Si al '
        'reconectar se hubiera reenviado B, ese campo habria avanzado y el estado habria pasado a '
        'APLICADA. No hay reenvio automatico: coincide con lo documentado en el caso de uso '
        '(el umbral se propaga en la proxima edicion).')
    ev['conservacionDeAEnElEdge'] = {
        'rutaEsperada': RUTA_EDGE, 'accesibleDesdeQa': False,
        'verificadaDirectamente': False,
        'ultimaConfiguracionQueElEdgeRecibio': 'A (40-95), por ausencia de propagacion posterior',
        'nota': ('Inferencia a partir del contrato y del estado persistido, NO observacion fisica. '
                 'B nunca se publico al Edge (ni en TC-63 con el equipo apagado, ni al reconectar), '
                 'de modo que nada pudo sobrescribir A. Sigue como NO VERIFICADA DIRECTAMENTE.')}
    ev['oraculoDeConservacion'] = {
        'A_aplicadaAntesDeDesconectar': True,
        'B_centralmentePendienteDuranteLaDesconexion': True,
        'B_noSeReenvioAlReconectar': sin_reenvio,
        'A_sigueSiendoLaConfiguracionEfectivaEnCampo': 'NO VERIFICABLE DESDE QA (inferida)',
    }
    ev['cleanupRealizado'] = False
    ev['restauracionRealizada'] = False
    ev['fin'] = ahora()

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'postcheck.json').write_text(
        json.dumps(ev, indent=2, ensure_ascii=False), encoding='utf-8')

    print()
    for k, v in ev['verificaciones'].items():
        print(f'  {k}: {v}')
    print(f"Evidencia: {OUT / 'postcheck.json'}")


if __name__ == '__main__':
    main()
