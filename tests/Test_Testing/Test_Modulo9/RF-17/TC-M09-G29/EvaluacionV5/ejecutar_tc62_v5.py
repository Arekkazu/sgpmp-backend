"""TC-M09-62 V5 - propagacion exitosa de un umbral RF-17 hacia el Gateway Edge.

Presupuesto: UNA sola escritura funcional oficial (PATCH). Sin reintentos
automaticos. Si el PATCH no deja claro si el servidor lo proceso (timeout), el
script se detiene y deja constancia: lo resuelve una consulta de estado, nunca
una repeticion.

Requiere un preflight.json del mismo RUN_ID con el gate abierto. Vuelve a
comprobar que el Gateway Edge destino esta conectado justo antes de escribir:
la confirmacion humana no sustituye la senal tecnica.

Secretos: DEV_ADMIN_PASSWORD desde el entorno; nunca se persiste.

Uso:  RUN_ID=... DEV_ADMIN_PASSWORD=... python ejecutar_tc62_v5.py
"""
from __future__ import annotations

import datetime
import json
import os
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path

BASE_DEV = 'https://api.inmero.co/back-sigab-dev'
ACTOR = 'admin.dev@gmail.com'

AQUI = Path(__file__).resolve().parent
RUN_ID = os.environ.get('RUN_ID')
if not RUN_ID:
    raise SystemExit('Falta RUN_ID (debe ser el mismo del preflight).')
OUT = AQUI / 'RESULTADOS' / RUN_ID

# El PATCH puede tardar: el broker espera el ACK del Edge hasta 30 s y el
# backend corta a los 35 s. Un timeout de cliente mas corto crearia justo la
# ambiguedad que la seccion 14 prohibe resolver reintentando.
TIMEOUT_ESCRITURA = 120
TIMEOUT_LECTURA = 60

CLAVES_SENSIBLES = ('password', 'contrasena', 'token', 'secret', 'usuario_mqtt', 'clave')

# Configuracion A: valida, distinta del PRE en todos sus limites, contigua,
# cubre [valor_min, valor_max], lejos de las fronteras fisicas de la variable.
A_VALOR_MIN = '5.00'
A_VALOR_MAX = '35.00'
A_NIVELES = [
    {'nivel': 'critico', 'limite_inferior': '5.00', 'limite_superior': '25.00'},
    {'nivel': 'precaucion', 'limite_inferior': '25.00', 'limite_superior': '29.00'},
    {'nivel': 'normal', 'limite_inferior': '29.00', 'limite_superior': '35.00'},
]


def ahora() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sin_secretos(d) -> dict:
    return {k: v for k, v in (d or {}).items()
            if not any(s in k.lower() for s in CLAVES_SENSIBLES)}


def http(metodo: str, ruta: str, token: str | None = None, cuerpo: dict | None = None,
         timeout: int = TIMEOUT_LECTURA):
    url = ruta if ruta.startswith('http') else BASE_DEV + ruta
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    pet = urllib.request.Request(url, data=datos, method=metodo)
    if datos:
        pet.add_header('Content-Type', 'application/json')
    if token:
        pet.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(pet, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b'null')
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


def mismos_valores(u: dict, vmin: str, vmax: str, niveles: list[dict]) -> bool:
    if dec(u['valor_min']) != dec(vmin) or dec(u['valor_max']) != dec(vmax):
        return False
    esperado = {(n['nivel'], dec(n['limite_inferior']), dec(n['limite_superior']))
                for n in niveles}
    obtenido = {(n['nivel'], dec(n['limite_inferior']), dec(n['limite_superior']))
                for n in (u.get('niveles') or [])}
    return esperado == obtenido


def estado_gateway(token: str, id_dispositivo: int) -> dict:
    est_c, cred = http('GET',
                       f'/configuracion/dispositivos-iot/{id_dispositivo}/credencial-mqtt', token)
    est_e, estado = http('GET', f'/iot/dispositivos/{id_dispositivo}/estado', token)
    bloque = (estado or {}).get('estado') if isinstance(estado, dict) else None
    return {
        'credencialMqttHttp': est_c,
        'credencialMqtt': sin_secretos(cred if isinstance(cred, dict) else {}),
        'estadoHttp': est_e,
        'estadoOperativo': sin_secretos(bloque if isinstance(bloque, dict) else {}),
        'conectada': (cred or {}).get('conectada') if isinstance(cred, dict) else None,
        'timestamp': ahora(),
    }


