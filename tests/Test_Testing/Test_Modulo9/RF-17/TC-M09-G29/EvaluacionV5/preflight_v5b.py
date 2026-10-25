"""TC-M09-G29 V5 (reejecucion) - FASE 1: preflight de solo lectura. 0 escrituras.

Fixture oficial de Desarrollo: TEST, finca 44, area 22, especie 4, variable 10
(Humedad Relativa), Gateway Edge SERBY-TAX-FIRMWARE como unico destino RF-17.

Comprueba las 8 precondiciones. Si alguna falla, se detiene sin escrituras.

Uso: RUN_ID=... TEST_ADMIN_PASSWORD=... python preflight_v5b.py
"""
from __future__ import annotations

import datetime
import json
import os
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path

BASE = 'https://api.inmero.co/back-sigab-test'
ACTOR = 'administador.dev@gmail.com'

FIXTURE = {'id_finca': 44, 'nombre_finca': 'Finca Prueba QA femjscac',
           'id_infraestructura': 22, 'nombre_area': 'QA-G36-Infra-1789010064',
           'id_especie': 4, 'nombre_especie': 'Cachama Blanca',
           'id_variable_ambiental': 10, 'nombre_variable': 'Humedad Relativa',
           'gateway': 'SERBY-TAX-FIRMWARE'}
# Rango que usaran TC-62 (40-90, 40-95) y TC-63 (40-100).
RANGO_NECESARIO = (Decimal('40'), Decimal('100'))

MUERTOS = {'INACTIVO', 'CERRADO', 'BAJA'}
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


