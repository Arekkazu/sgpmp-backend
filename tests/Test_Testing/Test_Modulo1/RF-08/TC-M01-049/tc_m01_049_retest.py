"""
Retest TC-M01-049 (2026-09-12)
Validar que la generacion del token de recuperacion se complete en menos de
1 segundo

Defecto original (2026-09-01): la generacion del TOKEN en si era casi
instantanea (~2ms, confirmado con `test_tc_m01_049_tiempo_generacion_token.py`),
pero la PETICION COMPLETA (`POST /contrasena/recuperar`) tardaba entre 3.5 y
4.5 segundos -- muy por encima del umbral de 1 segundo que exige la ficha,
medida como corresponde (la peticion completa, no un paso interno aislado).
La causa confirmada en el codigo era la misma que TC-M01-044: `send_email()`
se llamaba de forma SINCRONA dentro del mismo request en
`solicitar_recuperacion_use_case.py` (paso 5).

Causa raiz corregida (confirmada en codigo, sincronizado desde origin/test):
ese paso 5 ahora llama a `self.correo_recuperacion_port.programar_recuperacion(...)`,
que en la implementacion real (`CorreoRecuperacionBackgroundAdapter`, ver
TC-M01-044) usa `BackgroundTasks.add_task(...)` -- una operacion de encolado
casi instantanea que no espera a que el correo se envie realmente.

Esta prueba mide, contra el use case real (`SolicitarRecuperacionUseCase`,
con mocks de infraestructura), el tiempo de la operacion completa
(equivalente a la peticion HTTP end-to-end desde la perspectiva del backend)
para un correo EXISTENTE -- el caso que antes tardaba ~4 segundos -- y
confirma que ahora se completa muy por debajo del umbral de 1 segundo exigido
por la ficha.

Nota importante: esta prueba corre contra codigo mockeado (no golpea SMTP
real ni la base de datos real), por lo que no reemplaza una confirmacion
final en vivo contra el backend desplegado en TEST una vez se libere el cupo
compartido de `POST /contrasena/recuperar` -- se deja como verificacion
complementaria recomendada.

Ejecutar desde la raiz del repositorio:
    python -m pytest tests/Test_Testing/Test_Modulo1/RF-08/TC-M01-49/tc_m01_049_retest.py -v -s --html=reporte-TC-M01-049-v2.0.html --self-contained-html
"""
import time
from unittest.mock import MagicMock

from src.identity_access.application.use_cases.contrasena.solicitar_recuperacion_use_case import (
    SolicitarRecuperacionUseCase,
)
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dto.contrasena_dto import SolicitarRecuperacionDTO

UMBRAL_MS = 1000
REPETICIONES = 5


def _build_use_case_con_cuenta_activa():
    usuario = MagicMock()
    usuario.id_usuario = 68
    usuario.nombre = "Cuenta de prueba 68"

    cuenta = MagicMock()
    cuenta.id_estado_cuenta = Cuenta.ESTADO_ACTIVO
    cuenta.esta_pendiente.return_value = False

    usuarios_repo = MagicMock()
    usuarios_repo.obtener_por_correo.return_value = usuario

    cuentas_repo = MagicMock()
    cuentas_repo.obtener_por_usuario.return_value = cuenta

    eventos_repo = MagicMock()
    intentos_anonimos_repo = MagicMock()
    intentos_anonimos_repo.contar_por_ip.return_value = 1
    db = MagicMock()
    correo_recuperacion_port = MagicMock()

    use_case = SolicitarRecuperacionUseCase(
        usuarios_repo=usuarios_repo,
        cuentas_repo=cuentas_repo,
        eventos_repo=eventos_repo,
        intentos_anonimos_repo=intentos_anonimos_repo,
        db=db,
        correo_recuperacion_port=correo_recuperacion_port,
    )
    return use_case, correo_recuperacion_port


class TestTCM01049TiempoDeLaPeticionCompleta:
    """TC-M01-049: la peticion completa (correo existente) debe responder en
    menos de 1 segundo, ya no bloqueada por el envio sincrono de correo."""

    def test_peticion_completa_correo_existente_bajo_1_segundo(self):
        use_case, correo_port = _build_use_case_con_cuenta_activa()
        dto = SolicitarRecuperacionDTO(correo_electronico="existente@sgpmp-test.com")

        inicio = time.perf_counter()
        mensaje = use_case.execute(dto, ip="127.0.0.1")
        duracion_ms = (time.perf_counter() - inicio) * 1000

        print(f"\nTC-M01-049: peticion completa (correo existente) = {duracion_ms:.2f}ms")

        assert mensaje is not None
        assert duracion_ms < UMBRAL_MS, (
            f"La peticion completa tardo {duracion_ms:.2f}ms, se esperaba menos de {UMBRAL_MS}ms"
        )
        # Confirma que el envio de correo se DELEGO al puerto (encolado) en vez
        # de esperarse de forma sincrona dentro de este mismo tiempo medido.
        correo_port.programar_recuperacion.assert_called_once()

    def test_repeticiones_consistentes_bajo_el_umbral(self):
        """Repite la medicion varias veces para descartar que el resultado
        anterior haya sido una muestra atipicamente rapida."""
        tiempos = []
        for _ in range(REPETICIONES):
            use_case, _ = _build_use_case_con_cuenta_activa()
            dto = SolicitarRecuperacionDTO(correo_electronico="existente@sgpmp-test.com")
            inicio = time.perf_counter()
            use_case.execute(dto, ip="127.0.0.1")
            tiempos.append((time.perf_counter() - inicio) * 1000)

        print(f"\nTC-M01-049: {REPETICIONES} repeticiones -> {[f'{t:.2f}ms' for t in tiempos]}")
        print(f"TC-M01-049: promedio = {sum(tiempos) / len(tiempos):.2f}ms, maximo = {max(tiempos):.2f}ms")

        assert max(tiempos) < UMBRAL_MS, (
            f"La repeticion mas lenta tardo {max(tiempos):.2f}ms, se esperaba que todas fueran menores a {UMBRAL_MS}ms"
        )