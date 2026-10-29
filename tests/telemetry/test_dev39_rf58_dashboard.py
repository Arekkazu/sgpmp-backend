# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-39 RF-58: vista por permiso, GRIS sin umbral y anomalías visibles |
# | 2026-10-25 | Arekkazu | USAB-M03 M3-08 RF-58: el conteo del semáforo pide todos los sensores |
# | 2026-10-28 | destroyerban | INC-M03-177-G57B RF-58: el conteo pide el semáforo base de todos los sensores |
"""DEV-39 (RF-58, C-05): vista por permiso, GRIS sin umbral y anomalías visibles.

CA-8: los datos técnicos dependen del permiso de DB-08, no de id_rol == 2.
E7: variable sin umbral → GRIS "Sin umbral configurado" + aviso al Administrador.
R2 / E2: FUERA_DE_RANGO y ERROR_CALIBRACION visibles con indicador de anomalía.
"""
from __future__ import annotations

import inspect
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.telemetry.application.use_cases.monitoreo import obtener_dashboard_use_case as uc_mod
from src.telemetry.application.use_cases.monitoreo.obtener_dashboard_use_case import ObtenerDashboardUseCase
from src.telemetry.domain.entities.monitoreo import EstadoSensorActual
from src.telemetry.infrastructure.adapters import aviso_sin_umbral_email_adapter as aviso_mod


def _sensor(id_sensor=1, semaforo='VERDE', calidad='LECTURA_VALIDA', desactualizado=False, **kw) -> EstadoSensorActual:
    base = dict(
        id_sensor=id_sensor, id_dispositivo_iot=1, nombre_sensor=f'S{id_sensor}', tipo_variable='pH del agua',
        categoria_variable='HIDRICA', ultimo_valor=Decimal('7.1'), ultima_unidad='pH', ultimo_timestamp_captura=None,
        estado_semaforo=semaforo, estado_calidad=calidad, estado_desviacion=None, estado_conectividad='ACTIVO',
        tiempo_sin_reporte_min=0, dato_desactualizado=desactualizado, id_alerta=None, severidad_alerta=None,
        tendencia=None, id_infraestructura=1, nombre_infraestructura='Estanque 1', id_finca=1, nombre_finca='F',
        nivel_bateria_pct=Decimal('80'), calidad_senal_rssi=Decimal('-70'), calidad_senal_snr=Decimal('9'),
    )
    base.update(kw)
    return EstadoSensorActual(**base)


class _Repo:
    def __init__(self, sensores):
        self.sensores = sensores

    def obtener_estados_sensores(self, **kw):
        return self.sensores, len(self.sensores)

    def obtener_resumen_unidades(self, **kw):
        return []


class _Aviso:
    def __init__(self, falla=False):
        self.recibidos, self.falla = [], falla

    def avisar(self, sensores):
        if self.falla:
            raise RuntimeError('smtp caído')
        self.recibidos.extend(sensores)
        return len(sensores)


def _dashboard(sensores, ver_datos_tecnicos, aviso=None):
    resultado, _, _ = ObtenerDashboardUseCase(_Repo(sensores), aviso).execute(
        None, 1, 50, ver_datos_tecnicos=ver_datos_tecnicos)
    return resultado


# --- CA-8: por permiso, no por id_rol -----------------------------------------------------

def test_no_queda_un_id_rol_quemado():
    assert not hasattr(uc_mod, '_ROL_PRODUCTOR')
    parametros = inspect.signature(ObtenerDashboardUseCase.execute).parameters
    assert 'id_rol_usuario' not in parametros and 'ver_datos_tecnicos' in parametros


@pytest.mark.parametrize("ver, esperado", [(False, None), (True, Decimal('80'))])
def test_datos_tecnicos_solo_con_el_permiso(ver, esperado):
    [s] = _dashboard([_sensor()], ver_datos_tecnicos=ver)
    assert s.nivel_bateria_pct == esperado
    assert (s.calidad_senal_rssi is None) is (not ver) and (s.calidad_senal_snr is None) is (not ver)


# --- E7: GRIS sin umbral -------------------------------------------------------------------

def test_variable_sin_umbral_sale_gris_con_etiqueta_y_avisa():
    aviso = _Aviso()
    [s] = _dashboard([_sensor(semaforo='GRIS')], ver_datos_tecnicos=False, aviso=aviso)
    assert s.estado_semaforo == 'GRIS' and s.sin_umbral is True
    assert s.etiqueta_estado == 'Sin umbral configurado'
    assert s.ultimo_valor == Decimal('7.1')  # no se oculta la variable ni su valor
    assert [x.id_sensor for x in aviso.recibidos] == [1]


def test_gris_por_dato_desactualizado_no_es_sin_umbral():
    aviso = _Aviso()
    [s] = _dashboard([_sensor(semaforo='VERDE', desactualizado=True)], ver_datos_tecnicos=False, aviso=aviso)
    assert s.estado_semaforo == 'GRIS' and s.sin_umbral is False and s.etiqueta_estado is None
    assert aviso.recibidos == []


