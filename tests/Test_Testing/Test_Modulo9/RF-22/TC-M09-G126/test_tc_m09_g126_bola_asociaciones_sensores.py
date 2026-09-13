"""
TC-M09-G126 (TC-M09-247, TC-M09-248, TC-M09-249) - Pruebas de ataque:
control de acceso a nivel de objeto en asociaciones de sensores (OWASP API1
Broken Object Level Authorization, API3 Broken Object Property Level
Authorization).

RF relacionado: RF-22, CU-05 Gestionar Dispositivos IoT
Categoria: Seguridad - Ataque (OWASP). Caso nuevo agregado por QA.

Herramienta pedida en la ficha: Pytest (manipulacion directa del payload/
parametros con credenciales de un rol sin permiso sobre el recurso
objetivo). Ejecutado contra el backend real de TEST (autorizado por el
usuario para el mismo tipo de prueba que TC-M09-G125; los dispositivos
creados se desactivan al final via la fixture de limpieza).

CONTEXTO DE MULTI-TENANCY REAL EN EL SISTEMA (verificado en el codigo y en
vivo antes de construir esta prueba):
- `modulo9.fincas` SI tiene una columna `id_usuario` (dueno de la finca), y
  RF-19 (src/configuration/infrastructure/routers/finca_router.py,
  ConsultarFincasUseCase) SI implementa scoping por finca para el rol
  Productor: `listar_fincas`/`obtener_finca` filtran por
  `usuario_actual.id_usuario` cuando el rol es Productor, y devuelven 404
  (no 403 -- buena practica anti-enumeracion) si la finca no es suya.
- Ese scoping NO se propaga a RF-20 (infraestructuras/areas) ni a RF-22
  (asociaciones sensor-area): ni `ConsultarInfraestructurasUseCase`
  (listar_por_finca/obtener) ni `AsociarSensorAreaUseCase`/
  `ConsultarAsociacionesUseCase` reciben o verifican jamas el
  `id_usuario`/dueno de la finca a la que pertenece el area o el sensor.
  Esta es la causa raiz que se explota en los 3 escenarios.
- Cuenta de prueba usada como "usuario sin relacion con ninguna finca":
  el Productor ya conocido (u20221206763@usco.edu.co, id_usuario=58).
  Confirmado en vivo que `GET /configuracion/fincas` con su token devuelve
  `total:0` -- NO es dueno de NINGUNA finca. Esto hace la prueba MAS
  contundente que el escenario original de la ficha ("Usuario Finca A
  accede a Finca B"): un usuario sin ninguna finca propia puede igual leer
  infraestructura y asociaciones de sensores de fincas ajenas.
- Las 4 fincas seed de TEST (id 1-4) pertenecen todas a id_usuario=2 (no es
  la cuenta de Productor disponible). Se usan como "Finca A" el area activa
  id_infraestructura=3 (finca_id=1, "Alevinera-01") y como "Finca B" el
  area activa id_infraestructura=4 (finca_id=2, "Canal-Trucha-01").

Escenario 1 (TC-M09-247) - IDOR al asociar sensor a area de otra finca:
    POST /configuracion/sensores/{id}/asociar exige recurso 12 accion C=1,
    que solo tienen Administrador e Ingeniero (Productor/Veterinario NO
    pueden llegar aqui -- RBAC ya lo bloquea, confirmado en TC-M09-G65).
    No existe ninguna cuenta de prueba con rol Ingeniero disponible, asi
    que este escenario se ejecuta con Administrador. IMPORTANTE: que
    Administrador pueda operar sobre cualquier finca es esperado por
    diseno (rol global, igual que en RF-19 "Admin=todas") y NO es en si
    mismo el hallazgo. El hallazgo real, confirmado leyendo
    AsociarSensorAreaUseCase.execute(), es que la funcion NUNCA compara el
    area contra ninguna nocion de "finca del llamante" -- ni siquiera
    contra la finca del dispositivo dueno del sensor: se puede asociar un
    sensor de un dispositivo instalado en la Finca A a un area productiva
    de la Finca B sin ninguna validacion cruzada. Ese cheque esta ausente
    para TODOS los roles (no solo Admin), asi que un Ingeniero (si
    existiera la cuenta) sufriria exactamente el mismo problema -- no hay
    ninguna rama de codigo que lo trate distinto.

Escenario 2 (TC-M09-248) - Mass assignment con campos no documentados:
    AsociarSensorAreaDTO (BaseDTO, sin `extra="forbid"`) declara solo
    `id_dispositivo_iot`, `id_infraestructura`, `punto_instalacion`,
    `confirmar`. Pydantic v2 con `extra` no configurado descarta en
    silencio cualquier campo del JSON que no este declarado en el modelo
    ANTES de que el use case reciba el DTO. Ademas, el propio use case
    nunca usa `dto.id_usuario` ni similar: `id_usuario` de la asociacion
    creada SIEMPRE sale de `usuario_actual.id_usuario` (el JWT del que
    llama), nunca del body. EXPECTATIVA: este es el UNICO de los 3
    escenarios donde se espera que el sistema SI este protegido.

Escenario 3 (TC-M09-249) - IDOR al consultar asociaciones de otra finca:
    GET /configuracion/sensores/{id}/asociaciones exige recurso 12 accion
    R=2, que Productor SI tiene. ConsultarAsociacionesUseCase.listar_por_
    sensor(id_sensor) no recibe siquiera `usuario_actual` -- no hay forma
    de que filtre por finca aunque quisiera. Un Productor sin ninguna
    finca propia puede leer el historial completo de asociaciones de
    CUALQUIER sensor del sistema, incluidas fincas con las que no tiene
    ninguna relacion.

Como correrlo (desde la raiz del repo):
    python -m pytest <ruta>\\test_tc_m09_g126_bola_asociaciones_sensores.py -v \
        --html=Resultados/reporte-TC-M09-G126.html --self-contained-html
"""
from __future__ import annotations

