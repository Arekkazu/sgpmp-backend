"""TC-M09-G29 V5 (reejecucion) - TC-M09-62: POST (parte 1) y PATCH (parte 2) con Edge ONLINE.

Fixture oficial de Desarrollo: TEST, especie 4, variable 10 (Humedad Relativa),
unico destino RF-17 SERBY-TAX-FIRMWARE.

Parte 1: POST /configuracion/umbrales con 40-90. Una sola vez, sin reintentos.
         Si falla o no cumple lo esperado, se detiene y NO ejecuta el PATCH.
Parte 2: PATCH a 40-95 con la fecha_actualizacion exacta del GET. Una sola vez.

40-95 queda como Configuracion A para TC-M09-63.

Uso: RUN_ID=... TEST_ADMIN_PASSWORD=... python ejecutar_tc62_v5b.py
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
VARIABLE = 10
GATEWAY = 'SERBY-TAX-FIRMWARE'
RUTA_EDGE = '/var/lib/sgpmp-edge/umbrales.json'

CUERPO_POST = {
    'id_especie': ESPECIE,
    'id_variable_ambiental': VARIABLE,
    'valor_min': 40,
    'valor_max': 90,
    'niveles': [
        {'nivel': 'normal', 'limite_inferior': 40, 'limite_superior': 70},
        {'nivel': 'precaucion', 'limite_inferior': 70, 'limite_superior': 80},
        {'nivel': 'critico', 'limite_inferior': 80, 'limite_superior': 90},
    ],
}
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


def guardar(ev: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'tc62-result.json').write_text(
        json.dumps(ev, indent=2, ensure_ascii=False), encoding='utf-8')


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


def destinos_rf17() -> list[str]:
    _, tipos, _ = http('GET', '/configuracion/tipos-dispositivo-iot')
    tipo_por_id = {x['id_tipo_dispositivo']: x['nombre'] for x in (tipos or {}).get('items', [])}
    _, disp, _ = http('GET', '/configuracion/dispositivos-iot')
    dispositivos = (disp or {}).get('items', [])
    por_id = {d['id_dispositivo_iot']: d for d in dispositivos}
    _, fincas, _ = http('GET', '/configuracion/fincas?limite=500')
    areas = {}
    for f in (fincas or {}).get('items', []):
        _, infra, _ = http('GET', f"/configuracion/infraestructuras?finca_id={f['id_finca']}")
        for i in (infra or {}).get('items', []):
            areas[i['id_infraestructura']] = i
    activos, pagina = [], 1
    while True:
        _, a, _ = http('GET', f'/activos-biologicos?pagina={pagina}&registros_por_pagina=100')
        regs = (a or {}).get('registros', [])
        activos.extend(regs)
        if pagina >= (a or {}).get('total_paginas', 1) or not regs:
            break
        pagina += 1
    muertos = {'INACTIVO', 'CERRADO', 'BAJA'}
    ar = {k for k, v in areas.items() if v.get('es_activo') and v.get('especie_id') == ESPECIE}
    ar |= {r['id_infraestructura'] for r in activos
           if r.get('id_especie') == ESPECIE
           and (r.get('nombre_estado') or '').upper() not in muertos
           and areas.get(r.get('id_infraestructura'), {}).get('es_activo')}
    s = set()
    for d in dispositivos:
        if not d.get('es_activo') or d.get('id_infraestructura') not in ar:
            continue
        g = por_id.get(d.get('id_dispositivo_gateway') or d['id_dispositivo_iot'])
        if g and g.get('es_activo') and tipo_por_id.get(g['id_tipo_dispositivo']) == 'GATEWAY_EDGE':
            s.add(g['serial'])
    return sorted(s)


VERIFICACION_EDGE = {
    'rutaEsperada': RUTA_EDGE,
    'accesibleDesdeQa': False,
    'nota': ('verificacion fisica Edge no accesible desde QA: no hay acceso al sistema de '
             'archivos del Raspberry ni endpoint del producto que devuelva la configuracion '
             'efectiva en campo. No se fabrica la evidencia.'),
}


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

    ev: dict = {'runId': RUN_ID, 'caso': 'TC-M09-62', 'version': 'V5-reejecucion',
                'ambiente': 'TEST', 'inicio': ahora(),
                'actor': {'correo': ACTOR, 'tokenPersistido': False},
                'fixture': {'id_especie': ESPECIE, 'id_variable_ambiental': VARIABLE,
                            'gateway': GATEWAY},
                'escriturasOficiales': 0,
                'verificacionFisicaEdge': VERIFICACION_EDGE}

    # ================= PARTE 1: POST =================================================
    gw_pre = estado_gateway()
    dest_pre = destinos_rf17()
    ev['parte1'] = {'preGateway': gw_pre, 'destinosRf17': dest_pre}
    if gw_pre['clasificacion'] != 'EDGE_ONLINE' or dest_pre != [GATEWAY]:
        ev['parte1']['verdict'] = 'NO_EJECUTADO'
        ev['parte1']['motivo'] = (f"Precondicion invalidada justo antes del POST: "
                                  f"Edge={gw_pre['clasificacion']}, destinos={dest_pre}")
        ev['verdict'] = 'BLOQUEADO'
        ev['fin'] = ahora()
        guardar(ev)
        raise SystemExit(ev['parte1']['motivo'])

    ev['parte1']['request'] = {'metodo': 'POST', 'ruta': '/configuracion/umbrales',
                               'cuerpo': CUERPO_POST,
                               'cabeceras': ['Authorization: <omitido>',
                                             'Content-Type: application/json'],
                               'timestamp': ahora()}
    ev['escriturasOficiales'] = 1
    guardar(ev)

    estado_post, cuerpo_post, dur_post = http('POST', '/configuracion/umbrales',
                                              CUERPO_POST, timeout=TIMEOUT_ESCRITURA)
    ev['parte1']['response'] = {'http': estado_post, 'cuerpo': cuerpo_post,
                                'duracionSegundos': round(dur_post, 3),
                                'recibido': ahora()}
    guardar(ev)

    id_umbral = (cuerpo_post or {}).get('id_umbral_ambiental') if isinstance(cuerpo_post, dict) else None
    # Si el POST fallo pero pudo crear la fila, hay que localizarla sin reintentar el POST.
    if id_umbral is None:
        _, lista, _ = http('GET', f'/configuracion/umbrales?id_especie={ESPECIE}')
        encontrado = next((u for u in (lista or {}).get('items', [])
                           if u['id_variable_ambiental'] == VARIABLE and u.get('es_activo')), None)
        id_umbral = (encontrado or {}).get('id_umbral_ambiental')
        ev['parte1']['idRecuperadoPorGet'] = id_umbral

    post1 = leer(id_umbral) if id_umbral else None
    _, aud1, _ = http('GET', f'/configuracion/umbrales/{id_umbral}/auditoria') if id_umbral else (None, None, 0)
    ev['parte1'].update({
        'id_umbral_ambiental': id_umbral,
        'umbralTrasPost': post1,
        'auditoria': aud1,
        'postGateway': estado_gateway(),
        'estado_sincronizacion': (post1 or {}).get('estado_sincronizacion'),
        'fecha_ultima_sincronizacion': (post1 or {}).get('fecha_ultima_sincronizacion'),
        'motivo_fallo_sincronizacion': (post1 or {}).get('motivo_fallo_sincronizacion'),
    })

    oraculo1 = {
        'http201': estado_post == 201,
        'menosDe1Segundo': dur_post < 1.0,
        'umbralCreado': bool(post1),
        'valoresPersistidos40a90': bool(post1) and coincide(post1, 40, 90, CUERPO_POST['niveles']),
        'estadoAplicada': (post1 or {}).get('estado_sincronizacion') == 'APLICADA',
        'fechaSincronizacionNoNula': bool((post1 or {}).get('fecha_ultima_sincronizacion')),
        'sinMotivoDeFallo': not (post1 or {}).get('motivo_fallo_sincronizacion'),
        'propagacionAlGatewayUnico': dest_pre == [GATEWAY],
    }
    ev['parte1']['oraculo'] = oraculo1
    ev['parte1']['verdict'] = 'OK' if all(oraculo1.values()) else 'FALLO'
    guardar(ev)

    if not all(oraculo1.values()):
        ev['verdict'] = 'RECHAZADO'
        ev['motivo'] = ('La parte 1 (POST con Edge ONLINE) no cumplio lo esperado: '
                        + ', '.join(k for k, v in oraculo1.items() if not v)
                        + f". estado_sincronizacion={(post1 or {}).get('estado_sincronizacion')}, "
                        f"motivo={(post1 or {}).get('motivo_fallo_sincronizacion')}")
        ev['patchEjecutado'] = False
        ev['tc63'] = 'NO EJECUTADO (TC-62 no dejo Configuracion A aplicada)'
        ev['fin'] = ahora()
        guardar(ev)
        print(f"PARTE 1 FALLO: {ev['motivo']}")
        print(f"Evidencia: {OUT / 'tc62-result.json'}")
        return

    # ================= PARTE 2: PATCH ================================================
    actual = leer(id_umbral)
    fecha_exacta = (actual or {}).get('fecha_actualizacion')
    gw_pre2 = estado_gateway()
    ev['parte2'] = {'getPrevio': actual, 'fecha_actualizacion_capturada': fecha_exacta,
                    'preGateway': gw_pre2}
    if gw_pre2['clasificacion'] != 'EDGE_ONLINE':
        ev['parte2']['verdict'] = 'NO_EJECUTADO'
        ev['parte2']['motivo'] = f"Edge dejo de estar ONLINE ({gw_pre2['clasificacion']})"
        ev['verdict'] = 'BLOQUEADO'
        ev['fin'] = ahora()
        guardar(ev)
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
    guardar(ev)

    estado_pa, cuerpo_pa, dur_pa = http('PATCH', f'/configuracion/umbrales/{id_umbral}',
                                        cuerpo_patch, timeout=TIMEOUT_ESCRITURA)
    ev['parte2']['response'] = {'http': estado_pa, 'cuerpo': cuerpo_pa,
                                'duracionSegundos': round(dur_pa, 3), 'recibido': ahora()}
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
    }
    ev['parte2']['oraculo'] = oraculo2
    ev['parte2']['verdict'] = 'OK' if all(oraculo2.values()) else 'FALLO'

    if all(oraculo1.values()) and all(oraculo2.values()):
        ev['verdict'] = 'APROBADO'
        ev['configuracionA'] = {'id_umbral_ambiental': id_umbral, 'valor_min': 40,
                                'valor_max': 95, 'niveles': NIVELES_A,
                                'nota': 'baseline para TC-M09-63'}
        ev['tc63'] = 'PENDIENTE: requiere que el Edge pase a OFFLINE, comprobado por runtime'
    else:
        ev['verdict'] = 'RECHAZADO'
        ev['motivo'] = ('La parte 2 (PATCH con Edge ONLINE) no cumplio lo esperado: '
                        + ', '.join(k for k, v in oraculo2.items() if not v))
        ev['tc63'] = 'NO EJECUTADO'
    ev['fin'] = ahora()
    guardar(ev)

    print(f"TC-M09-62: {ev['verdict']}")
    print(f"  POST  HTTP {estado_post} en {dur_post:.3f}s · id={id_umbral} · "
          f"sync={ev['parte1']['estado_sincronizacion']} · "
          f"fecha={ev['parte1']['fecha_ultima_sincronizacion']}")
    print(f"  PATCH HTTP {estado_pa} en {dur_pa:.3f}s · "
          f"sync={ev['parte2']['estado_sincronizacion']} · "
          f"fecha={ev['parte2']['fecha_ultima_sincronizacion']}")
    print(f"  parte1 no cumplido: {[k for k, v in oraculo1.items() if not v] or 'ninguno'}")
    print(f"  parte2 no cumplido: {[k for k, v in oraculo2.items() if not v] or 'ninguno'}")
    print(f"Evidencia: {OUT / 'tc62-result.json'}")


if __name__ == '__main__':
    main()
