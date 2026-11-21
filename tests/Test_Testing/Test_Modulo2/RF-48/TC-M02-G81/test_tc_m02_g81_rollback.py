"""TC-M02-G81 / TC-M02-141 - RF-48: rollback ante fallo transaccional.

AMBIENTE: LOCAL AISLADO. Este archivo NUNCA debe ejecutarse contra el TEST
compartido: provoca deliberadamente una excepcion dentro de la transaccion de
`RegistrarTransferenciaUseCase`. El preflight de `_verificar_ambiente_local`
aborta la sesion completa si el DSN apunta a 158.69.200.27, al puerto 5448 o a
la base sgpmp_test.

Punto de fault injection (§15): se parchea
`SqlAlchemyTransferenciaRepository.guardar`, que el caso de uso invoca en el
paso (d) del bloque `try`, es decir:

    a) UPDATE historial_infraestructura_activo  (cierra la asociacion origen)
    b) INSERT historial_infraestructura_activo  (abre la asociacion destino)
    c) UPDATE activos_biologicos.id_infraestructura
    d) transferencia_repo.guardar(...)          <-- EXCEPCION FORZADA AQUI
       self.db.commit()

El fallo ocurre por tanto DESPUES de tres operaciones de persistencia y ANTES
del commit, que es exactamente lo que el sub-caso exige demostrar.

El estado posterior se comprueba con una CONEXION INDEPENDIENTE a la misma base
(psycopg2, autocommit), no con la sesion de la aplicacion: si el rollback fuese
incompleto, esa conexion veria los datos a medio escribir.

Ejecucion:
    set TC_G81_DSN=postgresql://postgres:postgres@127.0.0.1:5455/sgpmp_g81_local_test
    .venv\\Scripts\\python.exe -m pytest tests/Test_Testing/Test_Modulo2/RF-48/TC-M02-G81 \\
        -p no:cacheprovider --junitxml=Resultados/reporte_tc_m02_g81_rollback.xml
"""
from __future__ import annotations

import os
import random
import string
from datetime import date, datetime, timezone
from typing import Any

import psycopg2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

DSN = os.getenv(
    'TC_G81_DSN',
    'postgresql://postgres:postgres@127.0.0.1:5455/sgpmp_g81_local_test',
)

# Identificadores del ambiente TEST compartido: prohibidos en este archivo.
TEST_HOST_PROHIBIDO = '158.69.200.27'
TEST_PUERTO_PROHIBIDO = '5448'
TEST_BD_PROHIBIDA = 'sgpmp_test'

ESPECIE = 1          # Tilapia Roja (catalogo poblado por las migraciones)
ESTADO_ACTIVO = 1    # modulo2.estados_activos_biologicos
ESTADO_CUENTA_ACTIVA = 2
ROL_PRODUCTOR = 2
ROL_ADMINISTRADOR = 1

# modulo9.trg_fn_finca_nombre_unique impone unicidad global del nombre de finca y
# solo admite letras: se usa un sufijo alfabetico distinto en cada ejecucion para
# que las corridas sucesivas no choquen entre si.
SUFIJO = ''.join(random.choices(string.ascii_lowercase, k=6))


# ──────────────────────────── §1 / §10.3 preflight ────────────────────────────

def _verificar_ambiente_local() -> dict[str, Any]:
    """Aborta si el DSN pudiera apuntar al TEST compartido. Devuelve la evidencia."""
    if TEST_HOST_PROHIBIDO in DSN or TEST_BD_PROHIBIDA in DSN or f':{TEST_PUERTO_PROHIBIDO}/' in DSN:
        pytest.exit(
            f'DETENER INMEDIATAMENTE: el DSN apunta al ambiente TEST compartido ({DSN}). '
            'TC-M02-141 solo puede ejecutarse en LOCAL AISLADO.',
            returncode=2,
        )
    conexion = psycopg2.connect(DSN)
    conexion.autocommit = True
    with conexion.cursor() as cur:
        cur.execute(
            'select coalesce(host(inet_server_addr()), %s), inet_server_port(), current_database()',
            ('local',),
        )
        host, puerto, base = cur.fetchone()
    conexion.close()

    if host == TEST_HOST_PROHIBIDO or str(puerto) == TEST_PUERTO_PROHIBIDO or base == TEST_BD_PROHIBIDA:
        pytest.exit(
            f'DETENER INMEDIATAMENTE: la conexion real es {host}:{puerto}/{base}, '
            'que corresponde al ambiente TEST compartido.',
            returncode=2,
        )
    return {'host': host, 'puerto': puerto, 'base': base}


