"""TC-M02-G82 / TC-M02-142 - RF-48: control de concurrencia en la transferencia interna.

Seguridad, OWASP API6 (Sensitive Business Flows).

Por cada actor de RF-48 (Productor y Administrador) se libera desde una barrera comun un par
de POST simultaneos sobre el MISMO activo hacia DOS destinos validos y distintos. El resultado
correcto es exactamente una respuesta de exito y una de conflicto E-01, con una unica ubicacion
final, un unico movimiento nuevo y contadores actualizados una sola vez.

No se presupone cual de las dos solicitudes gana: el ganador se determina dinamicamente a
partir de las respuestas.

El SETUP es de solo lectura: SELECT, GET y login. Las unicas escrituras son las 4 peticiones
oficiales del caso, de las cuales el sistema debe aceptar exactamente 2 (una por ciclo).

Ejecucion:
    pytest -q test_tc_m02_g82.py --junitxml=Resultados/reporte_tc_m02_g82.xml
"""

from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import psycopg2
import pytest
import requests

BASE_URL = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test'
DSN = 'postgresql://member_qa:qaSGP2026@158.69.200.27:5448/sgpmp_test'
TIMEOUT = 30

# El contrato declara 201 como respuesta de exito del POST de transferencia, y esa es la
# respuesta real observada. La ficha del caso enuncia "HTTP 200"; la discrepancia se
# documenta en el informe y aqui se acepta cualquier 2xx como exito, sin relajar el criterio
# sustantivo: debe haber exactamente un exito y exactamente un 409 E-01.
EXITO_CONTRACTUAL = 201


@dataclass
class Escenario:
    clave: str
    actor: str
    correo: str
    contrasena: str
    id_usuario: int
    id_activo: int
    destino_a: int
    destino_b: int
    # Rellenados en tiempo de ejecucion.
    token: str = ''
    origen: int = -1
    antes: dict[str, Any] = field(default_factory=dict)
    despues: dict[str, Any] = field(default_factory=dict)
    respuestas: dict[str, Any] = field(default_factory=dict)
    tiempos: dict[str, float] = field(default_factory=dict)


# Recursos de la finca 57, verificados por SELECT en la Etapa 1. Cada actor usa un activo
# distinto: cada ciclo produce una transferencia efectiva, y compartir activo contaminaria
# el segundo escenario.
ESCENARIOS = [
    Escenario('productor', 'Productor', 'm2m.nuevo@ejemplo.com', 'Test1234!', 35,
              id_activo=290, destino_a=47, destino_b=51),   # QAJE-TRF-CONC, origen 48
    Escenario('admin', 'Administrador', 'admin@pecuaria.co', 'Test1234!', 1,
              id_activo=294, destino_a=48, destino_b=47),   # QAJE-TRF-REGLAS, origen 51
]

POR_CLAVE = {e.clave: e for e in ESCENARIOS}

EVIDENCIA: dict[str, Any] = {'ciclos': {}}


# --------------------------------------------------------------------------------------
# Utilidades de solo lectura
# --------------------------------------------------------------------------------------

def sql(consulta: str, parametros: tuple = ()) -> list[tuple]:
    """Consulta de SOLO LECTURA. La sesion se abre read-only, de modo que el propio servidor
    rechazaria cualquier escritura accidental."""
    with psycopg2.connect(DSN) as conexion:
        conexion.set_session(readonly=True, autocommit=True)
        with conexion.cursor() as cursor:
            cursor.execute(consulta, parametros)
            return cursor.fetchall()


def ocupacion(id_infra: int) -> int:
    """Reproduce exactamente el calculo del backend (infraestructura_m09_adapter)."""
    filas = sql(
        """
        SELECT COALESCE(SUM(CASE WHEN ab.tipo = 'INDIVIDUAL' THEN 1
                                 ELSE COALESCE(dp.cantidad_actual, 0) END), 0)
        FROM modulo2.activos_biologicos ab
        LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales dp
               ON dp.id_activo_biologico = ab.id_activo_biologico
        WHERE ab.id_infraestructura = %s AND ab.id_estado NOT IN (5, 6)
        """,
        (id_infra,),
    )
    return int(filas[0][0])


