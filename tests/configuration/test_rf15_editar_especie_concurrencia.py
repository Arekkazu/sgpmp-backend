"""Prueba unitaria para RF-15 (Módulo 9): Concurrencia Optimista en Edición de Especie (TC-M09-G06).

Sub-caso: TC-M09-16
Especie fixture: Cachama Blanca (id_especie=4)

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

Historial:
- Iteración anterior (TC-M09-G06 v1): ejecutada sobre Mojarra Plateada (id=5). Test unitario 1/1 PASSED.
- Iteración actual (TC-M09-G06 v2): especie cambiada a Cachama Blanca (id=4) según instrucción QA.
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


def _especie_cachama() -> Especie:
    """Fixture: Cachama Blanca (id=4) — estado confirmado en BD TEST 2026-09-07."""
    return Especie(
        id_especie=4,
        nombre=NombreEspecie("Cachama Blanca"),
        descripcion="Pez de agua dulce tropical con alta adaptabilidad a sistemas extensivos e intensivos.",
        es_activo=True,
        fecha_creacion=TS_V0,
        fecha_actualizacion=TS_V0,
    )


def test_concurrencia_optimista_rechaza_segundo_editor_412():
    """TC-M09-G06 / SC-16: El segundo usuario con timestamp desfasado debe ser rechazado con HTTP 412.

    Especie fixture: Cachama Blanca (id_especie=4).
    Timestamp ts_v0 = 2026-04-28T14:42:28.213141+00:00 (confirmado en BD TEST 2026-09-07).
    """
    especie_inicial = _especie_cachama()
    repo = EspecieRepoFake([especie_inicial])
    db = DbFake()
    auditoria = AuditoriaFake()
    uc = EditarEspecieUseCase(db=db, especies_repo=repo, auditoria_repo=auditoria)

    # CP-01 — Lectura inicial simultánea: A y B reciben el mismo ts_v0
    especie_leida_por_a = repo.obtener_por_id(4)
    especie_leida_por_b = repo.obtener_por_id(4)
    assert especie_leida_por_a.fecha_actualizacion == TS_V0
    assert especie_leida_por_b.fecha_actualizacion == TS_V0

    # CP-02 — Usuario A edita primero con ts_v0 → debe tener éxito (commit=1, ts actualizado)
    dto_a = EditarEspecieDTO(
        nombre="Cachama Blanca Edit A",
        descripcion="Modificacion por usuario A TC-G06",
        fecha_actualizacion=TS_V0,
    )
    especie_actualizada_a = uc.execute(4, dto_a, USUARIO_A)
    assert especie_actualizada_a.nombre.valor == "Cachama Blanca Edit A", "CP-02 FALLA: A no recibió éxito"
    assert repo.rows[4].nombre.valor == "Cachama Blanca Edit A"
    ts_v1 = especie_actualizada_a.fecha_actualizacion
    assert ts_v1 != TS_V0, "CP-02 FALLA: fecha_actualizacion no cambió tras edición de A"
    assert db.commits == 1, "CP-02 FALLA: se esperaba exactamente 1 commit tras edición de A"

    # CP-03 — Usuario B intenta guardar con timestamp obsoleto ts_v0 → debe ser rechazado 412
    dto_b = EditarEspecieDTO(
        nombre="Cachama Blanca Edit B",
        descripcion="Modificacion desactualizada por usuario B TC-G06",
        fecha_actualizacion=TS_V0,  # <-- ts_v0 obsoleto; BD ya tiene ts_v1
    )

    with pytest.raises(PreconditionFailedError) as exc_info:
        uc.execute(4, dto_b, USUARIO_B)

    assert exc_info.value.code == "CONFLICTO_CONCURRENCIA", "CP-03 FALLA: code incorrecto"
    assert exc_info.value.status_code == 412, "CP-03 FALLA: status_code no es 412"
    # B no generó commit adicional
    assert db.commits == 1, "CP-03 FALLA: B generó un commit inesperado"

    # CP-04 — Prevalece la versión de A; B no sobrescribió
    especie_final = repo.obtener_por_id(4)
    assert especie_final.nombre.valor == "Cachama Blanca Edit A", "CP-04 FALLA: prevalece B en vez de A"
    assert especie_final.descripcion == "Modificacion por usuario A TC-G06", "CP-04 FALLA: descripción incorrecta"

    # CP-05 — fecha_actualizacion se incrementó exactamente 1 vez (ts_v0 → ts_v1, no dos veces)
    assert especie_final.fecha_actualizacion == ts_v1, "CP-05 FALLA: timestamp no es ts_v1"
    assert especie_final.fecha_actualizacion != TS_V0, "CP-05 FALLA: timestamp sigue siendo ts_v0"
