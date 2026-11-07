# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-04 RF-60: parámetros de heartbeat por categoría y ventanas de visión reales |
"""AJF-04: la pantalla de dispositivos mostraba valores quemados (camarasMock.ts)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest

from src.shared.errors import NotFoundError, ValidationError
from src.telemetry.application.use_cases.infraestructura.consultar_parametros_heartbeat_use_case import (
    ConsultarParametrosHeartbeatUseCase,
)
from src.telemetry.domain.entities.parametros_heartbeat_categoria import (
    ConfiguracionHeartbeatLeida, VentanaObservada, parametros_por_categoria,
)


def _config(**kw):
    base = dict(intervalos_por_tipo={'NODO_AMBIENTAL': 300}, intervalo_camara_seg=120, frecuencia_muestreo_seg=600,
                margen_tolerancia_seg=300, inactividad_extendida_seg=21600, categorias=('NODO_AMBIENTAL', 'NODO_HIDRICO'))
    base.update(kw)
    return ConfiguracionHeartbeatLeida(**base)


def test_umbrales_con_las_mismas_formulas_que_rf60():
    por = {p.categoria: p for p in parametros_por_categoria(_config())}
    amb = por['NODO_AMBIENTAL']
    assert (amb.umbral_sin_senal_seg, amb.umbral_inactivo_seg, amb.cadena_valida, amb.configurado) == (900, 22500, True, True)
    cam = por['CAMARA']
    assert (cam.intervalo_heartbeat_seg, cam.umbral_sin_senal_seg) == (120, 900)


def test_categoria_sin_intervalo_queda_sin_configurar_sin_inventar_valores():
    hid = {p.categoria: p for p in parametros_por_categoria(_config())}['NODO_HIDRICO']
    assert hid.intervalo_heartbeat_seg is None and hid.umbral_sin_senal_seg is None
    assert hid.faltantes == ('intervalos_heartbeat_por_tipo',) and not hid.configurado


def test_sin_configuracion_rf18_todo_queda_sin_umbral():
    for p in parametros_por_categoria(_config(frecuencia_muestreo_seg=None)):
        assert p.umbral_sin_senal_seg is None and 'frecuencia_muestreo' in p.faltantes


def _ventana(i, cobertura):
    fin = datetime(2026, 11, 2, 12, tzinfo=timezone.utc) - timedelta(minutes=i)
    return VentanaObservada(i, fin - timedelta(minutes=1), fin, Decimal(cobertura), 3)


def _uc(categoria='CAMARA', ventanas=(), parametros=(3, Decimal('0.30'), 60)):
    port = Mock()
    port.categoria_dispositivo.return_value = categoria
    port.ventanas_recientes.return_value = list(ventanas)
    port.parametros_ventanas.return_value = parametros
    return ConsultarParametrosHeartbeatUseCase(port), port


def test_tres_ventanas_seguidas_bajo_el_minimo_es_sin_deteccion_valida():
    uc, _ = _uc(ventanas=[_ventana(0, '0.10'), _ventana(1, '0.20'), _ventana(2, '0.29'), _ventana(3, '0.90')])
    r = uc.ventanas_vision(5, None)
    assert (r.consecutivas_bajo_minimo, r.resultado) == (3, 'SIN_DETECCION_VALIDA')


def test_igual_al_minimo_corta_la_secuencia():
    uc, _ = _uc(ventanas=[_ventana(0, '0.10'), _ventana(1, '0.30'), _ventana(2, '0.10')])
    assert uc.ventanas_vision(5, None).resultado == 'DETECCION_VALIDA'


def test_dispositivo_que_no_es_camara_no_consulta_ventanas():
    uc, port = _uc(categoria='NODO_AMBIENTAL')
    assert uc.ventanas_vision(5, [1]).resultado == 'NO_ES_CAMARA'
    port.ventanas_recientes.assert_not_called()


def test_sin_parametros_de_vision_se_dice_sin_configurar():
    uc, _ = _uc(ventanas=[_ventana(0, '0.10')], parametros=(None, None, None))
    assert uc.ventanas_vision(5, None).resultado == 'SIN_CONFIGURAR'


def test_fuera_del_alcance_es_404_y_cantidad_invalida_400():
    uc, _ = _uc(categoria=None)
    with pytest.raises(NotFoundError):
        uc.ventanas_vision(5, [1])
    with pytest.raises(ValidationError):
        uc.ventanas_vision(5, None, cantidad=0)


@pytest.fixture
def cliente(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers
    from src.telemetry.infrastructure.routers import infraestructura_iot_router as router_mod

    port = Mock()
    port.leer_configuracion.return_value = _config()
    port.categoria_dispositivo.return_value = 'CAMARA'
    port.ventanas_recientes.return_value = [_ventana(0, '0.10')]
    port.parametros_ventanas.return_value = (3, Decimal('0.30'), 60)
    monkeypatch.setattr(router_mod, 'ParametrosHeartbeatCategoriaAdapter', lambda db: port)
    monkeypatch.setattr(router_mod, 'AlcanceFincaAdapter', lambda db: Mock(listar_ids_fincas_permitidas=lambda *a: None))
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router_mod.router)
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id_usuario=1, id_token=1, id_rol=4, id_estado_cuenta=2)
    for ruta in router_mod.router.routes:
        for dependencia in ruta.dependencies:
            app.dependency_overrides[dependencia.dependency] = lambda: None
    return TestClient(app)


def test_endpoints_responden_con_el_contrato(cliente):
    params = cliente.get('/iot/dispositivos/parametros-heartbeat').json()
    assert {p['categoria'] for p in params} == {'CAMARA', 'NODO_AMBIENTAL', 'NODO_HIDRICO'}
    assert next(p for p in params if p['categoria'] == 'NODO_HIDRICO')['configurado'] is False
    v = cliente.get('/iot/dispositivos/5/ventanas-vision', params={'cantidad': 5}).json()
    assert v['resultado'] == 'DETECCION_VALIDA' and v['ventanas'][0]['cobertura'] == '0.10'
