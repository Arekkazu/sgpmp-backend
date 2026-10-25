"""TC-M09-G29 V5 - PREFLIGHT FINAL de seleccion del umbral para TC-M09-62 (SOLO LECTURA).

Selecciona el umbral de la especie 4 sobre el que se ejecutara la unica
escritura oficial de TC-M09-62 en TEST, captura su PRE completo y revalida el
estado del Edge destino. No emite ninguna escritura.

Criterio de seleccion: ademas de ser modificable por el endpoint oficial, el
PRE debe poder restaurarse. Varias filas heredadas tienen valor_max por encima
del limite fisico de su variable y niveles que no cubren [valor_min, valor_max];
restaurarlas seria rechazado hoy por ``_validar_rangos`` (RANGO_FISICO_INVALIDO
/ SOLAPAMIENTO_NIVELES), asi que no son reutilizables aunque se puedan editar.

Uso: RUN_ID=... TEST_ADMIN_PASSWORD=... python preflight_tc62_test_v5.py
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
BROKER = 'https://api.inmero.co/broker-sigab-test'
ACTOR = 'administador.dev@gmail.com'
ESPECIE = 4
GATEWAY_OBJETIVO = 'SERBY-TAX-FIRMWARE'
NODO_OBJETIVO = 'TEST-AMBIENTAL'

MUERTOS = {'INACTIVO', 'CERRADO', 'BAJA'}
SENSIBLES = ('password', 'contrasena', 'token', 'secret', 'usuario_mqtt', 'clave')
# Desplazamientos candidatos para la Configuracion A, en orden de preferencia.
DELTAS = ('0.30', '-0.30', '0.10', '-0.10')

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


def http(metodo: str, ruta: str, cuerpo: dict | None = None, base: str = BASE):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    pet = urllib.request.Request(base + ruta, data=datos, method=metodo)
    if datos:
        pet.add_header('Content-Type', 'application/json')
    if _token and base == BASE:
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


def dec(x) -> Decimal:
    return Decimal(str(x))


def restaurable(u: dict, var: dict) -> tuple[bool, list[str]]:
    """El PRE pasaria hoy _validar_rangos? Condicion necesaria para poder revertir."""
    motivos: list[str] = []
    if not var:
        return False, ['variable ambiental no encontrada en el catalogo']
    vmin, vmax = dec(u['valor_min']), dec(u['valor_max'])
    if vmin < dec(var['valor_fisico_min']) or vmax > dec(var['valor_fisico_max']):
        motivos.append(f"PRE fuera del rango fisico [{var['valor_fisico_min']}, "
                       f"{var['valor_fisico_max']}]")
    niveles = u.get('niveles') or []
    if not niveles:
        return False, motivos + ['PRE sin niveles']
    orden = sorted(niveles, key=lambda n: dec(n['limite_inferior']))
    if dec(orden[0]['limite_inferior']) != vmin:
        motivos.append('el primer nivel no comienza en valor_min')
    if dec(orden[-1]['limite_superior']) != vmax:
        motivos.append('el ultimo nivel no termina en valor_max')
    for a, b in zip(orden, orden[1:]):
        if dec(a['limite_superior']) != dec(b['limite_inferior']):
            motivos.append('niveles no contiguos')
            break
    return not motivos, motivos


def construir_a(pre: dict, var: dict) -> dict | None:
    """Configuracion A: el PRE desplazado en bloque. Conserva contigüidad y
    cobertura, cambia todas las fronteras y se mantiene dentro del rango fisico."""
    pmin, pmax = dec(var['valor_fisico_min']), dec(var['valor_fisico_max'])
    orden = sorted(pre['niveles'], key=lambda n: dec(n['limite_inferior']))
    for d in DELTAS:
        delta = dec(d)
        nmin, nmax = dec(pre['valor_min']) + delta, dec(pre['valor_max']) + delta
        if nmin < pmin or nmax > pmax:
            continue
        return {
            'valor_min': f'{nmin:.2f}', 'valor_max': f'{nmax:.2f}',
            'niveles': [{'nivel': n['nivel'],
                         'limite_inferior': f"{dec(n['limite_inferior']) + delta:.2f}",
                         'limite_superior': f"{dec(n['limite_superior']) + delta:.2f}"}
                        for n in orden],
            'deltaAplicado': f'{delta:+.2f}',
        }
    return None


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

    ev: dict = {'runId': RUN_ID, 'caso': 'TC-M09-62', 'version': 'V5', 'ambiente': 'TEST',
                'escriturasOficialesRealizadas': 0, 'inicio': ahora()}

    _, yo = http('GET', '/usuarios/me')
    _, permisos = http('GET', '/sesiones/me/permisos')
    acc20 = sorted({p['id_accion'] for p in (permisos or {}).get('permisos', [])
                    if p.get('id_recurso') == 20})
    ev['actor'] = {'correo': ACTOR, 'tokenPersistido': False,
                   'identidad': {k: (yo or {}).get(k) for k in
                                 ('id_usuario', 'nombre', 'apellidos', 'nombre_rol',
                                  'estado_cuenta')},
                   'permisosRecurso20_umbralesAmbientales': acc20,
                   'puedeEjecutarRf17': {1, 2, 3}.issubset(set(acc20))}

    # --- 1. Umbrales existentes de la especie 4 -------------------------------------
    _, variables = http('GET', '/configuracion/variables-ambientales')
    var_por_id = {v['id_variable_ambiental']: v for v in (variables or {}).get('items', [])}
    _, lista = http('GET', f'/configuracion/umbrales?id_especie={ESPECIE}')
    umbrales = [u for u in (lista or {}).get('items', []) if u.get('es_activo')]

    # --- 2-3. Seleccion: reutilizar, nunca crear si hay uno reutilizable ------------
    candidatos = []
    for u in umbrales:
        var = var_por_id.get(u['id_variable_ambiental'], {})
        ok, motivos = restaurable(u, var)
        a = construir_a(u, var) if ok else None
        candidatos.append({
            'id_umbral_ambiental': u['id_umbral_ambiental'],
            'variable': {'id': u['id_variable_ambiental'], 'nombre': var.get('nombre'),
                         'unidad': var.get('unidad'),
                         'rangoFisico': [var.get('valor_fisico_min'),
                                         var.get('valor_fisico_max')]},
            'valor_min': u['valor_min'], 'valor_max': u['valor_max'],
            'preRestaurable': ok, 'motivosNoRestaurable': motivos,
            'configuracionAPosible': a is not None,
        })
    aptos = [c for c in candidatos if c['preRestaurable'] and c['configuracionAPosible']]
    ev['candidatos'] = candidatos
    ev['seleccion'] = {
        'criterio': ('umbral existente, editable por endpoint oficial, con PRE que hoy pasaria '
                     '_validar_rangos (restaurable) y Configuracion A construible dentro del '
                     'rango fisico'),
        'reutilizaUmbralExistente': bool(aptos),
        'noSeCrearaUmbralNuevo': True,
        'aptos': [c['id_umbral_ambiental'] for c in aptos],
    }
    if not aptos:
        ev['gate'] = {'abierto': False, 'causa': 'Ningun umbral de la especie 4 es reutilizable'}
        ev['fin'] = ahora()
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / 'preflight-tc62-test.json').write_text(
            json.dumps(ev, indent=2, ensure_ascii=False), encoding='utf-8')
        raise SystemExit('Sin umbral reutilizable: no se abre el gate.')

    elegido_id = aptos[0]['id_umbral_ambiental']
    pre = next(u for u in umbrales if u['id_umbral_ambiental'] == elegido_id)
    var = var_por_id[pre['id_variable_ambiental']]

    # --- 4. PRE completo -------------------------------------------------------------
    _, auditoria = http('GET', f'/configuracion/umbrales/{elegido_id}/auditoria')
    ev['pre'] = {
        'id_umbral_ambiental': pre['id_umbral_ambiental'],
        'id_especie': pre['id_especie'],
        'variable': {'id': var['id_variable_ambiental'], 'nombre': var['nombre'],
                     'unidad': var['unidad'],
                     'rangoFisico': [var['valor_fisico_min'], var['valor_fisico_max']]},
        'unidad_medida': pre['unidad_medida'],
        'valor_min': pre['valor_min'], 'valor_max': pre['valor_max'],
        'niveles': pre['niveles'],
        'es_activo': pre['es_activo'],
        'estado_sincronizacion': pre['estado_sincronizacion'],
        'fecha_ultima_sincronizacion': pre['fecha_ultima_sincronizacion'],
        'motivo_fallo_sincronizacion': pre['motivo_fallo_sincronizacion'],
        'fecha_actualizacion': pre['fecha_actualizacion'],
        'auditoria': auditoria,
        'cuerpoDeRestauracionExacto': {
            'valor_min': pre['valor_min'], 'valor_max': pre['valor_max'],
            'niveles': [{'nivel': n['nivel'], 'limite_inferior': n['limite_inferior'],
                         'limite_superior': n['limite_superior']} for n in pre['niveles']],
        },
        'capturadoEn': ahora(),
    }

    # --- 6. Configuracion A ----------------------------------------------------------
    ev['configuracionA'] = construir_a(pre, var)

    # --- 5. Revalidacion inmediata del destino y del Edge ---------------------------
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

    ar = {k for k, v in areas.items() if v.get('es_activo') and v.get('especie_id') == ESPECIE}
    ar |= {r['id_infraestructura'] for r in activos
           if r.get('id_especie') == ESPECIE
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

    gw = next((d for d in dispositivos if d['serial'] == GATEWAY_OBJETIVO), None)
    nodo = next((d for d in dispositivos if d['serial'] == NODO_OBJETIVO), None)
    gid = (gw or {}).get('id_dispositivo_iot')
    _, cred = http('GET', f'/configuracion/dispositivos-iot/{gid}/credencial-mqtt') if gid else (None, {})
    _, estado = http('GET', f'/iot/dispositivos/{gid}/estado') if gid else (None, {})
    bloque = (estado or {}).get('estado') if isinstance(estado, dict) else {}
    conectada = (cred or {}).get('conectada') if isinstance(cred, dict) else None

    ev['destino'] = {
        'destinosRf17Especie4': destinos,
        'cantidad': len(destinos),
        'unicoYEsElObjetivo': destinos == [GATEWAY_OBJETIVO],
        'gateway': {'serial': GATEWAY_OBJETIVO, 'id': gid,
                    'es_activo': (gw or {}).get('es_activo'),
                    'id_infraestructura': (gw or {}).get('id_infraestructura'),
                    'area': areas.get((gw or {}).get('id_infraestructura'), {}).get('nombre_infraestructura')},
        'nodo': {'serial': NODO_OBJETIVO, 'id': (nodo or {}).get('id_dispositivo_iot'),
                 'es_activo': (nodo or {}).get('es_activo'),
                 'sigueAsociado': bool(nodo) and nodo.get('id_dispositivo_gateway') == gid},
        'conectividad': {'credencialMqtt': limpio(cred if isinstance(cred, dict) else {}),
                         'heartbeat': limpio(bloque if isinstance(bloque, dict) else {}),
                         'conectada': conectada,
                         'clasificacion': ('EDGE_ONLINE' if conectada is True else
                                           'EDGE_OFFLINE' if conectada is False
                                           else 'EDGE_NO_VERIFICABLE')},
        'timestamp': ahora(),
    }

    # --- Endpoint e integracion ------------------------------------------------------
    _, openapi = http('GET', '/openapi.json')
    rutas = (openapi or {}).get('paths', {})
    ruta_patch = '/configuracion/umbrales/{id_umbral_ambiental}'
    op = rutas.get(ruta_patch, {}).get('patch', {})
    est_broker, _ = http('GET', '/health', base=BROKER)
    ev['endpoint'] = {
        'metodo': 'PATCH', 'ruta': ruta_patch,
        'disponibleEnOpenapi': bool(op),
        'respuestasDeclaradas': sorted(op.get('responses', {})),
        'declara500Sincronizacion': '500' in op.get('responses', {}),
        'descripcion500': op.get('responses', {}).get('500', {}).get('description'),
    }
    ev['integracionBroker'] = {
        'brokerUrl': BROKER,
        'healthHttp': est_broker,
        'evidenciaDeIntegracionViva': ('el backend reporta conectada=True para el Gateway '
                                       'objetivo; ese dato proviene del broker, de modo que la '
                                       'cadena backend->broker->Edge esta activa'),
        'gatewayReportadoPorElBroker': conectada is True,
        'credencialEmitidaYHabilitada': bool((cred or {}).get('emitida')) and bool((cred or {}).get('habilitada')),
    }

    # --- Gate -------------------------------------------------------------------------
    hb = bloque or {}
    cond = {
        'actorValido': ev['actor']['puedeEjecutarRf17'],
        'umbralReutilizableSeleccionado': True,
        'preCompletoYRestaurable': True,
        'configuracionAConstruida': ev['configuracionA'] is not None,
        'configuracionADistintaDelPre': (ev['configuracionA'] or {}).get('valor_min') != pre['valor_min'],
        'endpointOficialDisponible': bool(op),
        'endpointDeclara500Sincronizacion': '500' in op.get('responses', {}),
        'unicoDestinoRf17EsElObjetivo': destinos == [GATEWAY_OBJETIVO],
        'edgeOnline': conectada is True,
        'heartbeatReciente': isinstance(hb.get('tiempo_sin_contacto'), int)
                             and hb['tiempo_sin_contacto'] < 300,
        'nodoObjetivoAsociado': bool(nodo) and nodo.get('id_dispositivo_gateway') == gid,
        'integracionBrokerVerificable': conectada is True,
    }
    ev['gate'] = {'condiciones': cond, 'abierto': all(cond.values()),
                  'fallidas': [k for k, v in cond.items() if not v]}
    ev['fin'] = ahora()

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'preflight-tc62-test.json').write_text(
        json.dumps(ev, indent=2, ensure_ascii=False), encoding='utf-8')

    print('GATE_TC_M09_62_READY' if ev['gate']['abierto'] else 'GATE CERRADO')
    print(f"  umbral: {elegido_id} · {var['nombre']} ({var['unidad']})")
    print(f"  PRE: {pre['valor_min']}–{pre['valor_max']} · "
          f"sync={pre['estado_sincronizacion']} · fecha_act={pre['fecha_actualizacion']}")
    print(f"  niveles PRE: {[(n['nivel'], n['limite_inferior'], n['limite_superior']) for n in pre['niveles']]}")
    a = ev['configuracionA']
    print(f"  A: {a['valor_min']}–{a['valor_max']} (delta {a['deltaAplicado']})")
    print(f"  niveles A: {[(n['nivel'], n['limite_inferior'], n['limite_superior']) for n in a['niveles']]}")
    print(f"  destinos RF-17: {destinos} · Edge={ev['destino']['conectividad']['clasificacion']} "
          f"· sin_contacto={hb.get('tiempo_sin_contacto')}s")
    print(f"  fallidas: {ev['gate']['fallidas'] or 'ninguna'}")
    print(f"Evidencia: {OUT / 'preflight-tc62-test.json'}")


if __name__ == '__main__':
    main()
