"""Prueba de Integración: Validación de Límite de Paginación Exacta (500 vs 501 registros).

Módulo: M02 - Activos Biológicos
Requisito Funcional: RF-46 (CU10A - Historial de eventos del activo biológico)
Caso de Prueba: TC-M02-211 (Agrupado TC-M02-G76)
Entorno: TEST
"""
import os
import requests
import pytest
import psycopg2
from psycopg2.extras import execute_values

BASE_URL = os.getenv(
    "API_BASE_URL",
    "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
)

DB_URL = os.getenv(
    "TEST_DB_URL",
    "postgresql://member_qa:qaSGP2026@158.69.200.27:5448/sgpmp_test"
)

ID_ACTIVO = 130


def _login(correo: str = "admin@pecuaria.co", password: str = "Test1234!") -> str:
    resp = requests.post(f"{BASE_URL}/sesiones/", json={
        "correo_electronico": correo,
        "contrasena": password
    }, timeout=10)
    assert resp.status_code == 200, f"Fallo de autenticación para {correo}: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="session")
def admin_token() -> str:
    return _login("admin@pecuaria.co")


@pytest.fixture(scope="function")
def setup_sintetico_historial():
    """Fixture que gestiona la inserción y limpieza estricta de 500 registros sintéticos.
    
    Usa la tabla modulo2.indicadores_zootecnicos con rango_fecha en el año 2030,
    lo que alimenta la vista modulo2.vw_rf46_historial_completo_activo sin violar
    los triggers de inmutabilidad de modulo2.eventos_activos.
    """
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    try:
        # 1. Limpieza preventiva previa
        cursor.execute(
            "DELETE FROM modulo2.indicadores_zootecnicos "
            "WHERE id_activo_biologico = %s AND lower(rango_fecha) >= '2030-01-01'::date;",
            (ID_ACTIVO,)
        )
        conn.commit()

        # 2. Inserción en lote de 500 registros sintéticos iniciales
        # rango_fecha: [2030-01-01, 2030-01-02), tipo: 'ganancia_peso'
        records = [
            (ID_ACTIVO, "[2030-01-01, 2030-01-02)", "ganancia_peso", '{"sintetico": true, "subcaso": "TC-M02-211"}')
            for _ in range(500)
        ]
        insert_query = (
            "INSERT INTO modulo2.indicadores_zootecnicos "
            "(id_activo_biologico, rango_fecha, tipo, paramtros_calculo) "
            "VALUES %s"
        )
        execute_values(cursor, insert_query, records, template="(%s, %s::daterange, %s, %s::jsonb)")
        conn.commit()

        cursor.execute(
            "SELECT COUNT(*) FROM modulo2.indicadores_zootecnicos "
            "WHERE id_activo_biologico = %s AND lower(rango_fecha) >= '2030-01-01'::date;",
            (ID_ACTIVO,)
        )
        assert cursor.fetchone()[0] == 500, "La inserción masiva inicial de 500 registros no fue completa"

        yield conn

    finally:
        # Teardown garantizado con rollback preventivo
        try:
            conn.rollback()
            cursor.execute(
                "DELETE FROM modulo2.indicadores_zootecnicos "
                "WHERE id_activo_biologico = %s AND lower(rango_fecha) >= '2030-01-01'::date;",
                (ID_ACTIVO,)
            )
            conn.commit()
            cursor.execute(
                "SELECT COUNT(*) FROM modulo2.indicadores_zootecnicos "
                "WHERE id_activo_biologico = %s AND lower(rango_fecha) >= '2030-01-01'::date;",
                (ID_ACTIVO,)
            )
            rem = cursor.fetchone()[0]
            assert rem == 0, f"Quedaron {rem} registros sintéticos huérfanos tras teardown"
        finally:
            cursor.close()
            conn.close()


