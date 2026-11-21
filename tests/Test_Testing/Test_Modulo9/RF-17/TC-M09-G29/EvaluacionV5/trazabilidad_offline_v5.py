"""TC-M09-G29 V5 - trazabilidad de los destinos OFFLINE de la especie 4 (SOLO LECTURA).

Para la especie 4 (Cachama Blanca) RF-17 agrega 6 destinos: SERBY-TAX-FIRMWARE
esta ONLINE y 5 estan OFFLINE. Este script documenta, sin modificar nada, por
que cada uno de esos 5 entra en ``fn_seriales_gateway_edge_por_especie`` y si el
dato que lo arrastra es residuo de QA o esta vigente.

La funcion une area -> dispositivo activo del area -> Gateway Edge por
COALESCE(d.id_dispositivo_gateway, d.id_dispositivo_iot). Un Gateway puede por
tanto entrar por si mismo (esta en el area) o arrastrado por otro dispositivo
del area que lo declara como su gateway. El script reconstruye esa ruta exacta.

Uso: RUN_ID=... TEST_ADMIN_PASSWORD=... python trazabilidad_offline_v5.py
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
MUERTOS = {'INACTIVO', 'CERRADO', 'BAJA'}
SENSIBLES = ('password', 'contrasena', 'token', 'secret', 'usuario_mqtt', 'clave')

# Marcas que delatan generacion automatica por una ejecucion QA anterior.
MARCAS_QA = ('TC-M09', 'TC-M02', 'QA-', 'QA ', 'PRUEBA', 'TEST', 'G59', 'G69', 'G36',
             'CG66', 'FORGE', 'RESUELTO', 'CONCURRENCIA', 'PARALELO')

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


def marcas(texto: str | None) -> list[str]:
    t = (texto or '').upper()
    return [m for m in MARCAS_QA if m in t]


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

    _, especies = http('GET', '/configuracion/especies?limite=500')
    _, fincas = http('GET', '/configuracion/fincas?limite=500')
    _, tipos = http('GET', '/configuracion/tipos-dispositivo-iot')
    _, disp = http('GET', '/configuracion/dispositivos-iot')
    tipo_por_id = {x['id_tipo_dispositivo']: x['nombre']
                   for x in (tipos or {}).get('items', [])}
    dispositivos = (disp or {}).get('items', [])
    por_id = {d['id_dispositivo_iot']: d for d in dispositivos}
    por_serial = {d['serial']: d for d in dispositivos}
    finca_por_id = {f['id_finca']: f for f in (fincas or {}).get('items', [])}

    areas: dict[int, dict] = {}
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

    def vivo(r: dict) -> bool:
        return (r.get('nombre_estado') or '').upper() not in MUERTOS

    def areas_de_especie(ide: int) -> set[int]:
        s = {k for k, v in areas.items()
             if v.get('es_activo') and v.get('especie_id') == ide}
        s |= {r['id_infraestructura'] for r in activos
              if r.get('id_especie') == ide and vivo(r)
              and areas.get(r.get('id_infraestructura'), {}).get('es_activo')}
        return s

    def destinos(ids_area: set[int]) -> dict[str, list[dict]]:
        """serial del Gateway -> rutas (dispositivo del area que lo arrastra)."""
        rutas: dict[str, list[dict]] = {}
        for d in dispositivos:
            if not d.get('es_activo') or d.get('id_infraestructura') not in ids_area:
                continue
            g = por_id.get(d.get('id_dispositivo_gateway') or d['id_dispositivo_iot'])
            if not (g and g.get('es_activo')
                    and tipo_por_id.get(g['id_tipo_dispositivo']) == 'GATEWAY_EDGE'):
                continue
            rutas.setdefault(g['serial'], []).append({
                'areaQueLoArrastra': d['id_infraestructura'],
                'nombreArea': areas.get(d['id_infraestructura'], {}).get('nombre_infraestructura'),
                'dispositivoDelArea': {
                    'id': d['id_dispositivo_iot'], 'serial': d['serial'],
                    'tipo': tipo_por_id.get(d.get('id_tipo_dispositivo')),
                    'es_activo': d.get('es_activo'),
                    'id_dispositivo_gateway': d.get('id_dispositivo_gateway')},
                'entraPorSiMismo': d['id_dispositivo_iot'] == g['id_dispositivo_iot'],
            })
        return rutas

    areas_esp = areas_de_especie(ESPECIE)
    rutas_esp = destinos(areas_esp)

    # Conectividad de cada destino
    conect: dict[str, dict] = {}
    for serial in rutas_esp:
        g = por_serial[serial]
        gid = g['id_dispositivo_iot']
        _, cred = http('GET', f'/configuracion/dispositivos-iot/{gid}/credencial-mqtt')
        _, estado = http('GET', f'/iot/dispositivos/{gid}/estado')
        bloque = (estado or {}).get('estado') if isinstance(estado, dict) else {}
        c = (cred or {}).get('conectada') if isinstance(cred, dict) else None
        conect[serial] = {'conectada': c,
                          'credencialMqtt': limpio(cred if isinstance(cred, dict) else {}),
                          'heartbeat': limpio(bloque if isinstance(bloque, dict) else {}),
                          'clasificacion': ('EDGE_ONLINE' if c is True else
                                            'EDGE_OFFLINE' if c is False
                                            else 'EDGE_NO_VERIFICABLE')}

    offline = sorted(s for s in rutas_esp if conect[s]['clasificacion'] != 'EDGE_ONLINE')
    online = sorted(s for s in rutas_esp if conect[s]['clasificacion'] == 'EDGE_ONLINE')

    # Otras especies que tambien resuelven cada Gateway -> uso por otros escenarios
    otras: dict[str, list[dict]] = {s: [] for s in rutas_esp}
    for e in (especies or {}).get('items', []):
        if not e.get('es_activo') or e['id_especie'] == ESPECIE:
            continue
        r = destinos(areas_de_especie(e['id_especie']))
        for s in r:
            if s in otras:
                otras[s].append({'id_especie': e['id_especie'], 'nombre': e['nombre']})

    detalle = []
    for serial in offline:
        g = por_serial[serial]
        gid = g['id_dispositivo_iot']
        area_g = areas.get(g.get('id_infraestructura'), {})
        finca_g = finca_por_id.get(area_g.get('id_finca'), {})

        # 5-6. Activos vivos de especie 4 que meten cada area en la funcion
        ids_area_ruta = sorted({r['areaQueLoArrastra'] for r in rutas_esp[serial]})
        detonantes = []
        for ida in ids_area_ruta:
            por_campo = areas.get(ida, {}).get('especie_id') == ESPECIE
            vivos = [r for r in activos if r.get('id_infraestructura') == ida
                     and r.get('id_especie') == ESPECIE and vivo(r)]
            detonantes.append({
                'id_area': ida,
                'nombreArea': areas.get(ida, {}).get('nombre_infraestructura'),
                'areaDeclaraEspecie4EnEspecieId': por_campo,
                'activosVivosEspecie4': [{
                    'id_activo_biologico': r['id_activo_biologico'],
                    'identificador': r.get('identificador'),
                    'tipo': r.get('tipo'),
                    'nombre_estado': r.get('nombre_estado'),
                    'fecha_inicio_ciclo': r.get('fecha_inicio_ciclo'),
                    'fecha_creacion': r.get('fecha_creacion'),
                    'origen_financiero': r.get('origen_financiero'),
                    'soporte_documental': r.get('soporte_documental'),
                    'id_usuario': r.get('id_usuario'),
                    'marcasQaEnIdentificador': marcas(r.get('identificador')),
                    'marcasQaEnSoporte': marcas(r.get('soporte_documental')),
                } for r in vivos],
            })

        # 7. Uso por otros escenarios vigentes
        _, confs = http('GET', f'/configuracion/dispositivos-iot/{gid}/configuraciones')
        _, sensores = http('GET', f'/configuracion/dispositivos-iot/{gid}/sensores')
        colgados = [{'id': d['id_dispositivo_iot'], 'serial': d['serial'],
                     'es_activo': d.get('es_activo'),
                     'tipo': tipo_por_id.get(d.get('id_tipo_dispositivo'))}
                    for d in dispositivos if d.get('id_dispositivo_gateway') == gid]

        # 8. Que haria falta para sacarlo del fan-out
        por_si_mismo = any(r['entraPorSiMismo'] for r in rutas_esp[serial])
        intermediarios = sorted({r['dispositivoDelArea']['serial'] for r in rutas_esp[serial]
                                 if not r['entraPorSiMismo']})
        acciones = []
        if por_si_mismo:
            acciones.append('desactivar el Gateway (esta instalado en un area de la especie 4)')
        if intermediarios:
            acciones.append('desactivar o reapuntar el/los dispositivo(s) intermediario(s) '
                            f'que lo declaran como su gateway: {intermediarios}')
        acciones.append('alternativa sin tocar dispositivos: cerrar/inactivar los activos vivos '
                        'de especie 4 de esas areas (saca el area del fan-out)')
        if any(d['areaDeclaraEspecie4EnEspecieId'] for d in detonantes):
            acciones.append('alternativa: corregir especie_id del area que declara especie 4')

        detalle.append({
            '1_identidad': {'id_dispositivo_iot': gid, 'serial': serial,
                            'descripcion': g.get('descripcion'),
                            'tipo': tipo_por_id.get(g.get('id_tipo_dispositivo')),
                            'fecha_creacion': g.get('fecha_creacion'),
                            'marcasQaEnSerial': marcas(serial),
                            'marcasQaEnDescripcion': marcas(g.get('descripcion'))},
            '2_estadoAdministrativo': {'es_activo': g.get('es_activo')},
            '3_areaInfraestructura': {'id_infraestructura': area_g.get('id_infraestructura'),
                                      'nombre': area_g.get('nombre_infraestructura'),
                                      'tipo_area': area_g.get('tipo_area'),
                                      'es_activo': area_g.get('es_activo'),
                                      'especie_id': area_g.get('especie_id')},
            '4_finca': {'id_finca': finca_g.get('id_finca'), 'nombre': finca_g.get('nombre'),
                        'es_activo': finca_g.get('es_activo')},
            '5y6_detonantesDelFanOut': detonantes,
            '7_usoPorOtrosEscenarios': {
                'otrasEspeciesQueLoResuelven': otras.get(serial, []),
                'dispositivosColgadosDelGateway': colgados,
                'configuracionesRemotasRf23': (confs or {}).get('items',
                                                                confs if isinstance(confs, list) else []),
                'sensoresAsociados': (sensores or {}).get('items',
                                                          sensores if isinstance(sensores, list) else []),
                'tieneHeartbeatAlgunaVez': bool(conect[serial]['heartbeat']),
            },
            '8_queHariaFaltaParaSacarloDelFanOut': {
                'entraPorSiMismo': por_si_mismo,
                'dispositivosIntermediarios': intermediarios,
                'accionesPosibles': acciones,
            },
            'conectividad': conect[serial],
            'rutasDeEntradaAlFanOut': rutas_esp[serial],
        })

    ev = {'runId': RUN_ID, 'caso': 'TC-M09-G29', 'version': 'V5',
          'ambiente': 'TEST', 'especieAnalizada': ESPECIE,
          'escriturasFuncionales': 0, 'inicio': ahora(),
          'resumenDestinos': {'total': len(rutas_esp), 'online': online,
                              'offline': offline},
          'destinosOffline': detalle, 'fin': ahora()}

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'trazabilidad-offline.json').write_text(
        json.dumps(ev, indent=2, ensure_ascii=False), encoding='utf-8')

    print(f"especie {ESPECIE}: {len(rutas_esp)} destinos · ONLINE={online} · "
          f"OFFLINE={len(offline)}")
    for d in detalle:
        i = d['1_identidad']
        print(f"\n--- {i['serial']} (id {i['id_dispositivo_iot']})")
        print(f"    activo={d['2_estadoAdministrativo']['es_activo']} "
              f"area={d['3_areaInfraestructura']['id_infraestructura']} "
              f"{d['3_areaInfraestructura']['nombre']!r} "
              f"finca={d['4_finca']['id_finca']} {d['4_finca']['nombre']!r}")
        print(f"    heartbeat alguna vez: {d['7_usoPorOtrosEscenarios']['tieneHeartbeatAlgunaVez']}")
        print(f"    otras especies: {[e['id_especie'] for e in d['7_usoPorOtrosEscenarios']['otrasEspeciesQueLoResuelven']]}")
        for t in d['5y6_detonantesDelFanOut']:
            ids = [(a['id_activo_biologico'], a['identificador']) for a in t['activosVivosEspecie4']]
            print(f"    area {t['id_area']} {t['nombreArea']!r} activos4={ids}")
    print(f"\nEvidencia: {OUT / 'trazabilidad-offline.json'}")


if __name__ == '__main__':
    main()
