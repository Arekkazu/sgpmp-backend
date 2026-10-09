"""TC-M09-G29 V5 - saneamiento del fixture de TEST (PREPARACION, no TC-M09-62).

Desactiva administrativamente los 5 Gateway Edge OFFLINE que RF-17 agrega para
la especie 4, todos clasificados RESIDUO_QA_CONFIRMADO tras la confirmacion de
AIoT, para que el unico destino vigente sea SERBY-TAX-FIRMWARE.

Estas escrituras son PREPARACION / SANEAMIENTO DE FIXTURE. No cuentan como las
escrituras oficiales de TC-M09-62 ni de TC-M09-63.

Mecanismo: unicamente el endpoint oficial del producto
``PATCH /configuracion/dispositivos-iot/{id}/desactivar`` (RF-21). Sin SQL, sin
borrados, sin tocar activos biologicos, areas, fincas, especies ni asociaciones.

Ese endpoint desactiva EN CASCADA los dispositivos que el Gateway atiende, asi
que "cero dispositivos colgados" es una precondicion dura por Gateway: si
alguno tuviera hijos se omite, para no modificar entidades no autorizadas.

Ante cualquier fallo o efecto inesperado: se detiene de inmediato y no corrige
nada automaticamente.

Uso: RUN_ID=... TEST_ADMIN_PASSWORD=... python sanear_fixture_v5.py
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
ESPECIE = 4

# Autorizados por Juan, con id y serial emparejados: si el par no coincide en
# runtime no se escribe (protege contra que un id apunte a otro dispositivo).
AUTORIZADOS = [
    (133, 'TC-M09-G59-1791163477491'),
    (134, 'TC-M09-G59-RESUELTO-1791163477491'),
    (132, 'PRUEBA2'),
    (128, 'RASPBERRY3BPRUEBA'),
    (130, 'DISPOSITIVO-CAMARONERA-10'),
]
INTOCABLES = {'SERBY-TAX-FIRMWARE', 'TEST-AMBIENTAL'}
GATEWAY_OBJETIVO = 'SERBY-TAX-FIRMWARE'
NODO_OBJETIVO = 'TEST-AMBIENTAL'

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
            return exc.code, {'raw': bruto.decode('utf-8', 'replace')[:400]}
    except Exception as exc:                                   # noqa: BLE001
        return -1, {'error': f'{type(exc).__name__}: {str(exc)[:300]}'}


def guardar(ev: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'saneamiento-fixture.json').write_text(
        json.dumps(ev, indent=2, ensure_ascii=False), encoding='utf-8')


# --------------------------------------------------------------------------------------
def inventario() -> dict:
    """Foto de las entidades que NO deben cambiar, para diferenciar PRE vs POST."""
    _, especies = http('GET', '/configuracion/especies?limite=500')
    _, fincas = http('GET', '/configuracion/fincas?limite=500')
    _, disp = http('GET', '/configuracion/dispositivos-iot')
    areas = {}
    for f in (fincas or {}).get('items', []):
        _, infra = http('GET', f"/configuracion/infraestructuras?finca_id={f['id_finca']}")
        for i in (infra or {}).get('items', []):
            areas[i['id_infraestructura']] = {
                'es_activo': i.get('es_activo'), 'especie_id': i.get('especie_id'),
                'id_finca': i.get('id_finca')}
    activos, pagina = {}, 1
    while True:
        _, a = http('GET', f'/activos-biologicos?pagina={pagina}&registros_por_pagina=100')
        regs = (a or {}).get('registros', [])
        for r in regs:
            activos[r['id_activo_biologico']] = {
                'id_especie': r.get('id_especie'),
                'id_infraestructura': r.get('id_infraestructura'),
                'nombre_estado': r.get('nombre_estado')}
        if pagina >= (a or {}).get('total_paginas', 1) or not regs:
            break
        pagina += 1
    return {
        'dispositivos': {d['id_dispositivo_iot']: {
            'serial': d['serial'], 'es_activo': d.get('es_activo'),
            'id_infraestructura': d.get('id_infraestructura'),
            'id_dispositivo_gateway': d.get('id_dispositivo_gateway'),
            'id_tipo_dispositivo': d.get('id_tipo_dispositivo')}
            for d in (disp or {}).get('items', [])},
        'areas': areas,
        'fincas': {f['id_finca']: {'es_activo': f.get('es_activo')}
                   for f in (fincas or {}).get('items', [])},
        'especies': {e['id_especie']: {'es_activo': e.get('es_activo')}
                     for e in (especies or {}).get('items', [])},
        'activosBiologicos': activos,
    }


def destinos_rf17(inv: dict, tipo_por_id: dict, id_especie: int) -> list[str]:
    """Replica de modulo9.fn_seriales_gateway_edge_por_especie sobre el inventario."""
    areas = inv['areas']
    ar = {k for k, v in areas.items() if v['es_activo'] and v['especie_id'] == id_especie}
    ar |= {r['id_infraestructura'] for r in inv['activosBiologicos'].values()
           if r['id_especie'] == id_especie
           and (r['nombre_estado'] or '').upper() not in MUERTOS
           and areas.get(r['id_infraestructura'], {}).get('es_activo')}
    seriales = set()
    for gid, d in inv['dispositivos'].items():
        if not d['es_activo'] or d['id_infraestructura'] not in ar:
            continue
        g = inv['dispositivos'].get(d['id_dispositivo_gateway'] or gid)
        if g and g['es_activo'] and tipo_por_id.get(g['id_tipo_dispositivo']) == 'GATEWAY_EDGE':
            seriales.add(g['serial'])
    return sorted(seriales)


def conectividad(gid: int) -> dict:
    _, cred = http('GET', f'/configuracion/dispositivos-iot/{gid}/credencial-mqtt')
    _, estado = http('GET', f'/iot/dispositivos/{gid}/estado')
    bloque = (estado or {}).get('estado') if isinstance(estado, dict) else {}
    c = (cred or {}).get('conectada') if isinstance(cred, dict) else None
    return {'credencialMqtt': limpio(cred if isinstance(cred, dict) else {}),
            'heartbeat': limpio(bloque if isinstance(bloque, dict) else {}),
            'conectada': c,
            'clasificacion': ('EDGE_ONLINE' if c is True else
                              'EDGE_OFFLINE' if c is False else 'EDGE_NO_VERIFICABLE')}


def diferencias(pre: dict, post: dict) -> dict:
    cambios: dict = {}
    for entidad in pre:
        d = {}
        for k in set(pre[entidad]) | set(post[entidad]):
            a, b = pre[entidad].get(k), post[entidad].get(k)
            if a != b:
                d[str(k)] = {'pre': a, 'post': b}
        if d:
            cambios[entidad] = d
    return cambios


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

    ev: dict = {
        'runId': RUN_ID, 'caso': 'TC-M09-G29', 'version': 'V5', 'ambiente': 'TEST',
        'tipoDeEscritura': 'PREPARACION / SANEAMIENTO DE FIXTURE',
        'noCuentaComoEscrituraOficialDe': ['TC-M09-62', 'TC-M09-63'],
        'mecanismo': 'PATCH /configuracion/dispositivos-iot/{id}/desactivar (RF-21, oficial)',
        'sqlDirecto': False, 'registrosEliminados': 0,
        'autorizadoPor': 'Juan (QA), con confirmacion previa de AIoT',
        'inicio': ahora(), 'actor': {'correo': ACTOR, 'tokenPersistido': False},
        'desactivacionesEmitidas': 0,
    }

    _, tipos = http('GET', '/configuracion/tipos-dispositivo-iot')
    tipo_por_id = {x['id_tipo_dispositivo']: x['nombre']
                   for x in (tipos or {}).get('items', [])}

    # --- PRE completo ---------------------------------------------------------------
    inv_pre = inventario()
    pre_gw = {}
    for gid, serial in AUTORIZADOS:
        d = inv_pre['dispositivos'].get(gid)
        area = inv_pre['areas'].get((d or {}).get('id_infraestructura'), {})
        _, area_det = http('GET', f"/configuracion/infraestructuras/{(d or {}).get('id_infraestructura')}") \
            if d else (None, {})
        _, finca_det = http('GET', f"/configuracion/fincas/{area.get('id_finca')}") \
            if area else (None, {})
        hijos = [{'id': k, 'serial': v['serial'], 'es_activo': v['es_activo']}
                 for k, v in inv_pre['dispositivos'].items()
                 if v['id_dispositivo_gateway'] == gid]
        _, confs = http('GET', f'/configuracion/dispositivos-iot/{gid}/configuraciones')
        pre_gw[serial] = {
            'id_dispositivo_iot': gid,
            'serialEnRuntime': (d or {}).get('serial'),
            'existe': bool(d),
            'estadoAdministrativo': {'es_activo': (d or {}).get('es_activo')},
            'tipo': tipo_por_id.get((d or {}).get('id_tipo_dispositivo')),
            'area': {'id': (d or {}).get('id_infraestructura'),
                     'nombre': (area_det or {}).get('nombre_infraestructura'),
                     'es_activo': area.get('es_activo'),
                     'especie_id': area.get('especie_id')},
            'finca': {'id': area.get('id_finca'),
                      'nombre': (finca_det or {}).get('nombre'),
                      'es_activo': (finca_det or {}).get('es_activo')},
            'conectividad': conectividad(gid) if d else None,
            'dispositivosColgados': hijos,
            'configuracionesRf23': (confs or {}).get('items', []) if isinstance(confs, dict) else confs,
        }
    destinos_pre = destinos_rf17(inv_pre, tipo_por_id, ESPECIE)
    ev['pre'] = {'gateways': pre_gw, 'destinosRf17Especie4': destinos_pre,
                 'conteos': {k: len(v) for k, v in inv_pre.items()},
                 'timestamp': ahora()}
    guardar(ev)

    # --- Gates duros por Gateway -----------------------------------------------------
    plan = []
    for gid, serial in AUTORIZADOS:
        g = pre_gw[serial]
        motivos = []
        if not g['existe']:
            motivos.append('no existe en runtime')
        if g['serialEnRuntime'] != serial:
            motivos.append(f"el id {gid} apunta a {g['serialEnRuntime']!r}, no a {serial!r}")
        if g['tipo'] != 'GATEWAY_EDGE':
            motivos.append(f"no es GATEWAY_EDGE (es {g['tipo']!r})")
        if g['estadoAdministrativo']['es_activo'] is not True:
            motivos.append('ya esta inactivo')
        if g['dispositivosColgados']:
            motivos.append('tiene dispositivos colgados: la desactivacion seria en cascada '
                           'y modificaria entidades no autorizadas')
        if g['configuracionesRf23']:
            motivos.append('tiene configuraciones RF-23 registradas')
        if serial in INTOCABLES:
            motivos.append('esta en la lista de intocables')
        if serial not in destinos_pre:
            motivos.append('no figura entre los destinos RF-17 actuales de la especie 4')
        plan.append({'id': gid, 'serial': serial, 'apto': not motivos, 'motivos': motivos})
    ev['gatePorGateway'] = plan
    guardar(ev)

    no_aptos = [p for p in plan if not p['apto']]
    if no_aptos:
        ev['resultado'] = 'FIXTURE_G29_SANITIZATION_FAILED'
        ev['motivo'] = ('Gate cerrado antes de escribir: '
                        + '; '.join(f"{p['serial']}: {', '.join(p['motivos'])}" for p in no_aptos))
        ev['fin'] = ahora()
        guardar(ev)
        raise SystemExit(ev['motivo'])

    # --- Escrituras de saneamiento, una a una, sin correccion automatica ------------
    ev['desactivaciones'] = []
    for p in plan:
        estado, cuerpo = http('PATCH', f"/configuracion/dispositivos-iot/{p['id']}/desactivar")
        ev['desactivacionesEmitidas'] += 1
        registro = {'id': p['id'], 'serial': p['serial'], 'http': estado,
                    'respuesta': cuerpo, 'timestamp': ahora()}
        ev['desactivaciones'].append(registro)
        guardar(ev)
        ok = estado == 200 and (cuerpo or {}).get('es_activo') is False
        if not ok:
            ev['resultado'] = 'FIXTURE_G29_SANITIZATION_FAILED'
            ev['motivo'] = (f"La desactivacion de {p['serial']} (id {p['id']}) devolvio "
                            f'HTTP {estado}. Se detiene de inmediato sin corregir nada. '
                            f"Desactivaciones ya emitidas: {ev['desactivacionesEmitidas']}.")
            ev['fin'] = ahora()
            guardar(ev)
            raise SystemExit(ev['motivo'])

    # --- POSTCHECK de solo lectura ---------------------------------------------------
    inv_post = inventario()
    destinos_post = destinos_rf17(inv_post, tipo_por_id, ESPECIE)
    post_gw = {}
    for gid, serial in AUTORIZADOS:
        d = inv_post['dispositivos'].get(gid)
        post_gw[serial] = {'id_dispositivo_iot': gid, 'es_activo': (d or {}).get('es_activo'),
                           'conectividad': conectividad(gid)}

    nodo = next((v for v in inv_post['dispositivos'].values()
                 if v['serial'] == NODO_OBJETIVO), None)
    gw_obj_id = next((k for k, v in inv_post['dispositivos'].items()
                      if v['serial'] == GATEWAY_OBJETIVO), None)
    gw_obj = inv_post['dispositivos'].get(gw_obj_id)

    cambios = diferencias(inv_pre, inv_post)
    esperados = {str(gid) for gid, _ in AUTORIZADOS}
    cambios_dispositivos = set(cambios.get('dispositivos', {}))
    colaterales = {e: v for e, v in cambios.items() if e != 'dispositivos'}
    dispositivos_inesperados = cambios_dispositivos - esperados

    ev['postcheck'] = {
        'gatewaysSaneados': post_gw,
        'losCincoInactivos': all(v['es_activo'] is False for v in post_gw.values()),
        'destinosRf17Especie4': {'pre': destinos_pre, 'post': destinos_post},
        'unicoDestinoEsElObjetivo': destinos_post == [GATEWAY_OBJETIVO],
        'gatewayObjetivo': {'serial': GATEWAY_OBJETIVO, 'id': gw_obj_id,
                            'es_activo': (gw_obj or {}).get('es_activo'),
                            'conectividad': conectividad(gw_obj_id) if gw_obj_id else None},
        'nodoObjetivo': {'serial': NODO_OBJETIVO, 'detalle': nodo,
                         'sigueAsociadoAlGatewayObjetivo':
                             bool(nodo) and nodo['id_dispositivo_gateway'] == gw_obj_id,
                         'es_activo': (nodo or {}).get('es_activo')},
        'cambiosDetectados': cambios,
        'cambiosColateralesEnOtrasEntidades': colaterales,
        'dispositivosCambiadosNoAutorizados': sorted(dispositivos_inesperados),
        'conteos': {'pre': {k: len(v) for k, v in inv_pre.items()},
                    'post': {k: len(v) for k, v in inv_post.items()}},
        'timestamp': ahora(),
    }

    pc = ev['postcheck']
    edge_online = (pc['gatewayObjetivo']['conectividad'] or {}).get('clasificacion') == 'EDGE_ONLINE'
    todo_ok = (pc['losCincoInactivos'] and pc['unicoDestinoEsElObjetivo']
               and not colaterales and not dispositivos_inesperados
               and pc['nodoObjetivo']['sigueAsociadoAlGatewayObjetivo']
               and pc['gatewayObjetivo']['es_activo'] is True)

    ev['resultado'] = 'FIXTURE_G29_READY' if todo_ok else 'FIXTURE_G29_SANITIZATION_FAILED'
    ev['edgeObjetivoOnline'] = edge_online
    ev['siguientePaso'] = ('TC-M09-62 ejecutable: presentar el gate antes de escribir'
                           if todo_ok and edge_online else
                           'Edge objetivo no esta ONLINE: pedir a AIoT que reconecte la Raspberry'
                           if todo_ok else 'Revisar el postcheck: algo no coincide')
    ev['fin'] = ahora()
    guardar(ev)

    print(f"RESULTADO: {ev['resultado']}")
    print(f"  desactivaciones emitidas: {ev['desactivacionesEmitidas']}")
    print(f"  los cinco inactivos: {pc['losCincoInactivos']}")
    print(f"  destinos RF-17 especie 4: {destinos_pre} -> {destinos_post}")
    print(f"  unico destino = {GATEWAY_OBJETIVO}: {pc['unicoDestinoEsElObjetivo']}")
    print(f"  cambios colaterales en otras entidades: {colaterales or 'ninguno'}")
    print(f"  dispositivos cambiados no autorizados: {sorted(dispositivos_inesperados) or 'ninguno'}")
    print(f"  {NODO_OBJETIVO} sigue bajo {GATEWAY_OBJETIVO}: "
          f"{pc['nodoObjetivo']['sigueAsociadoAlGatewayObjetivo']}")
    print(f"  Edge objetivo ONLINE: {edge_online}")
    print(f"Evidencia: {OUT / 'saneamiento-fixture.json'}")


if __name__ == '__main__':
    main()
