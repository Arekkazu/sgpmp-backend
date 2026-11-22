# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-23 | Leandro | DEV-24 RF-24: verificar pares, contrato compatible y fallos multiespecie. |
"""RF-24 con composición DB-06; RF-56 aporta observaciones agregadas del área."""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from src.configuration.application.use_cases.sensores.calibrar_vision_use_case import (
    ConsultarCalibracionVisionUseCase,
)
from src.configuration.domain.value_objects.calibracion_vision import EstadoCalibracionVision
from src.configuration.infrastructure.routers import calibracion_vision_router as router
from src.shared.errors import BusinessRuleError, InfrastructureError, NotFoundError
from tests.configuration.test_inc_m09_78_g138_calibracion_vision import (
    _T0, _USUARIO, _area, _dto, _obs, _uc,
)


class LineasPorPar:
    def __init__(self):
        self.pares = {}

    def publicar(self, lb):
        self.pares[lb.id_infraestructura, lb.id_especie] = lb
        return lb

    def obtener_vigente(self, area, especie):
        return self.pares.get((area, especie))


def consulta(uc):
    return ConsultarCalibracionVisionUseCase(
        uc.infraestructura_repo, uc.calibracion_repo, uc.linea_base_repo,
    )


@pytest.mark.parametrize('especies', [[4], [4, 5], [6, 4, 5], [4, 5, 4]])
def test_una_calibracion_por_par_sin_usar_la_propiedad_singular(especies):
    area = _area(id_especies=especies)
    del area.id_especie
    uc = _uc(area=area, obs=_obs(), lineas=LineasPorPar())
    resultado = uc.execute(_dto(), _USUARIO)
    items = resultado if isinstance(resultado, list) else [resultado]
    assert [c.id_especie for c in items] == sorted(set(especies))
    assert len({c.id_calibracion_vision for c in items}) == len(set(especies))
    assert set(uc.linea_base_repo.pares) == {(2, i) for i in especies}
    assert uc.db.commits == 1
    assert len(uc.eventos_repo.eventos) == len(set(especies))
    if len(items) > 1:
        # RF-56 es agregado: valores iguales no implican identidad ni objetos compartidos.
        assert items[0].linea_base == items[1].linea_base
        assert items[0].linea_base is not items[1].linea_base
        assert items[0].linea_base['valores'] is not items[1].linea_base['valores']


def test_disparo_automatico_procesa_todas_y_audita_al_usuario_de_servicio():
    uc = _uc(area=_area(id_especies=[4, 5]), obs=_obs(), lineas=LineasPorPar())
    items = uc.execute_automatico(2, _T0 + timedelta(days=1), id_usuario_auditoria=132, motivo_disparo='nuevo lote')
    assert [c.id_especie for c in items] == [4, 5]
    assert all(c.id_usuario is None and c.origen_disparo.value == 'AUTOMATICO' for c in items)
    assert all(e['id_usuario'] == 132 for e in uc.eventos_repo.eventos)
    assert uc.db.commits == 1


def test_recalibracion_reemplaza_cada_par_y_conserva_todo_el_historial():
    uc = _uc(area=_area(id_especies=[4, 5]), obs=_obs(), lineas=LineasPorPar())
    antes = uc.execute(_dto(), _USUARIO)
    despues = uc.execute(_dto(), _USUARIO)
    assert len(consulta(uc).listar_por_area(2)) == 4
    assert [lb.id_calibracion_vision for lb in consulta(uc).obtener_linea_base_vigente(2)] == [3, 4]
    assert [c.id_calibracion_vision for c in antes] == [1, 2]
    assert [c.id_calibracion_vision for c in despues] == [3, 4]


@pytest.mark.parametrize('n', [0, 29])
def test_fallo_de_calculo_persiste_cada_intento_y_conserva_ambas_vigentes(n):
    uc = _uc(area=_area(id_especies=[4, 5]), obs=_obs(), lineas=LineasPorPar())
    uc.execute(_dto(), _USUARIO)
    anteriores = dict(uc.linea_base_repo.pares)
    uc.observacion_port.obs = _obs(n=n)
    with pytest.raises(BusinessRuleError, match='datos insuficientes') as exc:
        uc.execute(_dto(), _USUARIO)
    assert exc.value.code == 'LINEA_BASE_NO_CALCULADA'
    assert uc.linea_base_repo.pares == anteriores
    assert [c.estado for c in uc.calibracion_repo.guardadas[2:]] == [EstadoCalibracionVision.FALLIDA] * 2
    assert [e['detalle']['id_especie'] for e in uc.eventos_repo.eventos[2:]] == [4, 5]