import time

import httpx
import pytest

BASE_URL = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
ADMIN_CORREO = "admin@pecuaria.co"
ADMIN_CONTRASENA = "Test1234!"
PRODUCTOR_CORREO = "u20221206763@usco.edu.co"
PRODUCTOR_CONTRASENA = "Test123!"

ENDPOINT_DISPOSITIVOS = f"{BASE_URL}/configuracion/dispositivos-iot"
ID_AREA_FINCA_A = 3  # finca_id=1, "Alevinera-01"
ID_AREA_FINCA_B = 4  # finca_id=2, "Canal-Trucha-01"
RUN_ID = str(int(time.time() * 1000))


@pytest.fixture(scope="module")
def admin_headers() -> dict:
    resp = httpx.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": ADMIN_CORREO, "contrasena": ADMIN_CONTRASENA},
        timeout=30,
    )
    assert resp.status_code == 200, f"No se pudo iniciar sesion como admin: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['token']}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def productor_headers() -> dict:
    """Productor de prueba sin ninguna finca propia (GET /configuracion/fincas
    con este token devuelve total:0, confirmado en vivo antes de esta prueba)."""
    resp = httpx.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": PRODUCTOR_CORREO, "contrasena": PRODUCTOR_CONTRASENA},
        timeout=30,
    )
    assert resp.status_code == 200, f"No se pudo iniciar sesion como productor: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['token']}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def id_tipo_dispositivo(admin_headers: dict) -> int:
    resp = httpx.get(f"{BASE_URL}/configuracion/tipos-dispositivo-iot", headers=admin_headers, timeout=30)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items
    return items[0]["id_tipo_dispositivo"]


@pytest.fixture(scope="module")
def dispositivos_creados(admin_headers: dict):
    """Recolecta los IDs de dispositivos creados por esta suite y los
    desactiva al finalizar (autorizado por el usuario, mismo criterio que
    TC-M09-G125)."""
    ids: list[int] = []
    yield ids
    for id_dispositivo in ids:
        try:
            httpx.patch(f"{ENDPOINT_DISPOSITIVOS}/{id_dispositivo}/desactivar", headers=admin_headers, timeout=30)
        except Exception:
            pass


