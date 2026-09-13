"""
TC-M09-G73 (TC-M09-140) - Prevenir actualizacion parcial de la
configuracion remota ante fallo/interrupcion de la comunicacion MQTT.

RF relacionado: RF-23, CU-05 Gestionar Dispositivos IoT
Categoria: Pruebas de integridad / integracion

Criterio de aceptacion (segun la ficha):
    "Configuracion valida + interrupcion de comunicacion." Resultado
    esperado: "Verificar que la configuracion anterior permanezca
    consistente" / "Evitar estados parcialmente actualizados."

Herramienta pedida por la ficha: Pytest -- "Requiere verificar
consistencia transaccional en BD tras interrupcion simulada, no solo
respuesta HTTP", asi que se inspecciona directamente el use case con
dobles de prueba, no la respuesta HTTP de un endpoint.

Se leyo completo ConfigurarRemotamenteUseCase.execute()
(src/configuration/application/use_cases/dispositivos_iot/
configurar_remotamente_use_case.py) para entender el disenio
transaccional real:

  1. Se crea y persiste la config nueva con estado=PENDIENTE en un
     PRIMER commit, ANTES de intentar el envio MQTT.
  2. Se llama a mqtt_port.enviar_configuracion() (bloqueante, sin
     try/except alrededor).
  3. Si el resultado es PENDIENTE (broker inalcanzable o dispositivo
     offline -- el caso real de "interrupcion de comunicacion"), el use
     case retorna inmediatamente: NUNCA llama a config_repo.actualizar()
     ni a un segundo commit.
  4. Solo si el resultado es APLICADA o NO_CONF se hace un SEGUNDO commit
     que actualiza esa MISMA fila (marcar_aplicada/marcar_no_confirmada).

Conclusion de diseno (confirmada con estos tests): el mecanismo real de
RF-23 SI evita la actualizacion parcial, pero no por una transaccion
distribuida ni un patron saga -- simplemente porque cada configuracion es
una FILA NUEVA e inmutable en su creacion (nunca se modifica una config
"anterior"), y el segundo commit (que si podria fallar a mitad de camino)
jamas se alcanza en el escenario real de "interrupcion de comunicacion"
(mqtt_port nunca lanza, siempre degrada a PENDIENTE de forma sincrona
antes de que el use case intente ningun otro commit). No hay ningun
escenario, dentro del contrato documentado del adaptador, donde una fila
quede con valores parciales/inconsistentes de frecuencia_captura o
intervalo_transmision.

Test 1 verifica el camino real (interrupcion = PENDIENTE): un solo
commit, el segundo jamas se invoca, los valores de la fila persistida
quedan completos y consistentes con lo solicitado.

Test 2 va mas alla del contrato documentado (defensivo): si el adaptador
MQTT violara su contrato y lanzara una excepcion en vez de degradar a
PENDIENTE, la llamada mqtt_port.enviar_configuracion() no esta protegida
por try/except -- la excepcion se propaga sin control. Se documenta esto
como un hallazgo menor (no exactamente lo que pide la ficha, que asume
que la interrupcion se maneja via degradacion a PENDIENTE): la fila ya
persistida en el PRIMER commit NO se corrompe (sus valores siguen
completos), pero el use case no captura este caso -- el cliente HTTP
recibiria un 500 generico en vez de un estado de negocio claro, y la fila
quedaria "atascada" en PENDIENTE para siempre (nunca se reintenta el
segundo commit). No es una actualizacion PARCIAL (no hay valores a medio
escribir), pero si es un fallo de manejo de errores no documentado en el
contrato de MqttPort.

Como correrlo (desde la raiz del repo, con las env vars seteadas):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m09_140_sin_actualizacion_parcial.py -v \
        --html=Resultados/reporte-TC-M09-140.html --self-contained-html
"""
import datetime
from unittest.mock import MagicMock

import pytest

from src.configuration.application.use_cases.dispositivos_iot.configurar_remotamente_use_case import (
    ConfigurarRemotamenteUseCase,
)
from src.configuration.domain.entities.configuracion_remota import ConfiguracionRemota
from src.configuration.domain.entities.dispositivo_iot import DispositivoIot
from src.configuration.domain.entities.tipo_dispositivo_iot import TipoDispositivoIot
from src.configuration.domain.repositories.mqtt_port import ResultadoEnvioMqtt
from src.configuration.domain.value_objects.serial_dispositivo import SerialDispositivo
from src.configuration.infrastructure.dto.configurar_remotamente_dto import ConfigurarRemotamenteDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual

ID_DISPOSITIVO = 500
FRECUENCIA_SOLICITADA = 10
INTERVALO_SOLICITADO = 20


def _dispositivo() -> DispositivoIot:
    return DispositivoIot(
        serial=SerialDispositivo("TC-M09-G73-001"),
        descripcion="Sensor de prueba TC-M09-G73",
        id_infraestructura=3,
        id_tipo_dispositivo=1,
        es_activo=True,
        fecha_creacion=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        id_dispositivo_iot=ID_DISPOSITIVO,
    )


def _tipo_generico() -> TipoDispositivoIot:
    return TipoDispositivoIot(
        id_tipo_dispositivo=1, nombre="GENERICO",
        frecuencia_captura_min=1, frecuencia_captura_max=1440,
        intervalo_transmision_min=1, intervalo_transmision_max=1440,
    )


def _construir_use_case(dispositivo_repo, config_repo, mqtt_port):
    tipo_repo = MagicMock()
    tipo_repo.obtener_por_id.return_value = _tipo_generico()
    return ConfigurarRemotamenteUseCase(
        db=MagicMock(),
        dispositivo_repo=dispositivo_repo,
        config_repo=config_repo,
        tipo_repo=tipo_repo,
        mqtt_port=mqtt_port,
    )


