"""TC-M09-G29 - REEVALUACION V5 - PREFLIGHT (solo lectura, 0 escrituras funcionales).

Comprueba si existe una via ejecutable real para TC-M09-62 tras la correccion
INC-M09-104-G29 (stub -> adaptador MQTT real). Se ejecuta SIEMPRE, con el
Raspberry/Edge encendido o apagado.

Secretos: la contrasena se lee de DEV_ADMIN_PASSWORD y nunca se persiste. No se
guardan JWT, credenciales MQTT ni tokens del broker.

Uso:  python preflight_v5.py            (genera un RUN_ID nuevo)
      RUN_ID=... python preflight_v5.py (reusa un RUN_ID)
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

BASE_DEV = 'https://api.inmero.co/back-sigab-dev'
BROKER_DEV = 'https://api.inmero.co/broker-sigab-dev'
FRONT_DEV = 'https://dev.inmero.co/'
ACTOR = 'admin.dev@gmail.com'

AQUI = Path(__file__).resolve().parent
BACKEND = AQUI.parents[5]          # .../sgpmp-backend (raiz del repo)
RUN_ID = os.environ.get('RUN_ID') or (
    'G29-REEVAL-V5-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
OUT = AQUI / 'RESULTADOS' / RUN_ID

CLAVES_SENSIBLES = ('password', 'contrasena', 'token', 'secret', 'usuario_mqtt', 'clave')


def ahora() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def git(*args: str) -> str:
    try:
        return subprocess.run(['git', *args], cwd=BACKEND, capture_output=True,
                              text=True, timeout=120).stdout.strip()
    except Exception as exc:                                  # noqa: BLE001
        return f'<error: {type(exc).__name__}>'


def http(metodo: str, ruta: str, token: str | None = None, cuerpo: dict | None = None):
    url = ruta if ruta.startswith('http') else BASE_DEV + ruta
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    pet = urllib.request.Request(url, data=datos, method=metodo)
    if datos:
        pet.add_header('Content-Type', 'application/json')
    if token:
        pet.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(pet, timeout=60) as resp:
            return resp.status, json.loads(resp.read() or b'null')
    except urllib.error.HTTPError as exc:
        bruto = exc.read()
        try:
            return exc.code, json.loads(bruto or b'null')
        except ValueError:
            return exc.code, {'raw': bruto.decode('utf-8', 'replace')[:400]}
    except Exception as exc:                                   # noqa: BLE001
        return -1, {'error': f'{type(exc).__name__}: {str(exc)[:200]}'}


def sin_secretos(d: dict) -> dict:
    """Copia de un dict omitiendo cualquier clave sensible."""
    return {k: v for k, v in (d or {}).items()
            if not any(s in k.lower() for s in CLAVES_SENSIBLES)}


def guardar(ev: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'preflight.json').write_text(
        json.dumps(ev, indent=2, ensure_ascii=False), encoding='utf-8')


# --------------------------------------------------------------------------------------
def main() -> None:
    ev: dict = {'runId': RUN_ID, 'caso': 'TC-M09-G29', 'version': 'V5',
                'inicio': ahora(), 'escriturasFuncionales': 0}

    # --- A. Git (solo lectura) --------------------------------------------------------
    git('fetch', 'origin')
    ev['git'] = {
        'repo': str(BACKEND),
        'rama': git('branch', '--show-current'),
        'statusShort': git('status', '--short'),
        'diffStat': git('diff', '--stat'),
        'diffCachedStat': git('diff', '--cached', '--stat'),
        'head': git('rev-parse', 'HEAD'),
        'originDev': git('rev-parse', 'origin/dev'),
        'headVsOriginDev': git('rev-list', '--left-right', '--count', 'HEAD...origin/dev'),
        'headVsOriginTest': git('rev-list', '--left-right', '--count', 'HEAD...origin/test'),
        'diffConfiguracionVsOriginDev': git(
            'diff', '--stat', 'HEAD', 'origin/dev', '--', 'src/configuration/'),
    }

    # --- B. Correccion en el codigo desplegable (5.1) ---------------------------------
    adaptador = 'src/configuration/infrastructure/adapters/edge_sincronizacion_mqtt_adapter.py'
    router = 'src/configuration/infrastructure/routers/umbral_router.py'
    caso_uso = 'src/configuration/application/use_cases/umbrales/sincronizar_umbral_edge.py'
    # Solo la definicion o la instanciacion del stub cuentan: su nombre tambien aparece
    # citado en el docstring del adaptador real que lo reemplazo.
    stub_vivo = git('grep', '-nE',
                    r'(class|=|\()\s*EdgeSincronizacionStubAdapter\s*\(?',
                    'origin/dev', '--', 'src/')
    ev['correccionEnCodigo'] = {
        'adaptadorRealExisteEnOriginDev': git('cat-file', '-t', f'origin/dev:{adaptador}') == 'blob',
        'stubVivoEnOriginDevSrc': [l for l in stub_vivo.splitlines() if l],
        'stubSoloCitadoEnDocstrings': [
            l for l in git('grep', '-l', 'EdgeSincronizacionStubAdapter',
                           'origin/dev', '--', 'src/').splitlines() if l],
        'routerInyectaAdaptadorReal': git(
            'grep', '-n', 'edge_port=EdgeSincronizacionMqttAdapter()', 'origin/dev', '--', router
        ).count('edge_port=EdgeSincronizacionMqttAdapter()'),
        'routerInyectaStub': git(
            'grep', '-c', 'EdgeSincronizacionStubAdapter', 'origin/dev', '--', router),
        'commitsDeLaCorreccion': git(
            'log', '--oneline', '-5', 'origin/dev', '--', adaptador).splitlines(),
        'migracionDestinoEdge': git(
            'log', '--oneline', '-1', 'origin/dev', '--',
            'alembic/versions/a3c9e5d17b42_rf17_destinos_edge_umbrales.py'),
        'estadosContemplados': {
            est: bool(git('grep', '-c', est, 'origin/dev', '--', caso_uso))
            for est in ('APLICADA', 'PENDIENTE', 'NO_CONF', 'FALLO_SINCRONIZACION_EDGE')
        },
        'resolucionGatewayPorEspecie': bool(git(
            'grep', '-c', 'fn_seriales_gateway_edge_por_especie', 'origin/dev', '--', 'src/')),
    }

    # --- C. Runtime DEV (5.2) --------------------------------------------------------
    est_health, cuerpo_health = http('GET', '/health')
    est_openapi, openapi = http('GET', '/openapi.json')
    rutas = (openapi or {}).get('paths', {})
    esquema = (openapi or {}).get('components', {}).get('schemas', {}).get(
        'UmbralAmbientalResponse', {})
    metodos = ('get', 'post', 'patch', 'put', 'delete')
    rutas_rf17 = {r: sorted(k for k in rutas[r] if k in metodos)
                  for r in rutas if 'umbral' in r.lower()}
    quinientos = {}
    for r, ops in rutas.items():
        if 'umbral' not in r.lower():
            continue
        for m, op in ops.items():
            if m in ('post', 'patch') and '500' in op.get('responses', {}):
                quinientos[f'{m.upper()} {r}'] = op['responses']['500'].get('description')
    ev['runtimeDev'] = {
        'base': BASE_DEV, 'broker': BROKER_DEV, 'frontend': FRONT_DEV,
        'health': {'estado': est_health, 'cuerpo': cuerpo_health},
        'openapi': {'estado': est_openapi,
                    'version': (openapi or {}).get('info', {}).get('version')},
        'rutasRf17': rutas_rf17,
        'declara500Sincronizacion': quinientos,
        'camposSincronizacionEnRespuesta': [c for c in esquema.get('properties', {})
                                            if 'sincronizacion' in c],
    }

    # --- D. Actor (5.4) ---------------------------------------------------------------
    clave = os.environ.get('DEV_ADMIN_PASSWORD')
    if not clave:
        ev['actor'] = {'correo': ACTOR, 'loginEstado': None,
                       'error': 'DEV_ADMIN_PASSWORD no disponible en el entorno'}
        ev['gate'] = {'abierto': False,
                      'causa': 'Sin credencial segura del Administrador DEV'}
        ev['fin'] = ahora()
        guardar(ev)
        raise SystemExit('DEV_ADMIN_PASSWORD no disponible: no se continua (0 escrituras).')

    est_login, login = http('POST', '/sesiones/',
                            cuerpo={'correo_electronico': ACTOR, 'contrasena': clave})
    token = (login or {}).get('token')
    ev['actor'] = {'correo': ACTOR, 'loginEstado': est_login,
                   'clavesRespuestaLogin': sorted(login or {}), 'tokenPersistido': False}
    if not token:
        ev['gate'] = {'abierto': False, 'causa': 'Login del Administrador DEV fallido'}
        ev['fin'] = ahora()
        guardar(ev)
        raise SystemExit('login fallido')

    _, yo = http('GET', '/usuarios/me', token)
    _, permisos = http('GET', '/sesiones/me/permisos', token)
    acciones = sorted({p['id_accion'] for p in (permisos or {}).get('permisos', [])
                       if p.get('id_recurso') == 20})
    ev['actor'].update({
        'identidad': {k: (yo or {}).get(k) for k in
                      ('id_usuario', 'nombre', 'apellidos', 'correo_electronico',
                       'nombre_rol', 'estado_cuenta')},
        'permisosRecurso20_umbralesAmbientales': acciones,
        'puedeEjecutarRf17': {1, 2, 3}.issubset(set(acciones)),
    })

    # --- E. Contrato real de propagacion (5.3) ---------------------------------------
    ev['contratoPropagacion'] = {
        'fuente': 'origin/dev (codigo desplegable) + migracion a3c9e5d17b42',
        'resolucionDestino': ('modulo9.fn_seriales_gateway_edge_por_especie(id_especie): '
                              'areas activas de la especie (por infraestructuras.id_especie o '
                              'por activos biologicos vivos) -> dispositivos activos del area -> '
                              'GATEWAY_EDGE propio o el que los atiende '
                              '(id_dispositivo_gateway). Devuelve seriales DISTINCT ordenados.'),
        'endpointInternoBroker': 'POST {MQTT_BROKER_URL}/v1/commands',
        'origenComando': 'umbral',
        'tipoLogicoComando': 'UMBRAL_AMBIENTAL',
        'topicPublicadoPorBroker': 'sgpmp/<serial>/command',
        'mecanismoConfirmacion': 'ACK_UMBRAL del Edge, esperado por el broker (hasta 30 s)',
        'timeoutHttpBackendHaciaBroker': (
            os.environ.get('MQTT_BROKER_HTTP_TIMEOUT', '35') + ' s (MQTT_BROKER_HTTP_TIMEOUT)'),
        'significadoAPLICADA': ('ese Gateway Edge confirmo con ACK_UMBRAL; el broker lo reporta '
                                'en el cuerpo de /v1/commands'),
        'significadoPENDIENTE': ('el broker sabe que el Edge esta desconectado y no publico; '
                                 'para RF-17 es error de sincronizacion -> 500, y el Edge sigue '
                                 'con el umbral anterior'),
        'significadoNO_CONF': 'se intento y fallo (broker caido, timeout, sin ACK) -> 500',
        'significadoSIN_INTEGRACION': ('el ambiente no tiene MQTT_BROKER_URL/TOKEN: no hubo '
                                       'intento, no es error'),
        'consolidacion': ('todos APLICADA -> APLICADA (201/200); algun estado distinto de '
                          'APLICADA/PENDIENTE -> NO_CONF (500); algun PENDIENTE -> PENDIENTE '
                          '(500); sin Gateway o sin broker -> PENDIENTE (201/200)'),
        'payloadRf17': ['id_umbral_ambiental', 'version', 'variable', 'unidad',
                        'valor_min', 'valor_max',
                        'niveles[nivel,limite_inferior,limite_superior]'],
        'persistencia': ('el umbral se guarda en un primer commit, la propagacion corre despues '
                         'y el estado se persiste en un segundo commit; el 500 se lanza DESPUES '
                         'de persistir, por eso el 500 no implica rollback de B'),
        'reenvioAutomaticoAlReconectar': False,
        'secretosRegistrados': False,
    }

    # --- F. Fixture descubierto en runtime (5.5) -------------------------------------
    _, especies = http('GET', '/configuracion/especies?limite=200', token)
    _, variables = http('GET', '/configuracion/variables-ambientales', token)
    _, fincas = http('GET', '/configuracion/fincas?limite=100', token)
    items_esp = (especies or {}).get('items', [])
    activas = [e for e in items_esp if e.get('es_activo')]

    # Las areas exponen la especie como "especie_id" (no "id_especie"). En DEV esta
    # NULL en todas, asi que la fuente operativa del destino son los activos vivos.
    areas: list[dict] = []
    for f in (fincas or {}).get('items', []):
        _, infra = http('GET', '/configuracion/infraestructuras'
                               f"?finca_id={f['id_finca']}&limite=200", token)
        for i in (infra or {}).get('items', []):
            areas.append({'id_infraestructura': i.get('id_infraestructura'),
                          'nombre': i.get('nombre_infraestructura'),
                          'id_finca': i.get('id_finca'),
                          'id_especie': i.get('especie_id'),
                          'es_activo': i.get('es_activo')})

    # El tipo llega solo como id: GATEWAY_EDGE se resuelve por el catalogo.
    _, tipos = http('GET', '/configuracion/tipos-dispositivo-iot', token)
    tipo_por_id = {t['id_tipo_dispositivo']: t['nombre']
                   for t in (tipos or {}).get('items', [])}

    _, disp = http('GET', '/configuracion/dispositivos-iot?limite=500', token)
    dispositivos = [{'id_dispositivo_iot': d.get('id_dispositivo_iot'),
                     'serial': d.get('serial'),
                     'id_infraestructura': d.get('id_infraestructura'),
                     'id_dispositivo_gateway': d.get('id_dispositivo_gateway'),
                     'es_activo': d.get('es_activo'),
                     'id_tipo_dispositivo': d.get('id_tipo_dispositivo'),
                     'tipo': tipo_por_id.get(d.get('id_tipo_dispositivo'))}
                    for d in (disp or {}).get('items', [])]

    # /activos-biologicos pagina en "registros" con total_paginas.
    activos_bio: list[dict] = []
    pagina = 1
    while True:
        _, act = http('GET', f'/activos-biologicos?pagina={pagina}&registros_por_pagina=100',
                      token)
        registros = (act or {}).get('registros', [])
        activos_bio.extend({k: a.get(k) for k in
                            ('id_activo_biologico', 'id_especie', 'id_infraestructura',
                             'nombre_estado')}
                           for a in registros)
        if pagina >= (act or {}).get('total_paginas', 1) or not registros:
            break
        pagina += 1

    # Replica por API de modulo9.fn_seriales_gateway_edge_por_especie
    por_id = {d['id_dispositivo_iot']: d for d in dispositivos}
    areas_activas = {a['id_infraestructura'] for a in areas if a.get('es_activo')}
    muertos = {'INACTIVO', 'CERRADO', 'BAJA'}

    def gateways_de_especie(id_especie: int) -> list[str]:
        areas_esp = {a['id_infraestructura'] for a in areas
                     if a.get('es_activo') and a.get('id_especie') == id_especie}
        areas_esp |= {a['id_infraestructura'] for a in activos_bio
                      if a.get('id_especie') == id_especie
                      and (a.get('nombre_estado') or '').upper() not in muertos
                      and a.get('id_infraestructura') in areas_activas}
        seriales = set()
        for d in dispositivos:
            if not d.get('es_activo') or d.get('id_infraestructura') not in areas_esp:
                continue
            g = por_id.get(d.get('id_dispositivo_gateway') or d['id_dispositivo_iot'])
            if g and g.get('es_activo') and g.get('tipo') == 'GATEWAY_EDGE':
                seriales.add(g['serial'])
        return sorted(seriales)

    mapa = {e['id_especie']: {'nombre': e['nombre'],
                              'gatewaysEdge': gateways_de_especie(e['id_especie'])}
            for e in activas}

    umbrales: list[dict] = []
    for e in activas:
        _, u = http('GET', f"/configuracion/umbrales?id_especie={e['id_especie']}", token)
        umbrales.extend((u or {}).get('items', []))
    activos_umb = [u for u in umbrales if u.get('es_activo')]

    ev['fixture'] = {
        'especiesActivas': [{'id': e['id_especie'], 'nombre': e['nombre']} for e in activas],
        'variablesAmbientales': [{'id': v['id_variable_ambiental'], 'nombre': v['nombre'],
                                  'unidad': v.get('unidad'),
                                  'min': v.get('valor_fisico_min'),
                                  'max': v.get('valor_fisico_max')}
                                 for v in (variables or {}).get('items', [])],
        'fincas': [{'id': f['id_finca'], 'nombre': f.get('nombre'),
                    'es_activo': f.get('es_activo')} for f in (fincas or {}).get('items', [])],
        'areas': areas,
        'dispositivos': dispositivos,
        'gatewaysEdgePorEspecie': mapa,
        'umbralesActivos': [{k: u.get(k) for k in
                             ('id_umbral_ambiental', 'id_especie', 'id_variable_ambiental',
                              'unidad_medida', 'valor_min', 'valor_max', 'es_activo',
                              'fecha_actualizacion', 'estado_sincronizacion',
                              'fecha_ultima_sincronizacion', 'motivo_fallo_sincronizacion')}
                            for u in activos_umb],
        'censoSincronizacion': {
            'total': len(activos_umb),
            'porEstado': {est: len([u for u in activos_umb
                                    if u.get('estado_sincronizacion') == est])
                          for est in sorted({u.get('estado_sincronizacion')
                                             for u in activos_umb} - {None})},
            'conFechaUltimaSincronizacion': len([u for u in activos_umb
                                                 if u.get('fecha_ultima_sincronizacion')]),
        },
        'bovino': {
            'coincidencias': [{'id': e['id_especie'], 'nombre': e['nombre'],
                               'es_activo': e.get('es_activo'),
                               'gatewaysEdge': mapa.get(e['id_especie'], {}).get('gatewaysEdge')}
                              for e in items_esp
                              if 'bovino' in (e.get('nombre') or '').lower()],
        },
    }

    # --- G. Estado del Edge (5.7) ----------------------------------------------------
    especies_con_umbral = {u['id_especie'] for u in activos_umb}
    seriales_con_umbral = sorted({s for idesp in especies_con_umbral
                                  for s in mapa.get(idesp, {}).get('gatewaysEdge', [])})
    gateways: dict[str, dict] = {}
    for d in dispositivos:
        if d.get('tipo') != 'GATEWAY_EDGE' or not d.get('es_activo'):
            continue
        ident = d['id_dispositivo_iot']
        est_e, estado = http('GET', f'/iot/dispositivos/{ident}/estado', token)
        est_c, cred = http('GET',
                           f'/configuracion/dispositivos-iot/{ident}/credencial-mqtt', token)
        gateways[d['serial']] = {
            'id_dispositivo_iot': ident,
            'id_infraestructura': d.get('id_infraestructura'),
            'estadoHttp': est_e,
            'estadoDetalle': sin_secretos(estado if isinstance(estado, dict) else {}),
            'credencialMqttHttp': est_c,
            'credencialMqtt': sin_secretos(cred if isinstance(cred, dict) else {}),
        }

    def clasificar(g: dict) -> str:
        cred = g.get('credencialMqtt') or {}
        if g.get('credencialMqttHttp') != 200 or 'conectada' not in cred:
            return 'EDGE_NO_VERIFICABLE'
        return 'EDGE_ONLINE' if cred.get('conectada') else 'EDGE_OFFLINE'

    for g in gateways.values():
        g['clasificacion'] = clasificar(g)

    online = sorted(s for s, g in gateways.items() if g['clasificacion'] == 'EDGE_ONLINE')
    destino_online = [s for s in seriales_con_umbral if s in online]
    if destino_online:
        global_edge = 'EDGE_ONLINE'
    elif not gateways:
        global_edge = 'EDGE_OFFLINE'
    elif all(g['clasificacion'] == 'EDGE_OFFLINE' for g in gateways.values()):
        global_edge = 'EDGE_OFFLINE'
    else:
        global_edge = 'EDGE_NO_VERIFICABLE'

    ev['edge'] = {
        'senalPrimaria': ('GET /configuracion/dispositivos-iot/{id}/credencial-mqtt -> '
                          '"conectada": conexion MQTT del Gateway reportada por el broker'),
        'senalSecundaria': ('GET /iot/dispositivos/{id}/estado -> estado operativo derivado de '
                            'la antiguedad de la telemetria'),
        'gatewaysEdgeActivos': gateways,
        'gatewaysDestinoDeUmbralesActivos': seriales_con_umbral,
        'gatewaysOnline': online,
        'gatewaysDestinoOnline': destino_online,
        'clasificacionGlobal': global_edge,
        'timestamp': ahora(),
    }

    # --- H. Operacion reversible candidata (5.6) -------------------------------------
    # Un umbral solo es reversible si su PRE pasaria hoy _validar_rangos: varias filas
    # heredadas de DEV tienen valor_max por encima del limite fisico de su variable y
    # niveles que no cubren [valor_min, valor_max], asi que restaurarlas seria
    # rechazado (RANGO_FISICO_INVALIDO / SOLAPAMIENTO_NIVELES) y no habria rollback.
    var_por_id = {v['id_variable_ambiental']: v for v in (variables or {}).get('items', [])}
    umbral_completo = {u['id_umbral_ambiental']: u for u in umbrales}

    def pre_restaurable(u: dict) -> tuple[bool, list[str]]:
        from decimal import Decimal
        motivos: list[str] = []
        var = var_por_id.get(u['id_variable_ambiental'])
        if not var:
            return False, ['variable ambiental no encontrada en el catalogo']
        vmin, vmax = Decimal(str(u['valor_min'])), Decimal(str(u['valor_max']))
        if vmin < Decimal(str(var['valor_fisico_min'])) or vmax > Decimal(str(var['valor_fisico_max'])):
            motivos.append(f"PRE fuera del rango fisico [{var['valor_fisico_min']}, "
                           f"{var['valor_fisico_max']}] de '{var['nombre']}'")
        niveles = u.get('niveles') or []
        if not niveles:
            motivos.append('PRE sin niveles')
            return False, motivos
        orden = sorted(niveles, key=lambda n: Decimal(str(n['limite_inferior'])))
        if Decimal(str(orden[0]['limite_inferior'])) != vmin:
            motivos.append('el primer nivel no comienza en valor_min')
        if Decimal(str(orden[-1]['limite_superior'])) != vmax:
            motivos.append('el ultimo nivel no termina en valor_max')
        for a, b in zip(orden, orden[1:]):
            if Decimal(str(a['limite_superior'])) != Decimal(str(b['limite_inferior'])):
                motivos.append('niveles no contiguos')
                break
        return not motivos, motivos

    candidatos = []
    for u in activos_umb:
        gws = mapa.get(u['id_especie'], {}).get('gatewaysEdge', [])
        if not gws:
            continue
        pre = umbral_completo[u['id_umbral_ambiental']]
        ok, motivos = pre_restaurable(pre)
        candidatos.append({'id_umbral_ambiental': u['id_umbral_ambiental'],
                           'id_especie': u['id_especie'],
                           'especie': mapa[u['id_especie']]['nombre'],
                           'id_variable_ambiental': u['id_variable_ambiental'],
                           'variable': var_por_id.get(u['id_variable_ambiental'], {}).get('nombre'),
                           'rangoFisico': [var_por_id.get(u['id_variable_ambiental'], {}).get('valor_fisico_min'),
                                           var_por_id.get(u['id_variable_ambiental'], {}).get('valor_fisico_max')],
                           'gatewaysEdge': gws,
                           'gatewaysEdgeOnline': [s for s in gws if s in online],
                           'preRestaurable': ok,
                           'motivosNoRestaurable': motivos,
                           'valoresPre': pre})
    aptos = [c for c in candidatos if c['preRestaurable']]
    ev['operacionCandidata'] = {
        'metodo': 'PATCH /configuracion/umbrales/{id_umbral_ambiental}',
        'criterio': ('umbral activo + especie con Gateway Edge real + PRE que hoy pasaria '
                     '_validar_rangos (condicion necesaria para poder restaurarlo)'),
        'planRestauracion': ('tras capturar toda la evidencia de TC-63, PATCH de vuelta a los '
                             'valoresPre exactos, registrado como cleanup; solo si el registro '
                             'sigue en el estado B generado por este RUN'),
        'candidatos': candidatos,
        'aptosReversibles': [c['id_umbral_ambiental'] for c in aptos],
        'seleccionado': aptos[0] if aptos else None,
        'ejecutableAhora': bool(aptos and aptos[0]['gatewaysEdgeOnline']),
    }

    # --- I. Gate de ejecutabilidad de TC-M09-62 (seccion 6) --------------------------
    c = ev['correccionEnCodigo']
    cond = {
        'devDisponible': est_health == 200 and est_openapi == 200,
        'actorValido': bool(ev['actor'].get('puedeEjecutarRf17')),
        'rf17Desplegado': len(rutas_rf17) >= 3 and len(quinientos) >= 2,
        'adaptadorRealNoStub': (bool(c['adaptadorRealExisteEnOriginDev'])
                                and c['routerInyectaAdaptadorReal'] >= 2
                                and not c['stubVivoEnOriginDevSrc']),
        'gatewayDestinoRealIdentificado': bool(seriales_con_umbral),
        'edgeOnline': global_edge == 'EDGE_ONLINE',
        'operacionRf17Valida': ev['operacionCandidata']['seleccionado'] is not None,
        'preCapturado': ev['operacionCandidata']['seleccionado'] is not None,
        'mecanismoConfirmacionIdentificado': True,
        'planRestauracionDefinido': True,
    }
    ev['gate'] = {
        'condiciones': cond,
        'abierto': all(cond.values()),
        'fallidas': [k for k, v in cond.items() if not v],
        'nota': ('brokerConfigurado no se asume: el adaptador devuelve SIN_INTEGRACION si falta '
                 'MQTT_BROKER_URL/TOKEN, y eso se observaria en el estado persistido.'),
    }
    ev['fin'] = ahora()
    guardar(ev)

    print(f'RUN_ID={RUN_ID}')
    print(f'Edge: {global_edge}  online={online}  destino={seriales_con_umbral}')
    print(f"Gate abierto: {ev['gate']['abierto']}  fallidas={ev['gate']['fallidas']}")
    print(f'Evidencia: {OUT / "preflight.json"}')


if __name__ == '__main__':
    main()
