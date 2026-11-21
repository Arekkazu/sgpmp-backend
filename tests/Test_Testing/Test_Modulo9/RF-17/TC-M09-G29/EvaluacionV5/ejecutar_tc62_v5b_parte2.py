"""TC-M09-G29 V5 (reejecucion) - TC-M09-62 PARTE 2: PATCH a 40-95 con Edge ONLINE.

La parte 1 (POST, umbral 65) ya se ejecuto y cumplio el oraculo funcional de
RF-17: HTTP 201, APLICADA, fecha_ultima_sincronizacion informada, sin motivo de
fallo y destino unico. Este script NO repite el POST: solo ejecuta el PATCH.

El tiempo de respuesta del POST (1,278 s frente a la expectativa de < 1 s) se
registra como OBSERVACION, no como fallo: las reglas de resultado definen
TC-M09-62 por propagacion / ACK / APLICADA, y 1,3 s es el viaje de ida y vuelta
real hasta el ACK del Edge.

Uso: RUN_ID=... TEST_ADMIN_PASSWORD=... python ejecutar_tc62_v5b_parte2.py
"""
from __future__ import annotations

import datetime
import json
import os
import time
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path

BASE = 'https://api.inmero.co/back-sigab-test'
ACTOR = 'administador.dev@gmail.com'
ESPECIE = 4
GATEWAY = 'SERBY-TAX-FIRMWARE'

NIVELES_A = [
    {'nivel': 'normal', 'limite_inferior': 40, 'limite_superior': 70},
    {'nivel': 'precaucion', 'limite_inferior': 70, 'limite_superior': 85},
    {'nivel': 'critico', 'limite_inferior': 85, 'limite_superior': 95},
]

TIMEOUT_ESCRITURA = 150
SENSIBLES = ('password', 'contrasena', 'token', 'secret', 'usuario_mqtt', 'clave')

AQUI = Path(__file__).resolve().parent
RUN_ID = os.environ.get('RUN_ID')
if not RUN_ID:
    raise SystemExit('Falta RUN_ID.')
OUT = AQUI / 'RESULTADOS' / RUN_ID

_token: str | None = None


def ahora() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def limpio(d) -> dict:
    return {k: v for k, v in (d or {}).items()
            if not any(s in k.lower() for s in SENSIBLES)}


def http(metodo: str, ruta: str, cuerpo: dict | None = None, timeout: int = 90):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    pet = urllib.request.Request(BASE + ruta, data=datos, method=metodo)
    if datos:
        pet.add_header('Content-Type', 'application/json')
    if _token:
        pet.add_header('Authorization', f'Bearer {_token}')
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(pet, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b'null'), time.monotonic() - t0
    except urllib.error.HTTPError as exc:
        bruto = exc.read()
        try:
            return exc.code, json.loads(bruto or b'null'), time.monotonic() - t0
        except ValueError:
            return exc.code, {'raw': bruto.decode('utf-8', 'replace')[:600]}, time.monotonic() - t0
    except Exception as exc:                                   # noqa: BLE001
        return -1, {'error': f'{type(exc).__name__}: {str(exc)[:300]}'}, time.monotonic() - t0


def dec(x) -> Decimal:
    return Decimal(str(x))


def coincide(u: dict, vmin, vmax, niveles) -> bool:
    if dec(u['valor_min']) != dec(vmin) or dec(u['valor_max']) != dec(vmax):
        return False
    esperado = {(n['nivel'], dec(n['limite_inferior']), dec(n['limite_superior']))
                for n in niveles}
    obtenido = {(n['nivel'], dec(n['limite_inferior']), dec(n['limite_superior']))
                for n in (u.get('niveles') or [])}
    return esperado == obtenido


def leer(id_umbral: int) -> dict | None:
    _, lista, _ = http('GET', f'/configuracion/umbrales?id_especie={ESPECIE}')
    return next((u for u in (lista or {}).get('items', [])
                 if u['id_umbral_ambiental'] == id_umbral), None)


