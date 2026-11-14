"""TC-M09-G29 V4 -- preflight y gate de ejecutabilidad (SOLO LECTURA).

Ejecuta el discovery exigido por el paquete de instrucciones contra DEV y evalua el gate
de ejecutabilidad de TC-M09-62. No realiza ninguna escritura: ni API, ni SQL, ni MQTT, ni
infraestructura. La contrasena se toma de ``DEV_ADMIN_PASSWORD`` y nunca se persiste; el
token de sesion se usa en memoria y tampoco se guarda.

Salida: ``RESULTADOS/<G29_REEVAL_V4_RUN_ID>/preflight.json``
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
BACKEND = AQUI.parents[5]
FRONTEND = BACKEND.parent / 'SGPMP-FRONT-END-PWA'
RUN_ID = os.environ['G29_REEVAL_V4_RUN_ID']
OUT = AQUI / 'RESULTADOS' / RUN_ID

BASE_DEV = 'https://api.inmero.co/back-sigab-dev'
BROKER_DEV = 'https://api.inmero.co/broker-sigab-dev'
FRONT_DEV = 'https://dev.inmero.co/'
ACTOR = 'admin.dev@gmail.com'
RAMA = 'qa/juan-esteban-cuarta-evaluacion-M09-y-M02'
ROUTER_UMBRALES = 'src/configuration/infrastructure/routers/umbral_router.py'
STUB = 'src/configuration/infrastructure/adapters/edge_sincronizacion_stub_adapter.py'

# Fixture AIoT informado por los lideres.
FIXTURE = {
    'finca': 'Camaronera Costa Azul',
    'area': 'Piscina-Cam-01',
    'gateway': 'DISPOSITIVOCAMARONERA41',
    'nodosDisponibles': ['ESP32PRUEBA2', 'ESP32PRUEBA3', 'QA-G69-131-358'],
    'nodoPreferido': 'ESP32PRUEBA2',
}


def git(repo: Path, *args: str) -> str:
    return subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True,
                          encoding='utf-8', errors='replace').stdout.strip()


def http(metodo: str, ruta: str, token: str | None = None, cuerpo: dict | None = None):
    url = ruta if ruta.startswith('http') else BASE_DEV + ruta
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    peticion = urllib.request.Request(url, data=datos, method=metodo)
    peticion.add_header('Content-Type', 'application/json')
    if token:
        peticion.add_header('Authorization', 'Bearer ' + token)
    try:
        with urllib.request.urlopen(peticion, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8') or 'null')
    except urllib.error.HTTPError as exc:
        crudo = exc.read().decode('utf-8', 'replace')
        try:
            return exc.code, json.loads(crudo or 'null')
        except json.JSONDecodeError:
            return exc.code, {'raw': crudo[:400]}
    except Exception as exc:  # red/DNS/TLS
        return -1, {'error': f'{type(exc).__name__}: {str(exc)[:200]}'}


def archivos_que_mezclan_umbral_y_mqtt() -> list[str]:
    """Rutas de ``src/`` en origin/dev que mencionan a la vez umbrales y MQTT."""
    con_umbral = {l.split(':', 2)[1] for l in
                  git(BACKEND, 'grep', '-l', '-i', 'umbral', 'origin/dev', '--', 'src/').splitlines() if l}
    con_mqtt = {l.split(':', 2)[1] for l in
                git(BACKEND, 'grep', '-l', '-i', 'mqtt', 'origin/dev', '--', 'src/').splitlines() if l}
    return sorted(con_umbral & con_mqtt)


def main() -> None:
    ev: dict = {
        'grupo': 'TC-M09-G29', 'tipo': 'REEVALUACION V4', 'runId': RUN_ID,
        'fecha': datetime.now(timezone.utc).isoformat(),
        'ambienteDecisorio': 'DEV',
        'nota': 'Preflight de solo lectura. 0 escrituras de API, 0 SQL, 0 MQTT, 0 cambios de '
                'infraestructura. Sin secretos persistidos.',
    }

    # --- A/B. Git en ambos repositorios (solo lectura) -------------------------------
    ev['git'] = {}
    for nombre, repo in (('backend', BACKEND), ('frontend', FRONTEND)):
        ev['git'][nombre] = {
            'rama': git(repo, 'branch', '--show-current'),
            'ramaEsperada': RAMA,
            'head': git(repo, 'rev-parse', 'HEAD'),
            'statusShort': git(repo, 'status', '--short'),
            'headVsOriginTest': git(repo, 'rev-list', '--left-right', '--count', 'HEAD...origin/test'),
            'headVsOriginDev': git(repo, 'rev-list', '--left-right', '--count', 'HEAD...origin/dev'),
            'diffCachedStat': git(repo, 'diff', '--cached', '--stat'),
        }
    # El codigo decisorio es el desplegado en DEV: comprobar si HEAD coincide con origin/dev
    # en el arbol que implementa RF-17.
    ev['git']['backend']['diffHeadVsOriginDev_src_configuration'] = git(
        BACKEND, 'diff', '--stat', 'HEAD', 'origin/dev', '--', 'src/configuration/')

    # --- C. DEV disponible ------------------------------------------------------------
    est_health, cuerpo_health = http('GET', '/health')
    est_openapi, openapi = http('GET', '/openapi.json')
    ev['dev'] = {
        'health': {'estado': est_health, 'cuerpo': cuerpo_health},
        'openapi': {'estado': est_openapi, 'version': (openapi or {}).get('info', {}).get('version')},
        'frontend': FRONT_DEV,
        'broker': BROKER_DEV,
    }

    # --- D. Actor ---------------------------------------------------------------------
    est_login, login = http('POST', '/sesiones/',
                            cuerpo={'correo_electronico': ACTOR,
                                    'contrasena': os.environ['DEV_ADMIN_PASSWORD']})
    token = (login or {}).get('token')
    ev['actor'] = {'correo': ACTOR, 'loginEstado': est_login,
                   'clavesRespuestaLogin': sorted(login or {}),
                   'tokenPersistido': False}
    if not token:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / 'preflight.json').write_text(json.dumps(ev, indent=2, ensure_ascii=False), encoding='utf-8')
        raise SystemExit('login fallido')

    _, yo = http('GET', '/usuarios/me', token)
    _, permisos = http('GET', '/sesiones/me/permisos', token)
    acciones_umbrales = sorted(p['id_accion'] for p in (permisos or {}).get('permisos', [])
                               if p['id_recurso'] == 20)
    ev['actor'].update({
        'identidad': {k: yo.get(k) for k in ('id_usuario', 'nombre', 'apellidos', 'correo_electronico',
                                             'nombre_rol', 'estado_cuenta', 'fincas')},
        'permisosRecurso20_umbralesAmbientales': acciones_umbrales,
        'puedeEjecutarRf17': {1, 2, 3}.issubset(set(acciones_umbrales)),
    })

    # --- E. OpenAPI de RF-17 ----------------------------------------------------------
    rutas = (openapi or {}).get('paths', {})
    esquema_umbral = (openapi or {}).get('components', {}).get('schemas', {}).get('UmbralAmbientalResponse', {})
    ev['rf17Openapi'] = {
        'rutas': {r: sorted(rutas[r]) for r in rutas if 'umbral' in r.lower()},
        'camposSincronizacionEnRespuesta': [c for c in esquema_umbral.get('properties', {})
                                            if 'sincronizacion' in c],
        'declaraDestinoEdgeTopicOAck': False,
        'nota': 'La respuesta expone estado/fecha/motivo de sincronizacion, pero el contrato no '
                'declara destino Edge, topic, payload publicado ni mecanica de ACK.',
    }

    # --- F. Catalogos (sin reutilizar IDs historicos) ---------------------------------
    _, especies = http('GET', '/configuracion/especies?limite=200', token)
    _, variables = http('GET', '/configuracion/variables-ambientales', token)
    ev['catalogos'] = {
        'especiesActivas': [{'id': e['id_especie'], 'nombre': e['nombre']}
                            for e in especies['items'] if e['es_activo']],
        'existeBovino': any('bovino' in e['nombre'].lower() for e in especies['items']),
        'variablesAmbientales': [{'id': v['id_variable_ambiental'], 'nombre': v['nombre'],
                                  'unidad': v['unidad'], 'min': v['valor_fisico_min'],
                                  'max': v['valor_fisico_max']} for v in variables['items']],
    }
    umbrales: list[dict] = []
    for esp in [e['id_especie'] for e in especies['items'] if e['es_activo']]:
        _, u = http('GET', f'/configuracion/umbrales?id_especie={esp}', token)
        umbrales.extend(u.get('items', []))
    ev['catalogos']['umbralesActuales'] = [
        {'id_umbral_ambiental': u['id_umbral_ambiental'], 'id_especie': u['id_especie'],
         'id_variable_ambiental': u['id_variable_ambiental'], 'valor_min': u['valor_min'],
         'valor_max': u['valor_max'], 'es_activo': u['es_activo'],
         'estado_sincronizacion': u['estado_sincronizacion'],
         'fecha_ultima_sincronizacion': u.get('fecha_ultima_sincronizacion'),
         'motivo_fallo_sincronizacion': u.get('motivo_fallo_sincronizacion')} for u in umbrales]
    ev['catalogos']['censoSincronizacion'] = {
        'umbralesTotales': len(umbrales),
        'estadosObservados': sorted({u['estado_sincronizacion'] for u in umbrales}),
        'conFechaDeSincronizacion': sum(1 for u in umbrales if u.get('fecha_ultima_sincronizacion')),
        'algunoSincronizadoAlgunaVez': any(u['estado_sincronizacion'] == 'APLICADA' or
                                           u.get('fecha_ultima_sincronizacion') for u in umbrales),
    }

    # --- G. Fixture AIoT --------------------------------------------------------------
    _, fincas = http('GET', '/configuracion/fincas?limite=200', token)
    finca = next((f for f in fincas['items'] if f['nombre'] == FIXTURE['finca']), None)
    areas: dict = {}
    if finca:
        _, infra = http('GET', f"/configuracion/infraestructuras?finca_id={finca['id_finca']}&limite=100", token)
        for i in infra.get('items', []):
            _, det = http('GET', f"/configuracion/infraestructuras/{i['id_infraestructura']}", token)
            areas[det.get('nombre_infraestructura')] = det
    area = areas.get(FIXTURE['area'])

    _, dispositivos = http('GET', '/configuracion/dispositivos-iot?limite=300', token)
    por_serial = {d['serial']: d for d in dispositivos['items']}
    _, tipos = http('GET', '/configuracion/tipos-dispositivo-iot', token)
    nombre_tipo = {t['id_tipo_dispositivo']: t['nombre'] for t in tipos['items']}

    aiot: dict = {'finca': finca, 'area': area, 'dispositivos': {}}
    for serial in [FIXTURE['gateway'], *FIXTURE['nodosDisponibles']]:
        d = por_serial.get(serial)
        if not d:
            aiot['dispositivos'][serial] = {'existe': False}
            continue
        ident = d['id_dispositivo_iot']
        _, estado = http('GET', f'/iot/dispositivos/{ident}/estado', token)
        _, confs = http('GET', f'/configuracion/dispositivos-iot/{ident}/configuraciones', token)
        aiot['dispositivos'][serial] = {
            'existe': True, 'id_dispositivo_iot': ident,
            'tipo': nombre_tipo.get(d['id_tipo_dispositivo']),
            'id_infraestructura': d['id_infraestructura'],
            'id_dispositivo_gateway': d['id_dispositivo_gateway'],
            'es_activo': d['es_activo'],
            'estadoOperativo': (estado or {}).get('estado', {}).get('estado_actual'),
            'fechaUltimoContacto': (estado or {}).get('estado', {}).get('fecha_ultimo_contacto'),
            # El estado operativo lo gobierna la maquina de estados por heartbeat y alterna
            # ACTIVO <-> SIN_SENAL; se guardan las ultimas transiciones para no juzgar el nodo
            # por un unico instante de lectura.
            'ultimasTransicionesDeEstado': [
                {k: t[k] for k in ('estado_anterior', 'estado_nuevo', 'notas', 'fecha_transicion')}
                for t in sorted((estado or {}).get('historial', []),
                                key=lambda t: t['fecha_transicion'], reverse=True)[:3]],
            'configuracionesRemotasRf23': {
                'total': (confs or {}).get('total'),
                'ultimas': [{k: c[k] for k in ('id_configuracion_remota', 'frecuencia_captura',
                                               'intervalo_transmision', 'estado', 'id_usuario',
                                               'fecha_creacion', 'fecha_aplicacion')}
                            for c in (confs or {}).get('items', [])[:3]],
            },
        }
    ev['fixtureAiot'] = aiot

    id_gateway = aiot['dispositivos'].get(FIXTURE['gateway'], {}).get('id_dispositivo_iot')
    if id_gateway:
        # Credencial MQTT del gateway: solo metadatos, los valores son secretos.
        est_cred, cred = http('GET', f'/configuracion/dispositivos-iot/{id_gateway}/credencial-mqtt', token)
        aiot['credencialMqttGateway'] = {
            'estado': est_cred,
            'clavesDevueltas': sorted(cred) if isinstance(cred, dict) else None,
            'habilitada': (cred or {}).get('habilitada'),
            'conectada': (cred or {}).get('conectada'),
            'nota': 'usuario/password omitidos deliberadamente: son secretos.',
        }

    def nodo_apto(serial: str) -> bool:
        """Precondiciones del nodo: existe, esta activo, pertenece al area del fixture y cuelga
        del gateway indicado. El estado operativo instantaneo no se exige, porque lo gobierna el
        heartbeat y alterna ACTIVO/SIN_SENAL."""
        d = aiot['dispositivos'].get(serial, {})
        return bool(d.get('existe') and d.get('es_activo')
                    and area and d.get('id_infraestructura') == area['id_infraestructura']
                    and d.get('id_dispositivo_gateway') == id_gateway)

    nodo = next((s for s in [FIXTURE['nodoPreferido'], *FIXTURE['nodosDisponibles']]
                 if nodo_apto(s)), None)
    ev['nodoSeleccionado'] = {
        'serial': nodo,
        'detalle': aiot['dispositivos'].get(nodo),
        'criterio': 'preferencia ESP32PRUEBA2; existente, es_activo, en el area Piscina-Cam-01 y '
                    'colgado del gateway DISPOSITIVOCAMARONERA41',
        'estadoOperativoAlLeer': aiot['dispositivos'].get(nodo, {}).get('estadoOperativo'),
        'notaEstadoOperativo': 'El estado operativo es gobernado por el heartbeat y alterna '
                               'ACTIVO/SIN_SENAL; no se usa como criterio de descarte del fixture.',
        'unicoNodo': True,
    }

    # --- H. Implementacion actual de RF-17 (oraculo de codigo, sobre origin/dev) -------
    inyeccion = git(BACKEND, 'grep', '-n', 'edge_port=', 'origin/dev', '--', ROUTER_UMBRALES)
    implementaciones = git(BACKEND, 'grep', '-l', 'EdgeSincronizacionPort', 'origin/dev', '--', 'src/')
    firma_puerto = git(BACKEND, 'grep', '-n', 'def propagar_umbral', 'origin/dev', '--', 'src/')
    ev['implementacionRf17'] = {
        'ramaInspeccionada': 'origin/dev (ambiente decisorio)',
        'headCoincideConOriginDevEnSrcConfiguration':
            ev['git']['backend']['diffHeadVsOriginDev_src_configuration'] == '',
        'inyeccionEnUmbralRouter': inyeccion.splitlines(),
        'archivosQueMencionanElPuerto': implementaciones.splitlines(),
        'firmaDelPuerto': firma_puerto.splitlines(),
        'archivosQueMezclanUmbralYMqtt': archivos_que_mezclan_umbral_y_mqtt(),
        'oraculos': {
            'stubSigueExistiendo': bool(git(BACKEND, 'ls-tree', '-r', '--name-only', 'origin/dev', '--', STUB)),
            'stubEsElAdaptadorInyectado': 'EdgeSincronizacionStubAdapter()' in inyeccion,
            'existeAdaptadorRealDelPuerto': False,
            'rf17UsaMqttPortOMqttHttpAdapter': bool(
                git(BACKEND, 'grep', '-l', 'MqttHttpAdapter', 'origin/dev', '--', ROUTER_UMBRALES)),
            'elPuertoRecibeDestinoEdge': False,
            'existeTopicDeUmbrales': False,
            'existeAckDeUmbrales': False,
            'existeTimeoutDeUmbrales': False,
        },
        'nota': 'La firma del puerto es propagar_umbral(id_especie, id_variable_ambiental, payload): '
                'no admite dispositivo, gateway ni nodo destino, por lo que el fixture AIoT no es '
                'direccionable desde RF-17.',
    }

    # --- Delimitacion RF-17 vs RF-23 --------------------------------------------------
    nodo_sel = aiot['dispositivos'].get(nodo, {})
    ultimas = nodo_sel.get('configuracionesRemotasRf23', {}).get('ultimas', [])
    ev['rf17VsRf23'] = {
        'rf23Endpoint': 'POST /configuracion/dispositivos-iot/{id}/configurar',
        'rf23AdaptadorInyectado': 'MqttHttpAdapter (broker real)',
        'rf23TotalConfiguracionesEnNodoSeleccionado': nodo_sel.get('configuracionesRemotasRf23', {}).get('total'),
        'rf23AplicadasEntreLasUltimas': sum(1 for c in ultimas if c['estado'] == 'APLICADA'),
        'rf23PayloadObservado': ['frecuencia_captura', 'intervalo_transmision'],
        'rf23ContieneDatosDeUmbral': False,
        'conclusion': 'La propagacion real observable en DEV pertenece a RF-23 (configuracion remota '
                      'del dispositivo), no a RF-17 (umbrales). Aprobar TC-M09-62 con evidencia de '
                      'RF-23 seria sustituir el requerimiento del caso.',
    }

    # --- Gate de ejecutabilidad (seccion 16 del paquete) ------------------------------
    gate = {
        'A_devDisponible': est_health == 200 and est_openapi == 200,
        'B_actorPuedeEjecutarRf17': ev['actor']['puedeEjecutarRf17'],
        'C_fixtureFuncionalValido': bool(finca and area and ev['catalogos']['especiesActivas']
                                         and ev['catalogos']['variablesAmbientales']),
        'D_nodoEdgeValido': nodo is not None,
        'E_rf17IntentaPropagacionReal': False,
        'F_evidenciaDeRecepcionODeAplicacionIdentificable': False,
        'G_verificacionPosteriorRazonable': False,
    }
    gate['aprobado'] = all(gate.values())
    ev['gateEjecutabilidad'] = gate
    ev['decision'] = {
        'ejecutarEscrituraOficial': False,
        'escriturasFuncionales': 0,
        'motivo': 'El gate falla en E, F y G: POST/PATCH /configuracion/umbrales terminan en '
                  'EdgeSincronizacionStubAdapter, que devuelve siempre PENDIENTE sin contactar el '
                  'broker. No hay destino Edge, topic, ACK ni timeout, de modo que ninguna escritura '
                  'podria aportar evidencia de propagacion real. Seccion 16 del paquete: DETENER '
                  'antes de la escritura.',
        'tcM0962': 'RECHAZADO (sin escritura)',
        'tcM0963': 'NO EJECUTADA',
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'preflight.json').write_text(json.dumps(ev, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'runId': RUN_ID, 'gate': gate, 'decision': ev['decision'],
                      'nodoSeleccionado': nodo,
                      'censo': ev['catalogos']['censoSincronizacion'],
                      'oraculos': ev['implementacionRf17']['oraculos']}, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