def infraestructura(id_infra: int) -> dict[str, Any]:
    filas = sql(
        'SELECT id_finca, nombre, tipo, es_activo, capacidad_maxima, id_especie '
        'FROM modulo9.infraestructuras WHERE id_infraestructura = %s',
        (id_infra,),
    )
    assert filas, f'La infraestructura {id_infra} no existe'
    finca, nombre, tipo, activa, capacidad, especie = filas[0]
    return {
        'id': id_infra, 'id_finca': finca, 'nombre': nombre, 'tipo': tipo,
        'es_activo': activa, 'capacidad_maxima': capacidad, 'id_especie': especie,
        'ocupacion': ocupacion(id_infra),
    }


def estado_activo(id_activo: int) -> dict[str, Any]:
    filas = sql(
        """
        SELECT es.nombre, ab.tipo, ab.id_especie, ab.id_infraestructura,
               (SELECT count(*) FROM modulo2.historial_infraestructura_activo h
                 WHERE h.id_activo_biologico = ab.id_activo_biologico),
               (SELECT count(*) FROM modulo2.historial_infraestructura_activo h
                 WHERE h.id_activo_biologico = ab.id_activo_biologico AND h.fecha_fin IS NULL),
               (SELECT count(*) FROM modulo2.movimientos m
                 WHERE m.id_activo_biologico = ab.id_activo_biologico)
        FROM modulo2.activos_biologicos ab
        JOIN modulo2.estados_activos_biologicos es ON es.id_estado_activo_biologico = ab.id_estado
        WHERE ab.id_activo_biologico = %s
        """,
        (id_activo,),
    )
    assert filas, f'El activo {id_activo} no existe'
    nombre, tipo, especie, infra, n_hist, asoc, n_mov = filas[0]
    return {
        'estado': nombre, 'tipo': tipo, 'id_especie': especie, 'id_infraestructura': infra,
        'n_historial': n_hist, 'asociaciones_vigentes': asoc, 'n_movimientos': n_mov,
    }


def autenticar(e: Escenario) -> str:
    r = requests.post(
        f'{BASE_URL}/sesiones/',
        json={'correo_electronico': e.correo, 'contrasena': e.contrasena},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f'Login fallido para {e.actor}: HTTP {r.status_code} {r.text[:300]}'
    return r.json()['token']


def cuerpo(destino: int, etiqueta: str) -> dict[str, Any]:
    """Payloads identicos en todo salvo el destino, como exige la seccion 12."""
    return {
        'infraestructura_origen_id': None,   # se completa con el origen vigente
        'infraestructura_destino_id': destino,
        'fecha_transferencia': date.today().isoformat(),
        'motivo_transferencia': f'TC-M02-142 concurrencia {etiqueta}',
    }


# --------------------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------------------

@pytest.fixture(scope='session', autouse=True)
def volcar_evidencia() -> Any:
    yield
    destino = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Resultados', 'evidencia_g82.json')
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, 'w', encoding='utf-8') as fichero:
        json.dump(EVIDENCIA, fichero, ensure_ascii=False, indent=2, default=str)


@pytest.fixture(scope='session')
def contrato() -> dict[str, Any]:
    r = requests.get(f'{BASE_URL}/openapi.json', timeout=TIMEOUT)
    assert r.status_code == 200, 'El backend TEST HTTPS no responde 200 en openapi.json'
    return r.json()


