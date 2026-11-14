"""RF-62 DEV-02 contra PostgreSQL real, con el trigger RF-53 activo.

Usa TEST_DATABASE_URL y db_session: las filas se revierten al terminar cada
prueba. Las secuencias pueden avanzar, como en el resto de integración.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import importlib
import pkgutil
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.exc import InvalidRequestError

from src.telemetry.application.use_cases.calidad.evaluar_calidad_telemetria_use_case import EvaluarCalidadTelemetriaUseCase
from src.telemetry.domain.entities.telemetria import Telemetria
from src.telemetry.domain.entities.telemetria_calidad import ClasificacionCalidad, TelemetriaCalidad
from src.telemetry.domain.repositories.parametros_calidad_port import ParametrosCalidad
from src.telemetry.infrastructure.models.telemetria_model import TelemetriaModel
from src.telemetry.infrastructure.repositories.telemetria_calidad_repository import SqlAlchemyTelemetriaCalidadRepository
from src.telemetry.infrastructure.repositories.telemetria_repository import SqlAlchemyTelemetriaRepository

pytestmark = pytest.mark.integration


@pytest.fixture
def crear_escenario(db_session):
    # La aplicación registra estos modelos al cargar sus routers. La prueba
    # aislada debe registrarlos también para resolver las FK de TelemetriaModel.
    from src.configuration.infrastructure import models
    for modulo in pkgutil.iter_modules(models.__path__):
        importlib.import_module(f"{models.__name__}.{modulo.name}")
    sufijo = uuid4().hex[:12].translate(str.maketrans("0123456789abcdef", "abcdefghijklmnop"))
    finca = db_session.execute(text("""
        INSERT INTO modulo9.fincas
            (nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, es_activo)
        VALUES (:nombre, '{"departamento":"Huila","municipio":"Neiva","vereda":"Centro",
                "latitud":"2.93","longitud":"-75.28"}'::jsonb, 10, now(), now(), true)
        RETURNING id_finca
    """), {"nombre": "Finca Calidad " + sufijo}).scalar_one()
    area = db_session.execute(text("""
        INSERT INTO modulo9.infraestructuras (nombre,id_finca,superficie,es_activo,tipo)
        VALUES (:nombre,:finca,100,true,'Estanque') RETURNING id_infraestructura
    """), {"nombre": "Area Calidad " + sufijo, "finca": finca}).scalar_one()
    dispositivo = db_session.execute(text("""
        INSERT INTO modulo9.dispositivos_iot
            (serial,descripcion,es_activo,fecha_creacion,id_infraestructura,id_tipo_dispositivo)
        VALUES (:serial,'Dispositivo integracion RF62',true,now(),:area,1)
        RETURNING id_dispositivo_iot
    """), {"serial": "RF62-" + uuid4().hex, "area": area}).scalar_one()
    sensor = db_session.execute(text("""
        INSERT INTO modulo9.sensores (id_dispositivo_iot,es_activo,nombre,categoria)
        VALUES (:dispositivo,true,:nombre,'TEMPERATURA') RETURNING id_sensores
    """), {"dispositivo": dispositivo, "nombre": "Sensor Calidad " + sufijo}).scalar_one()
    lecturas = SqlAlchemyTelemetriaRepository(db_session)
    calidad = SqlAlchemyTelemetriaCalidadRepository(db_session)

    def crear(*, estado="LECTURA_VALIDA", valor=Decimal("22.5"), legacy=False):
        captura = datetime.now(timezone.utc) - timedelta(minutes=1)
        for indice in range(20):
            lecturas.guardar(Telemetria(
                id_sensor=sensor, id_variable=9, id_dispositivo_iot=dispositivo,
                valor_crudo=Decimal(22 + indice % 2), valor_ajustado=Decimal(22 + indice % 2),
                timestamp_captura=captura - timedelta(minutes=20 - indice),
                timestamp_procesamiento=captura, origen="TIEMPO_REAL",
                estado_calidad="LECTURA_VALIDA", calibrado=True, categoria_variable="AMBIENTAL",
                unidad_medida="°C", valor_agregado=False, tipo_dato="CRUDO",
            ))
        # Una columna legada verdadera demuestra que no se utiliza como fuente.
        # Solo INSERT de fixture; nunca UPDATE sobre telemetrias.
        objetivo = TelemetriaModel(
            id_sensor=sensor, id_variable=9, id_dispositivo_iot=dispositivo,
            valor_crudo=valor, valor_ajustado=valor, timestamp_captura=captura,
            timestamp_procesamiento=captura, origen="TIEMPO_REAL", estado_calidad=estado,
            calibrado=True, categoria_variable="AMBIENTAL", unidad_medida="°C",
            valor_agregado=False, tipo_dato="CRUDO", metadatos={},
            apto_para_ia=legacy, apto_para_nic41=legacy,
        )
        db_session.add(objetivo)
        db_session.flush()
        db_session.commit()  # Guarda el setup dentro de la transacción exterior.
        parametros = SimpleNamespace(obtener_parametros=lambda *args: ParametrosCalidad(
            k=3.0, M=5, N=20, umbral_drift=5.0, umbral_drift_significativo=10.0,
            P=3, frecuencia_muestreo_min=5,
        ))
        caso = EvaluarCalidadTelemetriaUseCase(db_session, lecturas, calidad, parametros)
        return SimpleNamespace(
            caso=caso, lecturas=lecturas, calidad=calidad, sensor=sensor,
            id_telemetria=objetivo.id_telemetria, captura=captura, parametros=parametros,
            datos=dict(id_telemetria=objetivo.id_telemetria, id_sensor=sensor, id_variable=9,
                       valor=valor, valor_ajustado=valor, timestamp_captura=captura,
                       estado_calidad_rf53=estado, parametros_calibracion={"ganancia": 1, "offset": 0}),
        )

    return crear


def _snapshot(db, sensor):
    # Excluye explícitamente las columnas obsoletas incluso en la comprobación.
    tabla = TelemetriaModel.__table__
    columnas = [c for c in tabla.c if c.name not in ("apto_para_ia", "apto_para_nic41")]
    return db.execute(select(*columnas).where(tabla.c.id_sensor == sensor).order_by(tabla.c.id_telemetria)).all()


def _cantidad(db, sensor):
    return db.execute(text("SELECT count(*) FROM modulo3.telemetria_calidad WHERE id_sensor=:sensor"),
                      {"sensor": sensor}).scalar_one()


@pytest.mark.parametrize("valor,calibracion,indice,aptitud", [
    (Decimal("22.5"), {"ganancia": 1, "offset": 0}, 100, (True, True)),
    (Decimal("30"), {"ganancia": 1, "offset": 1.5}, 70, (True, False)),
], ids=["APTO", "APTO_CON_RESERVA"])
def test_20_lecturas_persisten_aptitud_sin_actualizar_rf53(
    crear_escenario, db_session, valor, calibracion, indice, aptitud,
):
    e = crear_escenario(valor=valor)
    antes = _snapshot(db_session, e.sensor)
    assert len(antes) == 21
    trigger = db_session.execute(text("""
        SELECT tgenabled, pg_get_triggerdef(oid) FROM pg_trigger
        WHERE tgrelid='modulo3.telemetrias'::regclass AND tgname='trg_rf53_02_no_update'
    """)).one()
    assert trigger[0] != "D" and "BEFORE UPDATE" in trigger[1]
    statements = []
    connection = db_session.connection()

    def registrar(_conn, _cursor, statement, *_args):
        statements.append(statement.lower())

    event.listen(connection, "before_cursor_execute", registrar)
    try:
        evaluacion = e.caso.execute(**{**e.datos, "parametros_calibracion": calibracion})
        lectura = e.lecturas.obtener_por_id(e.id_telemetria)
    finally:
        event.remove(connection, "before_cursor_execute", registrar)
    assert evaluacion.indice_calidad == indice
    assert (evaluacion.apto_para_ia, evaluacion.apto_para_nic41) == aptitud
    assert e.calidad.obtener_por_lectura(e.id_telemetria).id_evaluacion == evaluacion.id_evaluacion
    assert (lectura.apto_para_ia, lectura.apto_para_nic41) == aptitud
    assert _cantidad(db_session, e.sensor) == 1
    assert _snapshot(db_session, e.sensor) == antes
    assert not any(s.lstrip().startswith("update modulo3.telemetrias") for s in statements)
    assert not any("telemetrias.apto_para_" in s for s in statements if s.lstrip().startswith("select"))


@pytest.mark.parametrize("fuera_de_rango", [False, True], ids=["indeterminada", "fuera-de-rango"])
def test_ramas_anticipadas_confirman_sin_depender_de_auditoria(crear_escenario, db_session, fuera_de_rango):
    e = crear_escenario(estado="FUERA_DE_RANGO" if fuera_de_rango else "LECTURA_VALIDA")
    if not fuera_de_rango:
        e.parametros.obtener_parametros = lambda *args: ParametrosCalidad(
            k=3.0, M=5, N=30, umbral_drift=5.0, umbral_drift_significativo=10.0,
            P=3, frecuencia_muestreo_min=5,
        )
    antes = _snapshot(db_session, e.sensor)
    evaluacion = e.caso.execute(**e.datos)
    assert evaluacion.clasificacion_calidad == ("NO_APTO" if fuera_de_rango else "INDETERMINADA")
    db_session.rollback()  # Una evaluación ya confirmada debe sobrevivir a este rollback.
    assert e.calidad.obtener_por_lectura(e.id_telemetria).id_evaluacion == evaluacion.id_evaluacion
    assert _snapshot(db_session, e.sensor) == antes


def test_nueva_evaluacion_supera_anterior_y_preserva_historial(crear_escenario, db_session):
    e = crear_escenario()
    antes = _snapshot(db_session, e.sensor)
    anterior = e.caso.execute(**e.datos)
    e.parametros.obtener_parametros = lambda *args: ParametrosCalidad(
        k=3.0, M=5, N=30, umbral_drift=5.0, umbral_drift_significativo=10.0,
        P=3, frecuencia_muestreo_min=5,
    )
    nueva = e.caso.execute(**e.datos)
    assert nueva.id_evaluacion_superada == anterior.id_evaluacion
    assert (nueva.apto_para_ia, nueva.apto_para_nic41) == (False, False)
    assert e.calidad.obtener_por_lectura(e.id_telemetria).id_evaluacion == nueva.id_evaluacion
    assert not e.lecturas.obtener_por_id(e.id_telemetria).apto_para_ia
    assert _cantidad(db_session, e.sensor) == 2
    anteriores, total = e.calidad.listar(id_sensor=e.sensor, estado_evaluacion="SUPERADA")
    assert total == 1 and anteriores[0].id_evaluacion == anterior.id_evaluacion
    assert anteriores[0].indice_calidad == 100 and anteriores[0].apto_para_ia
    vigentes, total = e.calidad.listar(id_sensor=e.sensor)
    assert total == 1 and vigentes[0].id_evaluacion == nueva.id_evaluacion
    assert _snapshot(db_session, e.sensor) == antes


@pytest.mark.parametrize("fase", ["guardar", "superar", "commit"])
def test_rollback_conserva_la_evaluacion_anterior(crear_escenario, db_session, monkeypatch, fase):
    e = crear_escenario()
    anterior = e.caso.execute(**e.datos)
    antes = _snapshot(db_session, e.sensor)

    def falla_despues(funcion):
        def ejecutar(*args, **kwargs):
            funcion(*args, **kwargs)
            raise RuntimeError("fallo transaccional RF62")
        return ejecutar

    if fase == "commit":
        def falla_commit():
            raise RuntimeError("fallo transaccional RF62")
        monkeypatch.setattr(db_session, "commit", falla_commit)
    else:
        nombre = "guardar" if fase == "guardar" else "marcar_superada"
        monkeypatch.setattr(e.calidad, nombre, falla_despues(getattr(e.calidad, nombre)))
    with pytest.raises(RuntimeError, match="fallo transaccional"):
        e.caso.execute(**e.datos)
    assert _cantidad(db_session, e.sensor) == 1
    assert e.calidad.obtener_por_lectura(e.id_telemetria).id_evaluacion == anterior.id_evaluacion
    assert _snapshot(db_session, e.sensor) == antes


def test_columnas_legadas_no_se_cargan_ni_se_consumen(crear_escenario, db_session):
    e = crear_escenario(legacy=True)
    db_session.expunge_all()
    lectura = e.lecturas.obtener_por_id(e.id_telemetria)
    assert (lectura.apto_para_ia, lectura.apto_para_nic41) == (False, False)
    orm = db_session.get(TelemetriaModel, e.id_telemetria)
    with pytest.raises(InvalidRequestError, match="raiseload"):
        _ = orm.apto_para_ia


def _evaluacion(e, instante, *, apta, anterior=None, identificador=None):
    return TelemetriaCalidad(
        id_evaluacion=identificador, id_telemetria=e.id_telemetria, id_sensor=e.sensor,
        timestamp_evaluacion=instante, indice_calidad=100 if apta else 0,
        clasificacion_calidad=ClasificacionCalidad.APTO if apta else ClasificacionCalidad.NO_APTO,
        apto_para_ia=apta, apto_para_nic41=apta, id_evaluacion_superada=anterior,
    )


def test_cadena_superada_prevalece_sobre_estado_legado(crear_escenario, db_session):
    e = crear_escenario()
    ahora = datetime.now(timezone.utc)
    anterior = e.calidad.guardar(_evaluacion(e, ahora, apta=True))
    nueva = e.calidad.guardar(_evaluacion(e, ahora - timedelta(seconds=1), apta=False,
                                         anterior=anterior.id_evaluacion))
    db_session.commit()
    # Ambas filas conservan estado VIGENTE; el enlace de sustitución manda.
    assert e.calidad.obtener_por_lectura(e.id_telemetria).id_evaluacion == nueva.id_evaluacion
    assert e.calidad.listar(id_sensor=e.sensor, clasificacion="APTO")[1] == 0


def test_varios_vigentes_no_duplican_ni_resucitan_aptitud_anterior(crear_escenario, db_session):
    e = crear_escenario()
    ahora = datetime.now(timezone.utc)
    e.calidad.guardar(_evaluacion(e, ahora - timedelta(seconds=1), apta=True))
    nueva = e.calidad.guardar(_evaluacion(e, ahora, apta=False))
    db_session.commit()
    assert e.calidad.obtener_por_lectura(e.id_telemetria).id_evaluacion == nueva.id_evaluacion
    items, total = e.calidad.listar(id_sensor=e.sensor, estado_evaluacion="VIGENTE")
    assert total == 1 and len(items) == 1
    assert e.calidad.listar(id_sensor=e.sensor, clasificacion="APTO")[1] == 0
    assert len(e.calidad.listar_vigentes_por_sensor_rango(
        e.sensor, ahora - timedelta(minutes=1), ahora + timedelta(minutes=1),
    )) == 1


def test_empate_de_timestamp_tiene_desempate_estable(crear_escenario, db_session):
    e = crear_escenario()
    ahora = datetime.now(timezone.utc)
    a = e.calidad.guardar(_evaluacion(e, ahora, apta=True))
    b = e.calidad.guardar(_evaluacion(e, ahora, apta=False))
    db_session.commit()
    esperado = max((a, b), key=lambda ev: (ev.fecha_creacion, ev.id_evaluacion))
    for _ in range(2):
        assert e.calidad.obtener_por_lectura(e.id_telemetria).id_evaluacion == esperado.id_evaluacion
    assert e.calidad.listar(id_sensor=e.sensor)[1] == 1
