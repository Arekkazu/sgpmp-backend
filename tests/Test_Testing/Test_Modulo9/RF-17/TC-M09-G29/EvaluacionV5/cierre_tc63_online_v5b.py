"""TC-M09-G29 V5 (reejecucion) - fase final ONLINE de TC-M09-63.

Con el Edge reconectado y operativo, una UNICA edicion valida del umbral 65 a la
Configuracion C = 40-98, para demostrar que el umbral vuelve a quedar APLICADA y
que B (40-100) deja de ser la configuracion pendiente efectiva.

Revalida las cinco precondiciones justo antes de escribir y se detiene sin
escribir si alguna cambia. Sin reintentos.

Uso: RUN_ID=... TEST_ADMIN_PASSWORD=... python cierre_tc63_online_v5b.py
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
ESPECIE, UMBRAL, GID = 4, 65, 138
GATEWAY = 'SERBY-TAX-FIRMWARE'
RUTA_EDGE = '/var/lib/sgpmp-edge/umbrales.json'
MUERTOS = {'INACTIVO', 'CERRADO', 'BAJA'}
SENSIBLES = ('password', 'contrasena', 'token', 'secret', 'usuario_mqtt', 'clave')

FECHA_SINC_DE_A = '2026-10-08T20:18:32.740677Z'
B = (Decimal('40'), Decimal('100'))
NIVELES_C = [
    {'nivel': 'normal', 'limite_inferior': 40, 'limite_superior': 70},
    {'nivel': 'precaucion', 'limite_inferior': 70, 'limite_superior': 85},
    {'nivel': 'critico', 'limite_inferior': 85, 'limite_superior': 98},
]
TIMEOUT_ESCRITURA = 150

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


def http(metodo, ruta, cuerpo=None, timeout=90):
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


def guardar(ev: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'tc63-cierre-online.json').write_text(
        json.dumps(ev, indent=2, ensure_ascii=False), encoding='utf-8')


def dec(x) -> Decimal:
    return Decimal(str(x))


def coincide(u, vmin, vmax, niveles) -> bool:
    if dec(u['valor_min']) != dec(vmin) or dec(u['valor_max']) != dec(vmax):
        return False
    esp = {(n['nivel'], dec(n['limite_inferior']), dec(n['limite_superior'])) for n in niveles}
    obt = {(n['nivel'], dec(n['limite_inferior']), dec(n['limite_superior']))
           for n in (u.get('niveles') or [])}
    return esp == obt


def leer():
    _, lista, _ = http('GET', f'/configuracion/umbrales?id_especie={ESPECIE}')
    return next((u for u in (lista or {}).get('items', [])
                 if u['id_umbral_ambiental'] == UMBRAL), None)


def destinos():
    _, tipos, _ = http('GET', '/configuracion/tipos-dispositivo-iot')
    tp = {x['id_tipo_dispositivo']: x['nombre'] for x in (tipos or {}).get('items', [])}
    _, disp, _ = http('GET', '/configuracion/dispositivos-iot')
    ds = (disp or {}).get('items', [])
    por_id = {d['id_dispositivo_iot']: d for d in ds}
    _, fincas, _ = http('GET', '/configuracion/fincas?limite=500')
    areas = {}
    for f in (fincas or {}).get('items', []):
        _, inf, _ = http('GET', f"/configuracion/infraestructuras?finca_id={f['id_finca']}")
        for i in (inf or {}).get('items', []):
            areas[i['id_infraestructura']] = i
    act, pg = [], 1
    while True:
        _, a, _ = http('GET', f'/activos-biologicos?pagina={pg}&registros_por_pagina=100')
        rg = (a or {}).get('registros', [])
        act += rg
        if pg >= (a or {}).get('total_paginas', 1) or not rg:
            break
        pg += 1
    ar = {k for k, v in areas.items() if v.get('es_activo') and v.get('especie_id') == ESPECIE}
    ar |= {r['id_infraestructura'] for r in act
           if r.get('id_especie') == ESPECIE
           and (r.get('nombre_estado') or '').upper() not in MUERTOS
           and areas.get(r.get('id_infraestructura'), {}).get('es_activo')}
    s = set()
    for d in ds:
        if not d.get('es_activo') or d.get('id_infraestructura') not in ar:
            continue
        g = por_id.get(d.get('id_dispositivo_gateway') or d['id_dispositivo_iot'])
        if g and g.get('es_activo') and tp.get(g['id_tipo_dispositivo']) == 'GATEWAY_EDGE':
            s.add(g['serial'])
    return sorted(s)


def estado_edge():
    hc, cred, _ = http('GET', f'/configuracion/dispositivos-iot/{GID}/credencial-mqtt')
    _, est, _ = http('GET', f'/iot/dispositivos/{GID}/estado')
    b = (est or {}).get('estado') if isinstance(est, dict) else {}
    return {'httpCredencial': hc, 'brokerOperativo': hc == 200,
            'credencialMqtt': limpio(cred if isinstance(cred, dict) else {}),
            'heartbeat': limpio(b if isinstance(b, dict) else {}),
            'estado_actual': (b or {}).get('estado_actual'),
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

    ev: dict = {'runId': RUN_ID, 'caso': 'TC-M09-63', 'fase': 'edicion final ONLINE',
                'ambiente': 'TEST', 'inicio': ahora(),
                'actor': {'correo': ACTOR, 'tokenPersistido': False},
                'configuracionC': {'valor_min': 40, 'valor_max': 98, 'niveles': NIVELES_C},
                'escriturasOficialesFaseFinal': 0}

    # --- Precondiciones ---------------------------------------------------------------
    pre = leer()
    edge = estado_edge()
    dest = destinos()
    hb = edge['heartbeat'] or {}
    ultimo = hb.get('fecha_ultimo_contacto')
    reciente = False
    if ultimo:
        delta = (datetime.datetime.now(datetime.timezone.utc)
                 - datetime.datetime.fromisoformat(ultimo.replace('Z', '+00:00'))).total_seconds()
        reciente = delta < 420      # cadencia observada de 5 min, con margen
    ev['precondiciones'] = {
        'umbral': pre, 'edge': edge, 'destinosRf17': dest,
        'segundosDesdeUltimoHeartbeat': round(delta, 1) if ultimo else None,
        'gatewayActivo': edge['estado_actual'] == 'ACTIVO',
        'heartbeatReciente': reciente,
        'unicoDestinoEsElGateway': dest == [GATEWAY],
        'brokerOperativo': edge['brokerOperativo'],
        'umbralEnBPendiente': bool(pre) and dec(pre['valor_min']) == B[0]
                              and dec(pre['valor_max']) == B[1]
                              and pre['estado_sincronizacion'] == 'PENDIENTE',
    }
    p = ev['precondiciones']
    frenos = [k for k in ('gatewayActivo', 'heartbeatReciente', 'unicoDestinoEsElGateway',
                          'brokerOperativo', 'umbralEnBPendiente') if not p[k]]
    if frenos:
        ev['verdict'] = 'NO_EJECUTADO'
        ev['motivo'] = f'Precondiciones cambiadas: {frenos}. 0 escrituras.'
        ev['fin'] = ahora()
        guardar(ev)
        raise SystemExit(ev['motivo'])

    fecha_exacta = pre.get('fecha_actualizacion')
    ev['fecha_actualizacion_capturada'] = fecha_exacta

    cuerpo = {'valor_min': 40, 'valor_max': 98, 'niveles': NIVELES_C,
              'fecha_actualizacion': fecha_exacta}
    marca = ahora()
    ev['request'] = {'metodo': 'PATCH', 'ruta': f'/configuracion/umbrales/{UMBRAL}',
                     'cuerpo': cuerpo,
                     'cabeceras': ['Authorization: <omitido>', 'Content-Type: application/json'],
                     'timestamp': marca}
    ev['escriturasOficialesFaseFinal'] = 1
    guardar(ev)

    estado_pa, cuerpo_pa, dur = http('PATCH', f'/configuracion/umbrales/{UMBRAL}',
                                     cuerpo, timeout=TIMEOUT_ESCRITURA)
    ev['response'] = {'http': estado_pa, 'cuerpo': cuerpo_pa,
                      'duracionSegundos': round(dur, 3), 'recibido': ahora()}
    guardar(ev)

    post = leer()
    _, aud, _ = http('GET', f'/configuracion/umbrales/{UMBRAL}/auditoria')
    ev['post'] = {'umbral': post, 'auditoria': aud, 'edge': estado_edge(),
                  'destinosRf17': destinos(), 'timestamp': ahora()}

    sync = (post or {}).get('estado_sincronizacion')
    fecha = (post or {}).get('fecha_ultima_sincronizacion')
    motivo = (post or {}).get('motivo_fallo_sincronizacion')

    ev['verificacionFisicaEdge'] = {
        'rutaEsperada': RUTA_EDGE, 'accesibleDesdeQa': False,
        'verificadaDirectamente': False,
        'nota': ('No existe acceso al sistema de archivos del Raspberry ni endpoint del producto que '
                 'devuelva la configuracion efectiva en campo. Se mantiene como NO VERIFICADA '
                 'DIRECTAMENTE. No se inventa evidencia.')}

    oraculo = {
        'http200': estado_pa == 200,
        'cPersistida40a98': bool(post) and coincide(post, 40, 98, NIVELES_C),
        'estadoAplicada': sync == 'APLICADA',
        'fechaAvanzaRespectoAA': bool(fecha) and fecha != FECHA_SINC_DE_A,
        'sinMotivoDeFallo': not motivo,
        'bDejaDeSerLaPendienteEfectiva': sync == 'APLICADA'
                                         and bool(post)
                                         and dec(post['valor_max']) != B[1],
        'ackImplicito': sync == 'APLICADA',
    }
    ev['oraculo'] = oraculo
    ev['trazabilidadDelAck'] = (
        'APLICADA solo puede originarse en el cuerpo que devuelve el broker tras el ACK_UMBRAL del '
        'Edge; con un unico destino la consolidacion no puede enmascarar un Gateway sin ACK. '
        'Comparar con la fase offline del mismo RUN, que dio PENDIENTE + 500 en 0,449 s.')
    ev['reenvioAutomaticoDeBObservado'] = False
    ev['nuevaEdicionCAplicada'] = oraculo['cPersistida40a98'] and oraculo['estadoAplicada']

    ev['verdict'] = 'APROBADO' if all(oraculo.values()) else 'RECHAZADO'
    if ev['verdict'] == 'RECHAZADO':
        ev['motivo'] = 'No se cumplio: ' + ', '.join(k for k, v in oraculo.items() if not v)
    ev['cleanupRealizado'] = False
    ev['umbral65Desactivado'] = False
    ev['umbral48Restaurado'] = False
    ev['fin'] = ahora()
    guardar(ev)

    print(f"CIERRE TC-M09-63 fase final ONLINE: {ev['verdict']}")
    print(f'  PATCH HTTP {estado_pa} en {dur:.3f}s')
    print(f"  central: {(post or {}).get('valor_min')}-{(post or {}).get('valor_max')}")
    print(f'  estado_sincronizacion={sync}')
    print(f'  fecha_ultima_sincronizacion={fecha}  (A era {FECHA_SINC_DE_A})')
    print(f'  motivo_fallo={motivo}')
    print(f"  auditoria total: {(aud or {}).get('total')}")
    print(f"  oraculo no cumplido: {[k for k, v in oraculo.items() if not v] or 'ninguno'}")
    print(f"Evidencia: {OUT / 'tc63-cierre-online.json'}")


if __name__ == '__main__':
    main()
