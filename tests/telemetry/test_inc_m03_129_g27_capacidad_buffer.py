# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-129-G27 RF-54/60/63: validar recepción, límites, consolidación y escalamiento del aviso de capacidad confirmado. |
from datetime import timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError as PydanticValidationError

from src.shared.database import get_db_sistema
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import NotFoundError
from src.telemetry.application.use_cases.infraestructura.registrar_evento_buffer_use_case import RegistrarEventoBufferUseCase
from src.telemetry.domain.repositories.dispositivo_port import DispositivoHeartbeatInfo
from src.telemetry.infrastructure.dto.evento_buffer_dto import RecibirEventoBufferDTO
from src.telemetry.infrastructure.routers import infraestructura_iot_router


class Alertas:
    def __init__(self):
        self.filas = []
        self.bloqueos = []
        self.escalamientos = []

    def bloquear_dispositivo(self, identificador):
        self.bloqueos.append(identificador)

    def buscar_tecnica_abierta(self, identificador, tipo):
        return next((a for a in reversed(self.filas) if a.tipo_variable == tipo and
                     a.estado_alerta in ('ACTIVA', 'EN_ATENCION')), None)

    def guardar(self, alerta):
        alerta.id_alerta = len(self.filas) + 1
        self.filas.append(alerta)
        return alerta

    def actualizar_deduplicacion(self, identificador, ultima_ocurrencia, nueva_severidad=None):
        alerta = next(a for a in self.filas if a.id_alerta == identificador)
        alerta.frecuencia_evento += 1
        alerta.ultima_ocurrencia = ultima_ocurrencia
        if nueva_severidad:
            self.escalamientos.append(nueva_severidad)
            alerta.severidad = nueva_severidad


def cuerpo(porcentaje=80, **cambios):
    return dict(dict(serial='GW-CAPACIDAD', evento='BUFFER_CAPACITY_WARNING',
        porcentaje_ocupacion=porcentaje, politica_aplicada=None, cantidad_datos_afectados=0,
        timestamp_evento='2026-10-27T10:00:00-05:00'), **cambios)


def construir():
    db, puerto, auditoria = Mock(), Mock(), Mock()
    puerto.obtener_por_serial.return_value = DispositivoHeartbeatInfo(
        id_dispositivo_iot=7, id_infraestructura=3, es_activo=True)
    alertas = Alertas()
    return RegistrarEventoBufferUseCase(db, puerto, alertas, auditoria), db, alertas, auditoria, puerto


@pytest.mark.parametrize('porcentaje,severidad', [(80, 'LEVE'), ('94.9999', 'LEVE'),
    (95, 'CRITICO'), (100, 'CRITICO')])
def test_aviso_capacidad_es_admitido_y_clasificado(porcentaje, severidad):
    uc, db, alertas, auditoria, _ = construir()
    r = uc.execute(RecibirEventoBufferDTO(**cuerpo(porcentaje)))
    assert (r.tipo_alerta_tecnica, r.severidad, r.es_duplicado) == ('BUFFER_CAPACITY_WARNING', severidad, False)
    assert len(alertas.filas) == 1 and alertas.bloqueos == [7]
    a = alertas.filas[0]
    assert (a.tipo_alerta, a.origen_evento, a.id_dispositivo_ioit, a.id_infraestructura) == ('TECNICA', 'EDGE', 7, 3)
    assert a.metadato_evento['porcentaje_ocupacion'] == str(Decimal(str(porcentaje)))
    evento = auditoria.registrar.call_args.args[0]
    assert evento.tipo_evento == 'BUFFER_CAPACITY_WARNING' and evento.hash_integridad
    assert evento.accion_detallada['severidad_alerta'] == severidad
    db.commit.assert_called()


def test_escalamiento_consolida_y_no_rebaja_una_alerta_critica():
    uc, _, alertas, auditoria, _ = construir()
    resultados = [uc.execute(RecibirEventoBufferDTO(**cuerpo(p))) for p in (80, 95, 80)]
    assert [r.id_alerta for r in resultados] == [1, 1, 1]
    assert [r.severidad for r in resultados] == ['LEVE', 'CRITICO', 'CRITICO']
    assert [r.es_duplicado for r in resultados] == [False, True, True]
    assert len(alertas.filas) == 1 and alertas.filas[0].frecuencia_evento == 3
    assert alertas.escalamientos == ['CRITICO']
    assert auditoria.registrar.call_count == 3
    assert [c.args[0].accion_detallada['porcentaje_ocupacion'] for c in auditoria.registrar.call_args_list] == ['80', '95', '80']


def test_en_atencion_conserva_estado_y_escala_severidad():
    uc, _, alertas, _, _ = construir()
    uc.execute(RecibirEventoBufferDTO(**cuerpo()))
    alertas.filas[0].estado_alerta = 'EN_ATENCION'
    r = uc.execute(RecibirEventoBufferDTO(**cuerpo(95)))
    assert r.id_alerta == 1 and r.severidad == 'CRITICO'
    assert alertas.filas[0].estado_alerta == 'EN_ATENCION'


def test_alerta_terminal_permite_nuevo_incidente():
    uc, _, alertas, _, _ = construir()
    uc.execute(RecibirEventoBufferDTO(**cuerpo()))
    alertas.filas[0].estado_alerta = 'DESCARTADA'
    r = uc.execute(RecibirEventoBufferDTO(**cuerpo(95)))
    assert len(alertas.filas) == 2 and r.id_alerta == 2 and r.es_duplicado is False


