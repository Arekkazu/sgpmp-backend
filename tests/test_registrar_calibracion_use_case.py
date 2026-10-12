"""Tests del use case de calibración (RF-24): rango, auditoría→500, no-numérico→400,
y auditoría FALLIDO de cada intento rechazado (RF-24 v1.1, RFC-006).

Fakes en memoria, sin DB ni framework. Ejecutable con `pytest` o `python -m`.
"""
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from src.configuration.application.use_cases.sensores.registrar_calibracion_use_case import (
    ConsultarCalibracionesUseCase,
    RegistrarCalibracionUseCase,
)
from src.configuration.domain.entities.rango_calibracion import RangoCalibracion
from src.configuration.infrastructure.dto.registrar_calibracion_dto import RegistrarCalibracionDTO
from src.configuration.infrastructure.schema.calibracion_schema import CalibracionResponse
from src.shared.errors import AuthorizationError, BusinessRuleError, InfrastructureError, NotFoundError, ValidationError


class _Db:
    def __init__(self): self.committed = self.rolledback = False
    def commit(self): self.committed = True
    def rollback(self): self.rolledback = True


class _Repo:  # sensor / dispositivo / sensor_area / rango
    def __init__(self, **kw): self.__dict__.update(kw)
    def obtener_por_id(self, _, ids_fincas_permitidas=None):
        # Alcance por finca (#503): el fake filtra como el repo real con el JOIN a infraestructuras.
        if ids_fincas_permitidas is not None and getattr(self.obj, "id_finca", None) not in ids_fincas_permitidas:
            return None
        return self.obj
    def obtener_asociacion_activa(self, _): return self.obj
    def obtener_por_categoria(self, _): return self.obj


class _CalRepo:
    def guardar(self, cal):
        cal.id_calibracion = 99
        return cal


class _AuditoriaOk:
    def __init__(self): self.calls = 0
    def registrar(self, **kw): self.calls += 1


class _AuditoriaRota:
    def registrar(self, **kw): raise RuntimeError("fallo escribiendo auditoría")


class _Eventos:  # modulo1.eventos (RF-10)
    def __init__(self, roto=False): self.eventos, self.roto = [], roto
    def registrar(self, **kw):
        if self.roto:
            raise RuntimeError("BD caída")
        self.eventos.append(kw)


_SENSOR = SimpleNamespace(id_dispositivo_iot=1, categoria="TEMPERATURA")
_DISPOSITIVO = SimpleNamespace(es_activo=True, id_finca=1)
_ASOCIACION = SimpleNamespace(id_infraestructura=1)


def _uc(db, auditoria, eventos=None, sensor=_SENSOR, dispositivo=_DISPOSITIVO, asociacion=_ASOCIACION):
    return RegistrarCalibracionUseCase(
        db=db,
        sensor_repo=_Repo(obj=sensor),
        dispositivo_repo=_Repo(obj=dispositivo),
        sensor_area_repo=_Repo(obj=asociacion),
        calibracion_repo=_CalRepo(),
        rango_repo=_Repo(obj=RangoCalibracion("TEMPERATURA", Decimal("0"), Decimal("45"))),
        auditoria_repo=auditoria,
        eventos_repo=eventos if eventos is not None else _Eventos(),
    )


def _dto(valor):
    return RegistrarCalibracionDTO(
        id_dispositivo_iot=1, id_infraestructura=1, valor_referencia=valor,
        fecha_calibracion=datetime.now(timezone.utc),
        modo_calibracion="SENSOR",
    )


_USUARIO = SimpleNamespace(id_usuario=1)


def test_happy_path_escribe_auditoria():
    db, aud, eventos = _Db(), _AuditoriaOk(), _Eventos()
    cal = _uc(db, aud, eventos).execute(1, _dto(Decimal("25")), _USUARIO)
    assert aud.calls == 1 and db.committed and cal.offset == Decimal("25")
    [evento] = eventos.eventos
    assert evento["tipo_evento"] == 30 and evento["exitoso"] is True
    assert evento["detalle"]["id_calibracion"] == 99
    assert evento["detalle"]["valor_referencia"] == "25"


def test_fallo_auditoria_rollback_500():
    db = _Db()
    try:
        _uc(db, _AuditoriaRota()).execute(1, _dto(Decimal("25")), _USUARIO)
        assert False, "debió lanzar InfrastructureError"
    except InfrastructureError as e:
        assert e.code == "AUDITORIA_CALIBRACION_FALLIDA" and e.status_code == 500
    assert db.rolledback and not db.committed


def test_no_numerico_devuelve_400():
    for bad in ("abc", "", None):
        try:
            _uc(_Db(), _AuditoriaOk()).execute(1, _dto(bad), _USUARIO)
            assert False, f"debió rechazar {bad!r}"
        except ValidationError as e:
            assert e.code == "VALOR_CALIBRACION_INVALIDO" and e.status_code == 400