AMBIENTE = _verificar_ambiente_local()


@pytest.fixture(scope='session')
def evidencia_ambiente() -> dict[str, Any]:
    return AMBIENTE


def test_preflight_el_ambiente_es_local_y_no_es_test(evidencia_ambiente: dict[str, Any]) -> None:
    """§10.3: deja constancia en el reporte de contra que base se ejecuto todo."""
    assert evidencia_ambiente['host'] != TEST_HOST_PROHIBIDO
    assert str(evidencia_ambiente['puerto']) != TEST_PUERTO_PROHIBIDO
    assert evidencia_ambiente['base'] != TEST_BD_PROHIBIDA
    assert 'test' in evidencia_ambiente['base'] or 'local' in evidencia_ambiente['base']


def test_preflight_el_backend_no_apunta_al_test_compartido() -> None:
    """A1: la DATABASE_URL que usara el codigo del producto tambien debe ser local.

    `src/shared/database.py` construye su engine a partir de DATABASE_URL al
    importarse. Aunque las dependencias se sobreescriben en las pruebas, se
    verifica el valor efectivo para descartar cualquier via hacia TEST.
    """
    from src.shared import database

    url = str(database.DATABASE_URL)
    assert TEST_HOST_PROHIBIDO not in url, f'el backend apunta al host de TEST: {url}'
    assert TEST_BD_PROHIBIDA not in url, f'el backend apunta a la base de TEST: {url}'
    assert f':{TEST_PUERTO_PROHIBIDO}/' not in url, f'el backend apunta al puerto de TEST: {url}'
    assert '127.0.0.1' in url or 'localhost' in url, f'la DATABASE_URL no es local: {url}'


# ──────────────────────────── §12 fixture desechable ────────────────────────────

def _conexion_independiente() -> psycopg2.extensions.connection:
    """Conexion aparte de la sesion de la app: es la que audita el estado real."""
    conexion = psycopg2.connect(DSN)
    conexion.autocommit = True
    return conexion


def _sembrar_catalogos(cur: Any) -> None:
    cur.execute(
        """
        INSERT INTO modulo2.estados_activos_biologicos (id_estado_activo_biologico, nombre)
        VALUES (1,'ACTIVO'),(2,'INACTIVO'),(3,'EN_TRATAMIENTO'),(4,'AISLADO'),(5,'CERRADO'),(6,'BAJA')
        ON CONFLICT (id_estado_activo_biologico) DO NOTHING
        """
    )


def _sembrar_usuario(cur: Any, correo: str, id_rol: int) -> int:
    cur.execute('SELECT id_usuario FROM modulo1.usuarios WHERE correo_electronico = %s', (correo,))
    fila = cur.fetchone()
    if fila:
        return int(fila[0])
    cur.execute(
        """
        INSERT INTO modulo1.usuarios (
            tipo_identificacion, numero_identificacion, nombre, apellidos, fecha_nacimiento,
            genero, correo_electronico, contrasena_cifrada, telefono, direccion, id_rol, fecha_registro
        ) VALUES (
            'CC', %s, 'Integracion', 'Prueba', %s, CAST('M' AS modulo1.enum_usuario_genero), %s,
            'x', '3001234567', 'Local QA', %s, now()
        ) RETURNING id_usuario
        """,
        (str(abs(hash(correo)) % 10**14).zfill(14), date(1990, 1, 1), correo, id_rol),
    )
    id_usuario = int(cur.fetchone()[0])
    cur.execute(
        """
        INSERT INTO modulo1.cuentas_usuarios (
            id_usuario, id_estado_cuenta, tiene_correo_verificado, fecha_verificacion, ultimo_acceso
        ) VALUES (%s, %s, TRUE, now(), now())
        """,
        (id_usuario, ESTADO_CUENTA_ACTIVA),
    )
    return id_usuario