class TestTCM09140SinActualizacionParcial:

    def test_interrupcion_de_comunicacion_no_genera_segundo_commit_ni_valores_parciales(self):
        """
        Camino real: mqtt_port degrada a PENDIENTE (interrupcion de
        comunicacion). El use case debe:
          1. Persistir la nueva configuracion en un unico commit, con los
             valores COMPLETOS solicitados (sin campos parciales/nulos).
          2. NUNCA llamar a config_repo.actualizar() (el "segundo commit")
             -- no hay nada que actualizar parcialmente porque el use case
             retorna apenas ve estado=PENDIENTE.
        """
        dispositivo_repo = MagicMock()
        dispositivo_repo.obtener_por_id.return_value = _dispositivo()

        config_repo = MagicMock()
        config_repo.obtener_pendiente.return_value = None
        config_guardada = ConfiguracionRemota.crear(
            id_dispositivo_iot=ID_DISPOSITIVO,
            frecuencia_captura=FRECUENCIA_SOLICITADA,
            intervalo_transmision=INTERVALO_SOLICITADO,
            id_usuario=1,
        )
        config_guardada.id_configuracion_remota = 900
        config_repo.guardar.return_value = config_guardada

        mqtt_port = MagicMock()
        mqtt_port.enviar_configuracion.return_value = ResultadoEnvioMqtt(
            estado="PENDIENTE",
            mensaje="No se pudo contactar al broker MQTT. La configuración quedará pendiente.",
        )

        use_case = _construir_use_case(dispositivo_repo, config_repo, mqtt_port)
        usuario_actual = UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)
        dto = ConfigurarRemotamenteDTO(
            frecuencia_captura=FRECUENCIA_SOLICITADA, intervalo_transmision=INTERVALO_SOLICITADO,
        )

        resultado, mensaje = use_case.execute(ID_DISPOSITIVO, dto, usuario_actual)

        config_repo.guardar.assert_called_once()
        config_repo.actualizar.assert_not_called(), (
            "RF-23 exige evitar actualizaciones parciales: si la comunicacion "
            "se interrumpe, el use case no debe intentar un segundo commit "
            "sobre la fila -- debe quedar en un unico estado consistente "
            "(PENDIENTE) desde su unica escritura."
        )
        assert resultado.estado == "PENDIENTE"
        assert resultado.frecuencia_captura == FRECUENCIA_SOLICITADA, (
            "La fila persistida debe tener el valor COMPLETO solicitado, "
            "no un valor parcial o por defecto."
        )
        assert resultado.intervalo_transmision == INTERVALO_SOLICITADO
        assert resultado.fecha_aplicacion is None, (
            "Una configuracion PENDIENTE no debe tener fecha_aplicacion -- "
            "eso demostraria un estado mixto/inconsistente (aplicada a medias)."
        )

    def test_fallo_inesperado_del_adaptador_mqtt_no_corrompe_la_fila_ya_persistida(self):
        """
        Escenario defensivo, fuera del contrato documentado de MqttPort
        ("nunca lanza"): si el adaptador violara ese contrato y lanzara una
        excepcion, confirma que el PRIMER commit (creacion de la fila con
        valores completos) ya es irreversible/consistente -- la excepcion
        se propaga (no hay try/except alrededor de mqtt_port.enviar_configuracion),
        pero eso no implica una fila con datos parciales, solo una fila que
        se queda "atascada" en PENDIENTE sin que el cliente reciba una
        respuesta de negocio clara.
        """
        dispositivo_repo = MagicMock()
        dispositivo_repo.obtener_por_id.return_value = _dispositivo()

        config_repo = MagicMock()
        config_repo.obtener_pendiente.return_value = None
        config_guardada = ConfiguracionRemota.crear(
            id_dispositivo_iot=ID_DISPOSITIVO,
            frecuencia_captura=FRECUENCIA_SOLICITADA,
            intervalo_transmision=INTERVALO_SOLICITADO,
            id_usuario=1,
        )
        config_guardada.id_configuracion_remota = 901
        config_repo.guardar.return_value = config_guardada

        mqtt_port = MagicMock()
        mqtt_port.enviar_configuracion.side_effect = RuntimeError(
            "simulated: fallo inesperado del adaptador MQTT (viola su propio contrato)"
        )

        use_case = _construir_use_case(dispositivo_repo, config_repo, mqtt_port)
        usuario_actual = UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)
        dto = ConfigurarRemotamenteDTO(
            frecuencia_captura=FRECUENCIA_SOLICITADA, intervalo_transmision=INTERVALO_SOLICITADO,
        )

        with pytest.raises(RuntimeError):
            use_case.execute(ID_DISPOSITIVO, dto, usuario_actual)

        # El primer commit (creacion) ya se hizo ANTES de la llamada mqtt --
        # la fila que se guardo tiene valores completos, no parciales.
        config_repo.guardar.assert_called_once()
        fila_guardada = config_repo.guardar.call_args.args[0]
        assert fila_guardada.frecuencia_captura == FRECUENCIA_SOLICITADA
        assert fila_guardada.intervalo_transmision == INTERVALO_SOLICITADO
        assert fila_guardada.estado == "PENDIENTE"

        # El segundo commit (actualizar) nunca se alcanza -- no hay riesgo
        # de escritura parcial de un UPDATE a medias, simplemente no ocurre.
        config_repo.actualizar.assert_not_called()
