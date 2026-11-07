"""Prueba unitaria para RF-15 (Módulo 9): Desactivación de Especie y Regla de Proceso Crítico (Sub-caso 2 / TC-M09-G04).

Verifica mediante fakes (sin BD):
- Bloqueo de desactivación cuando la especie tiene procesos críticos activos (proceso_critico_port.tiene_proceso_activo = True),
  lanzando `LockedError` con `code == "ESPECIE_CON_PROCESO_ACTIVO"` y `status_code == 423`.
- Mantenimiento de `es_activo = True` en la entidad cuando la desactivación se bloquea.
- Desactivación lógica exitosa cuando NO existen procesos críticos activos.
"""
from __future__ import annotations

from datetime import datetime, timezone
import pytest

from src.configuration.application.use_cases.especies.desactivar_especie_use_case import DesactivarEspecieUseCase
from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.repositories.proceso_critico_port import ProcesoCriticoPort
from src.configuration.domain.value_objects.nombre_especie import NombreEspecie
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import LockedError

USUARIO = UsuarioActual(id_usuario=1, id_token=1, id_rol=1)
TS_DB = datetime(2026, 5, 10, 8, 0, tzinfo=timezone.utc)


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class EspecieRepoFake:
    def __init__(self, especies: list[Especie]) -> None:
        self.rows = {e.id_especie: e for e in especies}

    def obtener_por_id(self, id_especie: int) -> Especie | None:
        return self.rows.get(id_especie)

    def actualizar(self, entidad: Especie) -> Especie:
        self.rows[entidad.id_especie] = entidad
        return entidad


class AuditoriaFake:
    def registrar(self, **kwargs) -> None:
        pass


class ProcesoCriticoPortFake(ProcesoCriticoPort):
    def __init__(self, tiene_activo: bool) -> None:
        self._tiene_activo = tiene_activo

    def tiene_proceso_activo(self, id_especie: int) -> bool:
        return self._tiene_activo


def _especie_activa(id_especie: int = 4, nombre: str = "Cachama Blanca") -> Especie:
    return Especie(
        id_especie=id_especie,
        nombre=NombreEspecie(nombre),
        descripcion="Especie activa de prueba",
        es_activo=True,
        fecha_creacion=TS_DB,
        fecha_actualizacion=TS_DB,
    )


def test_desactivacion_bloqueada_por_proceso_critico_activo_423():
    """SC-2: Intento de desactivar especie con proceso crítico activo lanza LockedError (HTTP 423)."""
    especie = _especie_activa(id_especie=4, nombre="Cachama Blanca")
    repo = EspecieRepoFake([especie])
    proceso_critico = ProcesoCriticoPortFake(tiene_activo=True)
    db = DbFake()
    
    uc = DesactivarEspecieUseCase(
        db=db,
        especies_repo=repo,
        auditoria_repo=AuditoriaFake(),
        proceso_critico_port=proceso_critico,
    )

    with pytest.raises(LockedError) as exc_info:
        uc.execute(4, USUARIO)

    assert exc_info.value.code == "ESPECIE_CON_PROCESO_ACTIVO"
    assert exc_info.value.status_code == 423
    assert repo.rows[4].es_activo is True  # La especie se mantiene activa
    assert db.commits == 0


def test_desactivacion_exitosa_sin_proceso_critico():
    """SC-1: Desactivación exitosa cuando no existen procesos críticos activos."""
    especie = _especie_activa(id_especie=4, nombre="Cachama Blanca")
    repo = EspecieRepoFake([especie])
    proceso_critico = ProcesoCriticoPortFake(tiene_activo=False)
    db = DbFake()

    uc = DesactivarEspecieUseCase(
        db=db,
        especies_repo=repo,
        auditoria_repo=AuditoriaFake(),
        proceso_critico_port=proceso_critico,
    )

    res = uc.execute(4, USUARIO)

    assert res.es_activo is False
    assert repo.rows[4].es_activo is False
    assert db.commits == 1
