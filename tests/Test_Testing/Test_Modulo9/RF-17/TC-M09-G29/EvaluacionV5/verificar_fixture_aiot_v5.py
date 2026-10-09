"""TC-M09-G29 V5 - verificacion del fixture indicado por AIoT (SOLO LECTURA, 0 escrituras).

AIoT indico: Nodo TEST-AMBIENTAL (id 139) bajo el Gateway Edge SERBY-TAX-FIRMWARE
(id 138), area QA-G36-Infra-1789010064, finca "Finca Prueba QA femjscac".

Este script responde los 10 puntos de la correccion de fixture sin escribir nada:
localiza esos elementos en runtime, comprueba la conectividad real del Gateway
(no el simple "Activo" administrativo), determina la especie del area y calcula
que Gateway devuelve realmente el mecanismo de resolucion de destinos de RF-17.

Busca primero en DEV (ambiente decisorio) y, si no aparece, contrasta en TEST en
solo lectura (seccion 12 del paquete: TEST documenta contraste, no sustituye a DEV).

Secretos: contrasenas desde el entorno; nunca se persisten.

Uso: RUN_ID=... DEV_ADMIN_PASSWORD=... TEST_ADMIN_PASSWORD=... \
     python verificar_fixture_aiot_v5.py
"""
from __future__ import annotations

import datetime
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

AMBIENTES = {
    'DEV': {'base': 'https://api.inmero.co/back-sigab-dev',
            'actor': 'admin.dev@gmail.com', 'env': 'DEV_ADMIN_PASSWORD'},
    'TEST': {'base': 'https://api.inmero.co/back-sigab-test',
             'actor': 'administador.dev@gmail.com', 'env': 'TEST_ADMIN_PASSWORD'},
}

FIXTURE_AIOT = {
    'nodo': {'serial': 'TEST-AMBIENTAL', 'idInterfaz': 139},
    'gateway': {'serial': 'SERBY-TAX-FIRMWARE', 'idInterfaz': 138},
    'area': 'QA-G36-Infra-1789010064',
    'finca': 'Finca Prueba QA femjscac',
}

MUERTOS = {'INACTIVO', 'CERRADO', 'BAJA'}
SENSIBLES = ('password', 'contrasena', 'token', 'secret', 'usuario_mqtt', 'clave')

AQUI = Path(__file__).resolve().parent
RUN_ID = os.environ.get('RUN_ID')
if not RUN_ID:
    raise SystemExit('Falta RUN_ID (el mismo del preflight).')
OUT = AQUI / 'RESULTADOS' / RUN_ID


def ahora() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def limpio(d) -> dict:
    return {k: v for k, v in (d or {}).items()
            if not any(s in k.lower() for s in SENSIBLES)}


class Api:
    def __init__(self, base: str) -> None:
        self.base = base
        self.token: str | None = None

    def __call__(self, metodo: str, ruta: str, cuerpo: dict | None = None):
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        pet = urllib.request.Request(self.base + ruta, data=datos, method=metodo)
        if datos:
            pet.add_header('Content-Type', 'application/json')
        if self.token:
            pet.add_header('Authorization', f'Bearer {self.token}')
        try:
            with urllib.request.urlopen(pet, timeout=90) as r:
                return r.status, json.loads(r.read() or b'null')
        except urllib.error.HTTPError as exc:
            bruto = exc.read()
            try:
                return exc.code, json.loads(bruto or b'null')
            except ValueError:
                return exc.code, {'raw': bruto.decode('utf-8', 'replace')[:300]}
        except Exception as exc:                               # noqa: BLE001
            return -1, {'error': f'{type(exc).__name__}: {str(exc)[:200]}'}


