"""RF-42: la restricción de LOTE (POBLACIONAL) en eventos reproductivos sí se aplica.

El use case comparaba ``activo.tipo == 'LOTE'``, valor que ``TipoActivo`` nunca
tiene (solo INDIVIDUAL y POBLACIONAL): la condición era código muerto y un activo
POBLACIONAL podía registrar servicio/inseminación/diagnóstico/parto/aborto sin que
el use case lo impidiera (solo lo bloqueaba el trigger de DB, que por el gap de
traducción de errores devolvía 500 en vez de 422). Estas pruebas fijan el
contrato de FA-04: POBLACIONAL solo puede registrar ``nacimiento``, con
``BusinessRuleError('EVENTO_NO_PERMITIDO_LOTE')`` antes de llegar a la base de datos.
"""
from __future__ import annotations

import pytest

from src.biological_assets.application.use_cases.gestion.registrar_evento_reproductivo_use_case import (
    RegistrarEventoReproductivoUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    EventoActivo,
    EventoAuditoria,
)
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.registrar_evento_reproductivo_dto import (
    RegistrarEventoReproductivoDTO,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError

CATEGORIAS_NO_PERMITIDAS_LOTE = ['servicio', 'inseminacion', 'diagnostico', 'parto', 'aborto']


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class ActivoRepoFake:
    def __init__(self, activos: dict[int, ActivoBiologico]) -> None:
        self.activos = activos

    def obtener_por_id(self, id_activo: int) -> ActivoBiologico | None:
        return self.activos.get(id_activo)


class EventoRepoFake:
    def __init__(self) -> None:
        self.guardado: EventoActivo | None = None

    def obtener_ultima_fecha(self, _id: int):
        return None

    def tiene_servicio_o_inseminacion_previa(self, _id: int) -> bool:
        return False

    def tiene_diagnostico_positivo_previo(self, _id: int) -> bool:
        return False

    def guardar(self, evento: EventoActivo) -> EventoActivo:
        self.guardado = evento
        return evento


class BitacoraRepoFake:
    def __init__(self, falla: bool = False) -> None:
        self.falla = falla
        self.eventos: list[EventoAuditoria] = []

    def registrar(self, evento: EventoAuditoria) -> None:
        if self.falla:
            raise RuntimeError('auditoría no disponible')
        self.eventos.append(evento)


def _activo(tipo: str, id_activo: int, id_estado: int = EstadoActivo.ACTIVO) -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=1,
        tipo=tipo,
        origen_financiero='compra',
        id_infraestructura=1,
        id_estado=id_estado,
        id_usuario=1,
        id_activo_biologico=id_activo,
    )


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=7, id_token=1, id_rol=2)


def _dto(categoria: str, **kwargs) -> RegistrarEventoReproductivoDTO:
    return RegistrarEventoReproductivoDTO(
        categoria=categoria,
        resultado='exitoso',
        **kwargs,
    )


def _uc(db, activo_repo, evento_repo, bitacora_repo=None) -> RegistrarEventoReproductivoUseCase:
    return RegistrarEventoReproductivoUseCase(
        db=db,
        activo_repo=activo_repo,
        evento_repo=evento_repo,
        bitacora_repo=bitacora_repo,
    )


@pytest.mark.parametrize('categoria', CATEGORIAS_NO_PERMITIDAS_LOTE)
def test_poblacional_rechaza_toda_categoria_distinta_de_nacimiento(categoria: str) -> None:
    db = DbFake()
    activo_repo = ActivoRepoFake({10: _activo('POBLACIONAL', 10)})
    evento_repo = EventoRepoFake()
    uc = _uc(db, activo_repo, evento_repo)

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(10, _dto(categoria), _usuario())

    assert exc.value.code == 'EVENTO_NO_PERMITIDO_LOTE'
    assert evento_repo.guardado is None
    assert db.commits == 0


def test_poblacional_permite_nacimiento() -> None:
    db = DbFake()
    activo_repo = ActivoRepoFake({10: _activo('POBLACIONAL', 10)})
    evento_repo = EventoRepoFake()
    uc = _uc(db, activo_repo, evento_repo)

    resultado = uc.execute(10, _dto('nacimiento', numero_crias=1), _usuario())

    assert resultado is not None
    assert evento_repo.guardado is not None
    assert evento_repo.guardado.reproductivo.categoria == 'nacimiento'
    assert db.commits == 1


def test_individual_servicio_no_aplica_restriccion_lote() -> None:
    db = DbFake()
    padre = _activo('INDIVIDUAL', 20)
    activo_repo = ActivoRepoFake({10: _activo('INDIVIDUAL', 10), 20: padre})
    evento_repo = EventoRepoFake()
    uc = _uc(db, activo_repo, evento_repo)

    resultado = uc.execute(10, _dto('servicio', id_padre=20), _usuario())

    assert resultado is not None
    assert evento_repo.guardado is not None
    assert evento_repo.guardado.reproductivo.categoria == 'servicio'
    assert db.commits == 1


def test_individual_alcanza_secuencia_y_no_el_error_de_lote() -> None:
    db = DbFake()
    activo_repo = ActivoRepoFake({10: _activo('INDIVIDUAL', 10)})
    evento_repo = EventoRepoFake()
    uc = _uc(db, activo_repo, evento_repo)

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(10, _dto('diagnostico'), _usuario())

    assert exc.value.code == 'SECUENCIA_REPRODUCTIVA_INVALIDA'
    assert evento_repo.guardado is None


def test_ca10_audita_nacimiento_rechazado_fuera_de_secuencia() -> None:
    db = DbFake()
    activo_repo = ActivoRepoFake({10: _activo('INDIVIDUAL', 10)})
    evento_repo = EventoRepoFake()
    bitacora_repo = BitacoraRepoFake()
    uc = _uc(db, activo_repo, evento_repo, bitacora_repo)

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(10, _dto('nacimiento', numero_crias=1), _usuario())

    assert exc.value.code == 'SECUENCIA_REPRODUCTIVA_INVALIDA'
    assert evento_repo.guardado is None
    assert db.rollbacks == 1
    assert db.commits == 1
    assert len(bitacora_repo.eventos) == 1

    auditoria = bitacora_repo.eventos[0]
    assert auditoria.rf_origen == 'RF42'
    assert auditoria.tipo_evento == 'SECUENCIA_REPRODUCTIVA_VIOLADA'
    assert auditoria.resultado == 'RECHAZADO'
    assert auditoria.severidad_log == 'WARNING'
    assert auditoria.id_activo_biologico == 10
    assert auditoria.tipo_activo == 'INDIVIDUAL'
    assert auditoria.id_usuario_responsable == 7
    assert auditoria.detalle_tecnico == {
        'error_code': 'SECUENCIA_REPRODUCTIVA_INVALIDA',
        'causa': (
            'No se puede registrar un nacimiento sin eventos previos de '
            'servicio o inseminación sobre este activo.'
        ),
        'id_activo_solicitado': 10,
    }


def test_ca10_fallo_de_auditoria_no_oculta_el_rechazo_funcional() -> None:
    db = DbFake()
    activo_repo = ActivoRepoFake({10: _activo('INDIVIDUAL', 10)})
    uc = _uc(db, activo_repo, EventoRepoFake(), BitacoraRepoFake(falla=True))

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(10, _dto('nacimiento', numero_crias=1), _usuario())

    assert exc.value.code == 'SECUENCIA_REPRODUCTIVA_INVALIDA'
    assert db.commits == 0
    assert db.rollbacks == 2
