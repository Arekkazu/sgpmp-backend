"""
TC-M09-G135 (RF-23, G135-02) - Envio automatico de PENDIENTE al reconectar.

Ficha: "Requiere broker que se reconecte para verificar el envio automatico
de PENDIENTE (DEV). Verificar que el usuario que origino el cambio quede en
el historial."

Por que BLOQUEADO (hallazgo estructural, no de ejecucion en vivo): leido
`configurar_remotamente_use_case.py` y `mqtt_http_adapter.py` completos --
este backend NO mantiene conexion MQTT propia ni escucha eventos de
reconexion del broker en absoluto. `ConfigurarRemotamenteUseCase.execute()`
hace UNA sola llamada HTTP sincrona y bloqueante
(`mqtt_port.enviar_configuracion`, ~30s de espera maxima) al microservicio
hermano BROKER-MQTT-SGPMP dentro de la misma request HTTP del usuario; no
hay ningun `on_connect`/listener/subscriber, ni job en segundo plano
(`BackgroundTasks`, scheduler, cron) en todo `src/configuration` que
re-envie configuraciones PENDIENTES cuando un dispositivo vuelve a
conectarse. Si ese reenvio automatico existe, vive en BROKER-MQTT-SGPMP
(fuera de este repo) -- confirmado por busqueda exhaustiva en el codigo
(ver tests abajo), no por inspeccion parcial.

Esto es la MISMA conclusion de alcance que ya se documento para G127 (ACLs/
TLS de Mosquitto) y G128 (LoRaWAN): el gap no es de este backend, es de
infraestructura/el otro microservicio. No es ejecutable como TC de este
repo sin acceso a BROKER-MQTT-SGPMP.

Como correrlo:
    python -m pytest tests/Test_Testing/Test_Modulo9/RF-23/TC-M09-G135/test_tc_m09_g135_envio_automatico_pendiente.py -v \
        --html=resultados/resultado_TC-M09-G135_reintento1.html --self-contained-html
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from src.configuration.infrastructure.adapters.mqtt_http_adapter import MqttHttpAdapter

_SRC_CONFIGURATION = Path(__file__).resolve().parents[5] / "src" / "configuration"
_PALABRAS_REENVIO_AUTOMATICO = (
    "on_connect",
    "reconnect",
    "reconectar",
    "reenviar_pendiente",
    "listener",
    "subscribe",
)


class TestTCM09G135EnvioAutomaticoPendiente:
    """TC-M09-G135 / G135-02: confirma estructuralmente que no existe, en
    este repo, ningun mecanismo de reenvio automatico al reconectar."""

    def test_mqtt_http_adapter_no_tiene_listener_ni_reconexion(self):
        """El unico adaptador MQTT del backend solo expone `enviar_configuracion`
        (llamada sincrona request/response) -- ningun metodo de escucha/evento."""
        metodos_publicos = {
            nombre
            for nombre, _ in inspect.getmembers(MqttHttpAdapter, predicate=inspect.isfunction)
            if not nombre.startswith("_")
        }
        assert metodos_publicos == {"enviar_configuracion"}, (
            f"Se esperaba que MqttHttpAdapter solo exponga 'enviar_configuracion' "
            f"(sin listener de reconexion); se encontraron: {metodos_publicos!r}"
        )

    def test_ningun_archivo_de_configuration_implementa_reenvio_automatico(self):
        """Barrido exhaustivo de src/configuration: ningun archivo define un
        on_connect/listener/job que reenvie configuraciones PENDIENTES."""
        assert _SRC_CONFIGURATION.is_dir(), f"Ruta inesperada: {_SRC_CONFIGURATION}"
        coincidencias = []
        for ruta in _SRC_CONFIGURATION.rglob("*.py"):
            texto = ruta.read_text(encoding="utf-8").lower()
            for palabra in _PALABRAS_REENVIO_AUTOMATICO:
                if palabra in texto:
                    coincidencias.append((ruta.relative_to(_SRC_CONFIGURATION), palabra))

        assert coincidencias == [], (
            "Se esperaba NO encontrar ningun mecanismo de reenvio automatico en "
            f"src/configuration; se encontraron referencias sospechosas: {coincidencias!r} "
            "-- revisar manualmente antes de seguir asumiendo que G135 esta bloqueado."
        )

    def test_use_case_solo_envia_una_vez_por_request_nunca_en_segundo_plano(self):
        """Confirma via AST que execute() invoca `enviar_configuracion` una sola
        vez, de forma sincrona dentro de la misma funcion -- no hay scheduling,
        hilos nuevos ni tareas diferidas alrededor de esa llamada."""
        archivo = (
            _SRC_CONFIGURATION
            / "application"
            / "use_cases"
            / "dispositivos_iot"
            / "configurar_remotamente_use_case.py"
        )
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        llamadas_enviar_config = [
            nodo
            for nodo in ast.walk(arbol)
            if isinstance(nodo, ast.Attribute) and nodo.attr == "enviar_configuracion"
        ]
        assert len(llamadas_enviar_config) == 1, (
            f"Se esperaba una unica invocacion sincrona a enviar_configuracion; "
            f"se encontraron {len(llamadas_enviar_config)}"
        )


@pytest.mark.skip(
    reason=(
        "BLOQUEADO (confirmado por codigo): el reenvio automatico de PENDIENTE al "
        "reconectar, si existe, vive en BROKER-MQTT-SGPMP (microservicio externo, "
        "fuera de este repo) -- no hay forma de ejecutar este TC desde aqui sin acceso "
        "a ese servicio. Pendiente de decision del equipo (igual que G127/G128)."
    )
)
def test_g135_02_envio_automatico_al_reconectar_NO_VERIFICABLE_desde_este_repo():
    """Placeholder explicito del caso bloqueado -- ver reason del skip."""
