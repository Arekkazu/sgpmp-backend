"""TC-M02-G97 REFORMULADO / TC-M02-314 - RF-51: falta de autorizacion de lectura.

Definicion vigente (§2, §19): un usuario **autenticado** que NO posee permiso de
lectura sobre el recurso requerido por `/indicadores` solicita un indicador y debe
recibir 403, sin que se exponga el indicador ni las variables del calculo.

Este Pytest demuestra conjuntamente (§21):
  1. el usuario es autenticable con credencial legitima;
  2. su rol NO tiene READ (recurso 29, accion 2) -> por SELECT sobre el RBAC real;
  3. el activo existe;
  4. la solicitud oficial devuelve 403 por autorizacion (ACCESO_DENEGADO);
  5. la respuesta no expone indicador ni variables_usadas.

NO modifica permisos, roles ni usuarios. Si el 403 exigiera revocar un permiso, el
test estaria mal disenado (§21): aqui la falta de READ es real y preexistente.

Recurso y accion se toman del codigo del router (fuente de verdad), no de valores
asumidos. Todo es de solo lectura: SELECT sobre TEST con `readonly=True` y GET/POST
sobre la API. Cero escrituras de QA.

Ejecucion:
    .venv\\Scripts\\python.exe -m pytest tests/Test_Testing/Test_Modulo2/RF-51/TC-M02-G97/test_tc_m02_g97.py \\
        -v --junitxml=Resultados/reporte_tc_m02_g97_pytest.xml
"""
from __future__ import annotations

from typing import Any

import psycopg2
import pytest
import requests

BASE_URL = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test'

BD = dict(host='158.69.200.27', port=5448, dbname='sgpmp_test',
          user='member_qa', password='qaSGP2026')

# AUTH_NO_READ: usuario real, rol sin READ, cuenta Activa, credencial legitima de TEST.
USUARIO_SIN_READ = {'correo_electronico': 'contador@pecuaria.co', 'contrasena': 'Test1234!'}
ROL_ESPERADO = 5           # Contador
ACTIVO_314 = 279           # activo existente y accesible; el unico motivo de rechazo sera autorizacion
ESTADO_CUENTA_ACTIVA = 2

RECURSO_INDICADORES = 29   # se valida contra el codigo del router mas abajo
ACCION_READ = 2
RUTA = f'/activos-biologicos/{ACTIVO_314}/indicadores'


@pytest.fixture(scope='module')
def bd():
    conexion = psycopg2.connect(**BD)
    conexion.set_session(readonly=True, autocommit=True)
    yield conexion
    conexion.close()


def _consultar(bd, sql: str, parametros: tuple = ()) -> list[tuple[Any, ...]]:
    with bd.cursor() as cur:
        cur.execute(sql, parametros)
        return cur.fetchall()


@pytest.fixture(scope='module')
def identidad_sin_read(bd) -> dict[str, Any]:
    """id_usuario, id_rol y estado de cuenta del usuario AUTH_NO_READ, leidos de BD."""
    filas = _consultar(bd, """
        SELECT u.id_usuario, u.id_rol, c.id_estado_cuenta
          FROM modulo1.usuarios u
          LEFT JOIN modulo1.cuentas_usuarios c ON c.id_usuario = u.id_usuario
         WHERE u.correo_electronico = %s
    """, (USUARIO_SIN_READ['correo_electronico'],))
    assert filas, f'el usuario {USUARIO_SIN_READ["correo_electronico"]} no existe en TEST'
    id_usuario, id_rol, estado = filas[0]
    return {'id_usuario': id_usuario, 'id_rol': id_rol, 'id_estado_cuenta': estado}


@pytest.fixture(scope='module')
def token_sin_read() -> str:
    respuesta = requests.post(f'{BASE_URL}/sesiones/', json=USUARIO_SIN_READ, timeout=30)
    assert respuesta.status_code == 200, f'AUTH_NO_READ no autentica: {respuesta.text}'
    return respuesta.json()['token']


# ─────────────────── El recurso/accion del endpoint son los que se prueban ───────────────────

def test_el_endpoint_de_indicadores_exige_read_sobre_activos_biologicos():
    """V30/A2: recurso y accion salen del codigo del router, no de un supuesto."""
    from src.biological_assets.infrastructure.routers import activo_biologico_router
    import inspect

    fuente = inspect.getsource(activo_biologico_router)
    assert '_RECURSO = 29' in fuente, 'el recurso de activos biologicos cambio'
    bloque = fuente.split("'/{id_activo}/indicadores'")[1].split('def consultar_indicadores')[0]
    assert f'require_permission(_RECURSO, {ACCION_READ})' in bloque, (
        'el endpoint de indicadores ya no exige (29, 2); revisar el analisis'
    )


# ─────────────────── V22/V23: usuario autenticable, cuenta activa ───────────────────

def test_usuario_autenticable_y_cuenta_activa(identidad_sin_read, token_sin_read):
    """V22/V23 y A10: autenticacion valida; el 403 no vendra de cuenta bloqueada."""
    assert token_sin_read and token_sin_read.count('.') == 2, 'token JWT mal formado'
    assert identidad_sin_read['id_rol'] == ROL_ESPERADO, (
        f'el rol del usuario cambio: {identidad_sin_read["id_rol"]}'
    )
    # A10: si la cuenta estuviera inactiva, un 403 seria CUENTA_NO_ACTIVA, no falta de READ.
    assert identidad_sin_read['id_estado_cuenta'] == ESTADO_CUENTA_ACTIVA, (
        'la cuenta no esta Activa; el 403 podria confundirse con cuenta inactiva'
    )


