# | Fecha      | Nombre       | Que se hizo                                           |
# |------------|--------------|-------------------------------------------------------|
# | 2026-10-23 | destroyerban | DEV-35 RF-64: patología base no editable ni inactivable |
# | 2026-10-25 | Arekkazu     | INC-M04-139-G001 RF-64: la versión viene del catálogo |
# | 2026-10-31 | Arekkazu | USAB-M03-M04 M4-02 RF-64: el fake de variables responde también las admitidas por patología |
"""DEV-35 (RF-64 E2 y CA-3, G-04): una patología base no se edita (405) ni se inactiva.

P-7: la Restricción 3 de la ficha se contradice con CA-3; se aplica la propuesta de
rechazar siempre la inactivación de una base, tenga o no modelos que la usen.
Fakes en memoria, sin DB.
"""
from __future__ import annotations

import pytest

from src.prediction.application.use_cases.catalogo_patologias.desactivar_patologia_use_case import (
    DesactivarPatologiaUseCase,
)
from src.prediction.application.use_cases.catalogo_patologias.editar_patologia_use_case import EditarPatologiaUseCase
from src.prediction.domain.entities.patologia_m04 import PatologiaM04
from src.prediction.domain.entities.patologia_variable import PatologiaVariable
from src.prediction.infrastructure.dto.editar_patologia_dto import EditarPatologiaDTO
from src.shared.errors import ConflictError, MethodNotAllowedError

DESCRIPCION = "Temperatura elevada con frecuencia respiratoria alta indica neumonía en aves de producción."


def _patologia(es_base: bool) -> PatologiaM04:
    return PatologiaM04(
        nombre="Neumonía", especie_aplicable="AVES", descripcion_clinica=DESCRIPCION, es_base=es_base,
        es_activo=True, version_catalogo=1, id_patologia=15,
        variables=[PatologiaVariable(id_variable_ambiental=11), PatologiaVariable(id_variable_ambiental=12)],
    )


class _Db:
    def __init__(self): self.commits = 0
    def commit(self): self.commits += 1
    def rollback(self): pass


class _Repo:
    def __init__(self, entidad): self.entidad, self.actualizadas = entidad, []
    def obtener_por_id(self, id_patologia, *, bloquear=False): return self.entidad
    def obtener_por_nombre(self, nombre): return None
    def obtener_por_combinacion_variables(self, ids, especie, excluir_id=None): return None
    def actualizar(self, entidad): self.actualizadas.append(entidad); return entidad
    def siguiente_version_catalogo(self): return 8  # el catálogo ya va en la versión 7


class _Registro:
    def __init__(self): self.llamadas = []
    def registrar(self, **kw): self.llamadas.append(kw)


class _Modelos:
    def __init__(self, en_uso=False): self.en_uso = en_uso
    def tiene_modelos_activos(self, id_patologia): return self.en_uso


class _Variables:
    def obtener_ids_activos(self, ids): return list(ids)
    def obtener_ids_para_patologia(self, ids): return list(ids)  # M4-02


def _editar(entidad):
    repo, historial, db = _Repo(entidad), _Registro(), _Db()
    uc = EditarPatologiaUseCase(db=db, repo=repo, historial_repo=historial, auditoria_repo=_Registro(),
                                variable_port=_Variables(), modelo_activo_port=_Modelos())
    dto = EditarPatologiaDTO(nombre_patologia="Neumonía aviar", descripcion_clinica=DESCRIPCION,
                             variables_sensoricas_asociadas=[11, 12, 13])
    return uc, repo, historial, db, dto


def _desactivar(entidad, en_uso=False):
    repo, historial, db = _Repo(entidad), _Registro(), _Db()
    uc = DesactivarPatologiaUseCase(db=db, repo=repo, historial_repo=historial, auditoria_repo=_Registro(),
                                    modelo_activo_port=_Modelos(en_uso))
    return uc, repo, historial, db


# --- E2: editar una base → 405 -------------------------------------------------------------

def test_e2_editar_patologia_base_es_405_sin_tocar_nada():
    uc, repo, historial, db, dto = _editar(_patologia(es_base=True))
    with pytest.raises(MethodNotAllowedError) as exc:
        uc.execute(15, dto, id_usuario=1)
    assert exc.value.status_code == 405
    assert exc.value.code == "PATOLOGIA_BASE_INMUTABLE"
    assert exc.value.message == "Las patologías base del sistema no pueden ser modificadas."
    assert repo.actualizadas == [] and historial.llamadas == [] and db.commits == 0


def test_editar_patologia_no_base_sigue_igual():
    uc, repo, historial, _, dto = _editar(_patologia(es_base=False))
    entidad = uc.execute(15, dto, id_usuario=1)
    assert entidad.nombre == "Neumonía aviar" and entidad.version_catalogo == 8
    assert historial.llamadas[0]["accion"] == "MODIFICADA"


# --- CA-3: inactivar una base → 405, con o sin modelos ------------------------------------

@pytest.mark.parametrize("en_uso", [False, True])
def test_ca3_inactivar_patologia_base_es_405_tenga_o_no_modelos(en_uso):
    uc, repo, historial, db = _desactivar(_patologia(es_base=True), en_uso=en_uso)
    with pytest.raises(MethodNotAllowedError) as exc:
        uc.execute(15, id_usuario=1)
    assert exc.value.status_code == 405
    assert exc.value.code == "PATOLOGIA_BASE_INMUTABLE"
    assert repo.entidad.es_activo is True
    assert repo.actualizadas == [] and historial.llamadas == [] and db.commits == 0


def test_inactivar_patologia_no_base_sigue_igual():
    uc, repo, historial, _ = _desactivar(_patologia(es_base=False))
    assert uc.execute(15, id_usuario=1).es_activo is False
    assert historial.llamadas[0]["accion"] == "INACTIVADA"


def test_inactivar_no_base_en_uso_sigue_en_409():
    uc, _, _, _ = _desactivar(_patologia(es_base=False), en_uso=True)
    with pytest.raises(ConflictError) as exc:
        uc.execute(15, id_usuario=1)
    assert exc.value.code == "PATOLOGIA_EN_USO_POR_MODELO"
