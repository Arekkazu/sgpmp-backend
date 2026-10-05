"""RF-20 v1.1 (RFC-009): especie del área, coherencia con `tipo_modelo_asignado`,
cambio de especie con activos alojados, reactivación del área y cambio de la
familia de modelo de la especie (RF-15).

Fakes en memoria, sin DB.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.configuration.application.use_cases.especies.editar_especie_use_case import EditarEspecieUseCase
from src.configuration.application.use_cases.infraestructuras.editar_infraestructura_use_case import EditarInfraestructuraUseCase
from src.configuration.application.use_cases.infraestructuras.reactivar_infraestructura_use_case import ReactivarInfraestructuraUseCase
from src.configuration.application.use_cases.infraestructuras.registrar_infraestructura_use_case import RegistrarInfraestructuraUseCase
from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.entities.infraestructura import Infraestructura
from src.configuration.domain.value_objects.nombre_especie import NombreEspecie
from src.configuration.domain.value_objects.nombre_infraestructura import NombreInfraestructura
from src.configuration.domain.value_objects.superficie import Superficie
from src.configuration.infrastructure.dto.editar_especie_dto import EditarEspecieDTO
from src.configuration.infrastructure.dto.editar_infraestructura_dto import EditarInfraestructuraDTO
from src.configuration.infrastructure.dto.registrar_infraestructura_dto import RegistrarInfraestructuraDTO
from src.shared.errors import BusinessRuleError

USUARIO = SimpleNamespace(id_usuario=1)


def _especie(id_especie, tipo_modelo, es_activo=True, nombre="Pollo de engorde"):
    return Especie(
        id_especie=id_especie, nombre=NombreEspecie(nombre), es_activo=es_activo, tipo_modelo=tipo_modelo,
    )


ESPECIES = {
    1: _especie(1, "MODELO_AVES"),
    2: _especie(2, "MODELO_ESPECIES_GRANDES", nombre="Bovino de leche"),
    3: _especie(3, "MODELO_AVES", es_activo=False, nombre="Codorniz"),
    4: _especie(4, None, nombre="Conejo"),
}


class _Db:
    def __init__(self): self.commits = 0
    def commit(self): self.commits += 1
    def rollback(self): pass


class _EspecieRepo:
    def obtener_por_id(self, id_especie): return ESPECIES.get(id_especie)


class _InfraRepo:
    def __init__(self, infra=None): self.infra, self.guardada = infra, None
    def obtener_por_id(self, _id): return self.infra
    def guardar(self, infra):
        infra.id_infraestructura = 10
        self.guardada = infra
        return infra
    def actualizar(self, infra):
        self.guardada = infra
        return infra


class _Auditoria:
    def __init__(self): self.registros = []
    def registrar(self, **kw): self.registros.append(kw)


class _Fincas:
    def __init__(self, activa=True): self.activa = activa
    def obtener_por_id(self, _id): return SimpleNamespace(es_activo=self.activa, id_finca=1)


class _TiposArea:
    def obtener_por_nombre(self, nombre): return SimpleNamespace(nombre=nombre, es_activo=True)


class _Dependencias:
    def __init__(self, otras=(0, None)): self.otras = otras
    def contar_activos_de_otra_especie(self, _id, _especie): return self.otras


def _registrar(especie_id, tipo_modelo=None):
    infra_repo, db = _InfraRepo(), _Db()
    uc = RegistrarInfraestructuraUseCase(
        db=db, infra_repo=infra_repo, finca_repo=_Fincas(), tipo_area_repo=_TiposArea(),
        auditoria_repo=_Auditoria(), especie_repo=_EspecieRepo(),
    )
    dto = RegistrarInfraestructuraDTO(
        nombre_infraestructura="Galpón 1", tipo_area="Galpón", superficie=Decimal("120"),
        finca_id=1, especie_id=especie_id, tipo_modelo_asignado=tipo_modelo,
    )
    return uc.execute(dto, USUARIO), infra_repo, db


def _area(id_especie=1, tipo_modelo="MODELO_AVES", es_activo=True):
    return Infraestructura(
        id_infraestructura=10, nombre=NombreInfraestructura("Galpón 1"), tipo="Galpón",
        superficie=Superficie(Decimal("120")), id_finca=1, es_activo=es_activo,
        fecha_actualizacion=datetime(2026, 10, 1, tzinfo=timezone.utc),
        id_especie=id_especie, tipo_modelo_asignado=tipo_modelo,
    )


def _editar(area, especie_id, tipo_modelo, otras=(0, None)):
    infra_repo = _InfraRepo(area)
    uc = EditarInfraestructuraUseCase(
        db=_Db(), infra_repo=infra_repo, finca_repo=_Fincas(), tipo_area_repo=_TiposArea(),
        auditoria_repo=_Auditoria(), especie_repo=_EspecieRepo(), dependency_port=_Dependencias(otras),
    )
    dto = EditarInfraestructuraDTO(
        nombre_infraestructura="Galpón 1", tipo_area="Galpón", superficie=Decimal("120"),
        especie_id=especie_id, tipo_modelo_asignado=tipo_modelo, fecha_actualizacion=area.fecha_actualizacion,
    )
    return uc.execute(10, dto, USUARIO)


def test_registra_area_con_especie_y_modelo_coherente():
    infra, repo, db = _registrar(1, "MODELO_AVES")
    assert (repo.guardada.id_especie, repo.guardada.tipo_modelo_asignado) == (1, "MODELO_AVES")
    assert db.commits == 1


def test_el_modelo_es_opcional():
    infra, _, _ = _registrar(2)
    assert infra.tipo_modelo_asignado is None


@pytest.mark.parametrize("especie_id", [99, 3], ids=["inexistente", "inactiva"])
def test_especie_invalida_es_422(especie_id):
    with pytest.raises(BusinessRuleError) as e:
        _registrar(especie_id)
    assert e.value.code == "ESPECIE_INVALIDA" and e.value.status_code == 422


@pytest.mark.parametrize(
    "especie_id, tipo_modelo",
    [
        (2, "MODELO_AVES"),              # bovinos no son aves
        (1, "MODELO_RIESGO_CONTAGIO"),   # meta-modelo: nunca asignable a un área
        (4, "MODELO_AVES"),              # especie sin familia de modelo configurada
    ],
    ids=["otra-familia", "meta-modelo", "especie-sin-familia"],
)
def test_incoherencia_especie_modelo_es_422(especie_id, tipo_modelo):
    with pytest.raises(BusinessRuleError) as e:
        _registrar(especie_id, tipo_modelo)
    assert e.value.code == "INCOHERENCIA_ESPECIE_MODELO" and e.value.status_code == 422
    assert tipo_modelo in e.value.message


def test_no_cambia_especie_con_activos_de_otra_especie_alojados():
    with pytest.raises(BusinessRuleError) as e:
        _editar(_area(), 2, "MODELO_ESPECIES_GRANDES", otras=(7, "Pollo de engorde"))
    assert e.value.code == "AREA_CON_ACTIVOS_DE_OTRA_ESPECIE" and e.value.status_code == 422
    assert "7 activos" in e.value.message and "Pollo de engorde" in e.value.message


def test_cambia_especie_si_no_hay_activos_de_otra_especie():
    infra = _editar(_area(), 2, "MODELO_ESPECIES_GRANDES")
    assert (infra.id_especie, infra.tipo_modelo_asignado) == (2, "MODELO_ESPECIES_GRANDES")


def test_especie_desactivada_despues_no_bloquea_editar_el_area():
    infra = _editar(_area(id_especie=3), 3, "MODELO_AVES")
    assert infra.id_especie == 3


def test_reactivar_area_inactiva_se_audita_como_update():
    auditoria, db = _Auditoria(), _Db()
    uc = ReactivarInfraestructuraUseCase(
        db=db, infra_repo=_InfraRepo(_area(es_activo=False)), finca_repo=_Fincas(), auditoria_repo=auditoria,
    )
    infra = uc.execute(10, USUARIO)
    assert infra.es_activo and db.commits == 1
    [registro] = auditoria.registros
    assert registro["tipo_operacion"] == "UPDATE"
    assert registro["valores_anteriores"]["es_activo"] is False and registro["valores_nuevos"]["es_activo"] is True


@pytest.mark.parametrize(
    "area, finca_activa, codigo",
    [
        (_area(es_activo=True), True, "INFRAESTRUCTURA_YA_ACTIVA"),
        (_area(es_activo=False), False, "FINCA_INACTIVA_O_INEXISTENTE"),
    ],
    ids=["ya-activa", "finca-inactiva"],
)
def test_reactivar_rechazos_son_422(area, finca_activa, codigo):
    uc = ReactivarInfraestructuraUseCase(
        db=_Db(), infra_repo=_InfraRepo(area), finca_repo=_Fincas(finca_activa), auditoria_repo=_Auditoria(),
    )
    with pytest.raises(BusinessRuleError) as e:
        uc.execute(10, USUARIO)
    assert e.value.code == codigo


# ── RF-15/RF-20: cambiar la familia de la especie no puede romper la coherencia ──

class _EspecieEditable:
    def __init__(self, especie, areas_incoherentes):
        self.especie, self.areas_incoherentes, self.consultado = especie, areas_incoherentes, None
    def obtener_por_id(self, _id): return self.especie
    def obtener_por_nombre(self, _nombre): return self.especie
    def contar_areas_con_modelo_distinto(self, id_especie, tipo_modelo):
        self.consultado = (id_especie, tipo_modelo)
        return self.areas_incoherentes
    def actualizar(self, especie): return especie


def _editar_familia(areas_incoherentes, **cambio):
    especie = _especie(1, "MODELO_AVES")
    especie.fecha_actualizacion = datetime(2026, 10, 1, tzinfo=timezone.utc)
    repo = _EspecieEditable(especie, areas_incoherentes)
    uc = EditarEspecieUseCase(_Db(), repo, _Auditoria())
    dto = EditarEspecieDTO(nombre="Pollo de engorde", fecha_actualizacion=especie.fecha_actualizacion, **cambio)
    return uc.execute(1, dto, USUARIO), repo


@pytest.mark.parametrize("nueva_familia", ["MODELO_PORCINOS", None])
def test_no_cambia_la_familia_si_deja_areas_con_modelo_incoherente(nueva_familia):
    with pytest.raises(BusinessRuleError) as e:
        _editar_familia(2, tipo_modelo=nueva_familia)
    assert e.value.code == "ESPECIE_CON_AREAS_DE_OTRO_MODELO" and e.value.status_code == 422
    assert "2 áreas" in e.value.message


def test_cambia_la_familia_si_ninguna_area_queda_incoherente():
    especie, repo = _editar_familia(0, tipo_modelo="MODELO_PORCINOS")
    assert especie.tipo_modelo == "MODELO_PORCINOS" and repo.consultado == (1, "MODELO_PORCINOS")


def test_editar_sin_tocar_la_familia_no_revisa_areas():
    especie, repo = _editar_familia(5)
    assert especie.tipo_modelo == "MODELO_AVES" and repo.consultado is None