# ─────────────────── V24/A11/A12: READ ausente demostrado, sin herencia ───────────────────

def test_el_rol_no_tiene_read_sobre_activos(bd, identidad_sin_read):
    """V24/A11: el rol carece del permiso (29, 2) en el RBAC real."""
    filas = _consultar(bd, """
        SELECT 1 FROM modulo1.permisos
         WHERE id_rol = %s AND id_recurso = %s AND id_accion = %s AND es_activo IS TRUE
    """, (identidad_sin_read['id_rol'], RECURSO_INDICADORES, ACCION_READ))
    assert filas == [], (
        f'el rol {identidad_sin_read["id_rol"]} SI tiene READ sobre activos biologicos; '
        'no sirve para aislar TC-M02-314'
    )


def test_no_hay_herencia_de_read_por_otra_via(bd, identidad_sin_read):
    """A12: el modelo asigna un unico rol por usuario; no hay READ heredado.

    `modulo1.usuarios.id_rol` es la unica fuente de rol (no existe tabla usuarios_roles),
    de modo que el permiso efectivo del usuario es exactamente el de su rol.
    """
    tablas_puente = _consultar(bd, """
        SELECT table_name FROM information_schema.tables
         WHERE table_schema = 'modulo1' AND table_name ILIKE %s
    """, ('%usuarios_roles%',))
    assert tablas_puente == [], 'existe una tabla de roles multiples; recalcular la herencia'
    # Confirmacion directa: ningun permiso de lectura de activos alcanza a este usuario.
    filas = _consultar(bd, """
        SELECT p.id_permiso FROM modulo1.permisos p
          JOIN modulo1.usuarios u ON u.id_rol = p.id_rol
         WHERE u.id_usuario = %s AND p.id_recurso = %s AND p.id_accion = %s AND p.es_activo IS TRUE
    """, (identidad_sin_read['id_usuario'], RECURSO_INDICADORES, ACCION_READ))
    assert filas == [], 'el usuario alcanza READ por su rol; no aisla la falta de permiso'


# ─────────────────── V25: el activo existe ───────────────────

def test_el_activo_existe(bd):
    """V25/A13: el activo de TC-314 existe y no es el ID inexistente."""
    assert ACTIVO_314 != 99999
    filas = _consultar(bd, """
        SELECT id_activo_biologico, id_estado FROM modulo2.activos_biologicos
         WHERE id_activo_biologico = %s
    """, (ACTIVO_314,))
    assert filas, f'el activo {ACTIVO_314} no existe'


# ─────────────────── V27/V28/V29: la solicitud oficial ───────────────────

def test_tc_m02_314_usuario_sin_read_recibe_403(token_sin_read):
    """TC-M02-314: 403 por autorizacion, sin exponer indicador ni variables."""
    respuesta = requests.get(
        f'{BASE_URL}{RUTA}',
        params={'tipo_indicador': 'CRECIMIENTO', 'fecha_inicio': '2026-06-01', 'fecha_fin': '2026-09-10'},
        headers={'Authorization': f'Bearer {token_sin_read}'}, timeout=30,
    )
    # V27 - criterio de la ficha reformulada.
    assert respuesta.status_code == 403, f'HTTP {respuesta.status_code}: {respuesta.text}'

    cuerpo = respuesta.json()
    # V28/A14 - la causa es autorizacion de rol, no autenticacion ni cuenta inactiva.
    assert cuerpo.get('error_code') == 'ACCESO_DENEGADO', (
        f'el 403 no es por permiso de rol: {cuerpo.get("error_code")}'
    )
    assert respuesta.status_code != 401, 'un 401 seria autenticacion, no autorizacion'

    # V29 - no se expone indicador ni variables del calculo.
    texto = respuesta.text.lower()
    assert 'indicadores' not in cuerpo, 'el 403 expone la lista de indicadores'
    for termino in ('variables_usadas', 'ganancia_peso', 'peso_inicial', 'total_mediciones',
                    'eventos_sanitarios'):
        assert termino not in texto, f'el 403 expone "{termino}" del calculo'


def test_control_el_mismo_activo_es_accesible_con_read():
    """Control positivo: AUTH_OK (con READ) obtiene 200 sobre el mismo activo.

    Demuestra que el 403 de TC-314 se debe al usuario sin READ y no a que el activo
    o el endpoint sean inaccesibles para todos (A13/A16 descartados).
    """
    login = requests.post(
        f'{BASE_URL}/sesiones/',
        json={'correo_electronico': 'm2m.nuevo@ejemplo.com', 'contrasena': 'Test1234!'},
        timeout=30,
    )
    assert login.status_code == 200
    token_ok = login.json()['token']
    respuesta = requests.get(
        f'{BASE_URL}{RUTA}', params={'tipo_indicador': 'CRECIMIENTO'},
        headers={'Authorization': f'Bearer {token_ok}'}, timeout=30,
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()['id_activo_biologico'] == ACTIVO_314