def inspeccionar(nombre: str) -> dict:
    cfg = AMBIENTES[nombre]
    ev: dict = {'ambiente': nombre, 'base': cfg['base'], 'timestamp': ahora()}
    clave = os.environ.get(cfg['env'])
    if not clave:
        ev['error'] = f"{cfg['env']} no disponible en el entorno"
        return ev

    api = Api(cfg['base'])
    est, login = api('POST', '/sesiones/',
                     {'correo_electronico': cfg['actor'], 'contrasena': clave})
    if est != 200 or not (login or {}).get('token'):
        ev['error'] = f'login fallido (HTTP {est})'
        return ev
    api.token = login['token']
    ev['actor'] = {'correo': cfg['actor'], 'tokenPersistido': False}

    # Alcance: un actor con gestion de fincas (recurso 9, accion 3 o 4) ve todo,
    # asi que una ausencia es real y no un 404 por filtro de finca.
    _, permisos = api('GET', '/sesiones/me/permisos')
    acc9 = sorted({p['id_accion'] for p in (permisos or {}).get('permisos', [])
                   if p.get('id_recurso') == 9})
    ev['alcance'] = {'permisosRecurso9_fincas': acc9,
                     'esGlobalSinFiltroDeFinca': bool({3, 4} & set(acc9))}

    _, tipos = api('GET', '/configuracion/tipos-dispositivo-iot')
    tipo_por_id = {x['id_tipo_dispositivo']: x['nombre']
                   for x in (tipos or {}).get('items', [])}

    # 1-4. Localizar nodo y gateway por serial (el listado no acepta limite:
    # devuelve todo lo visible para el actor).
    _, disp = api('GET', '/configuracion/dispositivos-iot')
    dispositivos = (disp or {}).get('items', [])
    por_id = {d['id_dispositivo_iot']: d for d in dispositivos}
    por_serial = {d['serial']: d for d in dispositivos}
    ev['totalDispositivosVisibles'] = len(dispositivos)

    nodo = por_serial.get(FIXTURE_AIOT['nodo']['serial'])
    gateway = por_serial.get(FIXTURE_AIOT['gateway']['serial'])
    ev['nodo'] = {'buscado': FIXTURE_AIOT['nodo'], 'encontrado': bool(nodo),
                  'detalle': nodo,
                  'tipo': tipo_por_id.get((nodo or {}).get('id_tipo_dispositivo'))}
    ev['gateway'] = {'buscado': FIXTURE_AIOT['gateway'], 'encontrado': bool(gateway),
                     'detalle': gateway,
                     'tipo': tipo_por_id.get((gateway or {}).get('id_tipo_dispositivo'))}
    for i in (FIXTURE_AIOT['nodo']['idInterfaz'], FIXTURE_AIOT['gateway']['idInterfaz']):
        est_i, cuerpo_i = api('GET', f'/configuracion/dispositivos-iot/{i}')
        ev.setdefault('accesoDirectoPorId', {})[str(i)] = {
            'http': est_i,
            'serial': (cuerpo_i or {}).get('serial') if isinstance(cuerpo_i, dict) else None,
            'error_code': (cuerpo_i or {}).get('error_code') if isinstance(cuerpo_i, dict) else None,
        }

    if not (nodo and gateway):
        ev['conclusion'] = f'El fixture indicado por AIoT no existe en {nombre}.'
        return ev

    ev['nodoAsociadoAlGateway'] = (
        nodo.get('id_dispositivo_gateway') == gateway['id_dispositivo_iot'])

    # 5. Area y finca
    _, area = api('GET', f"/configuracion/infraestructuras/{gateway['id_infraestructura']}")
    ev['area'] = area
    if isinstance(area, dict):
        _, finca = api('GET', f"/configuracion/fincas/{area['id_finca']}")
        ev['finca'] = {'id_finca': (finca or {}).get('id_finca'),
                       'nombre': (finca or {}).get('nombre'),
                       'es_activo': (finca or {}).get('es_activo')}
        ev['coincideConLoIndicadoPorAiot'] = {
            'area': area.get('nombre_infraestructura') == FIXTURE_AIOT['area'],
            'finca': (finca or {}).get('nombre') == FIXTURE_AIOT['finca'],
        }

    # 6. Conectividad real, no el "Activo" administrativo
    gid = gateway['id_dispositivo_iot']
    _, cred = api('GET', f'/configuracion/dispositivos-iot/{gid}/credencial-mqtt')
    _, estado = api('GET', f'/iot/dispositivos/{gid}/estado')
    bloque = (estado or {}).get('estado') if isinstance(estado, dict) else {}
    conectada = (cred or {}).get('conectada') if isinstance(cred, dict) else None
    ev['conectividadGateway'] = {
        'es_activo_administrativo': gateway.get('es_activo'),
        'credencialMqtt': limpio(cred if isinstance(cred, dict) else {}),
        'estadoOperativo': limpio(bloque if isinstance(bloque, dict) else {}),
        'conectada': conectada,
        'clasificacion': ('EDGE_ONLINE' if conectada is True else
                          'EDGE_OFFLINE' if conectada is False else 'EDGE_NO_VERIFICABLE'),
    }

    # 7. Especie / activos vivos del area
    activos, pagina = [], 1
    while True:
        _, a = api('GET', f'/activos-biologicos?pagina={pagina}&registros_por_pagina=100')
        regs = (a or {}).get('registros', [])
        activos.extend(regs)
        if pagina >= (a or {}).get('total_paginas', 1) or not regs:
            break
        pagina += 1
    del_area = [r for r in activos
                if r.get('id_infraestructura') == gateway['id_infraestructura']
                and (r.get('nombre_estado') or '').upper() not in MUERTOS]
    ev['especiesDelArea'] = {
        'porCampoEspecieIdDelArea': (area or {}).get('especie_id'),
        'porActivosVivos': sorted({r['id_especie'] for r in del_area}),
        'activosVivos': [{'id': r['id_activo_biologico'], 'id_especie': r['id_especie'],
                          'estado': r['nombre_estado']} for r in del_area],
    }

    # 8-10. Resolucion RF-17 real por especie
    areas: dict[int, dict] = {}
    _, fincas = api('GET', '/configuracion/fincas')
    for f in (fincas or {}).get('items', []):
        _, infra = api('GET', f"/configuracion/infraestructuras?finca_id={f['id_finca']}")
        for i in (infra or {}).get('items', []):
            areas[i['id_infraestructura']] = {'especie_id': i.get('especie_id'),
                                              'es_activo': i.get('es_activo')}

    def resolver(id_especie: int) -> list[str]:
        ar = {k for k, v in areas.items() if v['es_activo'] and v['especie_id'] == id_especie}
        ar |= {r['id_infraestructura'] for r in activos
               if r.get('id_especie') == id_especie
               and (r.get('nombre_estado') or '').upper() not in MUERTOS
               and areas.get(r.get('id_infraestructura'), {}).get('es_activo')}
        seriales = set()
        for d in dispositivos:
            if not d.get('es_activo') or d['id_infraestructura'] not in ar:
                continue
            g = por_id.get(d.get('id_dispositivo_gateway') or d['id_dispositivo_iot'])
            if g and g.get('es_activo') and tipo_por_id.get(g['id_tipo_dispositivo']) == 'GATEWAY_EDGE':
                seriales.add(g['serial'])
        return sorted(seriales)

    def conectado(serial: str):
        d = por_serial.get(serial)
        if not d:
            return None
        _, c = api('GET', f"/configuracion/dispositivos-iot/{d['id_dispositivo_iot']}/credencial-mqtt")
        return (c or {}).get('conectada') if isinstance(c, dict) else None

    _, especies = api('GET', '/configuracion/especies')
    mapa = {}
    for e in (especies or {}).get('items', []):
        if not e.get('es_activo'):
            continue
        g = resolver(e['id_especie'])
        if g:
            mapa[e['id_especie']] = {'nombre': e['nombre'], 'gatewaysRf17': g}
    estados = {s: conectado(s)
               for s in sorted({s for v in mapa.values() for s in v['gatewaysRf17']})}
    objetivo = FIXTURE_AIOT['gateway']['serial']
    for v in mapa.values():
        g = v['gatewaysRf17']
        v['conectividad'] = {s: estados.get(s) for s in g}
        v['incluyeGatewayDeAiot'] = objetivo in g
        v['soloGatewaysConectados'] = all(estados.get(s) is True for s in g)
        # Consolidacion de RF-17: un solo desconectado degrada todo el umbral a
        # PENDIENTE y fuerza el 500; solo si TODOS confirman se llega a APLICADA.
        v['vereditoEsperadoRf17'] = ('APLICADA (200/201)' if v['soloGatewaysConectados']
                                     else 'PENDIENTE + HTTP 500')
    ev['resolucionRf17PorEspecie'] = mapa
    ev['conectividadGateways'] = estados
    ev['especiesQueResuelvenSoloElGatewayDeAiot'] = [
        i for i, v in mapa.items() if v['gatewaysRf17'] == [objetivo]]
    ev['especiesAptasParaTc62'] = [i for i, v in mapa.items() if v['soloGatewaysConectados']]
    return ev