def http(metodo: str, ruta: str, cuerpo: dict | None = None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    pet = urllib.request.Request(BASE + ruta, data=datos, method=metodo)
    if datos:
        pet.add_header('Content-Type', 'application/json')
    if _token:
        pet.add_header('Authorization', f'Bearer {_token}')
    try:
        with urllib.request.urlopen(pet, timeout=90) as r:
            return r.status, json.loads(r.read() or b'null')
    except urllib.error.HTTPError as exc:
        bruto = exc.read()
        try:
            return exc.code, json.loads(bruto or b'null')
        except ValueError:
            return exc.code, {'raw': bruto.decode('utf-8', 'replace')[:300]}
    except Exception as exc:                                   # noqa: BLE001
        return -1, {'error': f'{type(exc).__name__}: {str(exc)[:200]}'}


def main() -> None:
    global _token
    clave = os.environ.get('TEST_ADMIN_PASSWORD')
    if not clave:
        raise SystemExit('TEST_ADMIN_PASSWORD no disponible.')
    est, login = http('POST', '/sesiones/',
                      {'correo_electronico': ACTOR, 'contrasena': clave})
    if est != 200 or not (login or {}).get('token'):
        raise SystemExit(f'login TEST fallido (HTTP {est}).')
    _token = login['token']

    ev: dict = {'runId': RUN_ID, 'caso': 'TC-M09-G29', 'version': 'V5-reejecucion',
                'ambiente': 'TEST', 'base': BASE, 'fixtureAutorizado': FIXTURE,
                'escriturasFuncionales': 0, 'inicio': ahora(),
                'actor': {'correo': ACTOR, 'tokenPersistido': False}}

    # 6. Actor
    _, yo = http('GET', '/usuarios/me')
    _, permisos = http('GET', '/sesiones/me/permisos')
    acc20 = sorted({p['id_accion'] for p in (permisos or {}).get('permisos', [])
                    if p.get('id_recurso') == 20})
    ev['actor'].update({
        'identidad': {k: (yo or {}).get(k) for k in
                      ('id_usuario', 'nombre', 'apellidos', 'nombre_rol', 'estado_cuenta')},
        'permisosRecurso20': acc20,
        'puedeCrearYEditarUmbrales': {1, 2, 3}.issubset(set(acc20)),
    })

    # 1. Especie activa
    _, especies = http('GET', '/configuracion/especies?limite=500')
    esp = next((e for e in (especies or {}).get('items', [])
                if e['id_especie'] == FIXTURE['id_especie']), None)
    ev['especie'] = {'encontrada': bool(esp), 'nombre': (esp or {}).get('nombre'),
                     'es_activo': (esp or {}).get('es_activo'),
                     'coincideConFixture': (esp or {}).get('nombre') == FIXTURE['nombre_especie']}

    # 2. Variable ambiental
    _, variables = http('GET', '/configuracion/variables-ambientales')
    var = next((v for v in (variables or {}).get('items', [])
                if v['id_variable_ambiental'] == FIXTURE['id_variable_ambiental']), None)
    rango_ok = False
    if var:
        rango_ok = (Decimal(str(var['valor_fisico_min'])) <= RANGO_NECESARIO[0]
                    and Decimal(str(var['valor_fisico_max'])) >= RANGO_NECESARIO[1])
    ev['variable'] = {'encontrada': bool(var), 'nombre': (var or {}).get('nombre'),
                      'unidad': (var or {}).get('unidad'),
                      'rangoFisico': [(var or {}).get('valor_fisico_min'),
                                      (var or {}).get('valor_fisico_max')],
                      'coincideConFixture': (var or {}).get('nombre') == FIXTURE['nombre_variable'],
                      'admite40a100': rango_ok}

    # 3. No debe existir umbral activo para especie 4 + variable 10
    _, lista = http('GET', f"/configuracion/umbrales?id_especie={FIXTURE['id_especie']}")
    umbrales = (lista or {}).get('items', [])
    duplicado = [u for u in umbrales
                 if u['id_variable_ambiental'] == FIXTURE['id_variable_ambiental']
                 and u.get('es_activo')]
    ev['duplicado'] = {
        'existeUmbralActivoParaEsaCombinacion': bool(duplicado),
        'detalle': duplicado,
        'riesgo409': bool(duplicado),
        'umbralesActivosDeLaEspecie': [
            {'id': u['id_umbral_ambiental'], 'id_variable_ambiental': u['id_variable_ambiental'],
             'valor_min': u['valor_min'], 'valor_max': u['valor_max'],
             'estado_sincronizacion': u['estado_sincronizacion']}
            for u in umbrales if u.get('es_activo')],
    }

    # 4-5. Gateway destino y resolucion RF-17
    _, tipos = http('GET', '/configuracion/tipos-dispositivo-iot')
    tipo_por_id = {x['id_tipo_dispositivo']: x['nombre']
                   for x in (tipos or {}).get('items', [])}
    _, disp = http('GET', '/configuracion/dispositivos-iot')
    dispositivos = (disp or {}).get('items', [])
    por_id = {d['id_dispositivo_iot']: d for d in dispositivos}
    _, fincas = http('GET', '/configuracion/fincas?limite=500')
    areas = {}
    for f in (fincas or {}).get('items', []):
        _, infra = http('GET', f"/configuracion/infraestructuras?finca_id={f['id_finca']}")
        for i in (infra or {}).get('items', []):
            areas[i['id_infraestructura']] = i
    activos, pagina = [], 1
    while True:
        _, a = http('GET', f'/activos-biologicos?pagina={pagina}&registros_por_pagina=100')
        regs = (a or {}).get('registros', [])
        activos.extend(regs)
        if pagina >= (a or {}).get('total_paginas', 1) or not regs:
            break
        pagina += 1

    ide = FIXTURE['id_especie']
    ar = {k for k, v in areas.items() if v.get('es_activo') and v.get('especie_id') == ide}
    ar |= {r['id_infraestructura'] for r in activos
           if r.get('id_especie') == ide
           and (r.get('nombre_estado') or '').upper() not in MUERTOS
           and areas.get(r.get('id_infraestructura'), {}).get('es_activo')}
    destinos = set()
    for d in dispositivos:
        if not d.get('es_activo') or d.get('id_infraestructura') not in ar:
            continue
        g = por_id.get(d.get('id_dispositivo_gateway') or d['id_dispositivo_iot'])
        if g and g.get('es_activo') and tipo_por_id.get(g['id_tipo_dispositivo']) == 'GATEWAY_EDGE':
            destinos.add(g['serial'])
    destinos = sorted(destinos)

    gw = next((d for d in dispositivos if d['serial'] == FIXTURE['gateway']), None)
    gid = (gw or {}).get('id_dispositivo_iot')
    _, cred = http('GET', f'/configuracion/dispositivos-iot/{gid}/credencial-mqtt') if gid else (None, {})
    _, estado = http('GET', f'/iot/dispositivos/{gid}/estado') if gid else (None, {})
    bloque = (estado or {}).get('estado') if isinstance(estado, dict) else {}
    conectada = (cred or {}).get('conectada') if isinstance(cred, dict) else None
    sin_contacto = (bloque or {}).get('tiempo_sin_contacto')

    area_gw = areas.get((gw or {}).get('id_infraestructura'), {})
    ev['gateway'] = {
        'serial': FIXTURE['gateway'], 'id_dispositivo_iot': gid,
        'es_activo': (gw or {}).get('es_activo'),
        'area': {'id': area_gw.get('id_infraestructura'),
                 'nombre': area_gw.get('nombre_infraestructura'),
                 'id_finca': area_gw.get('id_finca')},
        'credencialMqtt': limpio(cred if isinstance(cred, dict) else {}),
        'heartbeat': limpio(bloque if isinstance(bloque, dict) else {}),
        'conectada': conectada,
        'heartbeatReciente': isinstance(sin_contacto, int) and sin_contacto < 300,
        'credencialEmitidaYHabilitada': bool((cred or {}).get('emitida'))
                                        and bool((cred or {}).get('habilitada')),
        'clasificacion': ('EDGE_ONLINE' if conectada is True else
                          'EDGE_OFFLINE' if conectada is False else 'EDGE_NO_VERIFICABLE'),
    }
    ev['resolucionRf17'] = {'destinos': destinos, 'cantidad': len(destinos),
                            'unicoYEsElDelFixture': destinos == [FIXTURE['gateway']],
                            'areasDeLaEspecie': sorted(ar)}

    # 7. Contrato en OpenAPI
    _, openapi = http('GET', '/openapi.json')
    rutas = (openapi or {}).get('paths', {})
    post_op = rutas.get('/configuracion/umbrales', {}).get('post', {})
    patch_op = rutas.get('/configuracion/umbrales/{id_umbral_ambiental}', {}).get('patch', {})
    ev['contrato'] = {
        'POST /configuracion/umbrales': {'disponible': bool(post_op),
                                         'respuestas': sorted(post_op.get('responses', {}))},
        'PATCH /configuracion/umbrales/{id}': {'disponible': bool(patch_op),
                                               'respuestas': sorted(patch_op.get('responses', {}))},
        'ambosDeclaran500': '500' in post_op.get('responses', {})
                            and '500' in patch_op.get('responses', {}),
    }

    # 8. Fixture sin cambios respecto a lo entregado por Desarrollo
    ev['coherenciaFixture'] = {
        'areaDelGatewayEsLaIndicada': area_gw.get('id_infraestructura') == FIXTURE['id_infraestructura'],
        'nombreAreaCoincide': area_gw.get('nombre_infraestructura') == FIXTURE['nombre_area'],
        'fincaDelAreaEsLaIndicada': area_gw.get('id_finca') == FIXTURE['id_finca'],
        'especieCoincide': ev['especie']['coincideConFixture'],
        'variableCoincide': ev['variable']['coincideConFixture'],
    }

    # --- Precondiciones ---------------------------------------------------------------
    pre = {
        '1_especie4Activa': bool(esp) and esp.get('es_activo') is True,
        '2_variable10DisponibleYValida': bool(var) and rango_ok,
        '3_sinUmbralActivoParaEsaCombinacion': not duplicado,
        '4a_gatewayActivoAdministrativamente': (gw or {}).get('es_activo') is True,
        '4b_gatewayConectada': conectada is True,
        '4c_heartbeatReciente': ev['gateway']['heartbeatReciente'],
        '4d_credencialEmitidaYHabilitada': ev['gateway']['credencialEmitidaYHabilitada'],
        '5_unicoDestinoRf17EsElGateway': destinos == [FIXTURE['gateway']],
        '6_actorAutenticadoYAutorizado': ev['actor']['puedeCrearYEditarUmbrales'],
        '7_contratoPostYPatchDisponible': bool(post_op) and bool(patch_op),
        '8_fixtureSinCambios': all(ev['coherenciaFixture'].values()),
    }
    ev['precondiciones'] = pre
    ev['preflightOk'] = all(pre.values())
    ev['fallidas'] = [k for k, v in pre.items() if not v]
    ev['fin'] = ahora()

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'preflight.json').write_text(
        json.dumps(ev, indent=2, ensure_ascii=False), encoding='utf-8')

    print('PREFLIGHT_OK' if ev['preflightOk'] else 'PREFLIGHT CERRADO')
    print(f"  RUN_ID: {RUN_ID}")
    print(f"  especie 4: {ev['especie']['nombre']} activa={ev['especie']['es_activo']}")
    print(f"  variable 10: {ev['variable']['nombre']} ({ev['variable']['unidad']}) "
          f"rango={ev['variable']['rangoFisico']} admite40a100={rango_ok}")
    print(f"  umbral activo 4+10 ya existente: {bool(duplicado)} -> riesgo409={bool(duplicado)}")
    if duplicado:
        for u in duplicado:
            print(f"      id={u['id_umbral_ambiental']} {u['valor_min']}-{u['valor_max']} "
                  f"sync={u['estado_sincronizacion']}")
    print(f"  gateway: id={gid} activo={(gw or {}).get('es_activo')} "
          f"conectada={conectada} sin_contacto={sin_contacto}s")
    print(f"  destinos RF-17: {destinos}")
    print(f"  fallidas: {ev['fallidas'] or 'ninguna'}")
    print(f"Evidencia: {OUT / 'preflight.json'}")


if __name__ == '__main__':
    main()