def _sembrar_escenario(cur: Any, id_usuario: int, etiqueta: str) -> dict[str, int]:
    """Crea finca, origen, destino y un activo ACTIVO asociado al origen.

    `etiqueta` debe ser alfabetica: modulo9.trg_fn_finca_nombre_unique rechaza
    numeros y simbolos en el nombre de la finca.
    """
    # modulo2.trg_auditar_activo_biologico exige app.usuario_id en la sesion, igual
    # que hace el producto con SET LOCAL dentro de la transaccion de transferencia.
    cur.execute("SELECT set_config('app.usuario_id', %s, false)", (str(id_usuario),))
    cur.execute(
        """
        INSERT INTO modulo9.fincas (nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, id_usuario, es_activo)
        VALUES (%s, '{"lat":0,"lon":0}'::jsonb, 10, now(), now(), %s, TRUE)
        RETURNING id_finca
        """,
        (f'Finca Local {etiqueta} {SUFIJO}', id_usuario),
    )
    id_finca = int(cur.fetchone()[0])

    ids = {}
    for clave, nombre, capacidad in (('origen', 'Corral Local Origen', 100), ('destino', 'Corral Local Destino', 100)):
        cur.execute(
            """
            INSERT INTO modulo9.infraestructuras (nombre, id_finca, superficie, es_activo, tipo, capacidad_maxima, id_especie, fecha_actualizacion)
            VALUES (%s, %s, 50, TRUE, 'Corral', %s, %s, now())
            RETURNING id_infraestructura
            """,
            (f'{nombre} {etiqueta} {SUFIJO}', id_finca, capacidad, ESPECIE),
        )
        ids[clave] = int(cur.fetchone()[0])

    cur.execute(
        """
        INSERT INTO modulo2.activos_biologicos (
            id_especie, identificador, id_infraestructura, tipo, fecha_inicio_ciclo, id_estado,
            descripcion, origen_financiero, costo_adquisicion, soporte_documental, id_usuario, fecha_creacion
        ) VALUES (
            %s, %s, %s, CAST('INDIVIDUAL' AS modulo2.enum_activo_biologico_tipo), %s, %s,
            'Fixture local TC-M02-141',
            CAST('compra' AS modulo2.enum_activo_biologico_origen_financiero),
            1000, 'soporte-local-qa.pdf', %s, now()
        ) RETURNING id_activo_biologico
        """,
        # `identificador` es varchar(25): el sufijo va primero para que el truncado siga siendo unico.
        (ESPECIE, f'{SUFIJO} {etiqueta}'[:25], ids['origen'], date(2026, 6, 1), ESTADO_ACTIVO, id_usuario),
    )
    id_activo = int(cur.fetchone()[0])

    cur.execute(
        """
        INSERT INTO modulo2.detalles_activos_individuales (
            id_activo_biologico, raza, sexo, fecha_nacimeinto, peso_inicial, fecha_creacion, id_usuario
        ) VALUES (%s, 'QA', 'Macho', %s, 100, now(), %s)
        """,
        (id_activo, datetime(2025, 1, 1, tzinfo=timezone.utc), id_usuario),
    )
    cur.execute(
        """
        INSERT INTO modulo2.historial_infraestructura_activo (
            id_activo_biologico, id_infraestructura, fecha_inicio, fecha_fin, id_usuario_registro
        ) VALUES (%s, %s, %s, NULL, %s)
        """,
        (id_activo, ids['origen'], datetime(2026, 6, 1, tzinfo=timezone.utc), id_usuario),
    )
    return {'id_finca': id_finca, 'id_activo': id_activo, **ids}


@pytest.fixture(scope='session', autouse=True)
def catalogos() -> None:
    conexion = _conexion_independiente()
    with conexion.cursor() as cur:
        _sembrar_catalogos(cur)
    conexion.close()


