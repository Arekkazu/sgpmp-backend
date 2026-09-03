"""
TC-M01-049 (medicion aislada) - Cuanto tarda SOLO la generacion del token de
recuperacion, sin el viaje HTTP ni el envio de correo.

RF relacionado: RF-08
Categoria: Rendimiento

Criterio de aceptacion (ficha): "< 1 s", medido sobre al menos 10
repeticiones, reportando el promedio.

Por que esta version es NECESARIA ademas de la medicion con Newman
(tc-m01-049.json): el endpoint POST /contrasena/recuperar tiene un limite
de 3 solicitudes por hora por conexion, asi que no es posible hacer 10
repeticiones reales seguidas contra el backend desplegado sin toparse con
un 422 (ver evidencia de TC-M01-041). Ademas, una medicion extremo-a-extremo
via Newman mide el envio real de correo (send_email se llama de forma
SINCRONICA dentro del mismo request en solicitar_recuperacion_use_case.py,
paso 5), que en una muestra real tardo 4.455 segundos (ver TC-M01-041) --
muy por encima del umbral, pero por una razon ajena a la generacion del
token en si (secrets.token_urlsafe(32) + hashlib SHA-256 + un guardado en
BD). Esta prueba aisla exactamente esa parte: mockea el repositorio de
usuarios/cuentas/eventos (operaciones instantaneas en memoria) y el envio
de correo, y cronometra unicamente la llamada a
SolicitarRecuperacionUseCase.execute(), 10 veces seguidas, sin ningun
limite de frecuencia real de por medio (el rate limiting tambien esta
mockeado, ver _construir_use_case).

Como leer el resultado junto con el de Newman:
- Si ESTA prueba pasa (deberia, es solo hashing + mocks) pero la de Newman
  falla, el problema NO es la generacion del token -- es el envio
  sincronico de correo bloqueando la respuesta al usuario. Ese ya es un
  defecto conocido y documentado en TC-M01-044 (send_email fuera de
  cualquier try/except, sin manejo async).
- Si esta prueba tambien fallara, el problema estaria en la logica misma
  de generacion/guardado del token, no en el correo.

Como correrlo (desde la raiz del repo, con las env vars seteadas):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    python -m pytest <ruta>\\test_tc_m01_049_tiempo_generacion_token.py -v -s `
        --html=reporte-TC-M01-049-pytest.html --self-contained-html

(el flag -s es importante aqui: sin el, pytest oculta los prints con el
detalle de cada repeticion y el promedio final)
"""
import time
from unittest.mock import MagicMock, patch

from src.identity_access.application.use_cases.contrasena.solicitar_recuperacion_use_case import (
    SolicitarRecuperacionUseCase,
)
from src.identity_access.infrastructure.dto.contrasena_dto import SolicitarRecuperacionDTO

CORREO_PRUEBA = "ana.martinez.qa1@sgpmp-test.com"
UMBRAL_SEGUNDOS = 1.0
REPETICIONES = 10


def _construir_use_case():
    """Doble de prueba: cuenta activa, verificada, sin bloqueo por limite de
    solicitudes (mockeado a 0 siempre, para que las 10 repeticiones no
    choquen entre si) -- llega directo al paso de generar y guardar el
    token de recuperacion, sin tocar red ni base de datos real."""
    usuario = MagicMock()
    usuario.id_usuario = 74
    usuario.nombre = "Ana Martinez"

    cuenta = MagicMock()
    cuenta.id_estado_cuenta = 2  # activa, distinta de ESTADO_ELIMINADO (5)
    cuenta.esta_pendiente.return_value = False

    usuarios_repo = MagicMock()
    usuarios_repo.obtener_por_correo.return_value = usuario

    cuentas_repo = MagicMock()
    cuentas_repo.obtener_por_usuario.return_value = cuenta

    eventos_repo = MagicMock()
    eventos_repo.contar_solicitudes_recuperacion_por_ip.return_value = 0

    db = MagicMock()

    return SolicitarRecuperacionUseCase(
        usuarios_repo=usuarios_repo,
        cuentas_repo=cuentas_repo,
        eventos_repo=eventos_repo,
        db=db,
    )


class TestTCM01049TiempoGeneracionToken:
    """Suite de medicion de rendimiento para TC-M01-049 (parte aislada)."""

    @patch(
        "src.identity_access.application.use_cases.contrasena."
        "solicitar_recuperacion_use_case.send_email"
    )
    def test_generacion_de_token_bajo_un_segundo_promedio_10_repeticiones(
        self, mock_send_email
    ):
        """
        RF-08: la generacion del token de recuperacion (sin contar el
        envio de correo ni el viaje HTTP) debe completarse, en promedio
        sobre 10 repeticiones, en menos de 1 segundo.
        """
        mock_send_email.return_value = None  # el envio de correo no es parte de esta medicion

        tiempos = []
        for i in range(REPETICIONES):
            use_case = _construir_use_case()
            dto = SolicitarRecuperacionDTO(correo_electronico=CORREO_PRUEBA)

            inicio = time.perf_counter()
            use_case.execute(dto, ip=f"203.0.113.{10 + i}")
            fin = time.perf_counter()

            tiempos.append(fin - inicio)
            print(f"  Repeticion {i + 1}/{REPETICIONES}: {tiempos[-1] * 1000:.2f} ms")

        promedio = sum(tiempos) / len(tiempos)
        minimo = min(tiempos)
        maximo = max(tiempos)

        print("=== RESUMEN TC-M01-049 (Pytest, solo generacion del token) ===")
        print(f"Repeticiones: {REPETICIONES}")
        print(f"Promedio: {promedio * 1000:.2f} ms")
        print(f"Minimo: {minimo * 1000:.2f} ms | Maximo: {maximo * 1000:.2f} ms")

        assert promedio < UMBRAL_SEGUNDOS, (
            f"RF-08 exige que la generacion del token promedie menos de "
            f"{UMBRAL_SEGUNDOS}s sobre {REPETICIONES} repeticiones; el "
            f"promedio medido fue {promedio:.3f}s. Tiempos individuales "
            f"(s): {[round(t, 3) for t in tiempos]}"
        )