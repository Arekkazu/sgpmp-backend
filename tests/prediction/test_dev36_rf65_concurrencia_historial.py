# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | DEV-36 RF-65: concurrencia optimista e historial de la configuración |
"""DEV-36 (RF-65 CA-9 y Restricción 5): editar exige la config_version vigente (412 si
cambió) y el historial devuelve la vigente seguida de las anteriores."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.prediction.application.use_cases.motor_ia.configurar_motor_use_case import ConfigurarMotorUseCase
from src.prediction.application.use_cases.motor_ia.consultar_motor_use_case import ConsultarMotorUseCase
from src.prediction.domain.entities.configuracion_motor_ia import ConfiguracionMotorIA
from src.prediction.domain.entities.version_configuracion_motor import VersionConfiguracionMotor
from src.prediction.infrastructure.dto.configurar_motor_dto import ConfigurarMotorDTO
from src.shared.errors import NotFoundError, PreconditionFailedError

TIPO = "MODELO_ESPECIES_GRANDES"


def _config(version: int) -> ConfiguracionMotorIA:
    entidad = ConfiguracionMotorIA.crear(
        tipo_modelo=TIPO, umbral_riesgo_alto=Decimal("0.7"), umbral_alerta_critica=Decimal("0.8"),
        ventana_temporal_min=10, modo_ejecucion="SERVIDOR", w_factor_sanitario=Decimal("0.5"),
        w_factor_ambiental=Decimal("0.3"), w_factor_densidad=Decimal("0.2"), id_usuario_responsable=1,
    )
    entidad.id_configuracion_motor = 7
    entidad.config_version = version
    entidad.fecha_creacion = datetime(2026, 10, 1, tzinfo=timezone.utc)
    return entidad


class _Repo:
    def __init__(self, existente=None, historial=()):
        self.existente, self.historial = existente, list(historial)
        self.bloqueos = []

    def obtener_por_tipo(self, _tipo, *, bloquear=False):
        self.bloqueos.append(bloquear)
        return self.existente

    def guardar(self, entidad): return entidad
    def actualizar(self, entidad): return entidad
    def listar_historial(self, _id): return self.historial


class _Nada:
    def registrar(self, **_kw): pass
    def listar_nodos_activos(self, _tipo): return []
    def listar_por_tipo_modelo(self, _tipo): return []


class _Db:
    def __init__(self): self.rollbacks = 0
    def commit(self): pass
    def rollback(self): self.rollbacks += 1


def _ejecutar(repo, db, **cambios):
    datos = dict(tipo_modelo=TIPO, ventana_temporal_min=15, umbral_riesgo_alto=Decimal("0.7"),
                 umbral_alerta_critica=Decimal("0.8"))
    datos.update(cambios)
    return ConfigurarMotorUseCase(
        db=db, repo=repo, auditoria_repo=_Nada(), version_port=_Nada(), nodo_edge_port=_Nada(),
        sincronizacion_repo=_Nada(), config_edge_port=_Nada(),
    ).execute(ConfigurarMotorDTO(**datos), id_usuario=1)


def test_editar_con_la_version_vigente_la_incrementa_y_bloquea_la_fila():
    repo = _Repo(_config(3))
    resultado = _ejecutar(repo, _Db(), config_version=3)
    assert resultado.entidad.config_version == 4 and not resultado.es_nueva
    assert repo.bloqueos == [True]


@pytest.mark.parametrize("version_cliente", [2, None])
def test_version_distinta_o_ausente_responde_412_sin_tocar_la_configuracion(version_cliente):
    repo, db = _Repo(_config(3)), _Db()
    with pytest.raises(PreconditionFailedError) as error:
        _ejecutar(repo, db, config_version=version_cliente)
    assert error.value.code == "CONFLICTO_CONCURRENCIA"
    assert error.value.status_code == 412
    assert repo.existente.config_version == 3 and repo.existente.ventana_temporal_min == 10
    assert db.rollbacks == 1


def test_crear_no_exige_version():
    resultado = _ejecutar(_Repo(None), _Db())
    assert resultado.es_nueva and resultado.entidad.config_version == 1


def test_historial_vigente_primero_y_luego_las_anteriores():
    anterior = VersionConfiguracionMotor(configuracion=_config(2), es_vigente=False, operacion="UPDATE",
                                         id_usuario_cambio=1, fecha_cambio=datetime(2026, 10, 2, tzinfo=timezone.utc))
    versiones = ConsultarMotorUseCase(repo=_Repo(_config(3), [anterior])).historial(TIPO)
    assert [(v.configuracion.config_version, v.es_vigente) for v in versiones] == [(3, True), (2, False)]


def test_historial_sin_configuracion_404():
    with pytest.raises(NotFoundError):
        ConsultarMotorUseCase(repo=_Repo(None)).historial(TIPO)
