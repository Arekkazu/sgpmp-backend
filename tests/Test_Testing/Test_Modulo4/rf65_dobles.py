"""Dobles en memoria para RF-65 (ConfigurarMotorUseCase). No son SQL ni Edge."""
from __future__ import annotations

import copy
from decimal import Decimal
from typing import Optional

from src.prediction.application.use_cases.motor_ia.configurar_motor_use_case import (
    ConfigurarMotorUseCase,
)
from src.prediction.domain.entities.configuracion_motor_ia import ConfiguracionMotorIA
from src.prediction.infrastructure.dto.configurar_motor_dto import ConfigurarMotorDTO

TIPO_INDIVIDUAL = "MODELO_ESPECIES_GRANDES"


class SesionNula:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.fallar_commit = False

    def commit(self) -> None:
        if self.fallar_commit:
            raise RuntimeError("fallo simulado de commit; no es PostgreSQL")
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class AuditoriaMemoria:
    def __init__(self) -> None:
        self.eventos: list[dict] = []

    def registrar(self, **kw) -> None:
        self.eventos.append(kw)


class VersionPortFijo:
    def __init__(self, llaves: Optional[dict[int, tuple]] = None) -> None:
        self.llaves = llaves or {}

    def obtener_llave(self, id_version: int):
        return self.llaves.get(id_version)

    def obtener_estado(self, id_version: int):
        llave = self.llaves.get(id_version)
        return llave[0] if llave else None


class NodoEdgeFijo:
    def __init__(self, activos: bool = True) -> None:
        self.activos = activos
        self.consultas: list[str] = []

    def hay_nodos_activos(self, tipo_modelo: str) -> bool:
        self.consultas.append(tipo_modelo)
        return self.activos


class ConfigRepoMemoria:
    """Almacena copias: un rechazo o fallo no muta la fila guardada."""

    def __init__(self) -> None:
        self._por_tipo: dict[str, ConfiguracionMotorIA] = {}
        self.guardar_ok = True
        self.actualizar_ok = True

    def obtener_por_tipo(self, tipo_modelo: str) -> Optional[ConfiguracionMotorIA]:
        entidad = self._por_tipo.get(tipo_modelo)
        return copy.deepcopy(entidad) if entidad else None

    def guardar(self, entidad: ConfiguracionMotorIA) -> ConfiguracionMotorIA:
        if not self.guardar_ok:
            raise RuntimeError("fallo simulado al persistir configuración")
        entidad.id_configuracion_motor = entidad.id_configuracion_motor or 1
        self._por_tipo[entidad.tipo_modelo] = copy.deepcopy(entidad)
        return copy.deepcopy(self._por_tipo[entidad.tipo_modelo])

    def actualizar(self, entidad: ConfiguracionMotorIA) -> ConfiguracionMotorIA:
        if not self.actualizar_ok:
            raise RuntimeError("fallo simulado al aplicar configuración")
        self._por_tipo[entidad.tipo_modelo] = copy.deepcopy(entidad)
        return copy.deepcopy(entidad)


def dto_motor(**overrides) -> ConfigurarMotorDTO:
    data = dict(
        tipo_modelo=TIPO_INDIVIDUAL,
        umbral_riesgo_alto=Decimal("0.70"),
        umbral_alerta_critica=Decimal("0.80"),
        ventana_temporal_min=10,
        modo_ejecucion="SERVIDOR",
        w_factor_sanitario=Decimal("0.400"),
        w_factor_ambiental=Decimal("0.300"),
        w_factor_densidad=Decimal("0.300"),
    )
    data.update(overrides)
    return ConfigurarMotorDTO(**data)


def ensamblar(
    *,
    repo: Optional[ConfigRepoMemoria] = None,
    auditoria: Optional[AuditoriaMemoria] = None,
    versiones: Optional[VersionPortFijo] = None,
    nodos: Optional[NodoEdgeFijo] = None,
    db: Optional[SesionNula] = None,
):
    repo = repo or ConfigRepoMemoria()
    auditoria = auditoria or AuditoriaMemoria()
    versiones = versiones or VersionPortFijo()
    nodos = nodos or NodoEdgeFijo(True)
    db = db or SesionNula()
    uc = ConfigurarMotorUseCase(
        db=db,
        repo=repo,
        auditoria_repo=auditoria,
        version_port=versiones,
        nodo_edge_port=nodos,
    )
    return uc, repo, auditoria, versiones, nodos, db
