"""Tests del use case de calibración (RF-24): rango, auditoría→500, no-numérico→400.

Fakes en memoria, sin DB ni framework. Ejecutable con `pytest` o `python -m`.
"""
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from src.configuration.application.use_cases.sensores.registrar_calibracion_use_case import RegistrarCalibracionUseCase
from src.configuration.domain.entities.rango_calibracion import RangoCalibracion
from src.configuration.infrastructure.dto.registrar_calibracion_dto import RegistrarCalibracionDTO
from src.shared.errors import InfrastructureError, ValidationError


class _Db:
    def __init__(self): self.committed = self.rolledback = False
    def commit(self): self.committed = True
    def rollback(self): self.rolledback = True


class _Repo:  # sensor / dispositivo / sensor_area / rango
    def __init__(self, **kw): self.__dict__.update(kw)
    def obtener_por_id(self, _): return self.obj
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


def _uc(db, auditoria):
    sensor = SimpleNamespace(id_dispositivo_iot=1, categoria="TEMPERATURA")
    return RegistrarCalibracionUseCase(
        db=db,
        sensor_repo=_Repo(obj=sensor),
        dispositivo_repo=_Repo(obj=SimpleNamespace(es_activo=True)),
        sensor_area_repo=_Repo(obj=SimpleNamespace(id_infraestructura=1)),
        calibracion_repo=_CalRepo(),
        rango_repo=_Repo(obj=RangoCalibracion("TEMPERATURA", Decimal("0"), Decimal("45"))),
        auditoria_repo=auditoria,
    )


def _dto(valor):
    return RegistrarCalibracionDTO(
        id_dispositivo_iot=1, id_infraestructura=1, valor_referencia=valor,
        fecha_calibracion=datetime.now(timezone.utc),
    )


_USUARIO = SimpleNamespace(id_usuario=1)


def test_happy_path_escribe_auditoria():
    db, aud = _Db(), _AuditoriaOk()
    cal = _uc(db, aud).execute(1, _dto(Decimal("25")), _USUARIO)
    assert aud.calls == 1 and db.committed and cal.offset == Decimal("25")


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


def test_fuera_de_rango_devuelve_400():
    try:
        _uc(_Db(), _AuditoriaOk()).execute(1, _dto(Decimal("500")), _USUARIO)
        assert False, "debió rechazar 500 °C"
    except ValidationError as e:
        assert e.code == "VALOR_FUERA_DE_RANGO" and e.status_code == 400


if __name__ == "__main__":
    test_happy_path_escribe_auditoria()
    test_fallo_auditoria_rollback_500()
    test_no_numerico_devuelve_400()
    test_fuera_de_rango_devuelve_400()
    print("OK")
