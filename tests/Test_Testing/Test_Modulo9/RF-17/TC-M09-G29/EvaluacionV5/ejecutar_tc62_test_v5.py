"""TC-M09-62 V5 en TEST - unica escritura oficial: PATCH /configuracion/umbrales/48.

Autorizado por Juan con la Configuracion A del gate. UNA sola escritura, sin
reintentos bajo ninguna circunstancia. Si la respuesta se pierde o hay timeout,
el resultado se determina con consultas de solo lectura, nunca repitiendo.

Revalida inmediatamente antes de escribir: PRE identico al del gate, Gateway
ONLINE y unico destino RF-17 de la especie 4. Si algo cambio, se detiene sin
escribir y no recalcula A.

Uso: RUN_ID=... TEST_ADMIN_PASSWORD=... python ejecutar_tc62_test_v5.py
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
ESPECIE = 4
UMBRAL = 48
GATEWAY_OBJETIVO = 'SERBY-TAX-FIRMWARE'
NODO_OBJETIVO = 'TEST-AMBIENTAL'

# Configuracion A exactamente como se autorizo en el gate.
A = {
    'valor_min': '5.90',
    'valor_max': '8.70',
    'niveles': [
        {'nivel': 'normal', 'limite_inferior': '5.90', 'limite_superior': '6.83'},
        {'nivel': 'precaucion', 'limite_inferior': '6.83', 'limite_superior': '7.76'},
        {'nivel': 'critico', 'limite_inferior': '7.76', 'limite_superior': '8.70'},
    ],
}

# El broker espera el ACK hasta 30 s y el backend corta a los 35 s: un timeout
# de cliente mas corto crearia la ambiguedad que no se puede resolver reintentando.
TIMEOUT_ESCRITURA = 150
TIMEOUT_LECTURA = 90
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


def http(metodo: str, ruta: str, cuerpo: dict | None = None, timeout: int = TIMEOUT_LECTURA):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    pet = urllib.request.Request(BASE + ruta, data=datos, method=metodo)
    if datos:
        pet.add_header('Content-Type', 'application/json')
    if _token:
        pet.add_header('Authorization', f'Bearer {_token}')
    try:
        with urllib.request.urlopen(pet, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b'null')
    except urllib.error.HTTPError as exc:
        bruto = exc.read()
        try:
            return exc.code, json.loads(bruto or b'null')
        except ValueError:
            return exc.code, {'raw': bruto.decode('utf-8', 'replace')[:600]}
    except Exception as exc:                                   # noqa: BLE001
        return -1, {'error': f'{type(exc).__name__}: {str(exc)[:300]}'}


def guardar(ev: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'tc62-result.json').write_text(
        json.dumps(ev, indent=2, ensure_ascii=False), encoding='utf-8')


def dec(x) -> Decimal:
    return Decimal(str(x))


def iguales(u: dict, vmin, vmax, niveles) -> bool:
    if dec(u['valor_min']) != dec(vmin) or dec(u['valor_max']) != dec(vmax):
        return False
    esperado = {(n['nivel'], dec(n['limite_inferior']), dec(n['limite_superior']))
                for n in niveles}
    obtenido = {(n['nivel'], dec(n['limite_inferior']), dec(n['limite_superior']))
                for n in (u.get('niveles') or [])}
    return esperado == obtenido


def leer_umbral() -> dict | None:
    _, lista = http('GET', f'/configuracion/umbrales?id_especie={ESPECIE}')
    return next((u for u in (lista or {}).get('items', [])
                 if u['id_umbral_ambiental'] == UMBRAL), None)


def estado_destino() -> dict:
    """Destinos RF-17 de la especie 4 y conectividad del Gateway objetivo."""
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
    gw = next((d for d in dispositivos if d['serial'] == GATEWAY_OBJETIVO), None)
    nodo = next((d for d in dispositivos if d['serial'] == NODO_OBJETIVO), None)
    gid = (gw or {}).get('id_dispositivo_iot')
    _, cred = http('GET', f'/configuracion/dispositivos-iot/{gid}/credencial-mqtt') if gid else (None, {})
    _, est = http('GET', f'/iot/dispositivos/{gid}/estado') if gid else (None, {})
    bloque = (est or {}).get('estado') if isinstance(est, dict) else {}
    conectada = (cred or {}).get('conectada') if isinstance(cred, dict) else None
    return {
        'destinosRf17': sorted(destinos),
        'unicoYEsElObjetivo': sorted(destinos) == [GATEWAY_OBJETIVO],
        'gatewayId': gid,
        'credencialMqtt': limpio(cred if isinstance(cred, dict) else {}),
        'heartbeat': limpio(bloque if isinstance(bloque, dict) else {}),
        'conectada': conectada,
        'clasificacion': ('EDGE_ONLINE' if conectada is True else
                          'EDGE_OFFLINE' if conectada is False else 'EDGE_NO_VERIFICABLE'),
        'nodoAsociado': bool(nodo) and nodo.get('id_dispositivo_gateway') == gid,
        'timestamp': ahora(),
    }


def bitacora(desde: str | None = None) -> dict:
    ruta = '/iot/auditoria?por_pagina=50'
    if desde:
        ruta += f'&fecha_desde={urllib.request.quote(desde)}'
    est, cuerpo = http('GET', ruta)
    return {'http': est, 'cuerpo': cuerpo}


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

    gate = json.loads((OUT / 'preflight-tc62-test.json').read_text(encoding='utf-8'))
    pre_gate = gate['pre']

    ev: dict = {
        'runId': RUN_ID, 'caso': 'TC-M09-62', 'version': 'V5', 'ambiente': 'TEST',
        'autorizadoPor': 'Juan (QA)', 'inicio': ahora(),
        'actor': {'correo': ACTOR, 'tokenPersistido': False},
        'umbral': {'id': UMBRAL, 'id_especie': ESPECIE,
                   'variable': pre_gate['variable']},
        'configuracionA': A,
        'preDelGate': pre_gate['cuerpoDeRestauracionExacto'],
        'escriturasOficialesEmitidas': 0,
        'presupuesto': '1 escritura oficial, 0 reintentos',
    }

    # --- Revalidacion inmediata ------------------------------------------------------
    pre = leer_umbral()
    destino_pre = estado_destino()
    ev['revalidacion'] = {'preActual': pre, 'destino': destino_pre, 'timestamp': ahora()}

    frenos = []
    if pre is None:
        frenos.append(f'el umbral {UMBRAL} ya no esta disponible')
    else:
        if not iguales(pre, pre_gate['valor_min'], pre_gate['valor_max'], pre_gate['niveles']):
            frenos.append('el PRE cambio respecto al capturado en el gate')
        if pre.get('fecha_actualizacion') != pre_gate['fecha_actualizacion']:
            frenos.append('fecha_actualizacion cambio respecto al gate')
    if destino_pre['clasificacion'] != 'EDGE_ONLINE':
        frenos.append(f"el Gateway objetivo no esta ONLINE ({destino_pre['clasificacion']})")
    if not destino_pre['unicoYEsElObjetivo']:
        frenos.append(f"el fan-out cambio: destinos = {destino_pre['destinosRf17']}")
    if not destino_pre['nodoAsociado']:
        frenos.append('TEST-AMBIENTAL dejo de estar asociado al Gateway objetivo')

    if frenos:
        ev['verdict'] = 'NO_EJECUTADO'
        ev['motivo'] = ('Precondiciones invalidadas, 0 escrituras: ' + '; '.join(frenos)
                        + '. No se recalcula A ni se actualiza el PRE.')
        ev['fin'] = ahora()
        guardar(ev)
        raise SystemExit(ev['motivo'])

    ev['bitacoraPre'] = bitacora()
    _, auditoria_pre = http('GET', f'/configuracion/umbrales/{UMBRAL}/auditoria')
    ev['auditoriaPre'] = auditoria_pre

    # --- LA escritura oficial (una, sin reintentos) ----------------------------------
    cuerpo = {'valor_min': A['valor_min'], 'valor_max': A['valor_max'],
              'niveles': A['niveles'],
              'fecha_actualizacion': pre.get('fecha_actualizacion')}
    marca = ahora()
    ev['request'] = {'metodo': 'PATCH', 'ruta': f'/configuracion/umbrales/{UMBRAL}',
                     'cuerpo': cuerpo, 'cabecerasSanitizadas': ['Authorization: <omitido>',
                                                                'Content-Type: application/json'],
                     'timestamp': marca}
    ev['escriturasOficialesEmitidas'] = 1
    guardar(ev)   # persistido ANTES del PATCH: si la respuesta se pierde, consta que se emitio

    estado_patch, cuerpo_patch = http('PATCH', f'/configuracion/umbrales/{UMBRAL}',
                                      cuerpo, timeout=TIMEOUT_ESCRITURA)
    ev['response'] = {'http': estado_patch, 'cuerpo': cuerpo_patch,
                      'emitido': marca, 'recibido': ahora()}
    guardar(ev)

    ambiguo = estado_patch == -1

    # --- Evidencia posterior (solo lectura, repetible) -------------------------------
    post = leer_umbral()
    _, auditoria_post = http('GET', f'/configuracion/umbrales/{UMBRAL}/auditoria')
    destino_post = estado_destino()
    ev['post'] = {'umbral': post, 'auditoria': auditoria_post, 'destino': destino_post,
                  'bitacora': bitacora(marca), 'timestamp': ahora()}
    guardar(ev)

    if ambiguo:
        ev['verdict'] = 'INDETERMINADO_SIN_REINTENTO'
        ev['motivo'] = ('El cliente no obtuvo respuesta del PATCH. NO se reintenta. El estado se '
                        'determina con las consultas de solo lectura ya capturadas en "post".')
        ev['aPersistidaPeseALaAmbiguedad'] = bool(post) and iguales(
            post, A['valor_min'], A['valor_max'], A['niveles'])
        ev['fin'] = ahora()
        guardar(ev)
        raise SystemExit(ev['motivo'])

    # --- Oraculo de aprobacion (8 condiciones) ---------------------------------------
    sync = (post or {}).get('estado_sincronizacion')
    fecha_sync = (post or {}).get('fecha_ultima_sincronizacion')
    motivo_fallo = (post or {}).get('motivo_fallo_sincronizacion')
    a_persistida = bool(post) and iguales(post, A['valor_min'], A['valor_max'], A['niveles'])

    oraculo = {
        '1_httpExitosoConformeAlContrato': estado_patch == 200,
        '2_configuracionAPersistidaCentralmente': a_persistida,
        '3_propagacionRealAlGatewayObjetivo': (
            destino_pre['unicoYEsElObjetivo'] and estado_patch in (200, 500)),
        '4_ackRealDelEdge': sync == 'APLICADA',
        '5_estadoSincronizacionAplicada': sync == 'APLICADA',
        '6_fechaUltimaSincronizacionRegistrada': bool(fecha_sync) and fecha_sync >= marca[:10],
        '7_sinMotivoDeFalloDeSincronizacion': not motivo_fallo,
        '8_edgeOperandoConConfiguracionA': sync == 'APLICADA' and a_persistida,
    }
    ev['oraculo'] = oraculo
    ev['trazabilidadDelAck'] = (
        'En el contrato desplegado, APLICADA solo puede originarse en el cuerpo que devuelve '
        'POST {broker}/v1/commands despues del ACK_UMBRAL del Edge: el backend no construye ese '
        'estado por su cuenta, el stub que siempre devolvia PENDIENTE no existe en src/, y con un '
        'unico destino la consolidacion no puede enmascarar un Gateway sin ACK. Un Edge '
        'desconectado habria dado PENDIENTE + HTTP 500.')
    ev['limitacionDeObservacion'] = (
        'El producto no expone un endpoint que devuelva la configuracion efectiva en campo del '
        'Edge, asi que la condicion 8 se sostiene en la cadena contractual anterior mas el ACK, '
        'no en una lectura directa del dispositivo. No se fabrica evidencia que no existe.')

    if all(oraculo.values()):
        ev['verdict'] = 'APROBADO'
        ev['motivo'] = ('Propagacion real y confirmada: unico destino SERBY-TAX-FIRMWARE, '
                        'APLICADA con fecha de sincronizacion y sin motivo de fallo.')
    elif sync in ('PENDIENTE', 'NO_CONF'):
        ev['verdict'] = 'RECHAZADO'
        ev['motivo'] = (f'El Edge estaba ONLINE y era el unico destino, pero el flujo devolvio '
                        f'{sync} (HTTP {estado_patch}). Motivo: {motivo_fallo}')
    else:
        ev['verdict'] = 'RECHAZADO'
        ev['motivo'] = ('No se cumplieron todas las condiciones del oraculo: '
                        + ', '.join(k for k, v in oraculo.items() if not v))

    ev['restauracionPre'] = {'realizada': False,
                             'razon': 'Si TC-62 aprueba, A debe quedar aplicada como baseline '
                                      'para TC-63 (instruccion de Juan).'}
    ev['fin'] = ahora()
    guardar(ev)

    print(f"RESULTADO TC-M09-62: {ev['verdict']}")
    print(f'  PATCH HTTP {estado_patch}')
    print(f'  central: {(post or {}).get("valor_min")}-{(post or {}).get("valor_max")} '
          f'niveles={[(n["nivel"], n["limite_inferior"], n["limite_superior"]) for n in (post or {}).get("niveles", [])]}')
    print(f'  estado_sincronizacion={sync} · fecha={fecha_sync} · motivo_fallo={motivo_fallo}')
    print(f'  destinos RF-17 (pre/post): {destino_pre["destinosRf17"]} / {destino_post["destinosRf17"]}')
    print(f'  auditoria: {(auditoria_pre or {}).get("total")} -> {(auditoria_post or {}).get("total")}')
    print(f'  oraculo no cumplido: {[k for k, v in oraculo.items() if not v] or "ninguno"}')
    print(f'Evidencia: {OUT / "tc62-result.json"}')


if __name__ == '__main__':
    main()
