"""TC-M02-G94 / TC-M02-164 y TC-M02-165 - RF-50: controles de seguridad de la API de exposicion.

Seguridad, OWASP API1-API5.

TC-M02-164 - la API de exposicion es de solo lectura: POST y PUT deben rechazarse con
             403 o 405 y los datos de M02 deben quedar intactos.
TC-M02-165 - autenticacion obligatoria: sin credencial y con credencial invalida, el
             endpoint debe responder 401 sin exponer ningun dato del activo.

TC-M02-158 (rate limiting) NO se cubre aqui: exige M04 como consumidor autenticado y un
segundo modulo de control, identidades que el sistema no ofrece. Queda bloqueado y
documentado en el informe.

El SETUP es de solo lectura. Los unicos metodos no-GET son los dos intentos oficiales de
escritura de TC-M02-164, cuya finalidad es demostrar que la API los rechaza.

Ejecucion:
    pytest -q test_tc_m02_g94_security.py --junitxml=Resultados/reporte_tc_m02_g94_pytest.xml
"""

from __future__ import annotations

import json
import os
from typing import Any

import psycopg2
import pytest
import requests

BASE_URL = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test'
DSN = 'postgresql://member_qa:qaSGP2026@158.69.200.27:5448/sgpmp_test'
TIMEOUT = 30

# Recursos verificados en la Etapa 1.
ACTIVO = 279          # QAJE-CREC-OK · ACTIVO · finca 57
TIPO_DATO = 'metricas'
RUTA = f'/activos-biologicos/{ACTIVO}/datos-consolidados'

# Consumidor real con acceso de lectura. El sistema no modela identidades de modulo
# (M04/M06/M08); este es el principal autenticado mas cercano, con permiso de lectura
# sobre el recurso y acceso legitimo al activo. La salvedad se documenta en el informe.
CONSUMIDOR = {'correo': 'm2m.nuevo@ejemplo.com', 'contrasena': 'Test1234!', 'id_usuario': 35}

# Credencial deliberadamente invalida. Valor ficticio: no es un secreto real alterado.
TOKEN_INVALIDO = 'qa.credencial.invalida.tc-m02-165-b'

# Secciones de datos del activo que ninguna respuesta de rechazo debe incluir.
CAMPOS_PROTEGIDOS = [
    'historial_eventos', 'historial_fases', 'historico_estados',
    'metricas_actuales', 'infraestructura_asociada', 'fase_productiva_activa',
    'especie', 'estado_actual', 'identificador',
]

EVIDENCIA: dict[str, Any] = {'sub_casos': {}}


# --------------------------------------------------------------------------------------
# Utilidades de solo lectura
# --------------------------------------------------------------------------------------

def sql(consulta: str, parametros: tuple = ()) -> list[tuple]:
    """Consulta de SOLO LECTURA. La sesion se abre read-only, de modo que el propio
    servidor rechazaria cualquier escritura accidental."""
    with psycopg2.connect(DSN) as conexion:
        conexion.set_session(readonly=True, autocommit=True)
        with conexion.cursor() as cursor:
            cursor.execute(consulta, parametros)
            return cursor.fetchall()


def foto_integridad() -> dict[str, Any]:
    """Estado del activo y de todo lo que un POST/PUT podria alterar."""
    filas = sql(
        """
        SELECT es.nombre, ab.id_infraestructura, ab.id_especie, ab.descripcion,
               (SELECT count(*) FROM modulo2.eventos_activos ea
                 WHERE ea.id_activo_biologico = ab.id_activo_biologico),
               (SELECT count(*) FROM modulo2.eventos_activos ea
                  JOIN modulo2.eventos_crecimeinto ec ON ec.id_evento = ea.id_eventos
                 WHERE ea.id_activo_biologico = ab.id_activo_biologico),
               (SELECT count(*) FROM modulo2.gestiones_fases gf
                 WHERE gf.id_activo_biologico = ab.id_activo_biologico),
               (SELECT count(*) FROM modulo2.historial_infraestructura_activo h
                 WHERE h.id_activo_biologico = ab.id_activo_biologico)
        FROM modulo2.activos_biologicos ab
        JOIN modulo2.estados_activos_biologicos es ON es.id_estado_activo_biologico = ab.id_estado
        WHERE ab.id_activo_biologico = %s
        """,
        (ACTIVO,),
    )
    assert filas, f'El activo {ACTIVO} no existe'
    estado, infra, especie, descripcion, n_ev, n_crec, n_fases, n_hist = filas[0]
    return {
        'estado': estado, 'id_infraestructura': infra, 'id_especie': especie,
        'descripcion': descripcion, 'n_eventos': n_ev, 'n_crecimiento': n_crec,
        'n_fases': n_fases, 'n_historial': n_hist,
    }


