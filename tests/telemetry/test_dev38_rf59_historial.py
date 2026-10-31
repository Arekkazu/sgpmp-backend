# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-38 RF-59: zona horaria, truncado con aviso, bitácora y vacíos temporales |
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
# | 2026-10-26 | Arekkazu | INC-M03 lote 26-10 RF-59: fakes con alertas correlacionadas y validación de variables |
# | 2026-10-31 | Arekkazu | USAB-M03-M04 M3-09/N-06 RF-59: el fake de umbral responde también por área |
"""DEV-38 (RF-59, G-10): zona horaria, truncado con aviso, bitácora de consultas y vacíos.

E2: "hoy" y los límites del rango son días en Colombia.
E6 / CA-19: más de 10 000 registros → 200 con los primeros 10 000 y aviso (antes 422).
E1, postcondición 6 / CA-16: evento por consulta y por intento sin permiso.
E7 / CA-17: los vacíos > 3 × frecuencia viajan en la respuesta.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import src.shared.fechas as fechas
from src.shared.errors import AuthorizationError, BusinessRuleError
from src.telemetry.application.use_cases.monitoreo.consultar_historial_use_case import ConsultarHistorialUseCase
from src.telemetry.domain.entities.evento_auditoria_iot import ComponenteOrigen, SeveridadLog, TipoResultado
from src.telemetry.domain.entities.monitoreo import FiltrosHistorial, LecturaHistorica, VacioTemporal
from src.telemetry.infrastructure import rbac_auditoria
from src.telemetry.infrastructure.repositories.historial_telemetria_repository import (
    _COUNT_HISTORIAL,
    _build_query,
)



def _lectura(i: int) -> LecturaHistorica:
    return LecturaHistorica(
        id_telemetria=i, id_sensor=7, nombre_sensor='S7', id_variable=1, tipo_variable='TEMPERATURA_AMBIENTAL',
        categoria_variable='AMBIENTAL', valor=None, valor_ajustado=None, unidad_medida='°C',
        timestamp_captura=datetime(2026, 10, 1, tzinfo=timezone.utc) + timedelta(minutes=i),
        estado_calidad='LECTURA_VALIDA', estado_semaforo_historico='GRIS', origen_dato='TIEMPO_REAL',
        id_infraestructura=1, infraestructura='Galpón', finca='Finca', id_activo_biologico=None, especie=None,
        id_especie=None, id_alerta=None, nivel_bateria_pct=None, calidad_senal_rssi=None, calidad_senal_snr=None,
    )


class _Repo:
    """Simula la paginación del repositorio real sobre ``total`` filas."""

    def __init__(self, total: int, vacios=()):
        self.total, self.vacios = total, list(vacios)

    def consultar(self, f: FiltrosHistorial):
        inicio = (f.pagina - 1) * f.por_pagina
        fin = min(inicio + f.por_pagina, self.total)
        return [_lectura(i) for i in range(inicio, max(inicio, fin))], self.total

    def calcular_estadisticas(self, f):
        return []

    def detectar_vacios(self, f):
        return self.vacios

    def alertas_correlacionadas(self, f):
        return []

    def variables_no_reconocidas(self, tipos):
        return []


class _Umbral:
    def obtener_umbral_vigente(self, **kw):
        return None

    def obtener_umbral_vigente_area(self, **kw):  # M3-09/N-06
        return None


class _Auditoria:
    def __init__(self):
        self.eventos = []

    def execute(self, **kw):
        self.eventos.append(kw)


def _filtros(**cambios) -> FiltrosHistorial:
    base = dict(fecha_inicio=date(2026, 9, 1), fecha_fin=date(2026, 9, 30), tipo_variable='TEMPERATURA_AMBIENTAL')
    base.update(cambios)
    return FiltrosHistorial(**base)


def _consultar(total, auditoria=None, vacios=(), **filtros):
    uc = ConsultarHistorialUseCase(historial_repo=_Repo(total, vacios), umbral_port=_Umbral(), auditoria=auditoria)
    return uc.execute(_filtros(**filtros), id_usuario=5, id_rol=2)


# --- E2: zona horaria -------------------------------------------------------------------

def test_hoy_es_el_dia_en_colombia(monkeypatch, en_colombia):
    # 2026-10-24 03:00 UTC = 2026-10-23 22:00 en Colombia: el 24 todavía es futuro.
    monkeypatch.setattr(fechas, '_ahora', lambda: datetime(2026, 10, 24, 3, 0, tzinfo=timezone.utc).astimezone(en_colombia))
    with pytest.raises(BusinessRuleError) as exc:
        _consultar(1, fecha_inicio=date(2026, 10, 20), fecha_fin=date(2026, 10, 24))
    assert exc.value.code == 'FECHA_FIN_FUTURA'
    _consultar(1, fecha_inicio=date(2026, 10, 20), fecha_fin=date(2026, 10, 23))  # hoy en Colombia: válido


def test_el_rango_va_de_medianoche_a_medianoche_en_colombia(en_colombia):
    _, params = _build_query(_filtros(fecha_inicio=date(2026, 10, 1), fecha_fin=date(2026, 10, 22)), _COUNT_HISTORIAL)
    assert params['fecha_inicio'] == datetime(2026, 10, 1, 5, 0, tzinfo=timezone.utc)
    assert params['fecha_fin_ex'] == datetime(2026, 10, 23, 5, 0, tzinfo=timezone.utc)
    # Una lectura del 22 a las 22:00 en Colombia (23 a las 03:00 UTC) entra; antes quedaba fuera.
    lectura = datetime(2026, 10, 23, 3, 0, tzinfo=timezone.utc)
    assert params['fecha_inicio'] <= lectura < params['fecha_fin_ex']


def test_sin_zona_del_usuario_el_rango_es_en_utc():
    _, params = _build_query(_filtros(fecha_inicio=date(2026, 10, 1), fecha_fin=date(2026, 10, 22)), _COUNT_HISTORIAL)
    assert params['fecha_inicio'] == datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    assert params['fecha_fin_ex'] == datetime(2026, 10, 23, 0, 0, tzinfo=timezone.utc)


# --- E6 / CA-19: truncado con aviso -----------------------------------------------------

def test_12000_registros_responde_con_los_primeros_10000_y_aviso():
    lecturas, _, total, meta = _consultar(12_000)
    assert total == 10_000 and meta['total_encontrado'] == 12_000
    assert meta['truncado'] is True
    assert 'supera el límite de 10000' in meta['aviso'] and 'filtros adicionales' in meta['aviso']
    assert meta['total_paginas'] == 100  # 10 000 / 100
    assert len(lecturas) == 100


@pytest.mark.parametrize(
    "pagina, por_pagina, esperados",
    [(100, 100, 100), (101, 100, 0), (34, 300, 100), (20, 500, 500), (21, 500, 0)],
)
def test_no_se_sirven_registros_mas_alla_del_tope(pagina, por_pagina, esperados):
    lecturas, *_ = _consultar(12_000, pagina=pagina, por_pagina=por_pagina)
    assert len(lecturas) == esperados


def test_bajo_el_limite_no_se_trunca():
    lecturas, _, total, meta = _consultar(9_999)
    assert total == 9_999 and meta['truncado'] is False and meta['aviso'] is None


# --- Postcondición 6 / CA-16 / E6: bitácora de cada consulta ---------------------------

def test_cada_consulta_deja_su_evento_con_usuario_rol_filtros_y_registros():
    auditoria = _Auditoria()
    _consultar(250, auditoria=auditoria)
    [evento] = auditoria.eventos
    assert evento['tipo_evento'] == 'HISTORIAL_CONSULTADO'
    assert evento['componente_origen'] == ComponenteOrigen.RF59
    assert evento['resultado'] == TipoResultado.EXITOSO and evento['severidad_log'] == SeveridadLog.INFO
    assert evento['id_usuario'] == 5
    detalle = evento['accion_detallada']
    assert detalle['id_rol'] == 2
    assert detalle['filtros']['tipo_variable'] == ['TEMPERATURA_AMBIENTAL']
    assert detalle['registros_devueltos'] == 100 and detalle['total_encontrado'] == 250
    assert detalle['truncado'] is False and detalle['exportado'] is False


def test_una_consulta_truncada_queda_como_advertencia_para_el_analisis_de_rendimiento():
    auditoria = _Auditoria()
    _consultar(12_000, auditoria=auditoria)
    [evento] = auditoria.eventos
    assert evento['resultado'] == TipoResultado.ADVERTENCIA and evento['severidad_log'] == SeveridadLog.WARNING
    assert evento['accion_detallada']['truncado'] is True


def test_una_consulta_invalida_no_se_ejecuta_ni_se_registra():
    auditoria = _Auditoria()
    with pytest.raises(BusinessRuleError):
        _consultar(1, auditoria=auditoria, fecha_inicio=date(2026, 9, 30), fecha_fin=date(2026, 9, 1))
    assert auditoria.eventos == []


# --- E7 / CA-17: vacíos temporales -------------------------------------------------------

def test_los_vacios_temporales_llegan_en_la_respuesta():
    vacio = VacioTemporal(sensor_id=7, tipo_variable='TEMPERATURA_AMBIENTAL',
                          desde=datetime(2026, 9, 2, 10, tzinfo=timezone.utc),
                          hasta=datetime(2026, 9, 2, 14, tzinfo=timezone.utc),
                          duracion_min=240, frecuencia_esperada_min=10)
    auditoria = _Auditoria()
    _, _, _, meta = _consultar(5, auditoria=auditoria, vacios=[vacio])
    assert meta['vacios_temporales'] == [{
        'sensor_id': 7, 'tipo_variable': 'TEMPERATURA_AMBIENTAL',
        'desde': vacio.desde, 'hasta': vacio.hasta, 'duracion_min': 240, 'frecuencia_esperada_min': 10,
    }]
    assert auditoria.eventos[0]['accion_detallada']['vacios_temporales'] == 1


# --- E1: el intento sin permiso deja su evento -------------------------------------------

def test_intento_sin_permiso_queda_en_la_bitacora_y_responde_403(monkeypatch):
    def _sin_permiso(id_recurso, id_accion):
        def verificar(db, usuario_actual):
            raise AuthorizationError(code='ACCESO_DENEGADO', message='Acceso denegado.')
        return verificar

    registrados = []

    class _Registrar:
        def __init__(self, db, repo): pass
        def execute(self, **kw): registrados.append(kw)

    monkeypatch.setattr(rbac_auditoria, 'require_permission', _sin_permiso)
    monkeypatch.setattr(rbac_auditoria, 'RegistrarEventoAuditoriaIotUseCase', _Registrar)
    monkeypatch.setattr(rbac_auditoria, 'SqlAlchemyBitacoraAuditoriaIotRepository', lambda db: None)

    dependencia = rbac_auditoria.require_permission_auditado(
        34, 2, componente_origen=ComponenteOrigen.RF59, tipo_evento='HISTORIAL_ACCESO_DENEGADO',
    )
    request = SimpleNamespace(method='GET', scope={'route': SimpleNamespace(path='/iot/monitoreo/historial')},
                              url=SimpleNamespace(path='/iot/monitoreo/historial'),
                              query_params={'fecha_inicio': '2026-09-01'})
    with pytest.raises(AuthorizationError):
        dependencia(request=request, db=None, usuario_actual=SimpleNamespace(id_usuario=9, id_rol=5))

    [evento] = registrados
    assert evento['tipo_evento'] == 'HISTORIAL_ACCESO_DENEGADO'
    assert evento['resultado'] == TipoResultado.RECHAZADO and evento['componente_origen'] == ComponenteOrigen.RF59
    assert evento['id_usuario'] == 9
    assert evento['accion_detallada']['id_rol'] == 5
    assert evento['accion_detallada']['ruta'] == '/iot/monitoreo/historial'
    assert evento['accion_detallada']['filtros'] == {'fecha_inicio': '2026-09-01'}
