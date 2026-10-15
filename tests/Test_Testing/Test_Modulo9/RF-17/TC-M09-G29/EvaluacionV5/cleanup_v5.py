"""TC-M09-G29 V5 - CLEANUP final. Escrituras de restauracion, no de TC-62/63.

Fase 2: desactivar el umbral 65, creado solo para esta reevaluacion, por el
        mecanismo oficial PATCH /configuracion/umbrales/{id}/desactivar (Flujo D
        de RF-17): baja logica con asiento de auditoria DEACTIVATE, sin cuerpo,
        sin borrado fisico y sin propagacion al Edge.

Fase 3: restaurar el umbral 48 del RUN anterior a su PRE original
        (5.60-8.40 con sus niveles), por PATCH oficial. Como el Edge esta
        ONLINE se registra el resultado real de sincronizacion, pero NO cuenta
        como una nueva ejecucion de TC-M09-62.

Una sola operacion por fase. Sin SQL. Sin reintentos. Si una precondicion no se
cumple, esa fase no se ejecuta.

Uso: RUN_ID=... TEST_ADMIN_PASSWORD=... python cleanup_v5.py
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

UMBRAL_NUEVO = 65            # creado por esta reevaluacion -> desactivar
UMBRAL_A_RESTAURAR = 48      # del RUN anterior -> devolver a su PRE

# PRE original del umbral 48, capturado antes de la primera escritura.
PRE_48 = {
    'valor_min': '5.60', 'valor_max': '8.40',
    'niveles': [
        {'nivel': 'normal', 'limite_inferior': '5.60', 'limite_superior': '6.53'},
        {'nivel': 'precaucion', 'limite_inferior': '6.53', 'limite_superior': '7.46'},
        {'nivel': 'critico', 'limite_inferior': '7.46', 'limite_superior': '8.40'},
    ],
}
ESTADO_48_DEJADO_POR_QA = ('5.90', '8.70', 'NO_CONF')

SENSIBLES = ('password', 'contrasena', 'token', 'secret', 'usuario_mqtt', 'clave')
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
    (OUT / 'cleanup.json').write_text(
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


def leer(id_umbral, incluir_inactivos=False):
    """Los umbrales inactivos no aparecen en el listado por especie; se detecta su
    ausencia, que es justamente la comprobacion del cleanup."""
    _, lista, _ = http('GET', f'/configuracion/umbrales?id_especie={ESPECIE}')
    items = (lista or {}).get('items', [])
    u = next((x for x in items if x['id_umbral_ambiental'] == id_umbral), None)
    return u, [x['id_umbral_ambiental'] for x in items]


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

    ev: dict = {'runId': RUN_ID, 'caso': 'TC-M09-G29', 'fase': 'CLEANUP',
                'tipoDeEscritura': 'CLEANUP / RESTAURACION DE DATOS',
                'noCuentaComoEscrituraOficialDe': ['TC-M09-62', 'TC-M09-63'],
                'sqlDirecto': False, 'registrosEliminadosFisicamente': 0,
                'ambiente': 'TEST', 'inicio': ahora(),
                'actor': {'correo': ACTOR, 'tokenPersistido': False}}

    # ================= FASE 1: estado previo preservado =============================
    u65, activos = leer(UMBRAL_NUEVO)
    u48, _ = leer(UMBRAL_A_RESTAURAR)
    _, aud65, _ = http('GET', f'/configuracion/umbrales/{UMBRAL_NUEVO}/auditoria')
    _, aud48, _ = http('GET', f'/configuracion/umbrales/{UMBRAL_A_RESTAURAR}/auditoria')
    ev['fase1_estadoPrevio'] = {
        'umbral65': u65, 'auditoria65': aud65,
        'umbral48': u48, 'auditoria48': aud48,
        'umbralesActivosDeLaEspecie4': activos,
        'trazaAuditoria65Esperada': '#59 CREATE, #60 UPDATE, #61 UPDATE, #62 UPDATE',
        'timestamp': ahora(),
    }
    guardar(ev)

    # ================= FASE 2: desactivar el umbral 65 ===============================
    f2: dict = {'objetivo': UMBRAL_NUEVO,
                'mecanismo': 'PATCH /configuracion/umbrales/{id}/desactivar (Flujo D, RF-17)',
                'bajaLogicaNoBorradoFisico': True}
    gates = {
        'existeYEstaActivo': bool(u65) and u65.get('es_activo') is True,
        'idCorrecto': bool(u65) and u65['id_umbral_ambiental'] == UMBRAL_NUEVO,
        'especie4': bool(u65) and u65.get('id_especie') == ESPECIE,
        'variable10HumedadRelativa': bool(u65) and u65.get('id_variable_ambiental') == 10,
    }
    f2['gates'] = gates
    f2['fecha_actualizacion_previa'] = (u65 or {}).get('fecha_actualizacion')
    if all(gates.values()):
        f2['request'] = {'metodo': 'PATCH',
                         'ruta': f'/configuracion/umbrales/{UMBRAL_NUEVO}/desactivar',
                         'cuerpo': None, 'timestamp': ahora()}
        ev['fase2_cleanupUmbral65'] = f2
        guardar(ev)
        e, c, d = http('PATCH', f'/configuracion/umbrales/{UMBRAL_NUEVO}/desactivar',
                       timeout=TIMEOUT_ESCRITURA)
        f2['response'] = {'http': e, 'cuerpo': c, 'duracionSegundos': round(d, 3),
                          'recibido': ahora()}
        despues, activos_post = leer(UMBRAL_NUEVO)
        _, aud_post, _ = http('GET', f'/configuracion/umbrales/{UMBRAL_NUEVO}/auditoria')
        f2['verificacionPosterior'] = {
            'apareceEnElListadoDeActivos': despues is not None,
            'umbralesActivosDeLaEspecie4': activos_post,
            'es_activoEnLaRespuesta': (c or {}).get('es_activo') if isinstance(c, dict) else None,
            'auditoria': aud_post,
        }
        f2['verdict'] = ('OK' if e == 200 and despues is None else 'FALLO')
        f2['motivo'] = ('Umbral 65 desactivado: ya no figura entre los activos de la especie 4.'
                        if f2['verdict'] == 'OK' else
                        f'Resultado inesperado (HTTP {e}). No se reintenta.')
    else:
        f2['verdict'] = 'NO_EJECUTADO'
        f2['motivo'] = f'Gates no cumplidos: {[k for k, v in gates.items() if not v]}'
    ev['fase2_cleanupUmbral65'] = f2
    guardar(ev)

    # ================= FASE 3: restaurar el umbral 48 ===============================
    f3: dict = {'objetivo': UMBRAL_A_RESTAURAR,
                'preOriginal': PRE_48,
                'finalidad': 'restaurar los datos, no volver a probar RF-17'}
    u48_ahora, _ = leer(UMBRAL_A_RESTAURAR)
    sigue_como_lo_dejo_qa = (
        bool(u48_ahora)
        and u48_ahora['valor_min'] == ESTADO_48_DEJADO_POR_QA[0]
        and u48_ahora['valor_max'] == ESTADO_48_DEJADO_POR_QA[1]
        and u48_ahora['estado_sincronizacion'] == ESTADO_48_DEJADO_POR_QA[2])
    f3['estadoActual'] = u48_ahora
    f3['sigueComoLoDejoQa'] = sigue_como_lo_dejo_qa
    f3['fecha_actualizacion_capturada'] = (u48_ahora or {}).get('fecha_actualizacion')

    if sigue_como_lo_dejo_qa:
        cuerpo = {'valor_min': PRE_48['valor_min'], 'valor_max': PRE_48['valor_max'],
                  'niveles': PRE_48['niveles'],
                  'fecha_actualizacion': u48_ahora.get('fecha_actualizacion')}
        f3['request'] = {'metodo': 'PATCH',
                         'ruta': f'/configuracion/umbrales/{UMBRAL_A_RESTAURAR}',
                         'cuerpo': cuerpo, 'timestamp': ahora()}
        ev['fase3_restauracionUmbral48'] = f3
        guardar(ev)
        e, c, d = http('PATCH', f'/configuracion/umbrales/{UMBRAL_A_RESTAURAR}',
                       cuerpo, timeout=TIMEOUT_ESCRITURA)
        f3['response'] = {'http': e, 'cuerpo': c, 'duracionSegundos': round(d, 3),
                          'recibido': ahora()}
        post48, _ = leer(UMBRAL_A_RESTAURAR)
        _, aud48p, _ = http('GET', f'/configuracion/umbrales/{UMBRAL_A_RESTAURAR}/auditoria')
        f3['verificacionPosterior'] = {
            'umbral': post48, 'auditoria': aud48p,
            'valoresPreRestaurados': bool(post48) and coincide(
                post48, PRE_48['valor_min'], PRE_48['valor_max'], PRE_48['niveles']),
            'estado_sincronizacion': (post48 or {}).get('estado_sincronizacion'),
            'fecha_ultima_sincronizacion': (post48 or {}).get('fecha_ultima_sincronizacion'),
            'motivo_fallo_sincronizacion': (post48 or {}).get('motivo_fallo_sincronizacion'),
        }
        f3['verdict'] = ('OK' if f3['verificacionPosterior']['valoresPreRestaurados']
                         else 'FALLO')
        f3['notaSobreLaSincronizacion'] = (
            'El Edge esta ONLINE, de modo que esta restauracion tambien se propago. Se registra '
            'el resultado real por transparencia, pero NO constituye una ejecucion de TC-M09-62: '
            'su finalidad es devolver el dato a su valor original.')
    else:
        f3['verdict'] = 'NO_EJECUTADO'
        f3['motivo'] = ('El umbral 48 ya no esta como lo dejo QA (5.90-8.70 NO_CONF): pudo '
                        'intervenir un tercero. No se sobrescribe.')
    ev['fase3_restauracionUmbral48'] = f3

    # ================= Estado final ==================================================
    _, final, _ = http('GET', f'/configuracion/umbrales?id_especie={ESPECIE}')
    ev['estadoFinal'] = {
        'umbralesActivosDeLaEspecie4': [
            {'id': x['id_umbral_ambiental'], 'id_variable_ambiental': x['id_variable_ambiental'],
             'valor_min': x['valor_min'], 'valor_max': x['valor_max'],
             'estado_sincronizacion': x['estado_sincronizacion']}
            for x in (final or {}).get('items', [])],
        'umbral65Activo': any(x['id_umbral_ambiental'] == UMBRAL_NUEVO
                              for x in (final or {}).get('items', [])),
        'gatewaysSaneadosReactivados': False,
        'notaGatewaysSaneados': ('Los 5 Gateway Edge desactivados permanecen inactivos por '
                                 'decision documentada: AIoT confirmo que eran registros '
                                 'antiguos de prueba ya no utilizados.'),
        'otrasEntidadesModificadas': 'ninguna (especie 4, finca 44, area 22, 138 y 139 intactos)',
        'timestamp': ahora(),
    }
    ev['fin'] = ahora()
    guardar(ev)

    print(f"FASE 2 umbral 65: {f2['verdict']} · {f2.get('motivo', '')}")
    if 'response' in f2:
        print(f"   HTTP {f2['response']['http']} · activo tras el cleanup: "
              f"{f2['verificacionPosterior']['apareceEnElListadoDeActivos']}")
    print(f"FASE 3 umbral 48: {f3['verdict']}")
    if 'response' in f3:
        v = f3['verificacionPosterior']
        print(f"   HTTP {f3['response']['http']} · PRE restaurado: {v['valoresPreRestaurados']}")
        print(f"   {(v['umbral'] or {}).get('valor_min')}-{(v['umbral'] or {}).get('valor_max')} "
              f"· sync={v['estado_sincronizacion']} · fecha={v['fecha_ultima_sincronizacion']}")
        print(f"   motivo={v['motivo_fallo_sincronizacion']}")
    print(f"Umbrales activos especie 4: {[x['id'] for x in ev['estadoFinal']['umbralesActivosDeLaEspecie4']]}")
    print(f"Evidencia: {OUT / 'cleanup.json'}")


if __name__ == '__main__':
    main()
