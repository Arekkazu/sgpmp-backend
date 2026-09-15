"""INC-M02-58-G35: asignación manual de fases productivas (RF-37/RF-38)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.biological_assets.application.use_cases.gestion.cambiar_fase_use_case import (
    CambiarFaseUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    GestionFase,
)
from src.biological_assets.domain.repositories.ciclo_consulta_port import (
    CicloProductivoConsulta,
    FaseCiclo,
)
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.cambiar_fase_dto import CambiarFaseDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class ActivoRepoFake:
    def __init__(
        self,
        activo: ActivoBiologico,
        gestiones: list[GestionFase] | None = None,
        *,
        fallar_cierre: bool = False,
    ) -> None:
        self.activo = activo
        self.gestiones = gestiones or []
        self.fallar_cierre = fallar_cierre
        self.orden: list[str] = []
        self.cierres: list[tuple[int, datetime, str, int]] = []
        self.creadas: list[GestionFase] = []

    def obtener_por_id(self, _id: int) -> ActivoBiologico:
        return self.activo

    def obtener_gestiones_fases(self, _id: int) -> list[GestionFase]:
        return self.gestiones

    def cerrar_gestion_activa(
        self,
        id_activo: int,
        fecha_fin: datetime,
        motivo: str,
        usuario_id: int,
    ) -> None:
        self.orden.append('cerrar')
        self.cierres.append((id_activo, fecha_fin, motivo, usuario_id))
        if self.fallar_cierre:
            raise RuntimeError('fallo simulado al cerrar la fase anterior')

    def crear_gestion_fase(self, gestion: GestionFase) -> GestionFase:
        self.orden.append('crear')
        gestion.id_gestion_fases = 101
        self.creadas.append(gestion)
        return gestion


class CicloPortFake:
    def __init__(self, ciclo: CicloProductivoConsulta) -> None:
        self.ciclo = ciclo

    def obtener_ciclo_con_fases(self, _id: int) -> CicloProductivoConsulta:
        return self.ciclo

    def metrica_habilitada_en_ciclo(self, _id_ciclo: int, _id_metrica: int) -> bool:
        return False


def _activo() -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=4,
        tipo='INDIVIDUAL',
        origen_financiero='nacimiento',
        id_infraestructura=1,
        id_estado=EstadoActivo.ACTIVO,
        id_usuario=1,
        id_activo_biologico=10,
    )


def _ciclo() -> CicloProductivoConsulta:
    return CicloProductivoConsulta(
        id_ciclo_productivo=4,
        nombre='Cachama',
        fases=[
            FaseCiclo(1, 4, 'Alevinaje', 30),
            FaseCiclo(2, 4, 'Engorde', 60),
        ],
    )


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=7, id_token=1, id_rol=1)


def _gestion_anterior(fecha: datetime) -> GestionFase:
    return GestionFase(
        id_gestion_fases=100,
        id_activo_biologico=10,
        id_ciclo_productiva=4,
        nombre_ciclo='Cachama',
        nombre_fase_actual='Alevinaje',
        paso_actual=1,
        total_pasos=2,
        fecha_inicio=fecha,
        fecha_finalizacion=None,
        es_activa=True,
        id_usuario=3,
    )


def test_asignar_primera_fase_envia_usuario_y_retorna_gestion_activa() -> None:
    fecha = datetime(2026, 9, 11, tzinfo=timezone.utc)
    db = DbFake()
    repo = ActivoRepoFake(_activo())
    use_case = CambiarFaseUseCase(db=db, repo=repo, ciclo_port=CicloPortFake(_ciclo()))

    resultado = use_case.execute(
        10,
        CambiarFaseDTO(id_ciclo_productiva=4, fecha_inicio=fecha),
        _usuario(),
    )

    assert repo.cierres == [(10, fecha, '', 7)]
    assert repo.orden == ['cerrar', 'crear']
    assert resultado.nombre_fase_actual == 'Alevinaje'
    assert resultado.paso_actual == 1
    assert resultado.es_activa is True
    assert resultado.id_usuario == 7
    assert db.commits == 1
    assert db.rollbacks == 0


def test_avanzar_fase_cierra_la_anterior_con_el_usuario_responsable() -> None:
    fecha_anterior = datetime(2026, 8, 1, tzinfo=timezone.utc)
    fecha_cambio = datetime(2026, 9, 11, tzinfo=timezone.utc)
    db = DbFake()
    repo = ActivoRepoFake(_activo(), [_gestion_anterior(fecha_anterior)])
    use_case = CambiarFaseUseCase(db=db, repo=repo, ciclo_port=CicloPortFake(_ciclo()))

    resultado = use_case.execute(
        10,
        CambiarFaseDTO(
            id_ciclo_productiva=4,
            fecha_inicio=fecha_cambio,
            motivo_cambio='avance planificado',
        ),
        _usuario(),
    )

    assert repo.cierres == [(10, fecha_cambio, 'avance planificado', 7)]
    assert repo.orden == ['cerrar', 'crear']
    assert resultado.nombre_fase_actual == 'Engorde'
    assert resultado.paso_actual == 2
    assert resultado.motivo_cambio == 'avance planificado'
    assert db.commits == 1


def test_fallo_al_cerrar_fase_anterior_revierte_y_no_crea_la_nueva() -> None:
    fecha = datetime(2026, 9, 11, tzinfo=timezone.utc)
    db = DbFake()
    repo = ActivoRepoFake(_activo(), fallar_cierre=True)
    use_case = CambiarFaseUseCase(db=db, repo=repo, ciclo_port=CicloPortFake(_ciclo()))

    with pytest.raises(RuntimeError, match='fallo simulado'):
        use_case.execute(
            10,
            CambiarFaseDTO(id_ciclo_productiva=4, fecha_inicio=fecha),
            _usuario(),
        )

    assert repo.cierres == [(10, fecha, '', 7)]
    assert repo.creadas == []
    assert db.commits == 0
    assert db.rollbacks == 1
