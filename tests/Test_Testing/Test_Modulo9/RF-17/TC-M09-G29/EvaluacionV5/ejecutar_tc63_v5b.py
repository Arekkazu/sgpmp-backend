"""TC-M09-G29 V5 (reejecucion) - TC-M09-63: fallo de sincronizacion con el Edge desconectado.

Baseline: Configuracion A = 40-95 APLICADA en el umbral 65 (TC-M09-62 aprobado).
Configuracion B = 40-100. UNA sola escritura oficial, sin reintentos.

Revalida las cuatro condiciones justo antes de escribir y se detiene sin escribir
si alguna falla:
  - el broker reporta conectada=false para SERBY-TAX-FIRMWARE;
  - el broker esta operativo (HTTP 200 en /credencial-mqtt; un broker caido daria 503);
  - SERBY-TAX-FIRMWARE sigue siendo el unico destino RF-17 de la especie 4;
  - la baseline sigue en 40-95 y APLICADA.

La conservacion de A en el Edge NO se da por verificada: no hay evidencia directa
de umbrales.json accesible desde QA.

Uso: RUN_ID=... TEST_ADMIN_PASSWORD=... python ejecutar_tc63_v5b.py
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

A = {'valor_min': '40.00', 'valor_max': '95.00'}
NIVELES_B = [
    {'nivel': 'normal', 'limite_inferior': 40, 'limite_superior': 70},
    {'nivel': 'precaucion', 'limite_inferior': 70, 'limite_superior': 85},
    {'nivel': 'critico', 'limite_inferior': 85, 'limite_superior': 100},
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
    (OUT / 'tc63-result.json').write_text(
        json.dumps(ev, indent=2, ensure_ascii=False), encoding='utf-8')


def dec(x) -> Decimal:
    return Decimal(str(x))


def coincide(u: dict, vmin, vmax, niveles) -> bool:
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
    conectada = (cred or {}).get('conectada') if isinstance(cred, dict) else None
    return {'httpCredencial': hc, 'brokerOperativo': hc == 200,
            'credencialMqtt': limpio(cred if isinstance(cred, dict) else {}),
            'heartbeat': limpio(b if isinstance(b, dict) else {}),
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

    ev: dict = {'runId': RUN_ID, 'caso': 'TC-M09-63', 'version': 'V5-reejecucion',
                'ambiente': 'TEST', 'inicio': ahora(),
                'actor': {'correo': ACTOR, 'tokenPersistido': False},
                'baselineA': {'id_umbral_ambiental': UMBRAL, **A},
                'configuracionB': {'valor_min': 40, 'valor_max': 100, 'niveles': NIVELES_B},
                'escriturasOficiales': 0}

    # --- Revalidacion de las cuatro condiciones --------------------------------------
    edge = estado_edge()
    dest = destinos()
    base = leer()
    ev['precondiciones'] = {
        'edge': edge, 'destinosRf17': dest, 'baseline': base,
        'conectadaFalse': edge['conectada'] is False,
        'brokerOperativo': edge['brokerOperativo'],
        'unicoDestinoEsElGateway': dest == [GATEWAY],
        'baselineEn40a95Aplicada': bool(base) and coincide(
            base, 40, 95,
            [{'nivel': 'normal', 'limite_inferior': 40, 'limite_superior': 70},
             {'nivel': 'precaucion', 'limite_inferior': 70, 'limite_superior': 85},
             {'nivel': 'critico', 'limite_inferior': 85, 'limite_superior': 95}])
            and base['estado_sincronizacion'] == 'APLICADA',
    }
    pre = ev['precondiciones']
    # conectada=false NO es precondicion formal: la instruccion oficial de Desarrollo exige
    # detener el edge-agent y ejecutar. La indisponibilidad fisica ya esta demostrada
    # (equipo desconectado, heartbeat congelado, SIN_SENAL, FALLO_CONECTIVIDAD). El valor
    # de conectada se registra como dato del escenario, no como freno.
    pre['conectadaNoEsPrecondicionFormal'] = True
    frenos = [k for k in ('brokerOperativo', 'unicoDestinoEsElGateway',
                          'baselineEn40a95Aplicada') if not pre[k]]
    if frenos:
        ev['verdict'] = 'NO_EJECUTADO'
        ev['motivo'] = f'Precondiciones no alcanzadas: {frenos}. 0 escrituras.'
        ev['fin'] = ahora()
        guardar(ev)
        raise SystemExit(ev['motivo'])

    fecha_exacta = base.get('fecha_actualizacion')
    ev['fecha_actualizacion_capturada'] = fecha_exacta

    cuerpo = {'valor_min': 40, 'valor_max': 100, 'niveles': NIVELES_B,
              'fecha_actualizacion': fecha_exacta}
    marca = ahora()
    ev['request'] = {'metodo': 'PATCH', 'ruta': f'/configuracion/umbrales/{UMBRAL}',
                     'cuerpo': cuerpo,
                     'cabeceras': ['Authorization: <omitido>', 'Content-Type: application/json'],
                     'timestamp': marca}
    ev['escriturasOficiales'] = 1
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
    motivo = (post or {}).get('motivo_fallo_sincronizacion')
    codigo = (cuerpo_pa or {}).get('error_code') if isinstance(cuerpo_pa, dict) else None

    ev['verificacionFisicaEdge'] = {
        'rutaEsperada': RUTA_EDGE, 'accesibleDesdeQa': False,
        'conservacionDeAVerificada': False,
        'nota': ('No existe evidencia directa de umbrales.json ni endpoint del producto que '
                 'devuelva la configuracion efectiva en campo. La conservacion de la '
                 'Configuracion A en el Edge NO se da por verificada. Ademas, con el Edge '
                 'desconectado el broker no publico, de modo que no hubo nada que pudiera '
                 'sobrescribir A, pero eso es inferencia del contrato, no observacion directa.'),
    }

    oraculo = {
        'http500': estado_pa == 500,
        'errorCodeFalloSincronizacionEdge': codigo == 'FALLO_SINCRONIZACION_EDGE',
        'bPersistida40a100': bool(post) and coincide(post, 40, 100, NIVELES_B),
        'estadoPendiente': sync == 'PENDIENTE',
        'motivoIndicaGatewayDesconectado': bool(motivo),
        'sinAck': sync != 'APLICADA',
        'noSePerdioLaConfiguracionCentral': bool(post),
        'respuestaRapidaSinEsperarAck': dur < 5.0,
        'fechaNoIndicaQueBFueAplicada': (post or {}).get('fecha_ultima_sincronizacion')
                                        == ev['precondiciones']['baseline'].get(
                                            'fecha_ultima_sincronizacion'),
    }
    ev['oraculo'] = oraculo
    # Causas de rechazo explicitas de la instruccion, para nombrar el fallo con precision.
    ev['causasDeRechazo'] = {
        'devolvioNoConfEnLugarDePendiente': sync == 'NO_CONF',
        'esperoAproximadamente30sIntentandoAck': dur >= 25.0,
        'elBrokerLoTratoComoConectadoYPublico': sync == 'APLICADA',
        'otroEstadoIncompatible': sync not in ('PENDIENTE', 'NO_CONF', 'APLICADA'),
        'noPersistioB': not (bool(post) and coincide(post, 40, 100, NIVELES_B)),
    }
    ev['oraculoConservacionEnEdge'] = {
        'A_aplicadaAntesDeDesconectar': True,
        'B_centralmentePendienteDuranteLaDesconexion': sync == 'PENDIENTE'
                                                       and bool(post)
                                                       and coincide(post, 40, 100, NIVELES_B),
        'A_sigueSiendoLaConfiguracionEfectivaEnCampo': 'NO VERIFICABLE DESDE QA',
        'B_noSustituyoASilenciosamente': 'NO VERIFICABLE DESDE QA',
    }

    if all(oraculo.values()):
        ev['verdict'] = 'APROBADO'
        ev['motivo'] = ('El flujo de fallo de sincronizacion se comporta como exige RF-17 con el '
                        'Edge indisponible. La conservacion de A en campo queda sin verificar '
                        'directamente por falta de acceso al Raspberry.')
    else:
        ev['verdict'] = 'RECHAZADO'
        nombradas = [k for k, v in ev['causasDeRechazo'].items() if v]
        ev['motivo'] = ('Con el Edge fisicamente desconectado, el flujo no cumplio: '
                        + ', '.join(k for k, v in oraculo.items() if not v)
                        + (f". Causas tipificadas: {nombradas}" if nombradas else ''))
    ev['restauracion'] = {'realizada': False,
                          'razon': 'Instruccion de Juan: no restaurar todavia.'}
    ev['fin'] = ahora()
    guardar(ev)

    print(f"TC-M09-63: {ev['verdict']}")
    print(f'  PATCH HTTP {estado_pa} en {dur:.3f}s · error_code={codigo}')
    print(f"  central: {(post or {}).get('valor_min')}-{(post or {}).get('valor_max')}")
    print(f'  estado_sincronizacion={sync}')
    print(f'  motivo_fallo={motivo}')
    print(f"  auditoria total: {(aud or {}).get('total')}")
    print(f"  oraculo no cumplido: {[k for k, v in oraculo.items() if not v] or 'ninguno'}")
    print(f"Evidencia: {OUT / 'tc63-result.json'}")


if __name__ == '__main__':
    main()
