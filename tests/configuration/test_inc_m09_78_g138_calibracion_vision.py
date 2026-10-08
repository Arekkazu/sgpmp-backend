"""INC-M09-78-G138 (#514): RF-24 v2.0, modalidad VISION (línea base por área y especie).

QA no encontraba ninguna operación VISION publicada. Estos tests cubren:
- las cuatro precondiciones negativas de G138 (TC-M09-278..281) → 422 con el
  mensaje de la ficha, sin línea base nueva y auditadas como FALLIDO;
- el cálculo de las tres etapas (filtrado → recorte p5/p95 → refinamiento);
- el camino exitoso (reemplaza la línea base vigente) y el fallido (la conserva);
- el contrato publicado (DTO, OpenAPI y 403 auditado).

Fakes en memoria, sin DB ni framework.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pydantic
import pytest

from src.configuration.application.use_cases.sensores.calibrar_vision_use_case import (
    CalibrarVisionUseCase,
    ConsultarCalibracionVisionUseCase,
)
from src.configuration.domain.entities.linea_base_vision import (
    ParametrosLineaBase,
    calcular_linea_base,
    percentil,
)
from src.configuration.domain.entities.observacion_vision import ObservacionVision
from src.configuration.domain.value_objects.calibracion_vision import (
    EstadoCalibracionVision,
    EtapaCalibracionVision,
)
from src.configuration.infrastructure.dto.calibrar_vision_dto import CalibrarVisionDTO
from src.configuration.infrastructure.dto.registrar_calibracion_dto import RegistrarCalibracionDTO
from src.shared.errors import AuthorizationError, BusinessRuleError, InfrastructureError, NotFoundError

_T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)
_USUARIO = SimpleNamespace(id_usuario=7)


# ── Fakes ─────────────────────────────────────────────────────────────────────

class _Db:
    def __init__(self): self.commits = self.rollbacks = 0
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


class _Areas:
    def __init__(self, area): self.area = area
    def obtener_por_id(self, id_area, ids_fincas_permitidas=None, **_):
        if self.area is None or self.area.id_infraestructura != id_area:
            return None
        if ids_fincas_permitidas is not None and self.area.id_finca not in ids_fincas_permitidas:
            return None
        return self.area


class _Camaras:
    def __init__(self, camaras): self.camaras = camaras
    def listar_por_area(self, _): return self.camaras


class _Observaciones:
    def __init__(self, obs): self.obs, self.pedidas = obs, None
    def listar(self, ids, inicio, fin):
        self.pedidas = ids
        return self.obs


class _Calibraciones:
    def __init__(self): self.guardadas = []
    def guardar(self, cal):
        cal.id_calibracion_vision = len(self.guardadas) + 1
        self.guardadas.append(cal)
        return cal
    def listar_por_area(self, id_area): return [c for c in self.guardadas if c.id_infraestructura == id_area]


class _LineasBase:
    def __init__(self, vigente=None): self.vigente = vigente
    def obtener_vigente(self, id_area, id_especie):
        v = self.vigente
        return v if v and (v.id_infraestructura, v.id_especie) == (id_area, id_especie) else None
    def publicar(self, lb):
        self.vigente = lb
        return lb


class _Eventos:
    def __init__(self, roto=False): self.eventos, self.roto = [], roto
    def registrar(self, **kw):
        if self.roto:
            raise RuntimeError("permission denied for table eventos")
        self.eventos.append(kw)


def _area(**kw):
    base = dict(id_infraestructura=2, id_finca=1, id_especie=4, tipo_modelo_asignado="MODELO_AVES", es_activo=True)
    return SimpleNamespace(**{**base, **kw})


def _camara(activa=True, id_=30):
    return SimpleNamespace(id_dispositivo_iot=id_, es_activo=activa)


def _obs(n=60, apto=True, desplazamiento=0.0):
    # Valores distintos y repartidos para que el recorte p5/p95 tenga datos.
    return [
        ObservacionVision(
            id_dispositivo_iot=30,
            fecha_observacion=_T0 + timedelta(minutes=i),
            es_apto_para_ia=apto,
            cobertura_ventana=0.9,
            n_tracks=5,
            componentes={
                "densidad_actividad": 10 + (i % 20) * 0.1 + desplazamiento,
                "tasa_movimiento": 3 + (i % 15) * 0.05,
            },
        )
        for i in range(n)
    ]


def _dto(area_id=2, **kw):
    return CalibrarVisionDTO(
        modo_calibracion="VISION",
        area_id=area_id,
        ventana_observacion={"inicio": _T0, "fin": _T0 + timedelta(days=1)},
        **kw,
    )


def _uc(area=None, camaras=None, obs=None, eventos=None, lineas=None, calibraciones=None, db=None):
    return CalibrarVisionUseCase(
        db=db or _Db(),
        infraestructura_repo=_Areas(area if area is not None else _area()),
        camara_repo=_Camaras(camaras if camaras is not None else [_camara()]),
        observacion_port=_Observaciones(obs if obs is not None else []),
        calibracion_repo=calibraciones or _Calibraciones(),
        linea_base_repo=lineas or _LineasBase(),
        eventos_repo=eventos if eventos is not None else _Eventos(),
    )


def _mensaje_no_disponible(id_area):
    return (
        f"Calibración por visión no disponible: El área {id_area} no cuenta con observaciones "
        "de cámara aptas o no tiene un modelo poblacional asignado. Verifique las cámaras "
        "(RF-21/22) y la configuración del área (RF-20)."
    )


# ── G138: precondiciones negativas (TC-M09-278..281) ──────────────────────────

@pytest.mark.parametrize(
    "caso, area, camaras",
    [
        # TC-M09-291 (G143-01, #515) es el mismo escenario: AVES / MODELO_AVES sin cámaras.
        ("TC-M09-278 / TC-M09-291 área sin cámara", _area(), []),
        ("TC-M09-279 única cámara inactiva", _area(), [_camara(activa=False)]),
        ("TC-M09-280 paradigma INDIVIDUAL", _area(tipo_modelo_asignado="MODELO_ESPECIES_GRANDES"), [_camara()]),
        ("TC-M09-281 sin tipo_modelo_asignado", _area(tipo_modelo_asignado=None), [_camara()]),
        ("área sin especie", _area(id_especie=None), [_camara()]),
    ],
)
def test_precondicion_vision_incumplida_responde_422_sin_linea_base(caso, area, camaras):
    calibraciones, eventos, db = _Calibraciones(), _Eventos(), _Db()
    lineas = _LineasBase()
    with pytest.raises(BusinessRuleError) as exc:
        _uc(area=area, camaras=camaras, obs=_obs(), eventos=eventos, lineas=lineas,
            calibraciones=calibraciones, db=db).execute(_dto(), _USUARIO)
    e = exc.value
    assert (e.status_code, e.code, e.message) == (422, "VISION_NO_DISPONIBLE", _mensaje_no_disponible(2)), caso
    assert calibraciones.guardadas == [] and lineas.vigente is None
    [evento] = eventos.eventos
    assert evento["tipo_evento"] == 29 and evento["exitoso"] is False and evento["modulo"] == "MODULO9"
    assert evento["detalle"]["operacion"] == "CALIBRACION_VISION"
    assert evento["detalle"]["codigo_error"] == "VISION_NO_DISPONIBLE"
    assert evento["detalle"]["id_infraestructura"] == 2
    assert evento["id_usuario"] == _USUARIO.id_usuario  # el Ingeniero que disparó el cálculo


def test_observaciones_ninguna_apta_es_vision_no_disponible():
    with pytest.raises(BusinessRuleError) as exc:
        _uc(obs=_obs(apto=False)).execute(_dto(), _USUARIO)
    assert exc.value.code == "VISION_NO_DISPONIBLE"


def test_precondicion_con_auditoria_caida_conserva_el_422():
    db = _Db()
    with pytest.raises(BusinessRuleError) as exc:
        _uc(camaras=[], eventos=_Eventos(roto=True), db=db).execute(_dto(), _USUARIO)
    assert exc.value.status_code == 422 and db.rollbacks == 1


def test_area_inexistente_o_de_finca_ajena_responde_404():
    for area_id, alcance in ((99, None), (2, [5])):
        eventos = _Eventos()
        with pytest.raises(NotFoundError) as exc:
            _uc(eventos=eventos).execute(_dto(area_id=area_id), _USUARIO, ids_fincas_permitidas=alcance)
        assert exc.value.code == "AREA_NO_ENCONTRADA"
        assert eventos.eventos[0]["detalle"]["codigo_http"] == 404


def test_solo_se_consultan_las_camaras_activas():
    obs = _Observaciones(_obs())
    uc = _uc(camaras=[_camara(activa=False, id_=30), _camara(id_=31)])
    uc.observacion_port = obs
    uc.execute(_dto(), _USUARIO)
    assert obs.pedidas == [31]


# ── Fallo de etapa: se registra FALLIDA y se conserva la línea base ───────────

def test_sin_observaciones_queda_fallida_en_filtrado_y_conserva_la_vigente():
    # Es lo que pasa hoy en TEST: el stub de M03 no devuelve observaciones.
    vigente = SimpleNamespace(id_infraestructura=2, id_especie=4, id_calibracion_vision=1)
    lineas, calibraciones, eventos, db = _LineasBase(vigente), _Calibraciones(), _Eventos(), _Db()
    with pytest.raises(BusinessRuleError) as exc:
        _uc(obs=[], lineas=lineas, calibraciones=calibraciones, eventos=eventos, db=db).execute(_dto(), _USUARIO)
    e = exc.value
    assert (e.status_code, e.code) == (422, "LINEA_BASE_NO_CALCULADA")
    assert e.message == (
        "No se pudo calcular la línea base: datos insuficientes o sin convergencia para el "
        "área 2 y especie 4. Se conserva la línea base vigente anterior."
    )
    [cal] = calibraciones.guardadas
    assert cal.estado == EstadoCalibracionVision.FALLIDA
    assert cal.etapa_fallo == EtapaCalibracionVision.FILTRADO and cal.linea_base is None
    assert lineas.vigente is vigente  # la anterior no se toca
    assert db.commits >= 1            # el intento fallido sí queda guardado
    [evento] = eventos.eventos
    assert evento["detalle"]["etapa_fallo"] == "FILTRADO"
    assert evento["detalle"]["id_calibracion_vision"] == cal.id_calibracion_vision


# ── Camino exitoso ────────────────────────────────────────────────────────────

def test_calculo_exitoso_publica_y_reemplaza_la_linea_base():
    anterior = SimpleNamespace(id_infraestructura=2, id_especie=4, id_calibracion_vision=1)
    lineas, eventos, db = _LineasBase(anterior), _Eventos(), _Db()
    cal = _uc(obs=_obs(), lineas=lineas, eventos=eventos, db=db).execute(_dto(observaciones="nuevo lote"), _USUARIO)
    assert cal.estado == EstadoCalibracionVision.EXITOSA and cal.id_usuario == 7
    assert set(cal.linea_base["valores"]) == {"densidad_actividad", "tasa_movimiento"}
    assert lineas.vigente is not anterior and lineas.vigente.id_calibracion_vision == cal.id_calibracion_vision
    assert db.commits == 1 and db.rollbacks == 0
    [evento] = eventos.eventos
    assert evento["tipo_evento"] == 30 and evento["exitoso"] is True


def test_fallo_de_auditoria_en_el_exito_hace_rollback_y_500():
    db = _Db()
    with pytest.raises(InfrastructureError) as exc:
        _uc(obs=_obs(), eventos=_Eventos(roto=True), db=db).execute(_dto(), _USUARIO)
    assert exc.value.code == "AUDITORIA_CALIBRACION_FALLIDA" and exc.value.status_code == 500
    assert db.rollbacks == 1 and db.commits == 0


# ── Las tres etapas ───────────────────────────────────────────────────────────

def test_percentil_interpola_como_numpy():
    assert percentil([1, 2, 3, 4], 50) == 2.5
    assert percentil(list(range(101)), 5) == 5.0


def test_etapa_1_descarta_no_aptas_y_cobertura_insuficiente():
    obs = _obs(n=40) + _obs(n=40, apto=False)
    r = calcular_linea_base(obs, ParametrosLineaBase(min_observaciones=50))
    assert r.etapa_fallo == EtapaCalibracionVision.FILTRADO and r.n_observaciones_validas == 40


def test_etapa_2_aborta_si_la_mayoria_de_componentes_queda_sin_datos():
    r = calcular_linea_base(_obs(), ParametrosLineaBase(min_datos_componente=500))
    assert r.etapa_fallo == EtapaCalibracionVision.RECORTE
    assert r.componentes_no_calibrables == ["densidad_actividad", "tasa_movimiento"]


def test_etapa_3_sin_convergencia_queda_no_convergida():
    # ε = 0 es inalcanzable mientras el recorte siga moviendo la mediana.
    obs = [
        ObservacionVision(30, _T0, True, 0.9, 5, {"densidad_actividad": float(i ** 2)})
        for i in range(200)
    ]
    r = calcular_linea_base(obs, ParametrosLineaBase(epsilon=0.0, max_iteraciones=3))
    assert r.estado == EstadoCalibracionVision.NO_CONVERGIDA
    assert r.etapa_fallo == EtapaCalibracionVision.REFINAMIENTO and r.iteraciones == 3


def test_linea_base_es_la_mediana_por_componente():
    r = calcular_linea_base(_obs(), ParametrosLineaBase())
    assert r.es_exitosa
    assert r.valores["densidad_actividad"] == pytest.approx(10.95, abs=0.1)


# ── Consultas ─────────────────────────────────────────────────────────────────

def test_consulta_linea_base_vigente_y_404_sin_ella():
    vigente = SimpleNamespace(id_infraestructura=2, id_especie=4, id_calibracion_vision=1)
    uc = ConsultarCalibracionVisionUseCase(_Areas(_area()), _Calibraciones(), _LineasBase(vigente))
    assert uc.obtener_linea_base_vigente(2) is vigente
    uc = ConsultarCalibracionVisionUseCase(_Areas(_area()), _Calibraciones(), _LineasBase())
    with pytest.raises(NotFoundError) as exc:
        uc.obtener_linea_base_vigente(2)
    assert exc.value.code == "LINEA_BASE_NO_ENCONTRADA"


# ── Contrato ──────────────────────────────────────────────────────────────────

def test_dto_vision_exige_modo_vision_y_ventana_valida():
    base = dict(area_id=2, ventana_observacion={"inicio": _T0, "fin": _T0 + timedelta(hours=1)})
    assert CalibrarVisionDTO(modo_calibracion="VISION", **base).modo_calibracion == "VISION"
    for malo in (dict(base), dict(base, modo_calibracion="SENSOR")):
        with pytest.raises(pydantic.ValidationError):
            CalibrarVisionDTO(**malo)
    with pytest.raises(pydantic.ValidationError):
        CalibrarVisionDTO(modo_calibracion="VISION", area_id=2,
                          ventana_observacion={"inicio": _T0, "fin": _T0})


def test_el_endpoint_sensor_sigue_sin_aceptar_vision():
    with pytest.raises(pydantic.ValidationError):
        RegistrarCalibracionDTO(id_dispositivo_iot=1, id_infraestructura=1, valor_referencia="25",
                                fecha_calibracion=_T0, modo_calibracion="VISION")


def test_403_del_router_vision_usa_el_mensaje_de_la_ficha_y_queda_auditado():
    import src.shared.rbac as rbac
    from src.configuration.infrastructure.routers import calibracion_vision_router as router

    eventos = _Eventos()
    originales = rbac.tiene_permiso, router.SqlAlchemyEventoRepository
    rbac.tiene_permiso = lambda *a, **k: False
    router.SqlAlchemyEventoRepository = lambda db: eventos
    try:
        usuario = SimpleNamespace(id_usuario=5, id_rol=2, id_estado_cuenta=2)  # Cuenta.ESTADO_ACTIVO
        with pytest.raises(AuthorizationError) as exc:
            router._permiso_calibrar_auditado(db=_Db(), usuario_actual=usuario)
    finally:
        rbac.tiene_permiso, router.SqlAlchemyEventoRepository = originales
    assert exc.value.message == (
        "Acceso denegado: La calibración de sensores es una función crítica restringida "
        "exclusivamente al Ingeniero de Campo o al Administrador."
    )
    [evento] = eventos.eventos
    assert evento["detalle"]["codigo_http"] == 403 and evento["id_usuario"] == 5