def test_fallo_del_segundo_registro_no_confirma_el_primero():
    uc = _uc(area=_area(id_especies=[4, 5]), obs=_obs(), lineas=LineasPorPar())
    original = uc.calibracion_repo.guardar
    def guardar(cal):
        if cal.id_especie == 5:
            raise RuntimeError('segunda escritura')
        return original(cal)
    uc.calibracion_repo.guardar = guardar
    with pytest.raises(RuntimeError, match='segunda escritura'):
        uc.execute(_dto(), _USUARIO)
    assert uc.db.commits == 0 and uc.db.rollbacks == 1


def test_auditoria_del_segundo_par_falla_sin_commit_parcial():
    uc = _uc(area=_area(id_especies=[4, 5]), obs=_obs(), lineas=LineasPorPar())
    original = uc.eventos_repo.registrar
    def registrar(**kw):
        if kw['detalle']['id_especie'] == 5:
            raise RuntimeError('auditoria del segundo par')
        original(**kw)
    uc.eventos_repo.registrar = registrar
    with pytest.raises(InfrastructureError) as exc:
        uc.execute(_dto(), _USUARIO)
    assert exc.value.code == 'AUDITORIA_CALIBRACION_FALLIDA'
    assert uc.db.commits == 0 and uc.db.rollbacks == 1


def test_composicion_vacia_no_inventa_calibraciones():
    uc = _uc(area=_area(id_especies=[]), obs=_obs(), lineas=LineasPorPar())
    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(_dto(), _USUARIO)
    assert exc.value.code == 'VISION_NO_DISPONIBLE'
    assert not uc.calibracion_repo.guardadas and not uc.linea_base_repo.pares
    assert uc.eventos_repo.eventos[0]['detalle']['id_especies'] == []


def test_lectura_por_especie_no_escoge_la_primera_ni_expone_otras_areas():
    uc = _uc(area=_area(id_especies=[4, 5]), obs=_obs(), lineas=LineasPorPar())
    uc.execute(_dto(), _USUARIO)
    assert consulta(uc).obtener_linea_base_vigente(2, especie_id=5).id_especie == 5
    for kw in ({'especie_id': 999}, {'ids_fincas_permitidas': [999]}):
        with pytest.raises(NotFoundError):
            consulta(uc).obtener_linea_base_vigente(2, **kw)
    assert len(consulta(uc).obtener_linea_base_vigente(2)) == 2


def test_observaciones_y_bloqueo_de_calibracion_se_limitan_al_area():
    uc = _uc(area=_area(id_especies=[4, 5]), obs=_obs(), lineas=LineasPorPar())
    llamadas = []
    original = uc.infraestructura_repo.obtener_por_id
    def obtener(*args, **kw):
        llamadas.append(kw)
        return original(*args, **kw)
    uc.infraestructura_repo.obtener_por_id = obtener
    def listar(ids, inicio, fin, *, id_infraestructura):
        assert ids == [30] and id_infraestructura == 2
        return _obs()
    uc.observacion_port.listar = listar
    uc.execute(_dto(), _USUARIO, ids_fincas_permitidas=[1])
    assert llamadas == [{'ids_fincas_permitidas': [1]}]
    assert uc.calibracion_repo.bloqueadas == [2]


def test_router_publica_union_y_filtro_sin_cambiar_mono(monkeypatch):
    uc = _uc(area=_area(id_especies=[4, 5]), obs=_obs(), lineas=LineasPorPar())
    monkeypatch.setattr(router, 'CalibrarVisionUseCase', lambda **_: uc)
    monkeypatch.setattr(router, '_consultar', lambda _: consulta(uc))
    monkeypatch.setattr(router, '_alcance', lambda *_: [1])
    respuesta = router.calibrar_vision(_dto(), db=uc.db, usuario_actual=_USUARIO)
    assert respuesta.total == 2 and [c.especie_id for c in respuesta.items] == [4, 5]
    vigentes = router.obtener_linea_base_vision(2, especie_id=None, db=uc.db, usuario_actual=_USUARIO)
    assert vigentes.total == 2
    par = router.obtener_linea_base_vision(2, especie_id=5, db=uc.db, usuario_actual=_USUARIO)
    assert par.especie_id == 5
    uc.infraestructura_repo.area.id_especies = [4]
    mono = router.calibrar_vision(_dto(), db=uc.db, usuario_actual=_USUARIO)
    assert mono.especie_id == 4 and 'items' not in mono.model_dump()
    app = FastAPI()
    app.include_router(router.router)
    schema = app.openapi()
    post = schema['paths']['/configuracion/calibraciones-vision']['post']
    assert len(post['responses']['201']['content']['application/json']['schema']['anyOf']) == 2
    assert 'modo_calibracion' in schema['components']['schemas']['CalibrarVisionDTO']['required']