def test_no_finitos_son_formato_invalido_400():
    # INC-M09-75-G132 (#511): NaN daba 500 e Infinity/-Infinity "fuera de rango".
    for bad in ("NaN", "Infinity", "-Infinity"):
        db = _Db()
        try:
            _uc(db, _AuditoriaOk()).execute(1, _dto(bad), _USUARIO)
            assert False, f"debió rechazar {bad!r}"
        except ValidationError as e:
            assert e.code == "VALOR_CALIBRACION_INVALIDO" and e.status_code == 400
            assert e.message == (
                "Error de formato: El valor de referencia debe ser un número decimal "
                f"válido. Verifique la entrada '{bad}'."
            )


def test_literales_json_no_finitos_llegan_como_texto_al_use_case():
    import json
    for literal, esperado in (("NaN", "NaN"), ("Infinity", "Infinity"), ("-Infinity", "-Infinity")):
        cuerpo = json.loads(
            '{"id_dispositivo_iot":1,"id_infraestructura":1,'
            '"fecha_calibracion":"2026-10-07T00:00:00Z","modo_calibracion":"SENSOR","valor_referencia":' + literal + "}"
        )
        assert RegistrarCalibracionDTO.model_validate(cuerpo).valor_referencia == esperado


def test_decimal_finito_conserva_precision():
    cal = _uc(_Db(), _AuditoriaOk()).execute(1, _dto(Decimal("22.1234")), _USUARIO)
    assert cal.valor_referencia == Decimal("22.1234")


def test_fuera_de_rango_devuelve_400():
    try:
        _uc(_Db(), _AuditoriaOk()).execute(1, _dto(Decimal("500")), _USUARIO)
        assert False, "debió rechazar 500 °C"
    except ValidationError as e:
        assert e.code == "VALOR_FUERA_DE_RANGO" and e.status_code == 400


# ── RFC-006: cada rechazo queda auditado con resultado FALLIDO ────────────────

_RECHAZOS = (
    # (overrides del use case, valor, error esperado, código)
    ({"dispositivo": None}, Decimal("25"), NotFoundError, "DISPOSITIVO_NO_ENCONTRADO"),
    ({"dispositivo": SimpleNamespace(es_activo=False, id_finca=1, serial=SimpleNamespace(valor="IOT-INACT"))}, Decimal("25"), BusinessRuleError, "DISPOSITIVO_INACTIVO"),
    ({"sensor": None}, Decimal("25"), NotFoundError, "SENSOR_NO_ENCONTRADO"),
    ({"asociacion": SimpleNamespace(id_infraestructura=7)}, Decimal("25"), ValidationError, "SENSOR_AREA_INVALIDA"),
    ({}, "abc", ValidationError, "VALOR_CALIBRACION_INVALIDO"),
    ({}, Decimal("500"), ValidationError, "VALOR_FUERA_DE_RANGO"),
)


def test_cada_rechazo_queda_auditado_como_fallido():
    for overrides, valor, error, codigo in _RECHAZOS:
        db, eventos = _Db(), _Eventos()
        try:
            _uc(db, _AuditoriaOk(), eventos, **overrides).execute(1, _dto(valor), _USUARIO)
            assert False, f"debió rechazar con {codigo}"
        except error as e:
            assert e.code == codigo
        [evento] = eventos.eventos
        assert evento["tipo_evento"] == 29 and evento["exitoso"] is False
        assert evento["modulo"] == "MODULO9" and evento["id_usuario"] == 1
        assert evento["detalle"]["codigo_error"] == codigo
        assert evento["detalle"]["codigo_http"] == error.status_code
        assert evento["detalle"]["id_sensor"] == 1
        assert db.committed  # el evento se confirma aunque la operación se rechace


def test_si_la_auditoria_del_rechazo_falla_conserva_el_4xx():
    db = _Db()
    try:
        _uc(db, _AuditoriaOk(), _Eventos(roto=True), sensor=None).execute(1, _dto(Decimal("25")), _USUARIO)
        assert False, "debió lanzar NotFoundError"
    except NotFoundError as e:
        assert e.status_code == 404  # no se convierte en 500
    assert db.rolledback


def test_mensajes_de_rechazo_rf24_con_auditoria_caida():
    # INC-M09-76-G136 (#512): con el INSERT a modulo1.eventos fallando (best-effort),
    # el rechazo conserva su HTTP y el texto exacto de RF-24 v2.0.
    inactivo = SimpleNamespace(es_activo=False, id_finca=1, serial=SimpleNamespace(valor="IOT-G136-LAB-INACT"))
    casos = (
        ({}, Decimal("45.0001"), 400, "VALOR_FUERA_DE_RANGO",
         "Valor fuera de límites: El ajuste de 45.0001 excede los rangos de seguridad para la "
         "variable TEMPERATURA. Verifique el estándar de calibración utilizado."),
        ({"dispositivo": inactivo}, Decimal("22.5000"), 422, "DISPOSITIVO_INACTIVO",
         "Operación rechazada: El dispositivo IOT-G136-LAB-INACT está inactivo. Debe activar el "
         "dispositivo antes de proceder con el registro de nuevos parámetros de calibración."),
    )
    for overrides, valor, http, codigo, mensaje in casos:
        db = _Db()
        try:
            _uc(db, _AuditoriaOk(), _Eventos(roto=True), **overrides).execute(1, _dto(valor), _USUARIO)
            assert False, f"debió rechazar con {codigo}"
        except (ValidationError, BusinessRuleError) as e:
            assert (e.status_code, e.code, e.message) == (http, codigo, mensaje)
        assert db.rolledback and not db.committed