# ──────────────────────────── app local sobre el router real ────────────────────────────

@pytest.fixture(scope='session')
def engine_local():
    motor = create_engine(DSN, pool_pre_ping=True, use_insertmanyvalues=False)
    yield motor
    motor.dispose()


@pytest.fixture
def app_local(engine_local):
    """FastAPI con el router real de activos biologicos y los handlers de error del producto."""
    from src.biological_assets.infrastructure.routers import activo_biologico_router
    from src.shared.error_handlers import register_error_handlers

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(activo_biologico_router.router)
    return app


def _cliente(app: FastAPI, engine_local, id_usuario: int, id_rol: int):
    """TestClient en el MISMO proceso que el monkeypatch (§17), con sesion real.

    La sesion NO usa savepoints: el commit y el rollback del caso de uso son los
    reales, que es justo lo que TC-M02-141 debe observar.
    """
    from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
    from src.shared.database import get_db

    sesion = Session(bind=engine_local.connect(), expire_on_commit=False)

    def _get_db():
        yield sesion

    def _usuario_actual() -> UsuarioActual:
        return UsuarioActual(
            id_usuario=id_usuario, id_token=1, id_rol=id_rol,
            id_estado_cuenta=ESTADO_CUENTA_ACTIVA,
        )

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _usuario_actual
    return TestClient(app, raise_server_exceptions=False), sesion


def _foto(cur: Any, escenario: dict[str, int]) -> dict[str, Any]:
    """Estado observable del escenario, leido por la conexion independiente."""
    id_activo = escenario['id_activo']
    cur.execute('SELECT id_infraestructura, id_estado FROM modulo2.activos_biologicos WHERE id_activo_biologico = %s', (id_activo,))
    infra, estado = cur.fetchone()
    cur.execute(
        'SELECT id_infraestructura FROM modulo2.historial_infraestructura_activo '
        'WHERE id_activo_biologico = %s AND fecha_fin IS NULL', (id_activo,))
    vigentes = [f[0] for f in cur.fetchall()]
    cur.execute('SELECT count(*) FROM modulo2.historial_infraestructura_activo WHERE id_activo_biologico = %s', (id_activo,))
    n_historial = int(cur.fetchone()[0])
    cur.execute('SELECT count(*) FROM modulo2.movimientos WHERE id_activo_biologico = %s', (id_activo,))
    n_movimientos = int(cur.fetchone()[0])
    ocupaciones = {}
    for clave in ('origen', 'destino'):
        cur.execute(
            'SELECT count(*) FROM modulo2.activos_biologicos WHERE id_infraestructura = %s AND id_estado NOT IN (5,6)',
            (escenario[clave],))
        ocupaciones[clave] = int(cur.fetchone()[0])
    return {
        'infraestructura_activo': infra,
        'estado_activo': estado,
        'asociaciones_vigentes': vigentes,
        'n_historial': n_historial,
        'n_movimientos': n_movimientos,
        'ocupacion_origen': ocupaciones['origen'],
        'ocupacion_destino': ocupaciones['destino'],
    }


def _cuerpo(escenario: dict[str, int], motivo: str) -> dict[str, Any]:
    return {
        'infraestructura_origen_id': escenario['origen'],
        'infraestructura_destino_id': escenario['destino'],
        'fecha_transferencia': date.today().isoformat(),
        'motivo_transferencia': motivo,
    }


ACTORES = [
    pytest.param('Productor', ROL_PRODUCTOR, id='Productor'),
    pytest.param('Administrador', ROL_ADMINISTRADOR, id='Administrador'),
]


# ──────────────────────────── §13 validacion positiva ────────────────────────────

