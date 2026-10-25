# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-22 RF-20: multiespecie, capacidad por densidad y los 4 flujos 422 (RFC-012) |
"""DEV-22 (RFC-012 v1.1, RF-20): un área aloja 1..N especies del mismo grupo de manejo
y su capacidad es floor(MIN densidad ind/m² × superficie). Fakes en memoria, sin DB."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.configuration.application.use_cases.infraestructuras.editar_infraestructura_use_case import EditarInfraestructuraUseCase
from src.configuration.application.use_cases.infraestructuras.registrar_infraestructura_use_case import RegistrarInfraestructuraUseCase
from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.entities.infraestructura import Infraestructura
from src.configuration.domain.services.capacidad_area import EspecieDelArea, capacidad_efectiva
from src.configuration.domain.value_objects.nombre_especie import NombreEspecie
from src.configuration.domain.value_objects.nombre_infraestructura import NombreInfraestructura
from src.configuration.domain.value_objects.superficie import Superficie
from src.configuration.infrastructure.dto.editar_infraestructura_dto import EditarInfraestructuraDTO
from src.configuration.infrastructure.dto.registrar_infraestructura_dto import RegistrarInfraestructuraDTO
from src.shared.errors import BusinessRuleError

USUARIO = SimpleNamespace(id_usuario=1)
TS = datetime(2026, 10, 1, tzinfo=timezone.utc)


def _esp(id_, nombre, grupo, densidad):
    return Especie(id_especie=id_, nombre=NombreEspecie(nombre), es_activo=True, grupo_manejo=grupo,
                   densidad_maxima_por_especie=None if densidad is None else Decimal(densidad))


ESPECIES = {
    1: _esp(1, "Mojarra", "ACUICULTURA", "100"),
    2: _esp(2, "Cachama", "ACUICULTURA", "100"),
    3: _esp(3, "Salmon", "ACUICULTURA", "80"),
    4: _esp(4, "Tilapia", "ACUICULTURA", None),
    5: _esp(5, "Pollo", "AVES", "10"),
}


class _Db:
    def __init__(self): self.commits = 0
    def commit(self): self.commits += 1
    def rollback(self): pass


class _EspecieRepo:
    def obtener_por_id(self, id_, **_): return ESPECIES.get(id_)


class _InfraRepo:
    def __init__(self, infra=None): self.infra, self.guardada = infra, None
    def obtener_por_id(self, _id, **_): return self.infra
    def guardar(self, infra):
        infra.id_infraestructura = 10
        self.guardada = infra
        return infra
    def actualizar(self, infra):
        self.guardada = infra
        return infra


class _Nada:
    def registrar(self, **_): pass
    def propagar(self, *_a, **_k): pass


class _Fincas:
    def obtener_por_id(self, _id, **_): return SimpleNamespace(es_activo=True, id_finca=1)


class _Tipos:
    def obtener_por_nombre(self, n): return SimpleNamespace(nombre=n, es_activo=True)


class _Dependencias:
    def __init__(self, por_especie=None, carga=0): self.por_especie, self.carga = por_especie or {}, carga
    def contar_activos_por_especie(self, _id): return self.por_especie
    def calcular_carga(self, _id): return self.carga


def _registrar(**dto):
    repo = _InfraRepo()
    uc = RegistrarInfraestructuraUseCase(
        db=_Db(), infra_repo=repo, finca_repo=_Fincas(), tipo_area_repo=_Tipos(), auditoria_repo=_Nada(),
        especie_repo=_EspecieRepo(), propagador_tipo_modelo=_Nada(),
    )
    base = dict(nombre_infraestructura="Estanque 1", tipo_area="Estanque", superficie=Decimal("50"), finca_id=1)
    return uc.execute(RegistrarInfraestructuraDTO(**{**base, **dto}), USUARIO)


def _area(especies, superficie="50"):
    return Infraestructura(
        id_infraestructura=10, nombre=NombreInfraestructura("Estanque 1"), tipo="Estanque",
        superficie=Superficie(Decimal(superficie)), id_finca=1, es_activo=True, fecha_actualizacion=TS,
        id_especies=list(especies), tipo_modelo_asignado="MODELO_ACUICULTURA",
    )


def _editar(area, especies, superficie="50", **deps):
    uc = EditarInfraestructuraUseCase(
        db=_Db(), infra_repo=_InfraRepo(area), finca_repo=_Fincas(), tipo_area_repo=_Tipos(),
        auditoria_repo=_Nada(), especie_repo=_EspecieRepo(), dependency_port=_Dependencias(**deps),
        propagador_tipo_modelo=_Nada(),
    )
    dto = EditarInfraestructuraDTO(
        nombre_infraestructura="Estanque 1", tipo_area="Estanque", superficie=Decimal(superficie),
        especies=especies, tipo_modelo_asignado="MODELO_ACUICULTURA", fecha_actualizacion=TS,
    )
    return uc.execute(10, dto, USUARIO)


def _del_area(*ids):
    return [EspecieDelArea(i, ESPECIES[i].nombre.valor, ESPECIES[i].grupo_manejo,
                           ESPECIES[i].densidad_maxima_por_especie) for i in ids]


# ── capacidad_efectiva ───────────────────────────────────────────────────────

def test_ejemplo_del_profesor_rige_la_menor_densidad():
    # mojarra 100 + cachama 100 + salmón 80 ind/m² en 50 m² → 80 × 50
    assert capacidad_efectiva(Decimal("50"), _del_area(1, 2, 3)) == 4000


def test_capacidad_redondea_hacia_abajo():
    assert capacidad_efectiva(Decimal("10.55"), _del_area(3)) == 844  # 80 × 10.55 = 844.0
    assert capacidad_efectiva(Decimal("10.01"), _del_area(3)) == 800  # 800.8 → 800


@pytest.mark.parametrize("ids", [(), (1, 4)], ids=["sin-especies", "especie-sin-densidad"])
def test_capacidad_indefinida(ids):
    assert capacidad_efectiva(Decimal("50"), _del_area(*ids)) is None


# ── DTO ──────────────────────────────────────────────────────────────────────

def test_especie_id_sigue_siendo_alias_de_una_sola_especie():
    dto = RegistrarInfraestructuraDTO(nombre_infraestructura="E", tipo_area="Estanque",
                                      superficie=Decimal("1"), finca_id=1, especie_id=3)
    assert dto.especies == [3]


@pytest.mark.parametrize("extra", [{}, {"especies": []}, {"especies": [1], "especie_id": 2}],
                         ids=["sin-especie", "lista-vacia", "alias-contradice-lista"])
def test_dto_exige_al_menos_una_especie_coherente(extra):
    with pytest.raises(PydanticValidationError):
        RegistrarInfraestructuraDTO(nombre_infraestructura="E", tipo_area="Estanque",
                                    superficie=Decimal("1"), finca_id=1, **extra)


def test_dto_quita_especies_repetidas_conservando_el_orden():
    dto = RegistrarInfraestructuraDTO(nombre_infraestructura="E", tipo_area="Estanque",
                                      superficie=Decimal("1"), finca_id=1, especies=[3, 1, 3])
    assert dto.especies == [3, 1]


# ── registrar ────────────────────────────────────────────────────────────────

def test_registra_policultivo_del_mismo_grupo_con_criticidad():
    infra = _registrar(especies=[1, 2, 3], tipo_modelo_asignado="MODELO_ACUICULTURA", nivel_criticidad="ALTA")
    assert infra.id_especies == [1, 2, 3] and infra.nivel_criticidad == "ALTA"


def test_criticidad_por_defecto_es_media():
    assert _registrar(especies=[1]).nivel_criticidad == "MEDIA"


def test_grupos_de_manejo_distintos_es_422():
    with pytest.raises(BusinessRuleError) as e:
        _registrar(especies=[1, 5])
    assert e.value.code == "GRUPOS_MANEJO_INCOMPATIBLES" and e.value.status_code == 422
    assert "'ACUICULTURA'" in e.value.message and "'Pollo' pertenece a 'AVES'" in e.value.message


def test_registrar_con_especie_sin_densidad_se_permite():
    """Sin activos no hay operación de capacidad: la densidad faltante solo bloquea al operar."""
    assert _registrar(especies=[1, 4]).id_especies == [1, 4]


# ── editar ───────────────────────────────────────────────────────────────────

def test_agregar_especie_que_cabe_se_guarda():
    assert _editar(_area([1]), [1, 3], carga=4000).id_especies == [1, 3]


def test_entrante_que_baja_el_techo_por_debajo_de_la_carga_es_422_sin_tocar_el_area():
    area = _area([1])
    with pytest.raises(BusinessRuleError) as e:
        _editar(area, [1, 3], carga=4001)  # techo pasa de 5000 a 4000
    assert e.value.code == "CAPACIDAD_EXCEDIDA" and e.value.status_code == 422
    assert "(4000 individuos = MIN densidad 80 ind/m² × superficie 50 m²)" in e.value.message
    assert area.id_especies == [1]


def test_reducir_la_superficie_por_debajo_de_la_carga_es_422():
    with pytest.raises(BusinessRuleError) as e:
        _editar(_area([1]), [1], superficie="10", carga=1001)
    assert e.value.code == "CAPACIDAD_EXCEDIDA"


def test_agregar_especie_sin_densidad_con_activos_alojados_es_422():
    with pytest.raises(BusinessRuleError) as e:
        _editar(_area([1]), [1, 4], carga=1)
    assert e.value.code == "ESPECIE_SIN_DENSIDAD" and e.value.status_code == 422
    assert "'Tilapia'" in e.value.message


def test_area_vacia_no_valida_capacidad():
    assert _editar(_area([1]), [1, 4], carga=0).id_especies == [1, 4]


def test_retirar_especie_con_activos_es_422():
    with pytest.raises(BusinessRuleError) as e:
        _editar(_area([1, 2]), [1], por_especie={2: 3})
    assert e.value.code == "ESPECIE_CON_ACTIVOS_ALOJADOS" and e.value.status_code == 422
    assert "3 activos" in e.value.message and "'Cachama'" in e.value.message


def test_retirar_especie_sin_activos_se_permite():
    assert _editar(_area([1, 2]), [1], por_especie={1: 5}).id_especies == [1]


def test_editar_sin_enviar_criticidad_la_conserva():
    area = _area([1])
    area.nivel_criticidad = "BAJA"
    assert _editar(area, [1]).nivel_criticidad == "BAJA"
