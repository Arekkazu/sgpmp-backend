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

from datetime import datetime, timezone

import pytest

from src.biological_assets.application.use_cases.gestion.registrar_evento_reproductivo_use_case import (
    RegistrarEventoReproductivoUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    EventoActivo,
    EventoAuditoria,
    GestionFase,
)
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsulta
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.registrar_evento_reproductivo_dto import (
    RegistrarEventoReproductivoDTO,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError

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
    def __init__(
        self,
        activos: dict[int, ActivoBiologico],
        sin_fase_activa: set[int] | None = None,
    ) -> None:
        self.activos = activos
        # Por defecto todo activo conocido tiene una gestión de fase activa
        # (RF-42/INC-M02-78-G58); listar aquí los que deben simular no tenerla.
        self.sin_fase_activa = sin_fase_activa or set()

    def obtener_por_id(self, id_activo: int, *, ids_fincas_permitidas=None) -> ActivoBiologico | None:
        activo = self.activos.get(id_activo)
        if activo is None or ids_fincas_permitidas is None:
            return activo
        infra_a_finca = {1: 1, 2: 2}  # coincide con InfraPortFake
        if infra_a_finca.get(activo.id_infraestructura) not in ids_fincas_permitidas:
            return None
        return activo

    def obtener_fase_activa(self, id_activo: int) -> GestionFase | None:
        if id_activo not in self.activos or id_activo in self.sin_fase_activa:
            return None
        return GestionFase(
            id_activo_biologico=id_activo,
            id_ciclo_productiva=1,
            nombre_ciclo='Ciclo de prueba',
            fecha_inicio=datetime.now(timezone.utc),
            es_activa=True,
            id_usuario=1,
        )


class InfraPortFake:
    """id_infraestructura -> id_finca fijo: 1->1, 2->2 (para simular fincas distintas)."""

    _FINCA_POR_INFRA = {1: 1, 2: 2}

    def obtener_activa(self, id_infraestructura: int):
        id_finca = self._FINCA_POR_INFRA.get(id_infraestructura)
        if id_finca is None:
            return None
        return InfraestructuraConsulta(
            id_infraestructura=id_infraestructura,
            nombre=f'Infra {id_infraestructura}',
            tipo='Estanque',
            es_activo=True,
            id_finca=id_finca,
        )


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


def _uc(db, activo_repo, evento_repo, bitacora_repo=None, infra_port=None) -> RegistrarEventoReproductivoUseCase:
    return RegistrarEventoReproductivoUseCase(
        db=db,
        activo_repo=activo_repo,
        evento_repo=evento_repo,
        infra_port=infra_port or InfraPortFake(),
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


def test_padre_de_otra_finca_es_rechazado_como_no_encontrado() -> None:
    """INC-M02-77-G56 / issue #228 (OWASP API1, BOLA): antes de este fix, un
    id_padre de una finca completamente distinta se aceptaba sin validación."""
    db = DbFake()
    padre_otra_finca = _activo('INDIVIDUAL', 20)
    padre_otra_finca.id_infraestructura = 2  # finca 2, vía InfraPortFake
    activo_repo = ActivoRepoFake({10: _activo('INDIVIDUAL', 10), 20: padre_otra_finca})
    evento_repo = EventoRepoFake()
    uc = _uc(db, activo_repo, evento_repo)

    with pytest.raises(NotFoundError) as exc:
        uc.execute(10, _dto('servicio', id_padre=20), _usuario())

    assert exc.value.code == 'ACTIVO_RELACIONADO_NO_ENCONTRADO'
    assert evento_repo.guardado is None
    assert db.commits == 0


def test_padre_inexistente_sigue_siendo_rechazado() -> None:
    db = DbFake()
    activo_repo = ActivoRepoFake({10: _activo('INDIVIDUAL', 10)})
    evento_repo = EventoRepoFake()
    uc = _uc(db, activo_repo, evento_repo)

    with pytest.raises(NotFoundError) as exc:
        uc.execute(10, _dto('servicio', id_padre=999), _usuario())

    assert exc.value.code == 'ACTIVO_RELACIONADO_NO_ENCONTRADO'


def test_padre_inactivo_sigue_siendo_rechazado() -> None:
    db = DbFake()
    padre_inactivo = _activo('INDIVIDUAL', 20, id_estado=EstadoActivo.INACTIVO)
    activo_repo = ActivoRepoFake({10: _activo('INDIVIDUAL', 10), 20: padre_inactivo})
    evento_repo = EventoRepoFake()
    uc = _uc(db, activo_repo, evento_repo)

    with pytest.raises(NotFoundError) as exc:
        uc.execute(10, _dto('servicio', id_padre=20), _usuario())

    assert exc.value.code == 'ACTIVO_RELACIONADO_NO_ENCONTRADO'


def test_madre_de_otra_finca_es_rechazada() -> None:
    """INC-M02-77-G56: id_madre nunca se validaba (ni existencia, ni estado, ni
    finca) porque no tiene requisito de categoría como id_padre. Se corrige
    para validarla igual que id_padre cuando se envía."""
    db = DbFake()
    madre_otra_finca = _activo('INDIVIDUAL', 30)
    madre_otra_finca.id_infraestructura = 2
    activo_repo = ActivoRepoFake({10: _activo('INDIVIDUAL', 10), 30: madre_otra_finca})
    evento_repo = EventoRepoFake()
    uc = _uc(db, activo_repo, evento_repo)

    with pytest.raises(NotFoundError) as exc:
        uc.execute(10, _dto('nacimiento', numero_crias=1, id_madre=30), _usuario())

    assert exc.value.code == 'ACTIVO_RELACIONADO_NO_ENCONTRADO'
    assert evento_repo.guardado is None


def test_madre_en_la_misma_finca_es_aceptada() -> None:
    db = DbFake()
    activo_repo = ActivoRepoFake({10: _activo('INDIVIDUAL', 10), 30: _activo('INDIVIDUAL', 30)})
    evento_repo = EventoRepoFake()
    evento_repo.tiene_servicio_o_inseminacion_previa = lambda _id: True
    evento_repo.tiene_diagnostico_positivo_previo = lambda _id: True
    uc = _uc(db, activo_repo, evento_repo)

    resultado = uc.execute(10, _dto('nacimiento', numero_crias=1, id_madre=30), _usuario())

    assert resultado is not None
    assert evento_repo.guardado.reproductivo.id_madre == 30


def test_activo_objetivo_fuera_del_alcance_de_finca_es_404() -> None:
    """RF-25: antes de este fix, ni siquiera el activo objetivo (no solo
    id_padre) se validaba contra el alcance de finca del usuario."""
    db = DbFake()
    activo_otra_finca = _activo('INDIVIDUAL', 10)
    activo_otra_finca.id_infraestructura = 2
    activo_repo = ActivoRepoFake({10: activo_otra_finca})
    evento_repo = EventoRepoFake()
    uc = _uc(db, activo_repo, evento_repo)

    with pytest.raises(NotFoundError) as exc:
        uc.execute(10, _dto('nacimiento', numero_crias=1), _usuario(), ids_fincas_permitidas=[1])

    assert exc.value.code == 'ACTIVO_NO_ENCONTRADO'


def test_ca10_fallo_de_auditoria_no_oculta_el_rechazo_funcional() -> None:
    db = DbFake()
    activo_repo = ActivoRepoFake({10: _activo('INDIVIDUAL', 10)})
    uc = _uc(db, activo_repo, EventoRepoFake(), BitacoraRepoFake(falla=True))

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(10, _dto('nacimiento', numero_crias=1), _usuario())

    assert exc.value.code == 'SECUENCIA_REPRODUCTIVA_INVALIDA'
    assert db.commits == 0
    assert db.rollbacks == 2


def test_sin_fase_activa_es_409_para_cualquier_categoria() -> None:
    """INC-M02-78-G58 / issue #229: RF-42 exige "una fase productiva compatible
    con reproducción" -- antes de este fix no se validaba en absoluto."""
    db = DbFake()
    activo_repo = ActivoRepoFake({10: _activo('INDIVIDUAL', 10)}, sin_fase_activa={10})
    evento_repo = EventoRepoFake()
    uc = _uc(db, activo_repo, evento_repo)

    with pytest.raises(ConflictError) as exc:
        uc.execute(10, _dto('diagnostico'), _usuario())

    assert exc.value.code == 'FASE_NO_COMPATIBLE_REPRODUCCION'
    assert exc.value.message == 'La fase productiva del activo no permite registrar este tipo de evento.'
    assert evento_repo.guardado is None
    assert db.commits == 0


def test_sin_fase_activa_bloquea_incluso_poblacional_nacimiento() -> None:
    """La validación de fase corre antes que cualquier lógica de secuencia o
    de tipo de activo -- ningún camino la evade."""
    db = DbFake()
    activo_repo = ActivoRepoFake({10: _activo('POBLACIONAL', 10)}, sin_fase_activa={10})
    evento_repo = EventoRepoFake()
    uc = _uc(db, activo_repo, evento_repo)

    with pytest.raises(ConflictError) as exc:
        uc.execute(10, _dto('nacimiento', numero_crias=1), _usuario())

    assert exc.value.code == 'FASE_NO_COMPATIBLE_REPRODUCCION'
    assert evento_repo.guardado is None


def test_con_fase_activa_el_evento_se_registra_normalmente() -> None:
    """No regresión: el camino feliz existente sigue funcionando con la
    gestión de fase activa que ActivoRepoFake da por defecto."""
    db = DbFake()
    activo_repo = ActivoRepoFake({10: _activo('INDIVIDUAL', 10)})
    evento_repo = EventoRepoFake()
    evento_repo.tiene_servicio_o_inseminacion_previa = lambda _id: True
    uc = _uc(db, activo_repo, evento_repo)

    resultado = uc.execute(10, _dto('diagnostico'), _usuario())

    assert resultado is not None
    assert db.commits == 1