def test_403_del_router_queda_auditado():
    import src.shared.rbac as rbac
    from src.configuration.infrastructure.routers import sensor_router

    eventos = _Eventos()
    originales = rbac.tiene_permiso, sensor_router.SqlAlchemyEventoRepository
    rbac.tiene_permiso = lambda *a, **k: False
    sensor_router.SqlAlchemyEventoRepository = lambda db: eventos
    try:
        usuario = SimpleNamespace(id_usuario=5, id_rol=2, id_estado_cuenta=2)  # Cuenta.ESTADO_ACTIVO
        try:
            sensor_router._permiso_calibrar_auditado(id_sensor=3, db=_Db(), usuario_actual=usuario)
            assert False, "debió lanzar 403"
        except AuthorizationError as e:
            assert e.code == "ACCESO_DENEGADO"
    finally:
        rbac.tiene_permiso, sensor_router.SqlAlchemyEventoRepository = originales
    [evento] = eventos.eventos
    assert evento["exitoso"] is False and evento["detalle"]["codigo_http"] == 403
    assert evento["id_usuario"] == 5 and evento["detalle"]["id_sensor"] == 3



def test_modo_calibracion_se_valida_y_se_traza():
    """TC-M09-141 (#503): modo_calibracion ya no se descarta en silencio."""
    import pydantic

    cal = _uc(_Db(), _AuditoriaOk()).execute(1, _dto(Decimal("25")), _USUARIO)
    assert cal.modo_calibracion == "SENSOR"  # modalidad enviada explícitamente
    assert cal._snapshot()["modo_calibracion"] == "SENSOR"
    assert CalibracionResponse.from_entity(cal).model_dump(mode="json")["modo_calibracion"] == "SENSOR"

    base = dict(id_dispositivo_iot=1, id_infraestructura=1, valor_referencia=Decimal("25"),
                fecha_calibracion=datetime.now(timezone.utc))
    assert RegistrarCalibracionDTO(**base, modo_calibracion="SENSOR").modo_calibracion == "SENSOR"
    for malo in ("VISION", "cualquiera", ""):
        try:
            RegistrarCalibracionDTO(**base, modo_calibracion=malo)
            assert False, f"debió rechazar {malo!r}"
        except pydantic.ValidationError:
            pass



def test_sensor_de_finca_ajena_responde_404_y_queda_auditado():
    """TC-M09-141 (#503, observación secundaria): el Ingeniero no veía el
    dispositivo (finca fuera de su alcance) pero sí podía calibrar su sensor."""
    db, eventos = _Db(), _Eventos()
    try:
        _uc(db, _AuditoriaOk(), eventos).execute(1, _dto(Decimal("25")), _USUARIO, ids_fincas_permitidas=[65, 85])
        assert False, "debió rechazar un dispositivo de una finca ajena"
    except NotFoundError as e:
        assert e.code == "DISPOSITIVO_NO_ENCONTRADO" and e.status_code == 404
    [evento] = eventos.eventos
    assert evento["detalle"]["codigo_http"] == 404
    # Dentro del alcance (o rol global, None) la calibración procede igual que antes.
    assert _uc(_Db(), _AuditoriaOk()).execute(1, _dto(Decimal("25")), _USUARIO, ids_fincas_permitidas=[1]).id_calibracion == 99


def test_historial_de_calibraciones_respeta_alcance():
    class _Historial:
        def listar_por_sensor(self, _): return ["cal"]

    def consultar(ids, sensor=_SENSOR):
        return ConsultarCalibracionesUseCase(
            db=_Db(), calibracion_repo=_Historial(),
            sensor_repo=_Repo(obj=sensor), dispositivo_repo=_Repo(obj=_DISPOSITIVO),
        ).listar_por_sensor(1, ids_fincas_permitidas=ids)

    assert consultar(None) == ["cal"] and consultar([1]) == ["cal"]
    for ids, sensor in (([65], _SENSOR), ([1], None)):
        try:
            consultar(ids, sensor)
            assert False, "debió responder 404"
        except NotFoundError as e:
            assert e.code == "SENSOR_NO_ENCONTRADO"


if __name__ == "__main__":
    test_happy_path_escribe_auditoria()
    test_fallo_auditoria_rollback_500()
    test_no_numerico_devuelve_400()
    test_fuera_de_rango_devuelve_400()
    test_cada_rechazo_queda_auditado_como_fallido()
    test_si_la_auditoria_del_rechazo_falla_conserva_el_4xx()
    test_403_del_router_queda_auditado()
    test_modo_calibracion_se_valida_y_se_traza()
    test_sensor_de_finca_ajena_responde_404_y_queda_auditado()
    test_historial_de_calibraciones_respeta_alcance()
    print("OK")
