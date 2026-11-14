# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-10-25 | Arekkazu | INC-M04-138/139/140/142 RF-64: catálogo de patologías contra Postgres |
# | 2026-10-31 | Arekkazu | USAB-M03-M04 M4-02 RF-64: el fake de variables responde también las admitidas por patología |
"""RF-64 contra PostgreSQL real (INC-M04-138-G001, 139-G001, 140-G003, 142-G004).

- Cada alta, edición o inactivación sube la versión del catálogo completo.
- Un nombre con espacios internos repetidos es el mismo nombre.
- Repetir un id de variable no cuenta para el mínimo de 2.
- El listado busca por fragmento del nombre.
"""
from __future__ import annotations

import uuid
from unittest.mock import Mock

import pytest

from src.prediction.application.use_cases.catalogo_patologias.consultar_patologias_use_case import (
    ConsultarPatologiasUseCase,
)
from src.prediction.application.use_cases.catalogo_patologias.desactivar_patologia_use_case import (
    DesactivarPatologiaUseCase,
)
from src.prediction.application.use_cases.catalogo_patologias.editar_patologia_use_case import EditarPatologiaUseCase
from src.prediction.application.use_cases.catalogo_patologias.registrar_patologia_use_case import (
    RegistrarPatologiaUseCase,
)
from src.prediction.infrastructure.dto.editar_patologia_dto import EditarPatologiaDTO
from src.prediction.infrastructure.dto.registrar_patologia_dto import RegistrarPatologiaDTO
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import (
    SqlAlchemyEventoAuditoriaM04Repository,
)
from src.prediction.infrastructure.repositories.historial_catalogo_repository import (
    SqlAlchemyHistorialCatalogoRepository,
)
from src.prediction.infrastructure.repositories.patologia_m04_repository import SqlAlchemyPatologiaM04Repository
from src.shared.errors import BusinessRuleError, ConflictError

pytestmark = pytest.mark.integration

DESCRIPCION = "Temperatura elevada con frecuencia respiratoria alta, signo compatible con estres termico."


class _Todo:
    def especie_activa(self, especie): return True
    def obtener_ids_activos(self, ids): return list(ids)
    def obtener_ids_para_patologia(self, ids): return list(ids)  # M4-02
    def tiene_modelos_activos(self, id_patologia): return False


def _letras() -> str:
    return "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:8])


@pytest.fixture
def catalogo(db_session, crear_usuario_db):
    usuario = crear_usuario_db(id_rol=1)["id_usuario"]
    repo = SqlAlchemyPatologiaM04Repository(db_session)
    comunes = dict(db=db_session, repo=repo, historial_repo=SqlAlchemyHistorialCatalogoRepository(db_session),
                   auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db_session, Mock()))

    def registrar(nombre, variables):
        return RegistrarPatologiaUseCase(**comunes, variable_port=_Todo(), especie_port=_Todo()).execute(
            RegistrarPatologiaDTO(nombre_patologia=nombre, variables_sensoricas_asociadas=variables,
                                  descripcion_clinica=DESCRIPCION), usuario)

    def editar(entidad, nombre, variables):
        return EditarPatologiaUseCase(**comunes, variable_port=_Todo(), modelo_activo_port=_Todo()).execute(
            entidad.id_patologia, EditarPatologiaDTO(nombre_patologia=nombre, descripcion_clinica=DESCRIPCION,
                                                     variables_sensoricas_asociadas=variables), usuario)

    def desactivar(entidad):
        return DesactivarPatologiaUseCase(**comunes, modelo_activo_port=_Todo()).execute(entidad.id_patologia, usuario)

    return registrar, editar, desactivar, repo


def test_cada_cambio_sube_la_version_del_catalogo(catalogo):
    registrar, editar, desactivar, repo = catalogo
    base = repo.siguiente_version_catalogo() - 1
    a = registrar(f"Estres termico {_letras()}", [1, 2])
    b = registrar(f"Hipoxia {_letras()}", [3, 4])
    assert (a.version_catalogo, b.version_catalogo) == (base + 1, base + 2)
    assert editar(a, a.nombre, [1, 2, 5]).version_catalogo == base + 3
    assert desactivar(b).version_catalogo == base + 4


def test_nombre_con_espacios_internos_repetidos_es_duplicado(catalogo):
    registrar, *_ = catalogo
    nombre = f"Estres termico {_letras()}"
    creada = registrar(nombre, [1, 2])
    assert creada.nombre == nombre
    for variante in (nombre.replace(" ", "  "), nombre.replace(" ", "\t"), f"  {nombre.upper()} "):
        with pytest.raises(ConflictError) as exc:
            registrar(variante, [6, 7])
        assert exc.value.code == "NOMBRE_PATOLOGIA_DUPLICADO"


def test_variable_repetida_no_alcanza_el_minimo(catalogo):
    registrar, *_ = catalogo
    with pytest.raises(BusinessRuleError) as exc:
        registrar(f"Unica variable {_letras()}", [13, 13])
    assert exc.value.code == "CANTIDAD_VARIABLES_INVALIDA"


def test_listado_busca_por_fragmento_del_nombre(catalogo, db_session):
    registrar, *_ = catalogo
    sufijo = _letras()
    registrar(f"Coccidiosis {sufijo}", [8, 9])
    encontradas = ConsultarPatologiasUseCase(repo=SqlAlchemyPatologiaM04Repository(db_session)).execute(
        nombre=f"COCCIDIOSIS {sufijo}"[3:])
    assert [p.nombre for p in encontradas] == [f"Coccidiosis {sufijo}"]
    # '%' y '_' se buscan literales, no como comodines de LIKE.
    assert ConsultarPatologiasUseCase(repo=SqlAlchemyPatologiaM04Repository(db_session)).execute(nombre="%_%") == []
