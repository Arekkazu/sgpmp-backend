# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-27 | destroyerban | INC-M03-113-G56 RF-56: un intento no confirmado queda PENDIENTE y se reprograma |
"""RF-56 DEV-17: pendiente persistido, sin confirmación ficticia ni reenvío."""
from datetime import datetime, timedelta, timezone
from unittest.mock import ANY, Mock

import pytest

from src.shared.errors import BusinessRuleError
from src.telemetry.application.use_cases.inferencia.consolidar_paquete_inferencia_use_case import ConsolidarEnviarPaqueteUseCase
from src.telemetry.domain.entities.telemetria import EventoEdgeComputing, EstadoPaqueteInferencia
from src.telemetry.domain.repositories.motor_inferencia_port import MotorInferenciaNoIntegradoError, MotorInferenciaPort
from src.telemetry.domain.repositories.paquete_inferencia_repository import PaqueteInferenciaRepository
from src.telemetry.infrastructure.adapters.motor_inferencia_stub_adapter import MotorInferenciaStubAdapter


@pytest.fixture
def evento():
    ts = datetime.now(timezone.utc) - timedelta(minutes=1)
    return EventoEdgeComputing(
        id_evento_edge_computing=7, id_sensor=3, id_dispositivo_iot=2,
        clasificacion_rf55="DESVIACION_SIMPLE", tipo_evento="ALERTA_GENERADA",
        severidad="MODERADO", fecha_captura=ts, fecha_procesamiento=ts,
        origen_dato="TIEMPO_REAL", estado_conectividad=True,
        variables_involucradas=[
            {"tipo_variable":"TEMPERATURA_AMBIENTAL", "valor":"38.5000", "unidad":"°C"},
            {"tipo_variable":"HUMEDAD_RELATIVA", "valor":"90.0000", "unidad":"%"},
        ],
    )


@pytest.fixture
def repos():
    db = Mock()
    repo = Mock(spec=PaqueteInferenciaRepository)
    repo.obtener_por_evento.return_value = None
    def guardar(paquete):
        paquete.id_paquetes_inferencia = 11
        return paquete
    repo.guardar.side_effect = guardar
    return db, repo


def test_stub_senala_falta_de_integracion():
    with pytest.raises(MotorInferenciaNoIntegradoError) as result:
        MotorInferenciaStubAdapter().enviar_paquete(Mock())
    assert result.value.code == 'MOTOR_INFERENCIA_NO_INTEGRADO'
    assert result.value.status_code == 503


def test_stub_deja_pendiente_despues_del_commit(evento, repos, caplog):
    db, repo = repos
    orden = []
    db.commit.side_effect = lambda: orden.append('commit')
    motor = Mock(wraps=MotorInferenciaStubAdapter())
    def sin_integracion(paquete):
        orden.append('stub')
        raise MotorInferenciaNoIntegradoError()
    motor.enviar_paquete.side_effect = sin_integracion
    paquete = ConsolidarEnviarPaqueteUseCase(db, repo, motor).execute(evento)
    assert orden == ['commit','stub']
    assert paquete.estado_paquete == EstadoPaqueteInferencia.PENDIENTE
    assert paquete.intento_envios == 0
    assert paquete.contexto_ambiental['AMBIENTAL'] == evento.variables_involucradas
    assert paquete.metadatos['timestamp_captura'] == evento.fecha_captura.isoformat()
    repo.actualizar_estado.assert_not_called()
    db.rollback.assert_not_called()
    assert 'pendiente' in caplog.text


# INC-M03-113-G56: RF-56 restricción 14, un intento no confirmado deja PENDIENTE y se reprograma.
@pytest.mark.parametrize('resultado,estado', [(True,'ENVIADO'), (False,'PENDIENTE'), (RuntimeError('sin conexion'),'PENDIENTE')])
def test_conserva_semantica_del_puerto_con_doble_de_entrega(evento, repos, resultado, estado):
    db, repo = repos
    motor = Mock(spec=MotorInferenciaPort)
    if isinstance(resultado, Exception):
        motor.enviar_paquete.side_effect = resultado
    else:
        motor.enviar_paquete.return_value = resultado
    paquete = ConsolidarEnviarPaqueteUseCase(db, repo, motor).execute(evento)
    assert paquete.estado_paquete == estado and paquete.intento_envios == 1
    repo.actualizar_estado.assert_called_once_with(11, estado, 1, ANY)
    assert db.commit.call_count == 2


@pytest.mark.parametrize('fase', ['consulta','guardar','commit'])
def test_error_antes_de_confirmar_no_invoca_motor(evento, repos, fase):
    db, repo = repos
    motor = Mock(spec=MotorInferenciaPort)
    if fase == 'consulta':
        repo.obtener_por_evento.side_effect = RuntimeError('fallo consulta')
    elif fase == 'guardar':
        repo.guardar.side_effect = RuntimeError('fallo guardar')
    else:
        db.commit.side_effect = RuntimeError('fallo commit')
    with pytest.raises(RuntimeError):
        ConsolidarEnviarPaqueteUseCase(db, repo, motor).execute(evento)
    db.rollback.assert_called_once()
    motor.enviar_paquete.assert_not_called()
    repo.actualizar_estado.assert_not_called()


@pytest.mark.parametrize('estado', ['PENDIENTE','FALLIDO','ENVIADO'])
def test_reconsolidar_reutiliza_paquete_sin_reenviar(evento, repos, estado):
    db, repo = repos
    previo = Mock(estado_paquete=estado, intento_envios=0 if estado=='PENDIENTE' else 1)
    repo.obtener_por_evento.return_value = previo
    motor = Mock(spec=MotorInferenciaPort)
    assert ConsolidarEnviarPaqueteUseCase(db, repo, motor).execute(evento) is previo
    repo.obtener_por_evento.assert_called_once_with(7, bloquear_evento=True)
    repo.guardar.assert_not_called()
    repo.actualizar_estado.assert_not_called()
    motor.enviar_paquete.assert_not_called()
    db.commit.assert_called_once()


@pytest.mark.parametrize('variables', [[], [{}], [{'tipo_variable':'TEMPERATURA_AMBIENTAL'}]])
def test_datos_inconsistentes_no_generan_ni_envian_paquete(evento, repos, variables):
    db, repo = repos
    evento.variables_involucradas = variables
    motor = Mock(spec=MotorInferenciaPort)
    with pytest.raises(BusinessRuleError):
        ConsolidarEnviarPaqueteUseCase(db, repo, motor).execute(evento)
    repo.guardar.assert_not_called()
    motor.enviar_paquete.assert_not_called()


def test_normal_no_genera_paquete(evento, repos):
    db, repo = repos
    evento.clasificacion_rf55 = 'NORMAL'
    motor = Mock(spec=MotorInferenciaPort)
    assert ConsolidarEnviarPaqueteUseCase(db, repo, motor).execute(evento) is None
    repo.obtener_por_evento.assert_not_called()
    repo.guardar.assert_not_called()
    motor.enviar_paquete.assert_not_called()


def test_fallo_actualizando_estado_se_propaga_tras_persistencia(evento, repos):
    db, repo = repos
    motor = Mock(spec=MotorInferenciaPort)
    motor.enviar_paquete.return_value = True
    repo.actualizar_estado.side_effect = RuntimeError('fallo estado')
    with pytest.raises(RuntimeError):
        ConsolidarEnviarPaqueteUseCase(db, repo, motor).execute(evento)
    db.commit.assert_called_once()
    db.rollback.assert_called_once()