@pytest.mark.parametrize('etiqueta,id_rol', ACTORES)
def test_control_positivo_la_transferencia_valida_si_persiste(app_local, engine_local, etiqueta, id_rol):
    """§13: demuestra que el escenario base es valido y llega a persistir.

    Se ejecuta sobre un fixture INDEPENDIENTE del que usa el fault injection, para
    no consumir el que debe permanecer intacto. Sin este control, un 500 posterior
    podria atribuirse a C1/C2/C3, estado, permisos o fecha en vez de al fallo forzado.
    """
    conexion = _conexion_independiente()
    with conexion.cursor() as cur:
        id_usuario = _sembrar_usuario(cur, f'g81.control.{etiqueta.lower()}.{SUFIJO}@local.test', id_rol)
        escenario = _sembrar_escenario(cur, id_usuario, f'Control {etiqueta}')
        antes = _foto(cur, escenario)

    cliente, sesion = _cliente(app_local, engine_local, id_usuario, id_rol)
    try:
        respuesta = cliente.post(
            f"/activos-biologicos/{escenario['id_activo']}/transferencias",
            json=_cuerpo(escenario, f'Control positivo {etiqueta}'),
        )
    finally:
        sesion.close()

    assert respuesta.status_code == 201, f'el escenario base no es valido: {respuesta.status_code} {respuesta.text}'

    with conexion.cursor() as cur:
        despues = _foto(cur, escenario)
    conexion.close()

    # La transferencia valida SI mueve el activo: prueba que el flujo llega a persistir.
    assert antes['infraestructura_activo'] == escenario['origen']
    assert despues['infraestructura_activo'] == escenario['destino']
    assert despues['asociaciones_vigentes'] == [escenario['destino']]
    assert despues['n_movimientos'] == antes['n_movimientos'] + 1


# ──────────────────────────── §19 TC-M02-141 fault injection ────────────────────────────

