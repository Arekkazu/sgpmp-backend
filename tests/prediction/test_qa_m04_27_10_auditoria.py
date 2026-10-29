# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-29 | Arekkazu | QA-M04-27-10 CU05 H-03, CU09 H-01/H-02/H-03 RF-69/RF-73            |
"""Reporte de pruebas manuales M04 (27-10): eventos de auditoría y activación.

CU09 H-01: los eventos del catálogo de patologías llegan sin id_patologia y quedan
como AUDITORIA_EVENTO_INVALIDO. CU09 H-02: guardar notas se registraba como
VERSION_APROBADA. CU09 H-03: VERSION_ACTIVADA sin id_version_deprecada. CU05 H-03:
una versión POBLACIONAL sin componente se activaba. Fakes en memoria, sin DB.
"""
from __future__ import annotations

import dataclasses

import pytest

from src.prediction.application.use_cases.catalogo_patologias.registrar_patologia_use_case import (
    RegistrarPatologiaUseCase,
)
from src.prediction.application.use_cases.versiones_modelo.activar_version_modelo_use_case import (
    ActivarVersionModeloUseCase,
)
from src.prediction.application.use_cases.versiones_modelo.registrar_notas_version_use_case import (
    RegistrarNotasVersionUseCase,
)
from src.prediction.domain.services.validacion_auditoria_m04 import validar_evento
from src.prediction.infrastructure.dto.registrar_notas_version_dto import RegistrarNotasVersionDTO
from src.prediction.infrastructure.dto.registrar_patologia_dto import RegistrarPatologiaDTO
from src.shared.errors import BusinessRuleError
from tests.prediction.test_dev34_rf69_codigos_http import _version
from tests.prediction.test_dev35_rf64_patologia_base import (
    DESCRIPCION, _Db, _desactivar, _editar, _patologia, _Registro, _Variables,
)


def _valido(evento: dict) -> tuple[str, ...]:
    return validar_evento(
        tipo_evento=evento["tipo_evento"], tipo_actor=evento["tipo_actor"], id_usuario=evento["id_usuario"],
        id_sistema=None, id_referencia=evento["id_referencia"], payload_evento=evento["payload_evento"],
    )


# --- CU09 H-01: los tres eventos del catálogo llevan id_patologia ------------------------

class _RepoAlta:
    def obtener_por_nombre(self, nombre): return None
    def obtener_por_combinacion_variables(self, ids, especie): return None
    def siguiente_version_catalogo(self): return 9
    def guardar(self, entidad): return dataclasses.replace(entidad, id_patologia=40)


class _EspecieActiva:
    def especie_activa(self, especie): return True


def test_registrar_patologia_evento_valido_con_id_patologia():
    auditoria = _Registro()
    RegistrarPatologiaUseCase(
        db=_Db(), repo=_RepoAlta(), historial_repo=_Registro(), auditoria_repo=auditoria,
        variable_port=_Variables(), especie_port=_EspecieActiva(),
    ).execute(
        RegistrarPatologiaDTO(nombre_patologia="Neumonía", variables_sensoricas_asociadas=[11, 12],
                              descripcion_clinica=DESCRIPCION),
        id_usuario=1,
    )
    (evento,) = auditoria.llamadas
    assert evento["payload_evento"]["id_patologia"] == 40
    assert _valido(evento) == ()


def _evento_de(uc) -> dict:
    (evento,) = uc._auditoria_repo.llamadas
    return evento


def test_editar_patologia_evento_valido_con_id_patologia():
    uc, _, _, _, dto = _editar(_patologia(es_base=False))
    uc.execute(15, dto, id_usuario=1)
    evento = _evento_de(uc)
    assert evento["payload_evento"]["id_patologia"] == 15
    assert _valido(evento) == ()


def test_inactivar_patologia_evento_valido_con_id_patologia():
    uc, _, _, _ = _desactivar(_patologia(es_base=False))
    uc.execute(15, id_usuario=1)
    evento = _evento_de(uc)
    assert evento["payload_evento"]["id_patologia"] == 15
    assert _valido(evento) == ()


# --- CU09 H-02: registrar notas no es aprobar --------------------------------------------

class _RepoVersiones:
    def __init__(self, *versiones):
        self.versiones = {v.id_version_modelo: v for v in versiones}
        self.activa = None
    def obtener_por_id(self, id_version): return self.versiones.get(id_version)
    def actualizar(self, entidad): return entidad
    def obtener_activo_por_tipo(self, tipo, componente): return self.activa
    def registrar_historial(self, **_kw): pass


def test_notas_se_registran_como_notas_registradas():
    auditoria = _Registro()
    RegistrarNotasVersionUseCase(
        db=_Db(), repo=_RepoVersiones(_version("APROBADO", notas=None)), auditoria_repo=auditoria,
    ).execute(7, RegistrarNotasVersionDTO(notas_validacion="Revisado por el veterinario"), id_usuario=3)
    (evento,) = auditoria.llamadas
    assert evento["tipo_evento"] == "NOTAS_REGISTRADAS"
    assert evento["payload_evento"]["notas_validacion"] == "Revisado por el veterinario"
    assert _valido(evento) == ()


# --- CU09 H-03: VERSION_ACTIVADA dice qué versión se deprecó -----------------------------

def _activar(repo) -> list[dict]:
    auditoria = _Registro()
    ActivarVersionModeloUseCase(db=_Db(), repo=repo, auditoria_repo=auditoria).execute(7, id_usuario=3)
    return auditoria.llamadas


def test_activacion_con_version_previa_lleva_id_version_deprecada():
    repo = _RepoVersiones(_version("APROBADO"))
    repo.activa = dataclasses.replace(_version("ACTIVO"), id_version_modelo=5, nombre_version="v5")
    activada, deprecada = _activar(repo)
    assert activada["tipo_evento"] == "VERSION_ACTIVADA"
    assert activada["payload_evento"]["id_version_deprecada"] == 5
    assert deprecada["tipo_evento"] == "VERSION_DEPRECADA"
    assert activada["correlacion_id"] == deprecada["correlacion_id"]
    assert _valido(activada) == ()


def test_primera_activacion_lleva_id_version_deprecada_null():
    (activada,) = _activar(_RepoVersiones(_version("APROBADO")))
    assert activada["payload_evento"]["id_version_deprecada"] is None
    assert _valido(activada) == ()


# --- CU05 H-03: POBLACIONAL sin componente no se activa ----------------------------------

def test_poblacional_sin_componente_no_se_activa():
    version = dataclasses.replace(_version("APROBADO"), tipo_modelo="MODELO_AVES", componente=None)
    with pytest.raises(BusinessRuleError) as exc:
        version.activar()
    assert exc.value.code == "COMPONENTE_INVALIDO"
    assert version.estado_version == "APROBADO"


def test_poblacional_con_componente_se_activa():
    version = dataclasses.replace(_version("APROBADO"), tipo_modelo="MODELO_AVES", componente="DETECTOR")
    version.activar()
    assert version.estado_version == "ACTIVO"
