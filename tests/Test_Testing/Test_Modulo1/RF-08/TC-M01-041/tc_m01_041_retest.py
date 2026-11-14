"""
Retest TC-M01-041 (2026-09-12)
Validar que el sistema responda siempre con el mismo mensaje generico, exista
o no el correo ingresado (proteccion anti-enumeracion)

Defecto original (2026-09-03): el mensaje y el codigo HTTP eran identicos para
un correo existente y uno inexistente, pero el TIEMPO de respuesta los
distinguia con claridad (~4 segundos mas para el correo existente), porque
`solicitar_recuperacion_use_case.py` llamaba a `send_email(...)` de forma
SINCRONA antes de responder.

Causa raiz corregida (confirmada en codigo, sincronizado desde origin/test):
el paso 5 del use case ya no llama a `send_email` directamente -- llama a
`self.correo_recuperacion_port.programar_recuperacion(...)`, que en la
implementacion real (`CorreoRecuperacionBackgroundAdapter`, ver TC-M01-044)
solo hace `BackgroundTasks.add_task(...)`: una operacion de encolado casi
instantanea que NO espera a que el correo se envie. El envio real del correo
ocurre despues de que la respuesta ya fue entregada al cliente.

Esta prueba unitaria verifica, contra el use case real (con mocks de
infraestructura), que:
  1. El mensaje devuelto es EXACTAMENTE el mismo para correo existente,
     inexistente, cuenta pendiente y cuenta eliminada (anti-enumeracion por
     CONTENIDO -- ya se cumplia desde la primera ejecucion).
  2. El tiempo de ejecucion de `execute()` es practicamente igual entre todos
     esos casos y no depende de si el correo existe (anti-enumeracion por
     TIEMPO -- el defecto original), porque la unica diferencia de trabajo
     entre "existe" y "no existe" ya no incluye ninguna llamada bloqueante.
  3. El use case efectivamente delega el envio a `correo_recuperacion_port`
     (evidencia de que ya no hay una llamada sincrona a `send_email` en el
     propio use case).

Nota importante: esta prueba confirma que la CAUSA RAIZ estructural del
defecto (la llamada sincrona) fue eliminada del use case. La medicion de
tiempos AQUI es sobre codigo mockeado (no golpea SMTP real), asi que no
reemplaza una confirmacion final en vivo contra el backend desplegado en
TEST una vez se libere el cupo compartido de `POST /contrasena/recuperar`
-- se deja como verificacion complementaria recomendada.

Ejecutar desde la raiz del repositorio:
    python -m pytest tests/Test_Testing/Test_Modulo1/RF-08/TC-M01-41/tc_m01_041_retest.py -v --html=reporte-TC-M01-041-v2.0.html --self-contained-html
"""
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.identity_access.application.use_cases.contrasena.solicitar_recuperacion_use_case import (
    SolicitarRecuperacionUseCase,
    _MENSAJE_GENERICO,
)
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dto.contrasena_dto import SolicitarRecuperacionDTO


def _build_use_case(usuario=None, cuenta=None):
    """Arma el use case con mocks. `usuario`/`cuenta` en None simulan un
    correo que no existe en el sistema."""
    usuarios_repo = MagicMock()
    usuarios_repo.obtener_por_correo.return_value = usuario

    cuentas_repo = MagicMock()
    cuentas_repo.obtener_por_usuario.return_value = cuenta

    eventos_repo = MagicMock()
    intentos_anonimos_repo = MagicMock()
    intentos_anonimos_repo.contar_por_ip.return_value = 1  # muy por debajo del limite de 3
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
    return use_case, usuarios_repo, cuentas_repo, correo_recuperacion_port


def _usuario_y_cuenta_activa():
    usuario = MagicMock()
    usuario.id_usuario = 68
    usuario.nombre = "Cuenta de prueba 68"

    cuenta = MagicMock()
    cuenta.id_estado_cuenta = Cuenta.ESTADO_ACTIVO
    cuenta.esta_pendiente.return_value = False
    return usuario, cuenta


def _usuario_y_cuenta_pendiente():
    usuario = MagicMock()
    usuario.id_usuario = 70
    usuario.nombre = "Cuenta pendiente de prueba"

    cuenta = MagicMock()
    cuenta.id_estado_cuenta = Cuenta.ESTADO_PENDIENTE
    cuenta.esta_pendiente.return_value = True
    return usuario, cuenta


def _usuario_y_cuenta_eliminada():
    usuario = MagicMock()
    usuario.id_usuario = 71
    usuario.nombre = "Cuenta eliminada de prueba"

    cuenta = MagicMock()
    cuenta.id_estado_cuenta = Cuenta.ESTADO_ELIMINADO
    cuenta.esta_pendiente.return_value = False
    return usuario, cuenta