@pytest.mark.parametrize('porcentaje', [0, '79.9'])
def test_no_impone_otro_umbral_minimo_al_aviso_emitido_por_edge(porcentaje):
    # RF-54 permite configurar el umbral de advertencia en Edge.
    uc, _, _, _, _ = construir()
    assert uc.execute(RecibirEventoBufferDTO(**cuerpo(porcentaje))).severidad == 'LEVE'


def test_preserva_severidad_mayor_ya_asignada():
    uc, _, alertas, _, _ = construir()
    uc.execute(RecibirEventoBufferDTO(**cuerpo()))
    alertas.filas[0].severidad = 'MODERADO'
    assert uc.execute(RecibirEventoBufferDTO(**cuerpo())).severidad == 'MODERADO'


def test_reporte_atrasado_no_retrocede_ultima_ocurrencia():
    uc, _, alertas, _, _ = construir()
    uc.execute(RecibirEventoBufferDTO(**cuerpo(95)))
    fecha = alertas.filas[0].ultima_ocurrencia
    uc.execute(RecibirEventoBufferDTO(**cuerpo(80, timestamp_evento='2026-10-26T10:00:00-05:00')))
    assert alertas.filas[0].ultima_ocurrencia == fecha


@pytest.mark.parametrize('evento,severidad', [('BUFFER_OVERFLOW', 'MODERADO'), ('BUFFER_DATA_CORRUPTION', 'CRITICO')])
def test_conserva_tipos_previos_y_su_severidad(evento, severidad):
    uc, _, alertas, _, _ = construir()
    uc.execute(RecibirEventoBufferDTO(**cuerpo()))
    r = uc.execute(RecibirEventoBufferDTO(**cuerpo(100, evento=evento)))
    assert len(alertas.filas) == 2 and r.tipo_alerta_tecnica == evento and r.severidad == severidad


@pytest.mark.parametrize('cambio', [{'porcentaje_ocupacion': -1}, {'porcentaje_ocupacion': 101},
    {'porcentaje_ocupacion': 'NaN'}, {'porcentaje_ocupacion': 'Infinity'}, {'evento': 'NO_CATALOGADO'},
    {'cantidad_datos_afectados': -1}, {'timestamp_evento': 'no-es-fecha'}])
def test_entrada_invalida_conserva_validaciones(cambio):
    with pytest.raises(PydanticValidationError):
        RecibirEventoBufferDTO(**cuerpo(**cambio))


@pytest.mark.parametrize('operacion', ['bloquear_dispositivo', 'guardar', 'actualizar_deduplicacion'])
def test_fallo_de_persistencia_revierte_y_no_audita_aviso_como_exitoso(operacion):
    uc, db, alertas, auditoria, _ = construir()
    if operacion == 'actualizar_deduplicacion':
        uc.execute(RecibirEventoBufferDTO(**cuerpo()))
        auditoria.reset_mock()
    setattr(alertas, operacion, Mock(side_effect=RuntimeError('indisponible')))
    with pytest.raises(RuntimeError):
        uc.execute(RecibirEventoBufferDTO(**cuerpo(95)))
    db.rollback.assert_called_once()
    auditoria.registrar.assert_not_called()


def test_serial_desconocido_no_crea_alerta():
    uc, _, alertas, auditoria, puerto = construir()
    puerto.obtener_por_serial.return_value = None
    with pytest.raises(NotFoundError):
        uc.execute(RecibirEventoBufferDTO(**cuerpo()))
    assert not alertas.filas and not alertas.bloqueos
    auditoria.registrar.assert_not_called()


@pytest.fixture
def cliente(monkeypatch):
    uc, db, alertas, _, puerto = construir()
    monkeypatch.setenv('BROKER_SERVICE_TOKEN', 'inc684-unit-only')
    monkeypatch.setattr(infraestructura_iot_router, 'DispositivoM09Adapter', lambda db: puerto)
    monkeypatch.setattr(infraestructura_iot_router, 'SqlAlchemyAlertaRepository', lambda db: alertas)
    monkeypatch.setattr(infraestructura_iot_router, 'SqlAlchemyBitacoraAuditoriaIotRepository', lambda db: Mock())
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(infraestructura_iot_router.router)
    app.dependency_overrides[get_db_sistema] = lambda: db
    with TestClient(app) as cliente:
        yield cliente


@pytest.mark.parametrize('porcentaje,severidad', [(80, 'LEVE'), (95, 'CRITICO')])
def test_http_admite_aviso_y_conserva_schema(cliente, porcentaje, severidad):
    r = cliente.post('/iot/eventos-buffer', json=cuerpo(porcentaje), headers={'Authorization': 'Bearer inc684-unit-only'})
    assert r.status_code == 201, r.text
    assert r.json() == {'id_alerta': 1, 'es_duplicado': False, 'tipo_alerta_tecnica': 'BUFFER_CAPACITY_WARNING', 'severidad': severidad}


def test_http_exige_token_broker(cliente):
    assert cliente.post('/iot/eventos-buffer', json=cuerpo()).status_code == 401


def test_openapi_publica_el_nuevo_evento(cliente):
    esquema = cliente.get('/openapi.json').json()
    assert 'BUFFER_CAPACITY_WARNING' in esquema['components']['schemas']['EventoBuffer']['enum']


def test_preserva_normalizacion_utc_compartida_para_fecha_sin_zona():
    dto = RecibirEventoBufferDTO(**cuerpo(timestamp_evento='2026-10-27T10:00:00'))
    assert dto.timestamp_evento.tzinfo == timezone.utc
