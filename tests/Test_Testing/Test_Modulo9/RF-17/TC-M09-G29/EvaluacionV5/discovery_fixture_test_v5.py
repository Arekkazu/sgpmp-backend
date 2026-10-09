"""TC-M09-G29 V5 - discovery del fixture ejecutable en TEST (SOLO LECTURA, 0 escrituras).

TEST es el ambiente decisorio de esta ejecucion: la infraestructura MQTT/Edge
fue preparada alli para QA. Este script responde si existe una combinacion
NATURAL (sin crear, mover ni reasociar nada) en la que

    especie -> activos vivos -> area -> destino(s) RF-17

devuelva un conjunto de Gateway Edge en el que TODOS esten ONLINE, que es la
precondicion de una sincronizacion exitosa: la consolidacion de RF-17 exige que
todos confirmen ACK para llegar a APLICADA; un solo desconectado degrada el
umbral a PENDIENTE y fuerza el 500.

Replica fielmente ``modulo9.fn_seriales_gateway_edge_por_especie`` (migracion
a3c9e5d17b42) sin filtrar artificialmente ningun Gateway, y deja constancia de
la cobertura de los catalogos para que la ausencia de fixture no pueda
confundirse con un discovery incompleto.

Secretos: contrasena desde el entorno; nunca se persiste.

Uso: RUN_ID=... TEST_ADMIN_PASSWORD=... python discovery_fixture_test_v5.py
"""
from __future__ import annotations

import datetime
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

BASE = 'https://api.inmero.co/back-sigab-test'
ACTOR = 'administador.dev@gmail.com'
GATEWAY_PREFERIDO = 'SERBY-TAX-FIRMWARE'
NODO_PREFERIDO = 'TEST-AMBIENTAL'

# La funcion SQL filtra los estados por nombre, no por id (los ids son datos).
MUERTOS = {'INACTIVO', 'CERRADO', 'BAJA'}
SENSIBLES = ('password', 'contrasena', 'token', 'secret', 'usuario_mqtt', 'clave')