class TestTCM01041AntiEnumeracion:
    """TC-M01-041: mensaje y tiempo deben ser indistinguibles entre casos."""

    def _medir(self, usuario, cuenta, correo):
        use_case, usuarios_repo, cuentas_repo, correo_port = _build_use_case(usuario, cuenta)
        dto = SolicitarRecuperacionDTO(correo_electronico=correo)
        inicio = time.perf_counter()
        mensaje = use_case.execute(dto, ip="127.0.0.1")
        duracion_ms = (time.perf_counter() - inicio) * 1000
        return mensaje, duracion_ms, correo_port

    def test_mensaje_identico_en_los_4_escenarios(self):
        """Anti-enumeracion por CONTENIDO: el mensaje debe ser exactamente el
        mismo sin importar si el correo existe, esta pendiente o eliminado."""
        usuario_activo, cuenta_activa = _usuario_y_cuenta_activa()
        usuario_pendiente, cuenta_pendiente = _usuario_y_cuenta_pendiente()
        usuario_eliminado, cuenta_eliminada = _usuario_y_cuenta_eliminada()

        msg_existente, _, _ = self._medir(usuario_activo, cuenta_activa, "existente@sgpmp-test.com")
        msg_inexistente, _, _ = self._medir(None, None, "inexistente@sgpmp-test.com")
        msg_pendiente, _, _ = self._medir(usuario_pendiente, cuenta_pendiente, "pendiente@sgpmp-test.com")
        msg_eliminada, _, _ = self._medir(usuario_eliminado, cuenta_eliminada, "eliminada@sgpmp-test.com")

        assert msg_existente == _MENSAJE_GENERICO
        assert msg_inexistente == _MENSAJE_GENERICO
        assert msg_pendiente == _MENSAJE_GENERICO
        assert msg_eliminada == _MENSAJE_GENERICO
        assert msg_existente == msg_inexistente == msg_pendiente == msg_eliminada

    def test_tiempo_de_ejecucion_no_distingue_correo_existente_de_inexistente(self):
        """Anti-enumeracion por TIEMPO (el defecto original): la duracion de
        execute() no debe depender de si el correo existe, porque ya no hay
        ninguna llamada bloqueante (send_email sincrono) en el camino."""
        usuario_activo, cuenta_activa = _usuario_y_cuenta_activa()

        _, t_existente, correo_port_existente = self._medir(
            usuario_activo, cuenta_activa, "existente@sgpmp-test.com"
        )
        _, t_inexistente, correo_port_inexistente = self._medir(
            None, None, "inexistente@sgpmp-test.com"
        )

        diferencia = abs(t_existente - t_inexistente)
        print(f"\nTC-M01-041: tiempo existente={t_existente:.2f}ms, inexistente={t_inexistente:.2f}ms, diferencia={diferencia:.2f}ms")

        # Ambos deben ser rapidos (no hay ninguna llamada bloqueante real en el mock,
        # igual que en la implementacion real -- BackgroundTasks.add_task es casi instantaneo)
        assert t_existente < 200, f"El caso 'correo existente' tardo {t_existente:.2f}ms, se esperaba <200ms"
        assert t_inexistente < 200, f"El caso 'correo inexistente' tardo {t_inexistente:.2f}ms, se esperaba <200ms"
        # Y la diferencia entre ambos debe ser minima (no un canal lateral de varios segundos)
        assert diferencia < 100, f"La diferencia entre existente/inexistente fue {diferencia:.2f}ms, se esperaba <100ms"

        # Evidencia estructural: el use case delega el envio al puerto en vez de
        # bloquear con una llamada directa a SMTP -- solo se llama cuando el
        # correo SI existe (para uno inexistente no hay nada que programar).
        correo_port_existente.programar_recuperacion.assert_called_once()
        correo_port_inexistente.programar_recuperacion.assert_not_called()

    def test_cuenta_pendiente_tambien_delega_al_puerto_sin_bloquear(self):
        """El flujo de activacion (cuenta PENDIENTE) usa el mismo mecanismo de
        programacion en segundo plano, no una llamada sincrona distinta."""
        usuario_pendiente, cuenta_pendiente = _usuario_y_cuenta_pendiente()
        _, t_pendiente, correo_port = self._medir(usuario_pendiente, cuenta_pendiente, "pendiente@sgpmp-test.com")

        assert t_pendiente < 200, f"El caso 'cuenta pendiente' tardo {t_pendiente:.2f}ms, se esperaba <200ms"
        correo_port.programar_activacion.assert_called_once()
        correo_port.programar_recuperacion.assert_not_called()