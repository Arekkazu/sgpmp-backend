"""TC-M02-G47 V2 - reevaluacion dirigida de los hallazgos V1 (parte API + BD read-only).

No forma parte de TC-M02-089 ni modifica sus criterios. Reproduce explicitamente los
escenarios de los hallazgos registrados en el informe V1:

- OBS-G47-01 (V1 §3.2): la credencial documentada del Veterinario `juan.carlos@email.com`
  no existe y devuelve 401.
- OBS-G47-01 (V1 §10) / OBS-G47-02 (comentario del spec Cypress V1): el listado de
  activos devuelve varias paginas pero la vista no expone paginacion (parte API aqui;
  la parte UI esta en `hallazgos_g47_v2.cy.js`).
- OBS-G47-03 (V1 §8.3): `POST /sesiones/refresh` -> HTTP 500. V1 lo observo en Cypress
  tras recargar la pagina despues del login, y comprobo por API que sin cookie y con
  cookie invalida respondia 401. Aqui se repiten esas dos variantes y se anaden la de
  cookie valida recien emitida por el login y la de reutilizacion de una cookie ya rotada.

Escrituras: ninguna sobre datos de dominio. Solo logins/refresh (sesiones) y SELECT en
modo read-only. Los tokens y cookies se redactan en la evidencia.

Ejecucion (desde la raiz de sgpmp-backend), DESPUES de Pytest y Cypress V2:
    python <G47>/EvaluacionV2/hallazgos_api_g47_v2.py
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import psycopg2
import requests

BASE_URL = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test'
TIMEOUT = 30

ACTORES = [
    ('productor', 'm2m.nuevo@ejemplo.com', 'Test1234!', 450),
    ('veterinario', 'juan.carlos.qa133@sgpmp-test.com', 'Test1234!', 451),
    ('ingeniero', 'ingeniero@pecuaria.co', 'Pruebas12#', 452),
]
CORREO_VETERINARIO_DOCUMENTADO = 'juan.carlos@email.com'

DESTINO = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Resultados', 'hallazgos_api_v2.json')


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def cuerpo(respuesta: requests.Response) -> object:
    try:
        datos = respuesta.json()
    except ValueError:
        return respuesta.text[:500]
    if isinstance(datos, dict) and 'token' in datos:
        datos = {**datos, 'token': '<redactado>'}
    return datos


def atributos_set_cookie(respuesta: requests.Response) -> list[str]:
    """Atributos de Set-Cookie sin el valor del token."""
    salida = []
    for valor in respuesta.raw.headers.get_all('Set-Cookie') or []:
        nombre, _, resto = valor.partition('=')
        _, _, atributos = resto.partition(';')
        salida.append(f'{nombre}=<redactado>;{atributos}')
    return salida


def registro(respuesta: requests.Response) -> dict:
    return {
        'ts_utc': ahora(),
        'http': respuesta.status_code,
        'content_type': respuesta.headers.get('Content-Type'),
        'set_cookie': atributos_set_cookie(respuesta),
        'body': cuerpo(respuesta),
    }


def refresh(cookie: str | None) -> requests.Response:
    cookies = {'refresh_token': cookie} if cookie is not None else None
    return requests.post(f'{BASE_URL}/sesiones/refresh', cookies=cookies, timeout=TIMEOUT)


def main() -> None:
    evidencia: dict = {'inicio_utc': ahora()}

    # --- OBS-G47-01 (V1 §3.2): credencial documentada del Veterinario -------------------
    login_doc = requests.post(
        f'{BASE_URL}/sesiones/',
        json={'correo_electronico': CORREO_VETERINARIO_DOCUMENTADO, 'contrasena': 'Test1234!'},
        timeout=TIMEOUT,
    )
    with psycopg2.connect(host='158.69.200.27', port=5448, user='member_qa',
                          password=os.environ.get('PGPASSWORD_QA', 'qaSGP2026'), dbname='sgpmp_test') as con:
        con.set_session(readonly=True, autocommit=True)
        with con.cursor() as cur:
            cur.execute('SET default_transaction_read_only = on')
            cur.execute("SELECT current_user, current_database(), current_setting('transaction_read_only')")
            sesion_bd = cur.fetchone()
            cur.execute(
                'SELECT id_usuario, correo_electronico, id_rol FROM modulo1.usuarios '
                'WHERE correo_electronico IN (%s, %s) ORDER BY 1',
                (CORREO_VETERINARIO_DOCUMENTADO, 'juan.carlos.qa133@sgpmp-test.com'),
            )
            usuarios = [list(map(str, fila)) for fila in cur.fetchall()]
    evidencia['credencial_veterinario'] = {
        'login_correo_documentado': registro(login_doc),
        'sesion_bd': list(map(str, sesion_bd)),
        'usuarios_bd': usuarios,
    }

    # --- Por actor: listado (paginacion) y refresh -------------------------------------
    evidencia['actores'] = {}
    for clave, correo, contrasena, id_activo in ACTORES:
        datos: dict = {}
        login = requests.post(
            f'{BASE_URL}/sesiones/',
            json={'correo_electronico': correo, 'contrasena': contrasena},
            timeout=TIMEOUT,
        )
        datos['login'] = registro(login)
        token = login.json().get('token', '') if login.status_code == 200 else ''
        cookie_login = login.cookies.get('refresh_token')
        datos['login_emite_cookie_refresh'] = cookie_login is not None

        # OBS-G47-01/02: primera pagina del listado tal como la pide la vista (sin params).
        listado = requests.get(
            f'{BASE_URL}/activos-biologicos', headers={'Authorization': f'Bearer {token}'}, timeout=TIMEOUT
        )
        pagina = listado.json() if listado.status_code == 200 else {}
        registros = pagina.get('registros', []) if isinstance(pagina, dict) else []
        ids = [r.get('id_activo_biologico') for r in registros]
        datos['listado'] = {
            'http': listado.status_code,
            'claves': sorted(pagina.keys()) if isinstance(pagina, dict) else None,
            'pagina_actual': pagina.get('pagina_actual'),
            'total_paginas': pagina.get('total_paginas'),
            'total_registros': pagina.get('total_registros'),
            'registros_en_pagina': len(registros),
            'fixture': id_activo,
            'fixture_en_primera_pagina': id_activo in ids,
        }

        # OBS-G47-03: variantes de /sesiones/refresh.
        datos['refresh_sin_cookie'] = registro(refresh(None))
        datos['refresh_cookie_invalida'] = registro(refresh('cookie-invalida-qa'))
        if cookie_login is not None:
            valido = refresh(cookie_login)
            datos['refresh_cookie_valida'] = registro(valido)
            cookie_rotada = valido.cookies.get('refresh_token')
            datos['refresh_emite_cookie_nueva'] = cookie_rotada is not None and cookie_rotada != cookie_login
            # Reutilizacion de la cookie ya canjeada (el frontend documenta rotacion y
            # deteccion de reuso). Dato adicional, no escenario V1.
            datos['refresh_reuso_cookie_rotada'] = registro(refresh(cookie_login))
            if cookie_rotada is not None:
                datos['refresh_cookie_nueva_tras_reuso'] = registro(refresh(cookie_rotada))
        evidencia['actores'][clave] = datos

    evidencia['fin_utc'] = ahora()
    os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
    with open(DESTINO, 'w', encoding='utf-8') as fichero:
        json.dump(evidencia, fichero, ensure_ascii=False, indent=2)
    print(json.dumps(evidencia, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