def main() -> None:
    ev = {'runId': RUN_ID, 'caso': 'TC-M09-G29', 'version': 'V5',
          'proposito': 'Correccion de fixture indicada por AIoT (solo lectura)',
          'fixtureIndicadoPorAiot': FIXTURE_AIOT,
          'escriturasFuncionales': 0, 'inicio': ahora(),
          'ambientes': {n: inspeccionar(n) for n in ('DEV', 'TEST')}}
    ev['fin'] = ahora()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'fixture-aiot.json').write_text(
        json.dumps(ev, indent=2, ensure_ascii=False), encoding='utf-8')

    for n, a in ev['ambientes'].items():
        if a.get('error'):
            print(f"{n}: {a['error']}")
            continue
        print(f"{n}: nodo={a['nodo']['encontrado']} gateway={a['gateway']['encontrado']} "
              f"(de {a['totalDispositivosVisibles']} dispositivos, alcance global="
              f"{a['alcance']['esGlobalSinFiltroDeFinca']})")
        if a.get('conectividadGateway'):
            print(f"   conectividad Gateway: {a['conectividadGateway']['clasificacion']}")
            print(f"   especies aptas para TC-62: {a.get('especiesAptasParaTc62')}")
    print(f"Evidencia: {OUT / 'fixture-aiot.json'}")


if __name__ == '__main__':
    main()