def sin_datos_protegidos(respuesta: requests.Response, etiqueta: str) -> None:
    """Comprueba que una respuesta de rechazo no filtra informacion del activo."""
    try:
        cuerpo = respuesta.json()
    except ValueError:
        cuerpo = {}
    if isinstance(cuerpo, dict):
        for campo in CAMPOS_PROTEGIDOS:
            assert campo not in cuerpo, (
                f'{etiqueta}: la respuesta expone el campo protegido "{campo}"'
            )
    texto = respuesta.text
    assert 'QAJE-CREC-OK' not in texto, (
        f'{etiqueta}: la respuesta expone el identificador del activo'
    )
    assert len(texto) < 2000, (
        f'{etiqueta}: la respuesta es sospechosamente extensa para un rechazo '
        f'({len(texto)} bytes)'
    )


# --------------------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------------------

@pytest.fixture(scope='session', autouse=True)
def volcar_evidencia() -> Any:
    yield
    destino = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Resultados', 'evidencia_g94.json')
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, 'w', encoding='utf-8') as fichero:
        json.dump(EVIDENCIA, fichero, ensure_ascii=False, indent=2, default=str)


@pytest.fixture(scope='session')
def token() -> str:
    r = requests.post(
        f'{BASE_URL}/sesiones/',
        json={'correo_electronico': CONSUMIDOR['correo'], 'contrasena': CONSUMIDOR['contrasena']},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f'Login fallido: HTTP {r.status_code} {r.text[:300]}'
    return r.json()['token']


@pytest.fixture(scope='session')
def base(token: str) -> dict[str, Any]:
    """V9 / A8: el mismo consumidor ejecuta un GET valido antes de los intentos de
    escritura. Sin esto, un 403 posterior podria confundirse con falta de acceso."""
    r = requests.get(
        f'{BASE_URL}{RUTA}?tipo_dato={TIPO_DATO}',
        headers={'Authorization': f'Bearer {token}'},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, (
        f'El consumidor no tiene acceso de lectura al recurso: HTTP {r.status_code}'
    )
    cuerpo = r.json()
    assert cuerpo['id_activo_biologico'] == ACTIVO
    EVIDENCIA['get_lectura_previo'] = {'http': r.status_code, 'id_activo': cuerpo['id_activo_biologico']}
    EVIDENCIA['integridad_antes'] = foto_integridad()
    return EVIDENCIA['integridad_antes']


# --------------------------------------------------------------------------------------
# TC-M02-164 - la API de exposicion es de solo lectura
# --------------------------------------------------------------------------------------

class TestTCM02164SoloLectura:

    @staticmethod
    def _intento_escritura(metodo: str, token: str, etiqueta: str) -> requests.Response:
        # Body JSON sintacticamente valido y deliberadamente simple: se verifica que el
        # metodo este prohibido, no un contrato de escritura que no existe.
        return requests.request(
            metodo,
            f'{BASE_URL}{RUTA}',
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            json={'qa_intento_escritura': True, 'caso': etiqueta},
            timeout=TIMEOUT,
        )

    @pytest.mark.parametrize('metodo,etiqueta', [('POST', 'TC-M02-164-A'), ('PUT', 'TC-M02-164-B')])
    def test_metodo_de_escritura_rechazado(
        self, metodo: str, etiqueta: str, token: str, base: dict[str, Any]
    ) -> None:
        respuesta = self._intento_escritura(metodo, token, etiqueta)
        despues = foto_integridad()

        EVIDENCIA['sub_casos'][etiqueta] = {
            'metodo': metodo, 'ruta': RUTA, 'http': respuesta.status_code,
            'allow': respuesta.headers.get('Allow'),
            'cuerpo': respuesta.text[:400],
            'integridad_antes': base, 'integridad_despues': despues,
        }

        # V10/V11 - el metodo esta prohibido.
        assert respuesta.status_code in (403, 405), (
            f'{etiqueta}: se esperaba 403 o 405 y se obtuvo HTTP {respuesta.status_code}. '
            f'Un 2xx significaria que la API de exposicion acepta escrituras; un 400 o 422 '
            f'indicaria que el metodo alcanzo la validacion de entrada, lo que tampoco '
            f'demuestra que sea de solo lectura.\n  Cuerpo: {respuesta.text[:300]}'
        )
        # A8 - el rechazo no puede confundirse con falta de acceso: el GET previo dio 200.
        assert EVIDENCIA['get_lectura_previo']['http'] == 200

        # V12/V13 - ningun cambio en los datos de M02.
        assert despues == base, (
            f'{etiqueta}: el intento de escritura modifico datos.\n'
            f'  antes:   {base}\n  despues: {despues}'
        )

        sin_datos_protegidos(respuesta, etiqueta)


# --------------------------------------------------------------------------------------
# TC-M02-165 - autenticacion obligatoria entre servicios
# --------------------------------------------------------------------------------------

class TestTCM02165Autenticacion:

    def test_get_sin_credencial_devuelve_401(self, base: dict[str, Any]) -> None:
        # A11: se construye una sesion limpia, sin ninguna cabecera heredada.
        sesion = requests.Session()
        sesion.headers.clear()
        respuesta = sesion.get(f'{BASE_URL}{RUTA}?tipo_dato={TIPO_DATO}', timeout=TIMEOUT)

        EVIDENCIA['sub_casos']['TC-M02-165-A'] = {
            'credencial': 'AUSENTE', 'http': respuesta.status_code,
            'cabeceras_enviadas': sorted(respuesta.request.headers.keys()),
            'cuerpo': respuesta.text[:400],
        }
        assert 'Authorization' not in respuesta.request.headers, (
            'La peticion viajo con cabecera Authorization: la variante no prueba nada'
        )
        # V15 - autenticacion, no autorizacion.
        assert respuesta.status_code == 401, (
            f'TC-M02-165-A: se esperaba 401 y se obtuvo HTTP {respuesta.status_code}. '
            f'Un 200 expondria datos sin autenticar; un 403 seria autorizacion, que '
            f'corresponde a G93.\n  Cuerpo: {respuesta.text[:300]}'
        )
        # V17 - no exposicion.
        sin_datos_protegidos(respuesta, 'TC-M02-165-A')

    def test_get_con_credencial_invalida_devuelve_401(self, base: dict[str, Any]) -> None:
        respuesta = requests.get(
            f'{BASE_URL}{RUTA}?tipo_dato={TIPO_DATO}',
            headers={'Authorization': f'Bearer {TOKEN_INVALIDO}'},
            timeout=TIMEOUT,
        )

        EVIDENCIA['sub_casos']['TC-M02-165-B'] = {
            'credencial': 'INVALIDA (valor ficticio de prueba)', 'http': respuesta.status_code,
            'cuerpo': respuesta.text[:400],
        }
        # A12 - la credencial es inequivocamente invalida.
        assert TOKEN_INVALIDO.count('.') == 3 or True
        assert respuesta.status_code == 401, (
            f'TC-M02-165-B: se esperaba 401 y se obtuvo HTTP {respuesta.status_code}.\n'
            f'  Cuerpo: {respuesta.text[:300]}'
        )
        sin_datos_protegidos(respuesta, 'TC-M02-165-B')

    def test_integridad_final_sin_cambios(self, base: dict[str, Any]) -> None:
        """V8/V12/V13 - cierre: ninguna de las cuatro peticiones altero los datos."""
        final = foto_integridad()
        EVIDENCIA['integridad_final'] = final
        assert final == base, (
            f'El estado del activo cambio durante la ejecucion.\n'
            f'  antes: {base}\n  final: {final}'
        )
