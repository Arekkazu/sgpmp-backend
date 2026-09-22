"""
TC-M02-G99 (RF-52, CU13) - Inmutabilidad de la bitacora, resiliencia ante fallo
del repositorio y no bloqueo del flujo operativo.

Sub-casos:
    TC-M02-168  la bitacora es append-only (UPDATE/DELETE rechazados y auditados)
    TC-M02-169  repositorio caido -> buffer sin perdida, orden cronologico al recuperar
    TC-M02-170  un fallo/latencia de RF-52 no bloquea el flujo de otros RF (ej. RF-40)

Un solo archivo y un solo reporte para todo el TC. Los tests afirman lo que PIDE
LA FICHA: cuando el backend no lo cumple, el test queda en ROJO como evidencia
del defecto (mismo criterio de TC-M09-G64 / TC-M02-G53).

Como se verifica cada cosa:
  * 168 -> EN VIVO contra TEST (httpx): intentos de alteracion por API y conteo
    de la bitacora; mas una verificacion ESTRUCTURAL del esquema/migraciones
    (no hay acceso directo a la BD de TEST desde un cliente HTTP; el esquema del
    repo es la unica evidencia disponible del bloqueo a nivel de BD).
  * 169 y 170 -> dobles de prueba sobre RegistrarEventoCrecimientoUseCase (RF-40):
    no se puede apagar ni ralentizar el repositorio de auditoria de TEST desde
    caja negra, asi que se simula con un repositorio falso.

Como correrlo (desde la raiz del repo):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m02_g99_bitacora_inmutabilidad_resiliencia.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M02-G99.html --self-contained-html
"""
import os
import re
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from src.biological_assets.application.use_cases.gestion.registrar_evento_crecimiento_use_case import (
    RegistrarEventoCrecimientoUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, GestionFase
from src.biological_assets.infrastructure.dto.registrar_evento_crecimiento_dto import (
    RegistrarEventoCrecimientoDTO,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual

BASE_URL = os.getenv(
    'SGPMP_TEST_BASE_URL',
    'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test',
)
REPO_ROOT = Path(__file__).resolve().parents[5]
ID_ACTIVO_CON_HISTORIAL = 306   # activo con muchos registros de bitacora; nunca se modifica
ID_ACTIVO_CON_FASE = 374        # INDIVIDUAL ACTIVO con fase asignada (para RF-40 en vivo)
RUTA_AUDITORIA = '/activos-biologicos/auditoria'


def _token() -> str:
    r = httpx.post(
        f'{BASE_URL}/sesiones/',
        json={'correo_electronico': 'admin@pecuaria.co', 'contrasena': 'Test1234!'},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    return r.json()['token']


def _get(token: str, path: str, **params) -> httpx.Response:
    return httpx.get(f'{BASE_URL}{path}', params=params, headers={'Authorization': f'Bearer {token}'}, timeout=30)


def _total_bitacora(token: str) -> int:
    return _get(token, RUTA_AUDITORIA, page_size=1).json()['total_registros']


class TestSubcaso168InmutabilidadDeLaBitacora:

    def _intentos(self, id_registro: int):
        return [
            (metodo, ruta)
            for ruta in (RUTA_AUDITORIA, f'{RUTA_AUDITORIA}/{id_registro}')
            for metodo in ('PUT', 'PATCH', 'DELETE', 'POST')
        ]

    def _registro_objetivo(self, token: str) -> dict:
        registros = _get(token, RUTA_AUDITORIA, id_activo_biologico=ID_ACTIVO_CON_HISTORIAL, page_size=50).json()['registros']
        assert registros, 'se esperaba al menos un registro de bitacora para el activo de referencia'
        return registros[-1]  # el mas antiguo de la pagina

    def test_ningun_intento_de_update_o_delete_por_api_tiene_exito(self):
        token = _token()
        objetivo = self._registro_objetivo(token)
        for metodo, ruta in self._intentos(objetivo['id_bitacora']):
            r = httpx.request(
                metodo, f'{BASE_URL}{ruta}', json={'resultado': 'ALTERADO'},
                headers={'Authorization': f'Bearer {token}'}, timeout=30,
            )
            assert r.status_code >= 400, f'{metodo} {ruta} respondio {r.status_code}: la bitacora no deberia aceptar alteraciones'

    def test_el_registro_existente_permanece_intacto_tras_los_intentos(self):
        token = _token()
        antes = self._registro_objetivo(token)
        for metodo, ruta in self._intentos(antes['id_bitacora']):
            httpx.request(metodo, f'{BASE_URL}{ruta}', json={'resultado': 'ALTERADO'},
                          headers={'Authorization': f'Bearer {token}'}, timeout=30)
        despues = next(
            r for r in _get(token, RUTA_AUDITORIA, id_activo_biologico=ID_ACTIVO_CON_HISTORIAL, page_size=50).json()['registros']
            if r['id_bitacora'] == antes['id_bitacora']
        )
        assert despues == antes

    def test_los_intentos_de_alteracion_quedan_registrados_en_la_bitacora(self):
        """La ficha exige que el intento de alteracion quede registrado en la propia bitacora."""
        token = _token()
        objetivo = self._registro_objetivo(token)
        intentos = self._intentos(objetivo['id_bitacora'])
        antes = _total_bitacora(token)
        for metodo, ruta in intentos:
            httpx.request(metodo, f'{BASE_URL}{ruta}', json={'resultado': 'ALTERADO'},
                          headers={'Authorization': f'Bearer {token}'}, timeout=30)
        nuevos = _total_bitacora(token) - antes
        assert nuevos >= len(intentos), (
            f'Se hicieron {len(intentos)} intentos de alteracion y solo se registraron {nuevos} filas nuevas en la bitacora '
            '(las respuestas 404/405 del router no dejan rastro; el unico registro fue un VALIDACION_RECHAZADA accidental '
            'por colision de rutas en PATCH /activos-biologicos/auditoria).'
        )

    def test_la_bd_bloquea_update_y_delete_sobre_la_tabla_de_bitacora(self):
        """Evidencia estructural: debe existir un trigger o REVOKE que impida UPDATE/DELETE sobre modulo2.bitacora_auditoria_m02."""
        archivos = [REPO_ROOT / 'alembic' / 'baseline' / 'esquema_baseline.sql', *(REPO_ROOT / 'alembic').rglob('versions/*.py')]
        patron_trigger = re.compile(r'CREATE\s+(?:CONSTRAINT\s+)?TRIGGER[^;]*?\bON\s+modulo2\.bitacora_auditoria_m02', re.I | re.S)
        patron_revoke = re.compile(r'REVOKE\s+(?:UPDATE|DELETE)[^;]*bitacora_auditoria_m02', re.I | re.S)
        hallazgos = [
            str(a.relative_to(REPO_ROOT))
            for a in archivos
            if a.exists() and (lambda t: patron_trigger.search(t) or patron_revoke.search(t))(a.read_text(encoding='utf-8', errors='ignore'))
        ]
        assert hallazgos, (
            'No hay ningun trigger ni REVOKE que impida UPDATE/DELETE sobre modulo2.bitacora_auditoria_m02 '
            '(solo indices y PK): la inmutabilidad depende unicamente de que el router no exponga rutas de escritura.'
        )


def _activo() -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=4, tipo='INDIVIDUAL', origen_financiero='compra', id_infraestructura=6, id_estado=1,
        id_usuario=1, id_activo_biologico=ID_ACTIVO_CON_FASE, fecha_inicio_ciclo=date(2026, 8, 1),
        fecha_creacion=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )


def _fase() -> GestionFase:
    return GestionFase(
        id_gestion_fases=1, id_activo_biologico=ID_ACTIVO_CON_FASE, id_ciclo_productiva=4,
        nombre_ciclo='Ciclo completo cachama 2025-A', nombre_fase_actual='Fase juvenil cachama', paso_actual=1,
        total_pasos=2, fecha_inicio=datetime(2026, 8, 1, tzinfo=timezone.utc), fecha_finalizacion=None,
        es_activa=True, id_usuario=1,
    )


def _crecimiento_use_case(bitacora_repo) -> tuple[RegistrarEventoCrecimientoUseCase, MagicMock]:
    activo_repo = MagicMock()
    activo_repo.obtener_por_id.return_value = _activo()
    activo_repo.obtener_fase_activa.return_value = _fase()
    evento_repo = MagicMock()
    evento_repo.obtener_ultima_fecha.return_value = None
    parametros = MagicMock()
    parametros.obtener_por_tipo_medicion.return_value = MagicMock(valor_min=None, valor_max=None)
    ciclo_port = MagicMock()
    ciclo_port.obtener_ciclo_con_fases.return_value = None
    db = MagicMock()
    uc = RegistrarEventoCrecimientoUseCase(
        db=db, activo_repo=activo_repo, evento_repo=evento_repo, infra_port=MagicMock(),
        parametros_port=parametros, ciclo_port=ciclo_port, bitacora_repo=bitacora_repo,
    )
    return uc, db


def _dto() -> RegistrarEventoCrecimientoDTO:
    return RegistrarEventoCrecimientoDTO(
        tipo_medicion='PESO', valor_medicion=Decimal('1.5'), unidad_medida='kg',
        fecha=datetime(2026, 9, 14, 10, tzinfo=timezone.utc),
    )


USUARIO = UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)


class _RepositorioDeAuditoriaIntermitente:
    """Repositorio falso: lanza mientras esta caido y guarda lo que recibe cuando esta disponible."""

    def __init__(self):
        self.caido = True
        self.persistidos = []

    def registrar(self, evento):
        if self.caido:
            raise ConnectionError('simulated: repositorio de auditoria no disponible')
        self.persistidos.append(evento)


class TestSubcaso169ContinuidadAnteFalloDelRepositorio:

    def test_eventos_generados_con_el_repositorio_caido_se_persisten_en_orden_al_recuperarse(self):
        repo = _RepositorioDeAuditoriaIntermitente()
        uc, _ = _crecimiento_use_case(repo)

        uc.execute(ID_ACTIVO_CON_FASE, _dto(), USUARIO)   # evento 1, repositorio caido
        time.sleep(0.01)
        uc.execute(ID_ACTIVO_CON_FASE, _dto(), USUARIO)   # evento 2, repositorio caido
        repo.caido = False                                  # el repositorio se restaura
        time.sleep(0.01)
        uc.execute(ID_ACTIVO_CON_FASE, _dto(), USUARIO)   # evento 3, repositorio disponible

        assert len(repo.persistidos) == 3, (
            f'Se generaron 3 eventos de auditoria y solo {len(repo.persistidos)} llegaron al repositorio: '
            'los generados con el repositorio caido se descartan en silencio (except Exception: pass), '
            'no existe ningun buffer ni reintento en biological_assets.'
        )
        marcas = [e.timestamp_evento for e in repo.persistidos]
        assert marcas == sorted(marcas)


class TestSubcaso170FalloDeAuditoriaNoBloqueaElFlujoOperativo:

    def test_rf40_en_vivo_se_completa_y_queda_auditado(self):
        """Linea base en TEST: el flujo normal de RF-40 responde 201 y genera su registro de auditoria."""
        token = _token()
        antes = _total_bitacora(token)
        r = httpx.post(
            f'{BASE_URL}/activos-biologicos/{ID_ACTIVO_CON_FASE}/eventos/crecimiento',
            json={'tipo_medicion': 'PESO', 'valor_medicion': 1.5, 'unidad_medida': 'kg'},
            headers={'Authorization': f'Bearer {token}'}, timeout=30,
        )
        assert r.status_code == 201, r.text
        assert _total_bitacora(token) == antes + 1

    def test_la_operacion_se_completa_aunque_falle_el_repositorio_de_auditoria(self):
        repo = _RepositorioDeAuditoriaIntermitente()   # caido todo el tiempo
        uc, db = _crecimiento_use_case(repo)

        evento, _fase_avanzada = uc.execute(ID_ACTIVO_CON_FASE, _dto(), USUARIO)

        assert evento is not None
        db.commit.assert_called()
        db.rollback.assert_not_called()

    def test_la_latencia_del_repositorio_de_auditoria_no_retrasa_la_operacion(self):
        """La ficha pide 'sin bloqueo ni retraso perceptible por la falla de auditoria'."""
        repo = MagicMock()
        repo.registrar.side_effect = lambda evento: time.sleep(1.0)   # auditoria lenta
        uc, _ = _crecimiento_use_case(repo)

        inicio = time.perf_counter()
        uc.execute(ID_ACTIVO_CON_FASE, _dto(), USUARIO)
        transcurrido = time.perf_counter() - inicio

        assert transcurrido < 0.5, (
            f'La operacion tardo {transcurrido:.2f}s con una auditoria de 1.0s de latencia: '
            'el registro de auditoria se ejecuta de forma sincrona dentro de la peticion, sin timeout ni cola asincrona.'
        )