def test_tc_m02_211_limite_paginacion_500_vs_501(admin_token, setup_sintetico_historial):
    """TC-M02-211: Validar cálculo exacto del total de páginas en el límite (500 vs 501 registros).
    
    1. Con 500 registros y page_size=100 -> total_paginas=5, len(registros)=100 en pág 1.
    2. Al añadir 1 registro (501 total) y page_size=100 -> total_paginas=6.
    3. En página 6 -> exactamente 1 registro remanente.
    """
    headers = {"Authorization": f"Bearer {admin_token}"}
    conn = setup_sintetico_historial
    cursor = conn.cursor()

    # --- Fase 1: Validar con exactamente 500 registros ---
    resp_500 = requests.get(
        f"{BASE_URL}/activos-biologicos/{ID_ACTIVO}/historial",
        params={"fecha_inicio": "2030-01-01", "page_size": 100, "pagina": 1},
        headers=headers,
        timeout=10
    )
    assert resp_500.status_code == 200, f"Error al consultar historial con 500 registros: {resp_500.text}"
    data_500 = resp_500.json()

    assert data_500["total_registros"] == 500, f"total_registros esperado 500, obtenido {data_500['total_registros']}"
    assert data_500["total_paginas"] == 5, f"total_paginas esperado 5, obtenido {data_500['total_paginas']}"
    assert data_500["pagina_actual"] == 1, f"pagina_actual esperada 1, obtenida {data_500['pagina_actual']}"
    assert data_500["registros_por_pagina"] == 100, f"registros_por_pagina esperado 100, obtenido {data_500['registros_por_pagina']}"
    assert len(data_500["registros"]) == 100, f"Se esperaban 100 registros en la página 1, se recibieron {len(data_500['registros'])}"

    # --- Fase 2: Insertar el registro 501 ---
    cursor.execute(
        "INSERT INTO modulo2.indicadores_zootecnicos "
        "(id_activo_biologico, rango_fecha, tipo, paramtros_calculo) "
        "VALUES (%s, '[2030-02-01, 2030-02-02)'::daterange, 'ganancia_peso', '{\"sintetico\": true, \"numero\": 501}'::jsonb);",
        (ID_ACTIVO,)
    )
    conn.commit()

    cursor.execute(
        "SELECT COUNT(*) FROM modulo2.indicadores_zootecnicos "
        "WHERE id_activo_biologico = %s AND lower(rango_fecha) >= '2030-01-01'::date;",
        (ID_ACTIVO,)
    )
    assert cursor.fetchone()[0] == 501, "No se reflejaron los 501 registros en la base de datos"

    # --- Fase 3: Validar con 501 registros (Frontera de paginación) ---
    resp_501 = requests.get(
        f"{BASE_URL}/activos-biologicos/{ID_ACTIVO}/historial",
        params={"fecha_inicio": "2030-01-01", "page_size": 100, "pagina": 1},
        headers=headers,
        timeout=10
    )
    assert resp_501.status_code == 200, f"Error al consultar historial con 501 registros: {resp_501.text}"
    data_501 = resp_501.json()

    assert data_501["total_registros"] == 501, f"total_registros esperado 501, obtenido {data_501['total_registros']}"
    assert data_501["total_paginas"] == 6, f"total_paginas esperado 6 (ceil(501/100)), obtenido {data_501['total_paginas']}"
    assert len(data_501["registros"]) == 100, f"Se esperaban 100 registros en página 1, recibidos {len(data_501['registros'])}"

    # --- Fase 4: Validar la última página (Página 6 con exactamente 1 registro) ---
    resp_pag6 = requests.get(
        f"{BASE_URL}/activos-biologicos/{ID_ACTIVO}/historial",
        params={"fecha_inicio": "2030-01-01", "page_size": 100, "pagina": 6},
        headers=headers,
        timeout=10
    )
    assert resp_pag6.status_code == 200, f"Error al consultar página 6: {resp_pag6.text}"
    data_pag6 = resp_pag6.json()

    assert data_pag6["pagina_actual"] == 6, f"pagina_actual esperada 6, obtenida {data_pag6['pagina_actual']}"
    assert data_pag6["total_paginas"] == 6, f"total_paginas esperado 6, obtenido {data_pag6['total_paginas']}"
    assert len(data_pag6["registros"]) == 1, f"Se esperaba exactamente 1 registro en la página 6, se recibieron {len(data_pag6['registros'])}"
