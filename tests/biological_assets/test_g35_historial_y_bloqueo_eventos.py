"""G35: historial y bloqueo de eventos después del cierre del ciclo (RF-38/RF-39)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from src.biological_assets.application.use_cases.gestion.consultar_eventos_use_case import (
    ConsultarEventosUseCase,
)
from src.biological_assets.application.use_cases.gestion.registrar_evento_crecimiento_use_case import (
    RegistrarEventoCrecimientoUseCase,
)
from src.biological_assets.application.use_cases.gestion.registrar_evento_sanitario_use_case import (
    RegistrarEventoSanitarioUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, EventoActivo
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.registrar_evento_crecimiento_dto import (
    RegistrarEventoCrecimientoDTO,
)
from src.biological_assets.infrastructure.dto.registrar_evento_sanitario_dto import (
    RegistrarEventoSanitarioDTO,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import ConflictError


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class ActivoRepoFake:
    def __init__(self, activo: ActivoBiologico) -> None:
        self.activo = activo
        self.consultas_fase = 0

    def obtener_por_id(self, _id: int, **_kwargs) -> ActivoBiologico:
        return self.activo

    def obtener_fase_activa(self, _id: int):
        self.consultas_fase += 1
        return None


class EventoRepoFake:
    def __init__(self, eventos: list[EventoActivo] | None = None) -> None:
        self.eventos = eventos or []
        self.guardados = 0

    def listar_por_activo(self, _id: int) -> list[EventoActivo]:
        return self.eventos

    def guardar(self, _evento: EventoActivo) -> EventoActivo:
        self.guardados += 1
        raise AssertionError('no debe intentar persistir eventos sobre un activo cerrado')


def _activo(estado: EstadoActivo = EstadoActivo.ACTIVO) -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=4,
        tipo='INDIVIDUAL',
        origen_financiero='nacimiento',
        id_infraestructura=1,
        id_estado=estado,
        id_usuario=1,
        id_activo_biologico=10,
    )


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=7, id_token=1, id_rol=1)


def test_historial_de_eventos_admite_activo_individual_sin_eventos() -> None:
    repo = ActivoRepoFake(_activo())
    evento_repo = EventoRepoFake()
    use_case = ConsultarEventosUseCase(
        db=DbFake(),
        activo_repo=repo,
        evento_repo=evento_repo,
    )

    assert use_case.execute(10, ids_fincas_permitidas=[1]) == []


def test_crecimiento_sobre_activo_cerrado_es_409_antes_de_validar_fase() -> None:
    db = DbFake()
    repo = ActivoRepoFake(_activo(EstadoActivo.CERRADO))
    evento_repo = EventoRepoFake()
    use_case = RegistrarEventoCrecimientoUseCase(
        db=db,
        activo_repo=repo,
        evento_repo=evento_repo,
        infra_port=object(),
        parametros_port=object(),
        ciclo_port=object(),
    )

    with pytest.raises(ConflictError) as exc_info:
        use_case.execute(
            10,
            RegistrarEventoCrecimientoDTO(
                tipo_medicion='PESO',
                valor_medicion=Decimal('12.5'),
                unidad_medida='kg',
            ),
            _usuario(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == 'ESTADO_NO_PERMITE_EVENTOS'
    assert repo.consultas_fase == 0
    assert evento_repo.guardados == 0
    assert db.commits == 0


def test_evento_sanitario_sobre_activo_cerrado_es_409_sin_persistir() -> None:
    db = DbFake()
    repo = ActivoRepoFake(_activo(EstadoActivo.CERRADO))
    evento_repo = EventoRepoFake()
    use_case = RegistrarEventoSanitarioUseCase(
        db=db,
        activo_repo=repo,
        evento_repo=evento_repo,
        historico_repo=object(),
    )

    with pytest.raises(ConflictError) as exc_info:
        use_case.execute(
            10,
            RegistrarEventoSanitarioDTO(
                tipo='DIAGNOSTICO',
                diagnostico='Control posterior al cierre',
            ),
            _usuario(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == 'ESTADO_NO_PERMITE_EVENTOS'
    assert evento_repo.guardados == 0
    assert db.commits == 0
