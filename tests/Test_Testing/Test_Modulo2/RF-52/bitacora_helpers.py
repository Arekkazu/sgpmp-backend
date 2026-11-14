"""Utilidades compartidas por los TC de bitacora RF-52 (G99, G101, G103, G104, G106, G108).

Ayudantes de HTTP en vivo contra TEST, dobles de prueba de RF-40 y recalculo del
hash de integridad. Vive un nivel por encima de las carpetas de TC, por lo que
el scanner (que solo recorre las carpetas TC-M02-G*) no lo lee.
"""
import hashlib
import json
import os
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import httpx

BASE_URL = os.getenv(
    'SGPMP_TEST_BASE_URL',
    'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test',
)
REPO_ROOT = Path(__file__).resolve().parents[4]
RUTA_AUDITORIA = '/activos-biologicos/auditoria'
PASSWORD = 'Test1234!'
ADMIN = 'admin@pecuaria.co'
PRODUCTOR = 'm2m.nuevo@ejemplo.com'
CONTADOR = 'contador@pecuaria.co'
ID_ACTIVO_CON_HISTORIAL = 306
ID_ACTIVO_CON_BITACORA_MIXTA = 240   # activo con ACCESO_DATOS, TRANSFORMACION_BIOLOGICA, SANITARIO, etc.
ID_ACTIVO_CON_FASE = 374             # INDIVIDUAL ACTIVO con fase (RF-40 en vivo)


def login(correo: str) -> str:
    r = httpx.post(f'{BASE_URL}/sesiones/', json={'correo_electronico': correo, 'contrasena': PASSWORD}, timeout=30)
    assert r.status_code == 200, f'login {correo}: {r.status_code} {r.text}'
    return r.json()['token']


def get(token: str, path: str, **params) -> httpx.Response:
    return httpx.get(f'{BASE_URL}{path}', params=params, headers={'Authorization': f'Bearer {token}'}, timeout=30)


def request(token: str, metodo: str, path: str, **kwargs) -> httpx.Response:
    return httpx.request(metodo, f'{BASE_URL}{path}', headers={'Authorization': f'Bearer {token}'}, timeout=30, **kwargs)


def total_bitacora(token: str) -> int:
    return get(token, RUTA_AUDITORIA, page_size=1).json()['total_registros']


def ultimo_registro(token: str) -> dict:
    return get(token, RUTA_AUDITORIA, page_size=1).json()['registros'][0]


# --- hash de integridad (misma formula que SqlAlchemyBitacoraAuditoriaRepository._calcular_hash) -----------------

def _iso_python(marca: str) -> str:
    return datetime.fromisoformat(marca.replace('Z', '+00:00')).astimezone(timezone.utc).isoformat()


def recalcular_hash(registro: dict) -> str:
    payload = {
        'rf_origen': registro['rf_origen'],
        'tipo_evento': registro['tipo_evento'],
        'clasificacion_biologica': registro['clasificacion_biologica'],
        'id_activo_biologico': registro['id_activo_biologico'],
        'timestamp_evento': _iso_python(registro['timestamp_evento']),
        'timestamp_registro': _iso_python(registro['timestamp_registro']),
        'resultado': registro['resultado'],
        'id_usuario_responsable': registro['id_usuario_responsable'],
        'severidad_log': registro['severidad_log'],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


# --- evidencia estructural del esquema -------------------------------------------------------------------------

def hay_bloqueo_de_escritura_en_bd() -> list[str]:
    """Archivos del repo con un trigger o REVOKE que proteja modulo2.bitacora_auditoria_m02."""
    archivos = [REPO_ROOT / 'alembic' / 'baseline' / 'esquema_baseline.sql', *(REPO_ROOT / 'alembic').rglob('versions/*.py')]
    trigger = re.compile(r'CREATE\s+(?:CONSTRAINT\s+)?TRIGGER[^;]*?\bON\s+modulo2\.bitacora_auditoria_m02', re.I | re.S)
    revoke = re.compile(r'REVOKE\s+(?:UPDATE|DELETE|INSERT)[^;]*bitacora_auditoria_m02', re.I | re.S)
    return [
        str(a.relative_to(REPO_ROOT))
        for a in archivos
        if a.exists() and (lambda t: trigger.search(t) or revoke.search(t))(a.read_text(encoding='utf-8', errors='ignore'))
    ]


def archivos_de_m02_que_mencionan(patron: str) -> list[str]:
    rx = re.compile(patron, re.I)
    return [
        str(p.relative_to(REPO_ROOT))
        for p in (REPO_ROOT / 'src' / 'biological_assets').rglob('*.py')
        if rx.search(p.read_text(encoding='utf-8', errors='ignore'))
    ]


# --- dobles de RF-40 para probar resiliencia de la auditoria -----------------------------------------------------

USUARIO_ID = 1


def crecimiento_use_case(bitacora_repo):
    from src.biological_assets.application.use_cases.gestion.registrar_evento_crecimiento_use_case import (
        RegistrarEventoCrecimientoUseCase,
    )
    from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, GestionFase

    activo = ActivoBiologico(
        id_especie=4, tipo='INDIVIDUAL', origen_financiero='compra', id_infraestructura=6, id_estado=1,
        id_usuario=1, id_activo_biologico=ID_ACTIVO_CON_FASE, fecha_inicio_ciclo=date(2026, 8, 1),
        fecha_creacion=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    fase = GestionFase(
        id_gestion_fases=1, id_activo_biologico=ID_ACTIVO_CON_FASE, id_ciclo_productiva=4,
        nombre_ciclo='Ciclo completo cachama 2025-A', nombre_fase_actual='Fase juvenil cachama', paso_actual=1,
        total_pasos=2, fecha_inicio=datetime(2026, 8, 1, tzinfo=timezone.utc), fecha_finalizacion=None,
        es_activa=True, id_usuario=1,
    )
    activo_repo = MagicMock()
    activo_repo.obtener_por_id.return_value = activo
    activo_repo.obtener_fase_activa.return_value = fase
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


def dto_crecimiento():
    from src.biological_assets.infrastructure.dto.registrar_evento_crecimiento_dto import RegistrarEventoCrecimientoDTO

    return RegistrarEventoCrecimientoDTO(
        tipo_medicion='PESO', valor_medicion=Decimal('1.5'), unidad_medida='kg',
        fecha=datetime(2026, 9, 14, 10, tzinfo=timezone.utc),
    )


def usuario_actual():
    from src.identity_access.infrastructure.dependencies import UsuarioActual

    return UsuarioActual(id_usuario=USUARIO_ID, id_token=1, id_rol=1, id_estado_cuenta=2)


class RepositorioDeAuditoriaIntermitente:
    """Repositorio falso: lanza mientras esta caido y guarda lo que recibe cuando esta disponible."""

    def __init__(self):
        self.caido = True
        self.persistidos = []

    def registrar(self, evento):
        if self.caido:
            raise ConnectionError('simulated: repositorio de auditoria no disponible')
        self.persistidos.append(evento)