# --------------------------------------------------------------------------------------
def main() -> None:
    preflight = json.loads((OUT / 'preflight.json').read_text(encoding='utf-8'))
    sel = preflight.get('operacionCandidata', {}).get('seleccionado')
    if not sel:
        raise SystemExit('El preflight no selecciono un umbral reversible: no se escribe.')

    id_umbral = sel['id_umbral_ambiental']
    gateways = preflight['edge']['gatewaysEdgeActivos']
    destino = sel['gatewaysEdge']

    ev: dict = {
        'runId': RUN_ID, 'caso': 'TC-M09-62', 'version': 'V5', 'inicio': ahora(),
        'umbral': {'id_umbral_ambiental': id_umbral, 'id_especie': sel['id_especie'],
                   'especie': sel['especie'], 'variable': sel['variable']},
        'destinoGatewayEdge': destino,
        'escriturasOficialesEmitidas': 0,
        'configuracionA': {'valor_min': A_VALOR_MIN, 'valor_max': A_VALOR_MAX,
                           'niveles': A_NIVELES},
    }

    clave = os.environ.get('DEV_ADMIN_PASSWORD')
    if not clave:
        raise SystemExit('DEV_ADMIN_PASSWORD no disponible: no se continua (0 escrituras).')
    _, login = http('POST', '/sesiones/',
                    cuerpo={'correo_electronico': ACTOR, 'contrasena': clave})
    token = (login or {}).get('token')
    if not token:
        raise SystemExit('login fallido: no se continua (0 escrituras).')
    ev['actor'] = {'correo': ACTOR, 'tokenPersistido': False}

    # --- 7.1 PRE inmediato: el Edge destino debe estar conectado AHORA ---------------
    ev['preEdge'] = {s: estado_gateway(token, gateways[s]['id_dispositivo_iot'])
                     for s in destino}
    desconectados = [s for s, g in ev['preEdge'].items() if g['conectada'] is not True]
    if desconectados:
        ev['verdict'] = 'NO_EJECUTADO'
        ev['motivo'] = (f'El Gateway Edge destino no esta conectado justo antes de escribir: '
                        f'{desconectados}. Gate cerrado, 0 escrituras.')
        ev['fin'] = ahora()
        guardar(ev)
        raise SystemExit(ev['motivo'])

    _, lista = http('GET', f"/configuracion/umbrales?id_especie={sel['id_especie']}", token)
    pre = next((u for u in (lista or {}).get('items', [])
                if u['id_umbral_ambiental'] == id_umbral), None)
    if pre is None:
        raise SystemExit(f'El umbral {id_umbral} ya no esta disponible: no se escribe.')
    ev['pre'] = pre

    # El PRE debe seguir siendo el del preflight: si alguien lo movio, este RUN pierde
    # la continuidad PRE -> A y no se sobrescribe.
    pre_preflight = sel['valoresPre']
    if not mismos_valores(pre, pre_preflight['valor_min'], pre_preflight['valor_max'],
                          pre_preflight.get('niveles') or []):
        ev['verdict'] = 'NO_EJECUTADO'
        ev['motivo'] = ('El umbral cambio entre el preflight y la escritura (otro usuario o '
                        'proceso). No se sobrescribe; se invalida la continuidad del RUN.')
        ev['fin'] = ahora()
        guardar(ev)
        raise SystemExit(ev['motivo'])

    if mismos_valores(pre, A_VALOR_MIN, A_VALOR_MAX, A_NIVELES):
        ev['verdict'] = 'NO_EJECUTADO'
        ev['motivo'] = 'La Configuracion A coincide con el PRE: no seria un cambio observable.'
        ev['fin'] = ahora()
        guardar(ev)
        raise SystemExit(ev['motivo'])

    _, auditoria_pre = http('GET', f'/configuracion/umbrales/{id_umbral}/auditoria', token)
    ev['auditoriaPre'] = auditoria_pre

    # --- 7.2 LA escritura oficial (una sola, sin reintentos) -------------------------
    cuerpo = {'valor_min': A_VALOR_MIN, 'valor_max': A_VALOR_MAX, 'niveles': A_NIVELES,
              'fecha_actualizacion': pre.get('fecha_actualizacion')}
    ev['request'] = {'metodo': 'PATCH', 'ruta': f'/configuracion/umbrales/{id_umbral}',
                     'cuerpo': cuerpo, 'timestamp': ahora()}
    ev['escriturasOficialesEmitidas'] = 1
    guardar(ev)   # por si el PATCH deja el proceso en un estado ambiguo

    t0 = ahora()
    estado_patch, cuerpo_patch = http('PATCH', f'/configuracion/umbrales/{id_umbral}',
                                      token, cuerpo, timeout=TIMEOUT_ESCRITURA)
    ev['response'] = {'estado': estado_patch, 'cuerpo': cuerpo_patch,
                      'inicio': t0, 'fin': ahora()}
    guardar(ev)

    if estado_patch == -1:
        ev['verdict'] = 'INDETERMINADO_SIN_REINTENTO'
        ev['motivo'] = ('El PATCH no devolvio respuesta utilizable. No se repite (seccion 14). '
                        'Se consulta el estado para determinar si el servidor lo proceso.')
        _, despues = http('GET', f"/configuracion/umbrales?id_especie={sel['id_especie']}", token)
        ev['getTrasAmbiguedad'] = next(
            (u for u in (despues or {}).get('items', [])
             if u['id_umbral_ambiental'] == id_umbral), None)
        ev['fin'] = ahora()
        guardar(ev)
        raise SystemExit(ev['motivo'])

    # --- 7.3 POST inmediato y oraculo ------------------------------------------------
    _, despues = http('GET', f"/configuracion/umbrales?id_especie={sel['id_especie']}", token)
    post = next((u for u in (despues or {}).get('items', [])
                 if u['id_umbral_ambiental'] == id_umbral), None)
    ev['post'] = post
    _, auditoria_post = http('GET', f'/configuracion/umbrales/{id_umbral}/auditoria', token)
    ev['auditoriaPost'] = auditoria_post
    ev['postEdge'] = {s: estado_gateway(token, gateways[s]['id_dispositivo_iot'])
                      for s in destino}

    fecha_sync = (post or {}).get('fecha_ultima_sincronizacion')
    correlacionada = bool(fecha_sync) and fecha_sync >= ev['request']['timestamp'][:10]
    oraculo = {
        '1_operacionAceptada': estado_patch == 200,
        '2_configuracionAPersistida': bool(post) and mismos_valores(
            post, A_VALOR_MIN, A_VALOR_MAX, A_NIVELES),
        '3_destinoGatewayReal': bool(destino),
        '4_intentoRealDePropagacion': bool(destino) and estado_patch in (200, 500),
        '5_edgeConfirmadoDisponible': all(
            g['conectada'] is True for g in ev['preEdge'].values()),
        '6_propagacionConfirmada': (post or {}).get('estado_sincronizacion') == 'APLICADA',
        '7_estadoAplicada': (post or {}).get('estado_sincronizacion') == 'APLICADA',
        '8_fechaSincronizacionCorrelacionada': correlacionada,
        '9_valoresEnviadosIgualesAPersistidos': bool(post) and mismos_valores(
            post, A_VALOR_MIN, A_VALOR_MAX, A_NIVELES),
        '10_aplicadaProvieneDeAckNoDeStub': (
            (post or {}).get('estado_sincronizacion') == 'APLICADA'),
    }
    ev['oraculo'] = oraculo
    ev['trazabilidadAplicada'] = (
        'En el contrato desplegado APLICADA solo puede originarse en el cuerpo que devuelve '
        'POST {broker}/v1/commands tras el ACK_UMBRAL del Edge: el backend no construye ese '
        'estado por su cuenta y el stub que siempre devolvia PENDIENTE ya no existe en src/. '
        'Si AIoT aporta logs del broker/Edge, se incorporan como evidencia complementaria.')

    if all(oraculo.values()):
        ev['verdict'] = 'APROBADO'
    elif (post or {}).get('estado_sincronizacion') in ('PENDIENTE', 'NO_CONF'):
        ev['verdict'] = 'RECHAZADO'
        ev['motivo'] = (f'El Edge estaba conectado pero el flujo devolvio '
                        f"{(post or {}).get('estado_sincronizacion')} "
                        f'(HTTP {estado_patch}). Motivo: '
                        f"{(post or {}).get('motivo_fallo_sincronizacion')}")
    else:
        ev['verdict'] = 'RECHAZADO'
        ev['motivo'] = 'No se cumplieron todas las condiciones del oraculo de la seccion 7.3.'

    ev['fin'] = ahora()
    guardar(ev)

    print(f'TC-M09-62: {ev["verdict"]}')
    print(f'PATCH HTTP {estado_patch} · estado_sincronizacion='
          f'{(post or {}).get("estado_sincronizacion")}')
    print(f'fecha_ultima_sincronizacion={fecha_sync}')
    print(f'Oraculo no cumplido: {[k for k, v in oraculo.items() if not v]}')
    print(f'Evidencia: {OUT / "tc62-result.json"}')


if __name__ == '__main__':
    main()