def _registrar_dispositivo(headers: dict, id_infraestructura: int, id_tipo_dispositivo: int, sufijo: str) -> int:
    resp = httpx.post(
        ENDPOINT_DISPOSITIVOS,
        json={
            "serial": f"TC-M09-G126-{sufijo}-{RUN_ID}",
            "descripcion": f"Dispositivo de prueba TC-M09-G126 ({sufijo})",
            "id_infraestructura": id_infraestructura,
            "id_tipo_dispositivo": id_tipo_dispositivo,
            "es_activo": True,
        },
        headers=headers,
        timeout=30,
    )
    assert resp.status_code == 201, f"Precondicion fallida registrando dispositivo {sufijo}: {resp.text}"
    return resp.json()["id_dispositivo_iot"]


def _registrar_sensor(headers: dict, id_dispositivo: int, sufijo: str) -> int:
    resp = httpx.post(
        f"{ENDPOINT_DISPOSITIVOS}/{id_dispositivo}/sensores",
        json={"nombre": f"Sensor TC-M09-G126 {sufijo} {RUN_ID}", "categoria": "TEMPERATURA"},
        headers=headers,
        timeout=30,
    )
    assert resp.status_code == 201, f"Precondicion fallida registrando sensor {sufijo}: {resp.text}"
    return resp.json()["id_sensores"]


