"""TC-M02-G94 V3 -- TC-M02-164 (API de solo lectura) y TC-M02-165 (autenticacion obligatoria).

RF-50 / CU12. Adaptacion minima de ``test_tc_m02_g94_security.py`` (V1): se conservan el
objetivo, los oraculos y los criterios; cambian el dominio TEST vigente y la identidad tecnica,
que en V1 todavia no existia. No se modifica el archivo historico.

Las contrasenas llegan por variables de entorno y nunca se escriben en los artefactos. El token
se usa en memoria del proceso; no se persiste, ni el encabezado Authorization completo.

Uso:
    M04_RF50_PASSWORD=... python -m pytest test_tc_m02_g94_security_v3.py \
        --junitxml=RESULTADOS/<RUN_ID>/reporte-pytest-g94-v3.xml -p no:cacheprovider
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

BASE = os.environ.get('G94_BASE_TEST', 'https://api.inmero.co/back-sigab-test')
ID_ACTIVO = int(os.environ.get('G94_ID_ACTIVO', '279'))
CORREO_M04 = 'dev.m04.rf50@sgpmp-test.com'
TIPO_DATO_M04 = 'eventos'
TIEMPO_ESPERA = 45

RUTA_CONSOLIDADOS = f'/activos-biologicos/{ID_ACTIVO}/datos-consolidados'
RUTA_DETALLE = f'/activos-biologicos/{ID_ACTIVO}'
# Campos que delatarian exposicion de datos consolidados en una respuesta no autenticada.
CAMPOS_SENSIBLES = (
    'id_activo_biologico', 'identificador', 'tipo_activo', 'especie', 'estado_actual',
    'infraestructura_asociada', 'fase_productiva_activa', 'historial_eventos',
    'historial_fases', 'historico_estados', 'metricas_actuales',
)

# Observaciones que el runner del RUN recoge para la evidencia consolidada.
OBSERVADO: dict = {'TC-M02-164': {}, 'TC-M02-165': {}}


def _pedir(metodo: str, ruta: str, token: str | None = None, cuerpo: dict | None = None,
           authorization: str | None = None) -> requests.Response:
    cabeceras = {'Content-Type': 'application/json'}
    if authorization is not None:
        cabeceras['Authorization'] = authorization
    elif token:
        cabeceras['Authorization'] = f'Bearer {token}'
    return requests.request(metodo, BASE + ruta, headers=cabeceras, json=cuerpo, timeout=TIEMPO_ESPERA)


def _cuerpo(respuesta: requests.Response):
    try:
        return respuesta.json()
    except ValueError:
        return None


@pytest.fixture(scope='module')
def token_m04() -> str:
    """Token de la identidad tecnica M04. La contrasena solo vive en el entorno del proceso."""
    clave = os.environ.get('M04_RF50_PASSWORD')
    assert clave, 'Falta M04_RF50_PASSWORD: la credencial se pasa por variable de entorno'
    r = _pedir('POST', '/sesiones/', cuerpo={'correo_electronico': CORREO_M04, 'contrasena': clave})
    assert r.status_code == 200, f'La identidad tecnica M04 no autentico: {r.status_code}'
    cuerpo = _cuerpo(r) or {}
    token = cuerpo.get('token')
    assert token, 'La respuesta de sesion no trae token'
    return token


# ----------------------------------------------------------------- TC-M02-164 (solo lectura)

def test_tc_164_control_positivo_get_autorizado(token_m04: str) -> None:
    """Control positivo: el token es valido, el modulo esta autorizado y el activo es visible."""
    r = _pedir('GET', f'{RUTA_CONSOLIDADOS}?tipo_dato={TIPO_DATO_M04}&pagina=1&page_size=20',
               token=token_m04)
    cuerpo = _cuerpo(r) or {}
    OBSERVADO['TC-M02-164']['control_positivo'] = {
        'metodo': 'GET', 'http': r.status_code,
        'id_activo_devuelto': cuerpo.get('id_activo_biologico'),
        'identificador': cuerpo.get('identificador'),
        'instante': datetime.now(timezone.utc).isoformat(),
    }
    assert r.status_code == 200, f'El control positivo no devolvio 200: {r.status_code}'
    assert cuerpo.get('id_activo_biologico') == ID_ACTIVO


def test_tc_164_post_no_permitido(token_m04: str) -> None:
    """Un POST con token valido debe ser rechazado por metodo, no aceptado."""
    r = _pedir('POST', RUTA_CONSOLIDADOS, token=token_m04, cuerpo={'qa_intento_escritura': True})
    cuerpo = _cuerpo(r) or {}
    OBSERVADO['TC-M02-164']['post'] = {
        'metodo': 'POST', 'http': r.status_code, 'error_code': cuerpo.get('error_code'),
        'permitidos_cabecera_allow': r.headers.get('allow') or r.headers.get('Allow'),
    }
    assert r.status_code in (403, 405), f'POST devolvio {r.status_code}; se esperaba 403 o 405'
    assert not (200 <= r.status_code < 300), 'POST fue aceptado: la API no es de solo lectura'


def test_tc_164_put_no_permitido(token_m04: str) -> None:
    """Un PUT con token valido debe ser rechazado por metodo, no aceptado."""
    r = _pedir('PUT', RUTA_CONSOLIDADOS, token=token_m04, cuerpo={'qa_intento_escritura': True})
    cuerpo = _cuerpo(r) or {}
    OBSERVADO['TC-M02-164']['put'] = {
        'metodo': 'PUT', 'http': r.status_code, 'error_code': cuerpo.get('error_code'),
        'permitidos_cabecera_allow': r.headers.get('allow') or r.headers.get('Allow'),
    }
    assert r.status_code in (403, 405), f'PUT devolvio {r.status_code}; se esperaba 403 o 405'
    assert not (200 <= r.status_code < 300), 'PUT fue aceptado: la API no es de solo lectura'


def test_tc_164_integridad_del_activo_sin_cambios(token_m04: str) -> None:
    """Los intentos de escritura no deben haber alterado el activo.

    El snapshot se toma de ``GET /activos-biologicos/{id}``, que no comparte el contador de
    RF-50, para no consumir cuota del limitador antes de TC-M02-158.
    """
    antes = _cuerpo(_pedir('GET', RUTA_DETALLE, token=token_m04)) or {}
    _pedir('POST', RUTA_CONSOLIDADOS, token=token_m04, cuerpo={'qa_intento_escritura': True})
    _pedir('PUT', RUTA_CONSOLIDADOS, token=token_m04, cuerpo={'qa_intento_escritura': True})
    despues = _cuerpo(_pedir('GET', RUTA_DETALLE, token=token_m04)) or {}

    comparables = ('id_activo_biologico', 'identificador', 'tipo', 'id_especie', 'id_estado',
                   'nombre_estado', 'id_infraestructura', 'fecha_inicio_ciclo',
                   'fecha_actualizacion', 'atributos_dinamicos')
    recorte = lambda d: {k: d.get(k) for k in comparables}
    OBSERVADO['TC-M02-164']['integridad'] = {
        'antes': recorte(antes), 'despues': recorte(despues),
        'sin_cambios': recorte(antes) == recorte(despues),
        'fuente': 'GET /activos-biologicos/{id} (endpoint sin el contador de RF-50)',
    }
    assert antes, 'No se pudo leer el activo para el snapshot previo'
    assert recorte(antes) == recorte(despues), 'El activo cambio tras los intentos de escritura'
    assert despues.get('fecha_actualizacion') == antes.get('fecha_actualizacion')


# ------------------------------------------------------- TC-M02-165 (autenticacion obligatoria)

def _verificar_no_autenticado(r: requests.Response, variante: str) -> None:
    cuerpo = _cuerpo(r) or {}
    texto = json.dumps(cuerpo, ensure_ascii=False) if cuerpo else (r.text or '')
    expuestos = [c for c in CAMPOS_SENSIBLES if c in texto]
    OBSERVADO['TC-M02-165'][variante] = {
        'http': r.status_code, 'error_code': cuerpo.get('error_code'),
        'campos_sensibles_expuestos': expuestos,
        'menciona_el_identificador_del_activo': 'QAJE-CREC-OK' in texto,
        'menciona_el_id_del_activo': f'"id_activo_biologico": {ID_ACTIVO}' in texto,
    }
    assert r.status_code == 401, (
        f'{variante} devolvio {r.status_code}; TC-M02-165 exige 401 de autenticacion '
        '(un 403 de autorizacion no satisface el caso)'
    )
    assert not expuestos, f'{variante} expuso campos de datos consolidados: {expuestos}'
    assert 'QAJE-CREC-OK' not in texto, f'{variante} expuso el identificador del activo'


def test_tc_165_a_sin_encabezado_authorization() -> None:
    """Variante A: sin encabezado Authorization -> 401 y sin datos."""
    r = _pedir('GET', f'{RUTA_CONSOLIDADOS}?tipo_dato={TIPO_DATO_M04}')
    _verificar_no_autenticado(r, 'sin_token')


def test_tc_165_b_bearer_invalido() -> None:
    """Variante B: Bearer ficticio y deliberadamente invalido -> 401 y sin datos."""
    r = _pedir('GET', f'{RUTA_CONSOLIDADOS}?tipo_dato={TIPO_DATO_M04}',
               authorization='Bearer qa-token-ficticio-invalido-g94-v3')
    _verificar_no_autenticado(r, 'token_invalido')


# -------------------------------------------------------------------- volcado para la evidencia

def test_zz_volcar_observaciones() -> None:
    """Deja las observaciones en un JSON temporal para que el runner las consolide.

    No es una assertion funcional del caso: solo transporta lo observado.
    """
    destino = os.environ.get('G94_OBSERVADO_OUT')
    if destino:
        OBSERVADO['instante_ultimo_get_m04'] = datetime.now(timezone.utc).isoformat()
        Path(destino).write_text(json.dumps(OBSERVADO, indent=1, ensure_ascii=False), encoding='utf-8')
