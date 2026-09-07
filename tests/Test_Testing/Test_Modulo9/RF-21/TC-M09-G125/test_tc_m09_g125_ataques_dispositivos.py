"""
TC-M09-G125 (TC-M09-244, TC-M09-245, TC-M09-246) - Pruebas de ataque:
suplantacion y enumeracion de dispositivos IoT (OWASP API1 Broken Object
Level Authorization, API4 Unrestricted Resource Consumption, API8 Security
Misconfiguration).

RF relacionado: RF-21, CU-05 Gestionar Dispositivos IoT
Categoria: Seguridad - Ataque (OWASP). Caso nuevo agregado por QA.

Herramienta pedida en la ficha: "OWASP ZAP + Pytest". ZAP (escaner DAST) no
esta disponible en este entorno de ejecucion, asi que los 3 escenarios se
cubren con Pytest + httpx llamando DIRECTAMENTE al backend real desplegado
en TEST (no mocks, no TestClient local) -- es la forma mas fiel de simular
estos 3 ataques sin ZAP. Ejecutado con autorizacion explicita del usuario
(incluida la rafaga del escenario 3, que crea trafico real contra la BD
compartida de TEST); todos los dispositivos creados por esta suite se
desactivan automaticamente al final (fixture `dispositivos_creados`).

IMPORTANTE - como leer los resultados de esta suite: a diferencia de las
demas pruebas de M09, aqui las aserciones representan el comportamiento de
SEGURIDAD que la ficha exige (parametro "Ataque debe ser rechazado/
detectado por el sistema"), no necesariamente lo que el codigo hace hoy.
Un test en rojo aqui documenta una brecha de seguridad real encontrada en
el codigo (mismo criterio que TC-M09-G64), no un error de la prueba.

Escenario 1 (TC-M09-244) - Suplantacion via identificador reutilizado:
    El sistema NO tiene un UUID de dispositivo separado (confirmado
    revisando dispositivo_iot_model.py y el DTO): el identificador de
    negocio unico es el campo `serial` (value object SerialDispositivo,
    src/configuration/domain/value_objects/serial_dispositivo.py), y
    RegistrarDispositivoIotUseCase.execute() SI valida unicidad via
    dispositivo_repo.obtener_por_serial() antes de crear, respondiendo
    409 SERIAL_DUPLICADO si ya existe. Se prueba reutilizando el serial
    de un dispositivo real ya registrado. EXPECTATIVA: correctamente
    protegido (este es el unico de los 3 escenarios donde se espera que
    la asercion de seguridad SI pase contra el codigo actual).

Escenario 2 (TC-M09-245) - Inyeccion SQL/NoSQL en campos de texto:
    RegistrarDispositivoIotDTO.validar_serial/validar_descripcion y el
    value object SerialDispositivo (src/configuration/domain/value_objects/
    serial_dispositivo.py) SOLO verifican longitud y que no este vacio --
    no hay whitelist de caracteres ni rechazo de patrones sospechosos.
    HALLAZGO ESPERADO: un payload tipo `' OR '1'='1` en `serial` o
    `<script>alert(1)</script>` en `descripcion` NO sera rechazado con 400
    como pide la ficha; el backend respondera 201 y guardara el texto tal
    cual. Esto es una brecha de VALIDACION DE ENTRADA (OWASP API8), pero
    -- se verifica aparte -- NO es una inyeccion SQL explotable: el
    repositorio usa SQLAlchemy ORM con queries parametrizadas
    (`.filter(DispositivoIotModel.serial == serial)`, `db.add(orm)`), asi
    que el payload queda almacenado como dato literal, nunca se ejecuta
    como sentencia SQL. La suite documenta ambas cosas por separado: la
    aserion de "debe rechazarse con 400" (se espera que falle, documentando
    el hallazgo) y la aserion de "no hubo inyeccion real" (se espera que
    pase, confirmando que el ORM protege aunque la validacion de entrada
    no exista).

Escenario 3 (TC-M09-246) - Enumeracion/fuerza bruta sin rate limiting:
    src/shared/middlewares.py solo registra `RequestContextMiddleware`
    (request_id/IP/user-agent) y `AccessLogMiddleware` (logging) -- no
    existe ningun middleware ni dependencia de rate limiting en todo el
    proyecto (confirmado por busqueda de codigo). HALLAZGO ESPERADO: 50
    registros con seriales secuenciales disparados en paralelo en menos de
    10 segundos se aceptaran todos (201) sin ningun 429 ni bloqueo. La
    aserion de "el sistema debe limitar/bloquear la rafaga" se espera que
    falle, documentando la ausencia de rate limiting (OWASP API4).

Como correrlo (desde la raiz del repo):
    python -m pytest <ruta>\\test_tc_m09_g125_ataques_dispositivos.py -v \
        --html=Resultados/reporte-TC-M09-G125.html --self-contained-html
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

BASE_URL = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
ADMIN_CORREO = "admin@pecuaria.co"
ADMIN_CONTRASENA = "Test1234!"
ENDPOINT_DISPOSITIVOS = f"{BASE_URL}/configuracion/dispositivos-iot"
RUN_ID = str(int(time.time() * 1000))


@pytest.fixture(scope="module")
def admin_token() -> str:
    resp = httpx.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": ADMIN_CORREO, "contrasena": ADMIN_CONTRASENA},
        timeout=30,
    )
    assert resp.status_code == 200, f"No se pudo iniciar sesion como admin: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="module")
def headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def id_infraestructura(headers: dict) -> int:
    resp = httpx.get(
        f"{BASE_URL}/configuracion/infraestructuras",
        params={"finca_id": 1, "solo_activas": "true"},
        headers=headers,
        timeout=30,
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items, "Se necesita al menos un area productiva activa en TEST."
    return items[0]["id_infraestructura"]


@pytest.fixture(scope="module")
def id_tipo_dispositivo(headers: dict) -> int:
    resp = httpx.get(f"{BASE_URL}/configuracion/tipos-dispositivo-iot", headers=headers, timeout=30)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items, "Se necesita al menos un tipo de dispositivo en el catalogo de TEST."
    return items[0]["id_tipo_dispositivo"]


@pytest.fixture(scope="module")
def dispositivos_creados(headers: dict):
    """Recolecta los IDs de dispositivos creados por esta suite y los
    desactiva al finalizar, para no dejar basura en la BD compartida de
    TEST (autorizado explicitamente por el usuario para esta ficha)."""
    ids: list[int] = []
    yield ids
    for id_dispositivo in ids:
        try:
            httpx.patch(
                f"{ENDPOINT_DISPOSITIVOS}/{id_dispositivo}/desactivar",
                headers=headers,
                timeout=30,
            )
        except Exception:
            pass


class TestTCM09G125AtaquesDispositivos:
    """Suite de pruebas de ataque para TC-M09-G125."""

    def test_escenario1_tc_m09_244_suplantacion_via_serial_reutilizado(
        self, headers, id_infraestructura, id_tipo_dispositivo, dispositivos_creados,
    ):
        """OWASP API1: reutilizar el identificador (serial) de un
        dispositivo activo real no debe permitir crear un segundo
        dispositivo con esa misma identidad."""
        serial = f"TC-M09-G125-IMPERSONATE-{RUN_ID}"
        payload_legitimo = {
            "serial": serial,
            "descripcion": "Dispositivo legitimo original - TC-M09-G125",
            "id_infraestructura": id_infraestructura,
            "id_tipo_dispositivo": id_tipo_dispositivo,
            "es_activo": True,
        }

        resp_original = httpx.post(ENDPOINT_DISPOSITIVOS, json=payload_legitimo, headers=headers, timeout=30)
        assert resp_original.status_code == 201, f"Precondicion fallida: {resp_original.text}"
        id_original = resp_original.json()["id_dispositivo_iot"]
        dispositivos_creados.append(id_original)

        payload_impostor = dict(payload_legitimo, descripcion="Dispositivo IMPOSTOR - mismo serial - TC-M09-G125")
        resp_impostor = httpx.post(ENDPOINT_DISPOSITIVOS, json=payload_impostor, headers=headers, timeout=30)

        assert resp_impostor.status_code == 409, (
            "OWASP API1: el sistema debe rechazar la suplantacion de identidad "
            f"(serial reutilizado) con 409. Respondio {resp_impostor.status_code}: {resp_impostor.text}"
        )
        assert resp_impostor.json().get("error_code") == "SERIAL_DUPLICADO"

        listado = httpx.get(ENDPOINT_DISPOSITIVOS, params={"solo_activos": "false"}, headers=headers, timeout=30)
        assert listado.status_code == 200
        coincidencias = [d for d in listado.json()["items"] if d["serial"] == serial]
        assert len(coincidencias) == 1, (
            f"No debe existir mas de 1 dispositivo con el serial suplantado; se encontraron {len(coincidencias)}."
        )
        assert coincidencias[0]["id_dispositivo_iot"] == id_original

    def test_escenario2_tc_m09_245_payload_inyeccion_sql_nosql(
        self, headers, id_infraestructura, id_tipo_dispositivo, dispositivos_creados,
    ):
        """OWASP API8: un payload de inyeccion SQL/NoSQL en serial/
        descripcion debe ser rechazado (400) segun la ficha, y en
        cualquier caso nunca debe ejecutarse como sentencia SQL real."""
        serial_ataque = f"' OR '1'='1' -- {RUN_ID}"[:50]
        descripcion_ataque = "<script>alert(1)</script>"
        payload_ataque = {
            "serial": serial_ataque,
            "descripcion": descripcion_ataque,
            "id_infraestructura": id_infraestructura,
            "id_tipo_dispositivo": id_tipo_dispositivo,
            "es_activo": True,
        }

        resp = httpx.post(ENDPOINT_DISPOSITIVOS, json=payload_ataque, headers=headers, timeout=30)

        # Si el ataque quedo aceptado (201), lo registramos para limpieza y
        # verificamos que el ORM lo trato como dato literal (sin ejecutar
        # SQL ni romper el endpoint) antes de reportar el hallazgo de
        # validacion de entrada.
        if resp.status_code == 201:
            id_creado = resp.json()["id_dispositivo_iot"]
            dispositivos_creados.append(id_creado)

            detalle = httpx.get(f"{ENDPOINT_DISPOSITIVOS}/{id_creado}", headers=headers, timeout=30)
            assert detalle.status_code == 200, (
                "El payload de inyeccion no debe dejar el sistema en un estado "
                f"inconsistente (detalle respondio {detalle.status_code})."
            )
            assert detalle.json()["serial"] == serial_ataque, (
                "El ORM debe almacenar el payload como texto literal, sin interpretarlo "
                "como SQL (si esto falla, hay una inyeccion real explotable)."
            )
            assert detalle.json()["descripcion"] == descripcion_ataque

        assert resp.status_code == 400, (
            "OWASP API8: la ficha exige que un payload con sintaxis de inyeccion "
            f"SQL/NoSQL sea rechazado con 400. El backend no valida el charset de "
            f"serial/descripcion (solo longitud) y respondio {resp.status_code}: {resp.text}. "
            "Hallazgo: falta validacion de entrada a nivel de API, aunque el ORM "
            "(SQLAlchemy, queries parametrizadas) impide que el payload se ejecute "
            "como SQL real -- no es una inyeccion explotable, es una brecha de "
            "saneamiento/validacion de entrada."
        )

    def test_escenario3_tc_m09_246_enumeracion_masiva_sin_rate_limit(
        self, headers, id_infraestructura, id_tipo_dispositivo, dispositivos_creados,
    ):
        """OWASP API4: una rafaga de 50 registros con seriales secuenciales
        en menos de 10 segundos debe ser bloqueada, limitada o marcada
        como sospechosa por el sistema."""
        cantidad = 50

        def _registrar(indice: int) -> httpx.Response:
            payload = {
                "serial": f"TC-M09-G125-BURST-{RUN_ID}-{indice:03d}",
                "descripcion": f"Enumeracion masiva #{indice} - TC-M09-G125",
                "id_infraestructura": id_infraestructura,
                "id_tipo_dispositivo": id_tipo_dispositivo,
                "es_activo": True,
            }
            return httpx.post(ENDPOINT_DISPOSITIVOS, json=payload, headers=headers, timeout=30)

        inicio = time.monotonic()
        with ThreadPoolExecutor(max_workers=20) as pool:
            respuestas = list(pool.map(_registrar, range(cantidad)))
        duracion = time.monotonic() - inicio

        for indice, resp in enumerate(respuestas):
            if resp.status_code == 201:
                dispositivos_creados.append(resp.json()["id_dispositivo_iot"])

        codigos = [r.status_code for r in respuestas]
        exitosos = codigos.count(201)
        limitados = sum(1 for c in codigos if c == 429)

        print(
            f"\n--- TC-M09-246: {cantidad} solicitudes en {duracion:.2f}s -- "
            f"exitosas(201)={exitosos}, rate-limited(429)={limitados}, "
            f"otros={cantidad - exitosos - limitados} ---"
        )

        assert duracion < 10, (
            f"Precondicion de la prueba: la rafaga debe completarse en menos de 10s "
            f"para ser representativa; tomo {duracion:.2f}s."
        )

        assert limitados > 0 or exitosos < cantidad, (
            "OWASP API4: el sistema debe bloquear, limitar (429) o marcar como "
            f"sospechosa la rafaga de {cantidad} registros en {duracion:.2f}s. "
            f"Los {cantidad} registros se aceptaron sin ninguna restriccion "
            "(no existe rate limiting en ningun middleware del proyecto -- "
            "confirmado en src/shared/middlewares.py, que solo registra "
            "RequestContextMiddleware y AccessLogMiddleware). Hallazgo: falta "
            "control de tasa (rate limiting) en la API."
        )