AQUI = Path(__file__).resolve().parent
RUN_ID = os.environ.get('RUN_ID')
if not RUN_ID:
    raise SystemExit('Falta RUN_ID (el mismo del preflight).')
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
        raise SystemExit('TEST_ADMIN_PASSWORD no disponible: no se continua.')
    est, login = http('POST', '/sesiones/',
                      {'correo_electronico': ACTOR, 'contrasena': clave})
    if est != 200 or not (login or {}).get('token'):
        raise SystemExit(f'login TEST fallido (HTTP {est}).')
    _token = login['token']

    ev: dict = {'runId': RUN_ID, 'caso': 'TC-M09-G29', 'version': 'V5',
                'ambienteDecisorio': 'TEST', 'base': BASE,
                'escriturasFuncionales': 0, 'inicio': ahora(),
                'actor': {'correo': ACTOR, 'tokenPersistido': False}}

    _, permisos = http('GET', '/sesiones/me/permisos')
    acc9 = sorted({p['id_accion'] for p in (permisos or {}).get('permisos', [])
                   if p.get('id_recurso') == 9})
    ev['alcance'] = {'permisosRecurso9_fincas': acc9,
                     'esGlobalSinFiltroDeFinca': bool({3, 4} & set(acc9))}

    # --- Catalogos, con constancia de cobertura ------------------------------------
    _, especies = http('GET', '/configuracion/especies?limite=500')
    _, fincas = http('GET', '/configuracion/fincas?limite=500')
    _, tipos = http('GET', '/configuracion/tipos-dispositivo-iot')
    _, disp = http('GET', '/configuracion/dispositivos-iot')
    tipo_por_id = {x['id_tipo_dispositivo']: x['nombre']
                   for x in (tipos or {}).get('items', [])}
    dispositivos = (disp or {}).get('items', [])
    por_id = {d['id_dispositivo_iot']: d for d in dispositivos}
    por_serial = {d['serial']: d for d in dispositivos}

    areas: dict[int, dict] = {}
    for f in (fincas or {}).get('items', []):
        _, infra = http('GET', f"/configuracion/infraestructuras?finca_id={f['id_finca']}")
        for i in (infra or {}).get('items', []):
            areas[i['id_infraestructura']] = {
                'id_infraestructura': i['id_infraestructura'],
                'nombre': i.get('nombre_infraestructura'),
                'id_finca': i.get('id_finca'),
                'especie_id': i.get('especie_id'),
                'es_activo': i.get('es_activo'),
            }

    activos, pagina = [], 1
    total_declarado = None
    while True:
        _, a = http('GET', f'/activos-biologicos?pagina={pagina}&registros_por_pagina=100')
        regs = (a or {}).get('registros', [])
        total_declarado = (a or {}).get('total_registros', total_declarado)
        activos.extend(regs)
        if pagina >= (a or {}).get('total_paginas', 1) or not regs:
            break
        pagina += 1

    ev['cobertura'] = {
        'especies': {'declarado': (especies or {}).get('total'),
                     'recuperado': len((especies or {}).get('items', []))},
        'fincas': {'declarado': (fincas or {}).get('total'),
                   'recuperado': len((fincas or {}).get('items', []))},
        'dispositivos': {'declarado': (disp or {}).get('total'),
                         'recuperado': len(dispositivos)},
        'activosBiologicos': {'declarado': total_declarado, 'recuperado': len(activos)},
        'areas': {'recuperado': len(areas)},
        'areasConEspecieIdNoNula': [a for a in areas.values() if a['especie_id'] is not None],
        'nota': ('si declarado != recuperado, el discovery esta incompleto y una ausencia '
                 'de fixture no seria concluyente'),
    }

    # --- Inventario de Gateway Edge con area, finca, estado y conectividad ---------
    gateways: dict[str, dict] = {}
    for d in dispositivos:
        if tipo_por_id.get(d.get('id_tipo_dispositivo')) != 'GATEWAY_EDGE':
            continue
        area = areas.get(d.get('id_infraestructura'), {})
        finca = next((f for f in (fincas or {}).get('items', [])
                      if f['id_finca'] == area.get('id_finca')), {})
        gid = d['id_dispositivo_iot']
        _, cred = http('GET', f'/configuracion/dispositivos-iot/{gid}/credencial-mqtt')
        _, estado = http('GET', f'/iot/dispositivos/{gid}/estado')
        bloque = (estado or {}).get('estado') if isinstance(estado, dict) else {}
        conectada = (cred or {}).get('conectada') if isinstance(cred, dict) else None
        gateways[d['serial']] = {
            'id_dispositivo_iot': gid,
            'area': {'id': area.get('id_infraestructura'), 'nombre': area.get('nombre'),
                     'es_activo': area.get('es_activo')},
            'finca': {'id': finca.get('id_finca'), 'nombre': finca.get('nombre'),
                      'es_activo': finca.get('es_activo')},
            'estadoAdministrativo': {'es_activo': d.get('es_activo')},
            'credencialMqtt': limpio(cred if isinstance(cred, dict) else {}),
            'heartbeat': limpio(bloque if isinstance(bloque, dict) else {}),
            'conectada': conectada,
            'clasificacion': ('EDGE_ONLINE' if conectada is True else
                              'EDGE_OFFLINE' if conectada is False else
                              'EDGE_NO_VERIFICABLE'),
        }
    ev['gatewaysEdge'] = gateways
    online = sorted(s for s, g in gateways.items() if g['clasificacion'] == 'EDGE_ONLINE')
    ev['gatewaysOnline'] = online

    # --- Replica fiel de fn_seriales_gateway_edge_por_especie ---------------------
    def areas_de_especie(id_especie: int) -> dict:
        por_campo = sorted(k for k, v in areas.items()
                           if v['es_activo'] and v['especie_id'] == id_especie)
        por_activos = sorted({r['id_infraestructura'] for r in activos
                              if r.get('id_especie') == id_especie
                              and (r.get('nombre_estado') or '').upper() not in MUERTOS
                              and areas.get(r.get('id_infraestructura'), {}).get('es_activo')})
        return {'porEspecieIdDelArea': por_campo, 'porActivosVivos': por_activos,
                'union': sorted(set(por_campo) | set(por_activos))}

    def destinos(ids_area: list[int]) -> list[str]:
        seriales = set()
        for d in dispositivos:
            if not d.get('es_activo') or d.get('id_infraestructura') not in ids_area:
                continue
            g = por_id.get(d.get('id_dispositivo_gateway') or d['id_dispositivo_iot'])
            if g and g.get('es_activo') and tipo_por_id.get(g['id_tipo_dispositivo']) == 'GATEWAY_EDGE':
                seriales.add(g['serial'])
        return sorted(seriales)

    evaluadas = []
    for e in (especies or {}).get('items', []):
        if not e.get('es_activo'):
            continue
        ar = areas_de_especie(e['id_especie'])
        gws = destinos(ar['union'])
        estados = {s: gateways.get(s, {}).get('clasificacion', 'DESCONOCIDO') for s in gws}
        todos_online = bool(gws) and all(v == 'EDGE_ONLINE' for v in estados.values())
        if not gws:
            veredicto = ('PENDIENTE sin 500 (sin Gateway: no hay intento, '
                         'no puede llegar a APLICADA)')
        elif todos_online:
            veredicto = 'APLICADA posible (200/201)'
        else:
            veredicto = 'PENDIENTE + HTTP 500 (algun destino desconectado)'
        evaluadas.append({
            'id_especie': e['id_especie'], 'nombre': e['nombre'],
            'areas': ar, 'destinosRf17': gws, 'estadoDeCadaDestino': estados,
            'offline': sorted(s for s, v in estados.items() if v != 'EDGE_ONLINE'),
            'todosOnline': todos_online,
            'incluyeGatewayPreferido': GATEWAY_PREFERIDO in gws,
            'veredictoEsperadoRf17': veredicto,
        })
    ev['especiesEvaluadas'] = evaluadas

    aptas = [x for x in evaluadas if x['todosOnline']]
    con_preferido = [x for x in evaluadas if x['incluyeGatewayPreferido']]
    ev['resultadoDiscovery'] = {
        'especiesActivasEvaluadas': len(evaluadas),
        'especiesConDestinoRf17': len([x for x in evaluadas if x['destinosRf17']]),
        'especiesConTodosLosDestinosOnline': [x['id_especie'] for x in aptas],
        'especiesQueAlcanzanElGatewayPreferido': [x['id_especie'] for x in con_preferido],
        'fixtureSeleccionado': (aptas[0] if aptas else None),
        'ejecutableTc62': bool(aptas),
    }

    nodo = por_serial.get(NODO_PREFERIDO)
    gw_pref = gateways.get(GATEWAY_PREFERIDO)
    ev['cadenaPreferida'] = {
        'nodo': NODO_PREFERIDO,
        'nodoExiste': bool(nodo),
        'nodoBajoGatewayPreferido': bool(nodo) and bool(gw_pref) and
                                    nodo.get('id_dispositivo_gateway') == gw_pref['id_dispositivo_iot'],
        'gateway': GATEWAY_PREFERIDO,
        'gatewayClasificacion': (gw_pref or {}).get('clasificacion'),
        'especiesQueLoAlcanzan': [{'id_especie': x['id_especie'], 'nombre': x['nombre'],
                                   'destinosRf17': x['destinosRf17'],
                                   'offline': x['offline']} for x in con_preferido],
        'respaldadaPorRf17': any(x['todosOnline'] for x in con_preferido),
    }

    ev['fin'] = ahora()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'discovery-fixture-test.json').write_text(
        json.dumps(ev, indent=2, ensure_ascii=False), encoding='utf-8')

    print(f"Cobertura: {ev['cobertura']['especies']}, dispositivos "
          f"{ev['cobertura']['dispositivos']}, activos {ev['cobertura']['activosBiologicos']}")
    print(f'Gateway Edge ONLINE: {online}')
    print()
    for x in evaluadas:
        print(f"esp {x['id_especie']:>3} {x['nombre'][:22]:24} destinos={x['destinosRf17'] or '[]'}")
        print(f"            offline={x['offline'] or '[]'} -> {x['veredictoEsperadoRf17']}")
    print()
    print(f"EJECUTABLE TC-62: {ev['resultadoDiscovery']['ejecutableTc62']}  "
          f"aptas={ev['resultadoDiscovery']['especiesConTodosLosDestinosOnline']}")
    print(f"Evidencia: {OUT / 'discovery-fixture-test.json'}")


if __name__ == '__main__':
    main()
