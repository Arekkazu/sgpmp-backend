"""Prueba unitaria para RF-15 (Módulo 9): Concurrencia Optimista en Edición de Especie (TC-M09-G06).

Aclaración Metodológica:
Esta prueba valida la regla de negocio de concurrencia optimista implementada en `EditarEspecieUseCase`.
Dado que el control optimista opera mediante la verificación del timestamp `fecha_actualizacion`
declarado por el cliente contra el valor actual persistido en el modelo, la simulación determinística
de lecturas paralelas y solicitudes desfasadas produce la misma validación lógica exacta que dos
hilos o procesos HTTP concurrentes en tiempo real.

Verifica mediante fakes (sin BD):
1. Usuario A y Usuario B leen la especie obteniendo el timestamp inicial `ts_v0`.
2. Usuario A actualiza la especie enviando `fecha_actualizacion = ts_v0`. La operación tiene éxito (HTTP 200)
   y actualiza el timestamp en la entidad a `ts_v1`.
3. Usuario B intenta actualizar la misma especie enviando el timestamp desactualizado `ts_v0`.
   La operación es RECHAZADA lanzando `PreconditionFailedError` (HTTP 412 / `code == "CONFLICTO_CONCURRENCIA"`).
4. Se verifica que prevalecen los datos guardados por el Usuario A y que los datos de B no sobrescriben la entidad.
"""
from __future__ import annotations

from datetime import datetime, timezone
import pytest

from src.configuration.application.use_cases.especies.editar_especie_use_case import EditarEspecieUseCase
from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.value_objects.nombre_especie import NombreEspecie
from src.configuration.infrastructure.dto.editar_especie_dto import EditarEspecieDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import PreconditionFailedError

USUARIO_A = UsuarioActual(id_usuario=1, id_token=10, id_rol=1)
USUARIO_B = UsuarioActual(id_usuario=2, id_token=11, id_rol=1)

TS_V0 = datetime(2026, 4, 28, 14, 42, 28, 213141, tzinfo=timezone.utc)


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

    def obtener_por_nombre(self, nombre: NombreEspecie) -> Especie | None:
        for r in self.rows.values():
            if r.nombre.normalizado() == nombre.normalizado():
                return r
        return None

    def actualizar(self, entidad: Especie) -> Especie:
        self.rows[entidad.id_especie] = entidad
        return entidad


class AuditoriaFake:
    def registrar(self, **kwargs) -> None:
        pass


def _especie_mojarra() -> Especie:
    return Especie(
        id_especie=5,
        nombre=NombreEspecie("Mojarra Plateada"),
        descripcion="Especie de ciclo corto utilizada en policultivos y sistemas de pequeña escala.",
        es_activo=True,
        fecha_creacion=TS_V0,
        fecha_actualizacion=TS_V0,
    )


def test_concurrencia_optimista_rechaza_segundo_editor_412():
    """TC-M09-G06 / SC-16: El segundo usuario con timestamp desfasado debe ser rechazado con HTTP 412."""
    especie_inicial = _especie_mojarra()
    repo = EspecieRepoFake([especie_inicial])
    db = DbFake()
    auditoria = AuditoriaFake()
    uc = EditarEspecieUseCase(db=db, especies_repo=repo, auditoria_repo=auditoria)

    # 1. Simulación de lectura inicial simultánea de A y B (ambos reciben TS_V0)
    especie_leida_por_a = repo.obtener_por_id(5)
    especie_leida_por_b = repo.obtener_por_id(5)
    assert especie_leida_por_a.fecha_actualizacion == TS_V0
    assert especie_leida_por_b.fecha_actualizacion == TS_V0

    # 2. Usuario A edita primero y guarda exitosamente con fecha_actualizacion = TS_V0
    dto_a = EditarEspecieDTO(
        nombre="Mojarra Plateada Edit A",
        descripcion="Modificación por usuario A",
        fecha_actualizacion=TS_V0,
    )
    especie_actualizada_a = uc.execute(5, dto_a, USUARIO_A)
    assert especie_actualizada_a.nombre.valor == "Mojarra Plateada Edit A"
    assert repo.rows[5].nombre.valor == "Mojarra Plateada Edit A"
    assert db.commits == 1

    # 3. Usuario B intenta guardar sus cambios con el timestamp desactualizado TS_V0
    dto_b = EditarEspecieDTO(
        nombre="Mojarra Plateada Edit B",
        descripcion="Modificación desactualizada por usuario B",
        fecha_actualizacion=TS_V0,  # <-- TS_V0 ya no coincide con el nuevo timestamp en BD
    )

    with pytest.raises(PreconditionFailedError) as exc_info:
        uc.execute(5, dto_b, USUARIO_B)

    # 4. Verificaciones de checkpoints
    assert exc_info.value.code == "CONFLICTO_CONCURRENCIA"
    assert exc_info.value.status_code == 412

    # 5. Confirmar que prevalecen los datos del Usuario A y B no los sobrescribió
    especie_final = repo.obtener_por_id(5)
    assert especie_final.nombre.valor == "Mojarra Plateada Edit A"
    assert especie_final.descripcion == "Modificación por usuario A"