@pytest.fixture(scope='session', params=[e.clave for e in ESCENARIOS])
def escenario(request: pytest.FixtureRequest, contrato: dict[str, Any]) -> Escenario:
    """Etapa 1 por ciclo: revision de datos y captura del estado ANTES. 0 escrituras."""
    e = POR_CLAVE[request.param]

    ruta = '/activos-biologicos/{id_activo}/transferencias'
    assert ruta in contrato['paths'], 'El contrato no declara el endpoint de transferencias'
    assert '409' in contrato['paths'][ruta]['post']['responses'], 'El contrato no declara 409'

    e.token = autenticar(e)

    # El origen se lee inmediatamente antes del ciclo (hipotesis A12): TEST es un ambiente
    # compartido y el activo podria haber sido movido por otra sesion.
    activo = estado_activo(e.id_activo)
    assert activo['estado'] == 'ACTIVO', f"El activo {e.id_activo} no esta ACTIVO ({activo['estado']})"
    assert activo['tipo'] == 'INDIVIDUAL', 'El escenario asume un activo INDIVIDUAL (cantidad = 1)'
    e.origen = activo['id_infraestructura']

    cab = {'Authorization': f'Bearer {e.token}'}
    acceso = requests.get(f'{BASE_URL}/activos-biologicos/{e.id_activo}', headers=cab, timeout=TIMEOUT)
    assert acceso.status_code == 200, (
        f'{e.actor} no tiene acceso legitimo al activo {e.id_activo}: HTTP {acceso.status_code}'
    )

    origen = infraestructura(e.origen)
    a = infraestructura(e.destino_a)
    b = infraestructura(e.destino_b)

    # Seccion 10: validacion previa de los dos destinos.
    for etiqueta, d in (('A', a), ('B', b)):
        assert d['id'] != e.origen, f'El destino {etiqueta} coincide con el origen'
        assert d['es_activo'], f'El destino {etiqueta} ({d["id"]}) no esta activo'
        assert d['id_finca'] == origen['id_finca'], f'El destino {etiqueta} esta en otra finca'
        # C1 - especie: la infraestructura sin especie declarada admite cualquiera.
        assert d['id_especie'] is None or d['id_especie'] == activo['id_especie'], (
            f'C1 no se cumple en el destino {etiqueta}'
        )
        # C2 - tipo: un bovino INDIVIDUAL corresponde a un Corral, no a un Estanque ni a un Galpon.
        assert d['tipo'] == 'Corral', f'C2 no se cumple en el destino {etiqueta} (tipo {d["tipo"]})'
        # C3 - capacidad: cabe una unidad mas.
        assert d['capacidad_maxima'] is None or d['ocupacion'] + 1 <= d['capacidad_maxima'], (
            f'C3 no se cumple en el destino {etiqueta}: '
            f'{d["ocupacion"]} + 1 > {d["capacidad_maxima"]}'
        )
    assert a['id'] != b['id'], 'Los destinos A y B deben ser distintos'

    # Ambos destinos deben figurar en el listado de disponibles.
    disp = requests.get(
        f'{BASE_URL}/activos-biologicos/{e.id_activo}/transferencias/disponibles',
        headers=cab, timeout=TIMEOUT,
    )
    assert disp.status_code == 200
    ids_disponibles = {i['id_infraestructura'] for i in disp.json()}
    assert e.destino_a in ids_disponibles, f'El destino A ({e.destino_a}) no figura como disponible'
    assert e.destino_b in ids_disponibles, f'El destino B ({e.destino_b}) no figura como disponible'

    # Sin transferencia concurrente previa: una peticion aislada no debe devolver E-01.
    # No se envia ningun POST de sondeo; la comprobacion se hace sobre la fila del activo,
    # que estaria bloqueada si hubiese una operacion en curso.
    assert activo['asociaciones_vigentes'] == 1, (
        f'El activo {e.id_activo} tiene {activo["asociaciones_vigentes"]} asociaciones vigentes; '
        'se esperaba exactamente una'
    )

    e.antes = {
        'activo': activo,
        'origen': origen,
        'destino_a': a,
        'destino_b': b,
        'movimientos_globales': int(sql('SELECT count(*) FROM modulo2.movimientos')[0][0]),
        'max_id_movimiento': int(sql('SELECT COALESCE(max(id_movimiento), 0) FROM modulo2.movimientos')[0][0]),
        'historial_global': int(sql('SELECT count(*) FROM modulo2.historial_infraestructura_activo')[0][0]),
    }
    return e