@pytest.mark.parametrize('etiqueta,id_rol', ACTORES)
def test_tc_m02_141_rollback_completo_ante_fallo_transaccional(
    app_local, engine_local, monkeypatch, etiqueta, id_rol, evidencia_ambiente, request
):
    """TC-M02-141: excepcion tras 3 escrituras y antes del commit -> rollback total."""
    from src.biological_assets.infrastructure.repositories.transferencia_repository import (
        SqlAlchemyTransferenciaRepository,
    )

    conexion = _conexion_independiente()
    with conexion.cursor() as cur:
        id_usuario = _sembrar_usuario(cur, f'g81.fault.{etiqueta.lower()}.{SUFIJO}@local.test', id_rol)
        escenario = _sembrar_escenario(cur, id_usuario, f'Falla {etiqueta}')
        antes = _foto(cur, escenario)
        cur.execute(
            "SELECT count(*) FROM modulo2.bitacora_auditoria_m02 "
            "WHERE rf_origen='RF48' AND tipo_evento='TRANSFERENCIA_FALLIDA' AND id_activo_biologico=%s",
            (escenario['id_activo'],))
        auditoria_antes = int(cur.fetchone()[0])

    # Precondiciones: el fixture es valido y el fallo no puede atribuirse a los datos.
    assert antes['estado_activo'] == ESTADO_ACTIVO, 'el activo debe estar ACTIVO'
    assert antes['asociaciones_vigentes'] == [escenario['origen']], 'debe existir una unica asociacion vigente al origen'
    assert antes['n_movimientos'] == 0
    assert escenario['destino'] != escenario['origen']

    # §15/§16 - punto de fallo: paso (d), despues de a/b/c y antes del commit.
    escrituras_previas: dict[str, Any] = {}

    def guardar_con_fallo(self, transferencia):  # noqa: ANN001
        # En este punto a), b) y c) ya se ejecutaron sobre la sesion. Se comprueba
        # que efectivamente hay escrituras pendientes que el rollback debera revertir.
        sesion_uc = self.db if hasattr(self, 'db') else None
        if sesion_uc is not None:
            fila = sesion_uc.execute(
                text('SELECT id_infraestructura FROM modulo2.activos_biologicos WHERE id_activo_biologico = :i'),
                {'i': escenario['id_activo']},
            ).scalar()
            escrituras_previas['infra_en_transaccion'] = fila
            escrituras_previas['vigentes_en_transaccion'] = [
                f[0] for f in sesion_uc.execute(
                    text('SELECT id_infraestructura FROM modulo2.historial_infraestructura_activo '
                         'WHERE id_activo_biologico = :i AND fecha_fin IS NULL'),
                    {'i': escenario['id_activo']},
                ).fetchall()
            ]
        raise RuntimeError('TC-M02-141 fault injection')

    monkeypatch.setattr(SqlAlchemyTransferenciaRepository, 'guardar', guardar_con_fallo)

    cliente, sesion = _cliente(app_local, engine_local, id_usuario, id_rol)
    try:
        respuesta = cliente.post(
            f"/activos-biologicos/{escenario['id_activo']}/transferencias",
            json=_cuerpo(escenario, f'TC-M02-141 {etiqueta}'),
        )
    finally:
        sesion.close()

    # A7/A8 - el fallo ocurrio DESPUES de escribir y ANTES del commit.
    assert escrituras_previas.get('infra_en_transaccion') == escenario['destino'], (
        'el fault injection no ocurrio despues de las escrituras: dentro de la transaccion '
        f"el activo apuntaba a {escrituras_previas.get('infra_en_transaccion')}"
    )
    assert escrituras_previas.get('vigentes_en_transaccion') == [escenario['destino']]

    # §19 - respuesta esperada para un fallo transaccional no controlado.
    assert respuesta.status_code == 500, f'HTTP {respuesta.status_code}: {respuesta.text}'
    assert 'TC-M02-141 fault injection' not in respuesta.text, 'el 500 no debe filtrar el detalle tecnico'

    # §20 - estado DESPUES leido por la conexion independiente.
    with conexion.cursor() as cur:
        despues = _foto(cur, escenario)
        cur.execute(
            "SELECT count(*) FROM modulo2.bitacora_auditoria_m02 "
            "WHERE rf_origen='RF48' AND tipo_evento='TRANSFERENCIA_FALLIDA' AND id_activo_biologico=%s",
            (escenario['id_activo'],))
        auditoria_despues = int(cur.fetchone()[0])
    conexion.close()

    assert despues['infraestructura_activo'] == antes['infraestructura_activo'] == escenario['origen']
    assert despues['asociaciones_vigentes'] == [escenario['origen']], 'el destino no debe quedar asociado'
    assert despues['n_historial'] == antes['n_historial'], 'no debe quedar una asociacion destino creada'
    assert despues['n_movimientos'] == antes['n_movimientos'] == 0, 'no debe existir evento de transferencia exitoso'
    assert despues['ocupacion_origen'] == antes['ocupacion_origen']
    assert despues['ocupacion_destino'] == antes['ocupacion_destino']
    assert despues['estado_activo'] == antes['estado_activo']

    # Evidencia ANTES/DESPUES para el informe (queda en el stdout del JUnit XML).
    print('')
    print(f'=== TC-M02-141 / {etiqueta} ===')
    print(f"  ambiente        : {evidencia_ambiente['host']}:{evidencia_ambiente['puerto']}/{evidencia_ambiente['base']}")
    print(f"  activo/origen/destino: {escenario['id_activo']} / {escenario['origen']} / {escenario['destino']}")
    print(f"  dentro de la transaccion (antes del commit): infra={escrituras_previas['infra_en_transaccion']} "
          f"vigentes={escrituras_previas['vigentes_en_transaccion']}")
    print(f'  HTTP            : {respuesta.status_code}')
    for campo in ('infraestructura_activo', 'asociaciones_vigentes', 'n_historial', 'n_movimientos',
                  'ocupacion_origen', 'ocupacion_destino', 'estado_activo'):
        print(f'  {campo:24s}: ANTES={antes[campo]!r:22s} DESPUES={despues[campo]!r}')
    print(f'  auditoria FALLIDA       : ANTES={auditoria_antes} DESPUES={auditoria_despues}')

    # §21 - el fallo debe quedar auditado, y no confundirse con un evento exitoso.
    request.node.auditoria = (auditoria_antes, auditoria_despues)
    assert auditoria_despues == auditoria_antes + 1, (
        'RF-48 exige que el fallo quede auditado; la bitacora no registro TRANSFERENCIA_FALLIDA'
    )