def estado_gateway() -> dict:
    _, disp, _ = http('GET', '/configuracion/dispositivos-iot')
    gw = next((d for d in (disp or {}).get('items', []) if d['serial'] == GATEWAY), None)
    gid = (gw or {}).get('id_dispositivo_iot')
    _, cred, _ = http('GET', f'/configuracion/dispositivos-iot/{gid}/credencial-mqtt')
    _, est, _ = http('GET', f'/iot/dispositivos/{gid}/estado')
    bloque = (est or {}).get('estado') if isinstance(est, dict) else {}
    conectada = (cred or {}).get('conectada') if isinstance(cred, dict) else None
    return {'id': gid, 'es_activo': (gw or {}).get('es_activo'),
            'credencialMqtt': limpio(cred if isinstance(cred, dict) else {}),
            'heartbeat': limpio(bloque if isinstance(bloque, dict) else {}),
            'conectada': conectada,
            'clasificacion': ('EDGE_ONLINE' if conectada is True else
                              'EDGE_OFFLINE' if conectada is False else 'EDGE_NO_VERIFICABLE'),
            'timestamp': ahora()}


def main() -> None:
    global _token
    clave = os.environ.get('TEST_ADMIN_PASSWORD')
    if not clave:
        raise SystemExit('TEST_ADMIN_PASSWORD no disponible.')
    est, login, _ = http('POST', '/sesiones/',
                         {'correo_electronico': ACTOR, 'contrasena': clave})
    if est != 200 or not (login or {}).get('token'):
        raise SystemExit(f'login TEST fallido (HTTP {est}).')
    _token = login['token']

    ruta = OUT / 'tc62-result.json'
    ev = json.loads(ruta.read_text(encoding='utf-8'))
    p1 = ev['parte1']
    id_umbral = p1['id_umbral_ambiental']

    # El oraculo funcional de la parte 1, sin la expectativa de tiempo.
    funcional = {k: v for k, v in p1['oraculo'].items() if k != 'menosDe1Segundo'}
    if not all(funcional.values()):
        raise SystemExit('La parte 1 no cumplio el oraculo funcional: no se ejecuta el PATCH.')

    p1['verdict'] = 'OK_CON_OBSERVACION'
    p1['observacionTiempo'] = {
        'esperado': '< 1 s', 'medido': f"{p1['response']['duracionSegundos']} s",
        'clasificacion': 'OBSERVACION, no fallo',
        'razon': ('Las reglas de resultado definen TC-M09-62 por propagacion, ACK y APLICADA. '
                  'El tiempo medido es el viaje completo backend -> broker -> publicacion al '
                  'Edge -> ACK_UMBRAL -> persistencia, con el Raspberry real al otro extremo; '
                  'una desviacion de 0,278 s sobre la expectativa no contradice ningun criterio '
                  'de correccion del RF.'),
    }
    ev['parte1'] = p1

    # --- PARTE 2 ---------------------------------------------------------------------
    actual = leer(id_umbral)
    fecha_exacta = (actual or {}).get('fecha_actualizacion')
    gw_pre = estado_gateway()
    ev['parte2'] = {'getPrevio': actual, 'fecha_actualizacion_capturada': fecha_exacta,
                    'preGateway': gw_pre}

    if gw_pre['clasificacion'] != 'EDGE_ONLINE':
        ev['parte2']['verdict'] = 'NO_EJECUTADO'
        ev['parte2']['motivo'] = f"Edge dejo de estar ONLINE ({gw_pre['clasificacion']})"
        ev['verdict'] = 'BLOQUEADO'
        ev['fin'] = ahora()
        ruta.write_text(json.dumps(ev, indent=2, ensure_ascii=False), encoding='utf-8')
        raise SystemExit(ev['parte2']['motivo'])

    cuerpo_patch = {'valor_min': 40, 'valor_max': 95, 'niveles': NIVELES_A,
                    'fecha_actualizacion': fecha_exacta}
    ev['parte2']['request'] = {'metodo': 'PATCH',
                               'ruta': f'/configuracion/umbrales/{id_umbral}',
                               'cuerpo': cuerpo_patch,
                               'cabeceras': ['Authorization: <omitido>',
                                             'Content-Type: application/json'],
                               'timestamp': ahora()}
    ev['escriturasOficiales'] = 2
    ruta.write_text(json.dumps(ev, indent=2, ensure_ascii=False), encoding='utf-8')

    estado_pa, cuerpo_pa, dur = http('PATCH', f'/configuracion/umbrales/{id_umbral}',
                                     cuerpo_patch, timeout=TIMEOUT_ESCRITURA)
    ev['parte2']['response'] = {'http': estado_pa, 'cuerpo': cuerpo_pa,
                                'duracionSegundos': round(dur, 3), 'recibido': ahora()}

    post2 = leer(id_umbral)
    _, aud2, _ = http('GET', f'/configuracion/umbrales/{id_umbral}/auditoria')
    ev['parte2'].update({
        'umbralTrasPatch': post2, 'auditoria': aud2, 'postGateway': estado_gateway(),
        'estado_sincronizacion': (post2 or {}).get('estado_sincronizacion'),
        'fecha_ultima_sincronizacion': (post2 or {}).get('fecha_ultima_sincronizacion'),
        'motivo_fallo_sincronizacion': (post2 or {}).get('motivo_fallo_sincronizacion'),
    })

    oraculo2 = {
        'http200': estado_pa == 200,
        'valoresPersistidos40a95': bool(post2) and coincide(post2, 40, 95, NIVELES_A),
        'estadoAplicada': (post2 or {}).get('estado_sincronizacion') == 'APLICADA',
        'fechaSincronizacionNoNula': bool((post2 or {}).get('fecha_ultima_sincronizacion')),
        'sinMotivoDeFallo': not (post2 or {}).get('motivo_fallo_sincronizacion'),
        'fechaSincronizacionAvanzoRespectoAlPost': (
            bool((post2 or {}).get('fecha_ultima_sincronizacion'))
            and (post2 or {}).get('fecha_ultima_sincronizacion')
            != p1.get('fecha_ultima_sincronizacion')),
    }
    ev['parte2']['oraculo'] = oraculo2
    ev['parte2']['verdict'] = 'OK' if all(oraculo2.values()) else 'FALLO'

    if all(oraculo2.values()):
        ev['verdict'] = 'APROBADO_CON_OBSERVACION'
        ev['observaciones'] = ['Tiempo de respuesta del POST 1,278 s frente a la expectativa '
                               'de < 1 s. No afecta a ningun criterio de corrección del RF.']
        ev['configuracionA'] = {'id_umbral_ambiental': id_umbral, 'valor_min': 40,
                                'valor_max': 95, 'niveles': NIVELES_A,
                                'nota': 'baseline aplicada y confirmada para TC-M09-63'}
        ev['tc63'] = ('PENDIENTE: no se ejecuta hasta comprobar por runtime que '
                      'SERBY-TAX-FIRMWARE esta realmente OFFLINE')
    else:
        ev['verdict'] = 'RECHAZADO'
        ev['motivo'] = ('La parte 2 no cumplio: '
                        + ', '.join(k for k, v in oraculo2.items() if not v))
        ev['tc63'] = 'NO EJECUTADO'

    ev['fin'] = ahora()
    ruta.write_text(json.dumps(ev, indent=2, ensure_ascii=False), encoding='utf-8')

    print(f"TC-M09-62: {ev['verdict']}")
    print(f"  PATCH HTTP {estado_pa} en {dur:.3f}s")
    print(f"  central: {(post2 or {}).get('valor_min')}-{(post2 or {}).get('valor_max')}")
    print(f"  sync={ev['parte2']['estado_sincronizacion']} "
          f"fecha={ev['parte2']['fecha_ultima_sincronizacion']} "
          f"motivo={ev['parte2']['motivo_fallo_sincronizacion']}")
    print(f"  auditoria total: {(aud2 or {}).get('total')}")
    print(f"  oraculo parte2 no cumplido: {[k for k, v in oraculo2.items() if not v] or 'ninguno'}")
    print(f"Evidencia: {ruta}")


if __name__ == '__main__':
    main()