# --------------------------------------------------------------------------------------
# Ciclo concurrente
# --------------------------------------------------------------------------------------

def _disparar(e: Escenario, destino: int, etiqueta: str, barrera: threading.Barrier) -> dict[str, Any]:
    """Prepara la peticion, espera en la barrera y la envia. Registra tiempos monotonicos."""
    sesion = requests.Session()
    payload = cuerpo(destino, etiqueta)
    payload['infraestructura_origen_id'] = e.origen
    cab = {'Authorization': f'Bearer {e.token}', 'Content-Type': 'application/json'}

    barrera.wait()                       # punto de sincronizacion comun
    inicio = time.monotonic()
    respuesta = sesion.post(
        f'{BASE_URL}/activos-biologicos/{e.id_activo}/transferencias',
        headers=cab, json=payload, timeout=TIMEOUT,
    )
    fin = time.monotonic()
    try:
        json_cuerpo = respuesta.json()
    except ValueError:
        json_cuerpo = {'raw': respuesta.text[:500]}
    return {
        'etiqueta': etiqueta, 'destino': destino, 'http': respuesta.status_code,
        'cuerpo': json_cuerpo, 'payload': payload, 'inicio': inicio, 'fin': fin,
    }


class TestTCM02142:
    """Un ciclo concurrente independiente por actor."""

    def test_concurrencia(self, escenario: Escenario) -> None:
        e = escenario
        barrera = threading.Barrier(2)

        # --- Paso 7/8: los dos POST se liberan desde la misma barrera ---
        t_barrera = time.monotonic()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futuro_a = pool.submit(_disparar, e, e.destino_a, 'A', barrera)
            futuro_b = pool.submit(_disparar, e, e.destino_b, 'B', barrera)
            ra = futuro_a.result()
            rb = futuro_b.result()

        e.respuestas = {'A': ra, 'B': rb}
        e.tiempos = {
            'barrera': t_barrera,
            'inicio_a': ra['inicio'] - t_barrera, 'fin_a': ra['fin'] - t_barrera,
            'inicio_b': rb['inicio'] - t_barrera, 'fin_b': rb['fin'] - t_barrera,
        }

        # --- Evidencia de concurrencia real (seccion 13) ---
        solapan = ra['inicio'] < rb['fin'] and rb['inicio'] < ra['fin']
        assert solapan, (
            'Las dos solicitudes no se solaparon en el tiempo: la corrida fue secuencial y no '
            'sirve como evidencia de TC-M02-142.\n'
            f"  A: {ra['inicio'] - t_barrera:.4f}s -> {ra['fin'] - t_barrera:.4f}s\n"
            f"  B: {rb['inicio'] - t_barrera:.4f}s -> {rb['fin'] - t_barrera:.4f}s"
        )

        # --- C1: distribucion de codigos, sin presuponer el ganador ---
        codigos = sorted([ra['http'], rb['http']])
        exitos = [r for r in (ra, rb) if 200 <= r['http'] < 300]
        conflictos = [r for r in (ra, rb) if r['http'] == 409]

        assert len(exitos) == 1 and len(conflictos) == 1, (
            f'Se esperaba exactamente un exito y un conflicto E-01; se obtuvo {codigos}.\n'
            f"  A -> HTTP {ra['http']}: {json.dumps(ra['cuerpo'], ensure_ascii=False)[:200]}\n"
            f"  B -> HTTP {rb['http']}: {json.dumps(rb['cuerpo'], ensure_ascii=False)[:200]}"
        )

        ganador, perdedor = exitos[0], conflictos[0]
        e.respuestas['ganador'] = ganador['etiqueta']
        e.respuestas['perdedor'] = perdedor['etiqueta']

        assert ganador['http'] == EXITO_CONTRACTUAL, (
            f"El exito llego con HTTP {ganador['http']}; el contrato declara {EXITO_CONTRACTUAL}"
        )

        # --- C2: el 409 corresponde a E-01 y no a otra validacion ---
        assert perdedor['cuerpo'].get('error_code') == 'TRANSFERENCIA_CONCURRENTE', (
            f"El 409 no corresponde a E-01: {json.dumps(perdedor['cuerpo'], ensure_ascii=False)[:300]}"
        )
        mensaje = str(perdedor['cuerpo'].get('message', '')).lower()
        assert 'transferencia en progreso' in mensaje, (
            f'El mensaje del 409 no identifica la operacion en progreso: {mensaje}'
        )

        # --- C3: el ganador devuelve una transferencia valida ---
        assert 'id_movimiento' in ganador['cuerpo'], 'El exito no devuelve identificador de movimiento'
        id_movimiento = ganador['cuerpo']['id_movimiento']

        # --- Etapa 3: verificacion del estado final ---
        despues_activo = estado_activo(e.id_activo)
        destino_ganador = ganador['destino']
        destino_perdedor = perdedor['destino']
        e.despues = {
            'activo': despues_activo,
            'origen': infraestructura(e.origen),
            'ganador': infraestructura(destino_ganador),
            'perdedor': infraestructura(destino_perdedor),
            'id_movimiento': id_movimiento,
        }

        antes = e.antes
        cantidad = 1  # activo INDIVIDUAL

        # V2 - el activo queda en el destino ganador.
        assert despues_activo['id_infraestructura'] == destino_ganador, (
            f'El activo quedo en la infraestructura {despues_activo["id_infraestructura"]} '
            f'en vez de en el destino ganador {destino_ganador}'
        )

        # V3 - una sola asociacion vigente.
        assert despues_activo['asociaciones_vigentes'] == 1, (
            f'Quedaron {despues_activo["asociaciones_vigentes"]} asociaciones vigentes; '
            'no puede existir doble asociacion'
        )
        vigentes = sql(
            'SELECT id_infraestructura FROM modulo2.historial_infraestructura_activo '
            'WHERE id_activo_biologico = %s AND fecha_fin IS NULL',
            (e.id_activo,),
        )
        assert [f[0] for f in vigentes] == [destino_ganador], (
            f'La asociacion vigente apunta a {[f[0] for f in vigentes]} y no al destino ganador'
        )

        # V5 - exactamente un movimiento nuevo para este activo.
        assert despues_activo['n_movimientos'] == antes['activo']['n_movimientos'] + 1, (
            f'El activo paso de {antes["activo"]["n_movimientos"]} a '
            f'{despues_activo["n_movimientos"]} movimientos; se esperaba exactamente uno mas'
        )

        # V6 - el movimiento registrado es coherente con la peticion ganadora.
        mov = sql(
            'SELECT id_activo_biologico, id_infraestructura_origen, id_infraestructura_destino, '
            '       id_usuario, motivo_transferencia '
            'FROM modulo2.movimientos WHERE id_movimiento = %s',
            (id_movimiento,),
        )
        assert mov, f'El movimiento {id_movimiento} no existe en base de datos'
        m_activo, m_origen, m_destino, m_usuario, m_motivo = mov[0]
        assert m_activo == e.id_activo
        assert m_origen == e.origen, f'El movimiento registra origen {m_origen} y no {e.origen}'
        assert m_destino == destino_ganador, (
            f'El movimiento registra destino {m_destino} y no el ganador {destino_ganador}'
        )
        assert m_usuario == e.id_usuario, (
            f'El movimiento quedo asociado al usuario {m_usuario} y no a {e.actor} ({e.id_usuario})'
        )
        assert m_motivo == ganador['payload']['motivo_transferencia'], (
            'El motivo registrado no corresponde al de la peticion ganadora'
        )

        # V8 - no existe un segundo movimiento hacia el destino perdedor.
        perdedores = sql(
            'SELECT count(*) FROM modulo2.movimientos '
            'WHERE id_activo_biologico = %s AND id_infraestructura_destino = %s '
            '  AND id_movimiento > %s',
            (e.id_activo, destino_perdedor, antes['max_id_movimiento']),
        )
        assert int(perdedores[0][0]) == 0, (
            'La solicitud rechazada dejo un movimiento hacia el destino perdedor'
        )

        # V7 - la ocupacion del origen baja exactamente una vez.
        assert e.despues['origen']['ocupacion'] == antes['origen']['ocupacion'] - cantidad, (
            f'Ocupacion del origen {e.origen}: {antes["origen"]["ocupacion"]} -> '
            f'{e.despues["origen"]["ocupacion"]}; se esperaba -{cantidad}'
        )

        # V8 - la ocupacion del destino ganador sube exactamente una vez.
        ocupacion_ganador_antes = (
            antes['destino_a']['ocupacion'] if destino_ganador == e.destino_a
            else antes['destino_b']['ocupacion']
        )
        assert e.despues['ganador']['ocupacion'] == ocupacion_ganador_antes + cantidad, (
            f'Ocupacion del destino ganador {destino_ganador}: {ocupacion_ganador_antes} -> '
            f'{e.despues["ganador"]["ocupacion"]}; se esperaba +{cantidad}'
        )

        # V9 - la ocupacion del destino perdedor no cambia.
        ocupacion_perdedor_antes = (
            antes['destino_a']['ocupacion'] if destino_perdedor == e.destino_a
            else antes['destino_b']['ocupacion']
        )
        assert e.despues['perdedor']['ocupacion'] == ocupacion_perdedor_antes, (
            f'Ocupacion del destino perdedor {destino_perdedor}: {ocupacion_perdedor_antes} -> '
            f'{e.despues["perdedor"]["ocupacion"]}; no debia cambiar'
        )

        # V11 - la transferencia ganadora queda auditada en la vista de RF-52.
        auditoria = sql(
            'SELECT id_movimiento, id_activo_biologico, id_infraestructura_destino, id_usuario '
            'FROM modulo2.vw_rf52_auditoria_transferencias_internas WHERE id_movimiento = %s',
            (id_movimiento,),
        )
        assert auditoria, f'El movimiento {id_movimiento} no aparece en la auditoria de RF-52'
        assert auditoria[0][2] == destino_ganador and auditoria[0][3] == e.id_usuario

        # V12 - la trazabilidad previa permanece: el historial solo crece en una fila.
        assert despues_activo['n_historial'] == antes['activo']['n_historial'] + 1, (
            f'El historial del activo paso de {antes["activo"]["n_historial"]} a '
            f'{despues_activo["n_historial"]} filas; se esperaba exactamente una mas'
        )

        EVIDENCIA['ciclos'][e.clave] = {
            'actor': e.actor, 'id_usuario': e.id_usuario, 'id_activo': e.id_activo,
            'origen': e.origen, 'destino_a': e.destino_a, 'destino_b': e.destino_b,
            'tiempos': e.tiempos, 'solapan': solapan,
            'respuestas': {
                'A': {'destino': ra['destino'], 'http': ra['http'], 'cuerpo': ra['cuerpo']},
                'B': {'destino': rb['destino'], 'http': rb['http'], 'cuerpo': rb['cuerpo']},
            },
            'ganador': ganador['etiqueta'], 'destino_ganador': destino_ganador,
            'perdedor': perdedor['etiqueta'], 'destino_perdedor': destino_perdedor,
            'id_movimiento': id_movimiento,
            'antes': antes, 'despues': e.despues,
        }