def test_si_el_aviso_falla_el_dashboard_responde_igual():
    [s] = _dashboard([_sensor(semaforo='GRIS')], ver_datos_tecnicos=True, aviso=_Aviso(falla=True))
    assert s.sin_umbral is True


# --- R2 / E2: anomalías visibles -----------------------------------------------------------

def test_error_calibracion_se_ve_y_el_ingeniero_lee_requiere_calibracion():
    [s] = _dashboard([_sensor(calidad='ERROR_CALIBRACION')], ver_datos_tecnicos=True)
    assert s.indicador_anomalia is True and s.es_valor_operativo is False
    assert s.etiqueta_estado == 'Requiere calibración'
    assert s.ultimo_valor == Decimal('7.1')  # detalle técnico para el Ingeniero


def test_error_calibracion_en_la_vista_del_productor_no_muestra_el_valor_como_operativo():
    [s] = _dashboard([_sensor(calidad='ERROR_CALIBRACION')], ver_datos_tecnicos=False)
    assert s.indicador_anomalia is True and s.etiqueta_estado == 'En revisión técnica'
    assert s.ultimo_valor is None


def test_fuera_de_rango_se_ve_con_indicador_y_su_valor():
    [s] = _dashboard([_sensor(calidad='FUERA_DE_RANGO', ultimo_valor=Decimal('14'))], ver_datos_tecnicos=False)
    assert s.indicador_anomalia is True and s.es_valor_operativo is False
    assert s.etiqueta_estado == 'Lectura fuera de rango' and s.ultimo_valor == Decimal('14')


def test_lectura_valida_no_lleva_indicador():
    [s] = _dashboard([_sensor()], ver_datos_tecnicos=False)
    assert s.indicador_anomalia is False and s.es_valor_operativo is True and s.etiqueta_estado is None


# --- Adaptador del aviso -------------------------------------------------------------------

class _Db:
    def __init__(self, ya_avisados=()):
        self.ya_avisados, self.rollbacks = list(ya_avisados), 0

    def execute(self, sql, params=None):
        texto = str(sql)
        if 'bitacora_auditoria_iot' in texto:
            return SimpleNamespace(scalars=lambda: self.ya_avisados)
        admins = [SimpleNamespace(id_usuario=1, nombre='Ana', apellidos='Ruiz', correo_electronico='admin@x.co')]
        return SimpleNamespace(fetchall=lambda: admins)

    def rollback(self):
        self.rollbacks += 1


@pytest.fixture
def adaptador(monkeypatch):
    enviados, eventos = [], []
    monkeypatch.setattr(aviso_mod, 'send_email', lambda **kw: enviados.append(kw))
    monkeypatch.setattr(aviso_mod, 'como_sistema', lambda db: __import__('contextlib').nullcontext())
    monkeypatch.setattr(aviso_mod, 'SqlAlchemyBitacoraAuditoriaIotRepository', lambda db: None)

    class _Registrar:
        def __init__(self, db, repo): pass
        def execute(self, **kw): eventos.append(kw)

    monkeypatch.setattr(aviso_mod, 'RegistrarEventoAuditoriaIotUseCase', _Registrar)
    return enviados, eventos


def test_el_aviso_va_a_los_administradores_y_queda_en_la_bitacora(adaptador):
    enviados, eventos = adaptador
    assert aviso_mod.AvisoSinUmbralEmailAdapter(_Db()).avisar([_sensor(id_sensor=4)]) == 1
    assert [e['to'] for e in enviados] == ['admin@x.co'] and enviados[0]['intentos'] == 1
    assert 'pH del agua' in enviados[0]['subject'] and 'Sin umbral configurado' in enviados[0]['html_body']
    [evento] = eventos
    assert evento['tipo_evento'] == 'VARIABLE_SIN_UMBRAL' and evento['entidad_afectada_id'] == '4'


def test_no_se_repite_el_aviso_de_un_sensor_ya_avisado_en_24h(adaptador):
    enviados, eventos = adaptador
    assert aviso_mod.AvisoSinUmbralEmailAdapter(_Db(ya_avisados=['4'])).avisar([_sensor(id_sensor=4)]) == 0
    assert enviados == [] and eventos == []


# --- M3-08: el conteo no es el de la página ----------------------------------------------

def test_m3_08_conteo_del_semaforo_sobre_todos_los_sensores():
    """Antes el front contaba la página: "50 sensores" en un área de 200."""
    pedidos = []

    class _RepoTodos(_Repo):
        # G57B: el conteo usa el semáforo base, no la consulta completa de estados.
        def obtener_semaforos_sensores(self, id_infraestructura, **kw):
            pedidos.append(id_infraestructura)
            return self.sensores

    sensores = [_sensor(i) for i in range(60)] + [
        _sensor(61, id_alerta=9, severidad_alerta='CRITICO'),  # CA-4: alerta crítica activa → ROJO
        _sensor(62, desactualizado=True),                       # CA-5: sin datos recientes → GRIS
    ]
    conteo = ObtenerDashboardUseCase(_RepoTodos(sensores)).contar_semaforos(None)

    assert pedidos == [None]  # todo el alcance, sin página
    assert conteo == {'VERDE': 60, 'ROJO': 1, 'GRIS': 1}