class TestTCM09G126BolaAsociacionesSensores:
    """Suite de pruebas de ataque para TC-M09-G126."""

    def test_escenario1_tc_m09_247_idor_asociar_sensor_a_area_de_otra_finca(
        self, admin_headers, id_tipo_dispositivo, dispositivos_creados,
    ):
        """OWASP API1: un sensor de un dispositivo instalado en la Finca A
        no debe poder asociarse a un area productiva de la Finca B
        modificando directamente id_infraestructura en el payload."""
        id_dispositivo = _registrar_dispositivo(admin_headers, ID_AREA_FINCA_A, id_tipo_dispositivo, "ESC1-DISPOSITIVO")
        dispositivos_creados.append(id_dispositivo)
        id_sensor = _registrar_sensor(admin_headers, id_dispositivo, "ESC1")

        payload_cruzado = {
            "id_dispositivo_iot": id_dispositivo,
            "id_infraestructura": ID_AREA_FINCA_B,
            "punto_instalacion": "Ataque IDOR - sensor de Finca A asociado a area de Finca B - TC-M09-G126",
        }
        resp = httpx.post(
            f"{BASE_URL}/configuracion/sensores/{id_sensor}/asociar",
            json=payload_cruzado,
            headers=admin_headers,
            timeout=30,
        )

        assert resp.status_code in (403, 404, 422), (
            "OWASP API1: el sistema debe rechazar la asociacion de un sensor de un "
            "dispositivo de la Finca A (id_infraestructura del dispositivo="
            f"{ID_AREA_FINCA_A}) a un area de la Finca B (id_infraestructura="
            f"{ID_AREA_FINCA_B}) por no pertenecer a la misma finca/tenant. "
            f"Respondio {resp.status_code}: {resp.text}. Hallazgo: "
            "AsociarSensorAreaUseCase.execute() (src/configuration/application/"
            "use_cases/sensores/asociar_sensor_area_use_case.py) solo valida que "
            "el area exista y este activa -- nunca compara la finca del area "
            "contra la finca del dispositivo/sensor. Cualquier rol con permiso "
            "C=1 sobre el recurso 'sensores' (Admin o Ingeniero) puede mezclar "
            "objetos de fincas distintas sin ninguna validacion cruzada."
        )

    def test_escenario2_tc_m09_248_mass_assignment_campos_no_documentados(
        self, admin_headers, id_tipo_dispositivo, dispositivos_creados,
    ):
        """OWASP API3: campos adicionales no documentados en el payload de
        asociacion (id_usuario_propietario, activo, etc.) no deben ser
        aceptados ni alterar datos no autorizados."""
        id_dispositivo = _registrar_dispositivo(admin_headers, ID_AREA_FINCA_A, id_tipo_dispositivo, "ESC2-DISPOSITIVO")
        dispositivos_creados.append(id_dispositivo)
        id_sensor = _registrar_sensor(admin_headers, id_dispositivo, "ESC2")

        payload_mass_assignment = {
            "id_dispositivo_iot": id_dispositivo,
            "id_infraestructura": ID_AREA_FINCA_A,
            "punto_instalacion": "Prueba mass assignment - TC-M09-G126",
            # Campos NO documentados en AsociarSensorAreaDTO:
            "id_usuario_propietario": 999999,
            "id_usuario": 999999,
            "activo": True,
            "es_administrador": True,
            "id_sensores_area_asociada": 1,
        }
        resp = httpx.post(
            f"{BASE_URL}/configuracion/sensores/{id_sensor}/asociar",
            json=payload_mass_assignment,
            headers=admin_headers,
            timeout=30,
        )

        assert resp.status_code == 201, f"Precondicion: la asociacion valida (sin los campos extra) debe aceptarse: {resp.text}"
        cuerpo = resp.json()

        assert cuerpo["id_infraestructura"] == ID_AREA_FINCA_A
        assert cuerpo["id_sensores_area_asociada"] != 1, (
            "OWASP API3: el sistema NO debe permitir que el cliente fije "
            "id_sensores_area_asociada via el body (mass assignment)."
        )
        assert cuerpo.get("id_usuario") != 999999, (
            "OWASP API3: el campo id_usuario de la asociacion debe salir del "
            "usuario autenticado (JWT), nunca de un valor enviado en el payload."
        )
        assert "id_usuario_propietario" not in cuerpo and "es_administrador" not in cuerpo, (
            "OWASP API3: los campos no documentados enviados en el payload no "
            "deben reflejarse en la respuesta ni persistirse."
        )

    def test_escenario3_tc_m09_249_idor_consultar_asociacion_de_otra_finca(
        self, admin_headers, productor_headers, id_tipo_dispositivo, dispositivos_creados,
    ):
        """OWASP API1: un usuario sin relacion con una finca no debe poder
        consultar el detalle/historial de asociaciones de un sensor que
        pertenece a esa finca cambiando el ID en la URL."""
        id_dispositivo = _registrar_dispositivo(admin_headers, ID_AREA_FINCA_B, id_tipo_dispositivo, "ESC3-DISPOSITIVO")
        dispositivos_creados.append(id_dispositivo)
        id_sensor = _registrar_sensor(admin_headers, id_dispositivo, "ESC3")

        resp_asociar = httpx.post(
            f"{BASE_URL}/configuracion/sensores/{id_sensor}/asociar",
            json={
                "id_dispositivo_iot": id_dispositivo,
                "id_infraestructura": ID_AREA_FINCA_B,
                "punto_instalacion": "Asociacion de la Finca B a proteger - TC-M09-G126",
            },
            headers=admin_headers,
            timeout=30,
        )
        assert resp_asociar.status_code == 201, f"Precondicion fallida: {resp_asociar.text}"

        # El Productor de prueba no es dueno de NINGUNA finca (confirmado:
        # GET /configuracion/fincas con su token devuelve total:0) -- no
        # tiene ninguna relacion legitima con la Finca B ni con este sensor.
        resp_ataque = httpx.get(
            f"{BASE_URL}/configuracion/sensores/{id_sensor}/asociaciones",
            headers=productor_headers,
            timeout=30,
        )

        assert resp_ataque.status_code in (403, 404), (
            "OWASP API1: un usuario Productor sin relacion con la Finca B "
            f"(id_infraestructura={ID_AREA_FINCA_B}) no debe poder consultar el "
            f"historial de asociaciones del sensor {id_sensor} de esa finca. "
            f"Respondio {resp_ataque.status_code}: {resp_ataque.text}. Hallazgo: "
            "ConsultarAsociacionesUseCase.listar_por_sensor() (src/configuration/"
            "application/use_cases/sensores/asociar_sensor_area_use_case.py) ni "
            "siquiera recibe el usuario autenticado como parametro, asi que no "
            "hay forma de que filtre por finca -- cualquier rol con permiso R=2 "
            "sobre 'sensores' (incluye Productor) puede leer el historial de "
            "CUALQUIER sensor del sistema, sin importar la finca a la que "
            "pertenezca ni si el usuario tiene alguna relacion con ella."
        )
