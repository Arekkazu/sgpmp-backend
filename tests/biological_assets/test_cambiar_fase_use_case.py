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
from src.shared.errors import BusinessRuleError, ConflictError, ValidationError


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


def _ciclo_3fases() -> CicloProductivoConsulta:
    return CicloProductivoConsulta(
        id_ciclo_productivo=4,
        nombre='Cachama',
        fases=[
            FaseCiclo(1, 4, 'Alevinaje', 30),
            FaseCiclo(2, 4, 'Engorde', 60),
            FaseCiclo(3, 4, 'Finalizacion', 15),
        ],
    )


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=7, id_token=1, id_rol=1)


def _gestion_anterior(fecha: datetime, *, id_ciclos_productivo_biologico: int = 1) -> GestionFase:
    return GestionFase(
        id_gestion_fases=100,
        id_activo_biologico=10,
        id_ciclo_productiva=4,
        id_ciclos_productivo_biologico=id_ciclos_productivo_biologico,
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


# ── RF-37 (tarea Taiga fase_destino/confirmacion_no_estandar) ───────────────

def test_fase_destino_id_estandar_se_comporta_igual_que_sin_especificar() -> None:
    """fase_destino_id = la fase estándar siguiente -> mismo resultado que
    omitir el campo, sin exigir confirmación."""
    fecha_anterior = datetime(2026, 8, 1, tzinfo=timezone.utc)
    fecha_cambio = datetime(2026, 9, 11, tzinfo=timezone.utc)
    db = DbFake()
    repo = ActivoRepoFake(_activo(), [_gestion_anterior(fecha_anterior)])
    use_case = CambiarFaseUseCase(db=db, repo=repo, ciclo_port=CicloPortFake(_ciclo()))

    resultado = use_case.execute(
        10,
        CambiarFaseDTO(id_ciclo_productiva=4, fecha_inicio=fecha_cambio, fase_destino_id=2),
        _usuario(),
    )

    assert resultado.nombre_fase_actual == 'Engorde'
    assert resultado.paso_actual == 2
    assert resultado.es_transicion_no_estandar is False


def test_fase_destino_salto_hacia_adelante_sin_confirmar_lanza_409() -> None:
    fecha_anterior = datetime(2026, 8, 1, tzinfo=timezone.utc)
    db = DbFake()
    repo = ActivoRepoFake(_activo(), [_gestion_anterior(fecha_anterior, id_ciclos_productivo_biologico=1)])
    use_case = CambiarFaseUseCase(db=db, repo=repo, ciclo_port=CicloPortFake(_ciclo_3fases()))

    with pytest.raises(ConflictError) as exc:
        use_case.execute(
            10,
            CambiarFaseDTO(id_ciclo_productiva=4, fase_destino_id=3),  # salta Engorde
            _usuario(),
        )

    assert exc.value.code == 'TRANSICION_NO_ESTANDAR_SIN_CONFIRMAR'
    assert repo.creadas == []
    assert db.commits == 0


def test_fase_destino_salto_hacia_adelante_confirmado_procede() -> None:
    fecha_anterior = datetime(2026, 8, 1, tzinfo=timezone.utc)
    db = DbFake()
    repo = ActivoRepoFake(_activo(), [_gestion_anterior(fecha_anterior, id_ciclos_productivo_biologico=1)])
    use_case = CambiarFaseUseCase(db=db, repo=repo, ciclo_port=CicloPortFake(_ciclo_3fases()))

    resultado = use_case.execute(
        10,
        CambiarFaseDTO(id_ciclo_productiva=4, fase_destino_id=3, confirmacion_no_estandar=True),
        _usuario(),
    )

    assert resultado.nombre_fase_actual == 'Finalizacion'
    assert resultado.paso_actual == 3
    assert resultado.es_transicion_no_estandar is True
    assert db.commits == 1


def test_fase_destino_retroceso_sin_confirmar_lanza_409() -> None:
    fecha_anterior = datetime(2026, 8, 1, tzinfo=timezone.utc)
    db = DbFake()
    repo = ActivoRepoFake(_activo(), [_gestion_anterior(fecha_anterior, id_ciclos_productivo_biologico=2)])
    use_case = CambiarFaseUseCase(db=db, repo=repo, ciclo_port=CicloPortFake(_ciclo_3fases()))

    with pytest.raises(ConflictError) as exc:
        use_case.execute(
            10,
            CambiarFaseDTO(id_ciclo_productiva=4, fase_destino_id=1),  # retrocede a Alevinaje
            _usuario(),
        )

    assert exc.value.code == 'TRANSICION_NO_ESTANDAR_SIN_CONFIRMAR'


def test_fase_destino_id_inexistente_en_el_ciclo_lanza_validation_error() -> None:
    db = DbFake()
    repo = ActivoRepoFake(_activo())
    use_case = CambiarFaseUseCase(db=db, repo=repo, ciclo_port=CicloPortFake(_ciclo()))

    with pytest.raises(ValidationError) as exc:
        use_case.execute(
            10,
            CambiarFaseDTO(id_ciclo_productiva=4, fase_destino_id=999),
            _usuario(),
        )

    assert exc.value.code == 'FASE_DESTINO_INVALIDA'
    assert exc.value.field == 'fase_destino_id'


def test_ciclo_completado_sin_fase_destino_sigue_lanzando_ciclo_completado() -> None:
    """Sin fase_destino_id, el comportamiento histórico se conserva
    exactamente: ciclo agotado -> CICLO_COMPLETADO, no 409."""
    fecha_1 = datetime(2026, 8, 1, tzinfo=timezone.utc)
    fecha_2 = datetime(2026, 8, 15, tzinfo=timezone.utc)
    db = DbFake()
    gestiones = [
        _gestion_anterior(fecha_1, id_ciclos_productivo_biologico=1),
        GestionFase(
            id_gestion_fases=101, id_activo_biologico=10, id_ciclo_productiva=4,
            id_ciclos_productivo_biologico=2, nombre_ciclo='Cachama',
            nombre_fase_actual='Engorde', paso_actual=2, total_pasos=2,
            fecha_inicio=fecha_2, fecha_finalizacion=None, es_activa=True, id_usuario=3,
        ),
    ]
    repo = ActivoRepoFake(_activo(), gestiones)
    use_case = CambiarFaseUseCase(db=db, repo=repo, ciclo_port=CicloPortFake(_ciclo()))

    with pytest.raises(BusinessRuleError) as exc:
        use_case.execute(10, CambiarFaseDTO(id_ciclo_productiva=4), _usuario())

    assert exc.value.code == 'CICLO_COMPLETADO'


def test_reentrar_fase_tras_completar_ciclo_requiere_confirmacion() -> None:
    """Con fase_destino_id explícito, un ciclo ya completado no bloquea de
    entrada -- pero re-entrar a cualquier fase sigue siendo no estándar."""
    fecha_1 = datetime(2026, 8, 1, tzinfo=timezone.utc)
    fecha_2 = datetime(2026, 8, 15, tzinfo=timezone.utc)
    db = DbFake()
    gestiones = [
        _gestion_anterior(fecha_1, id_ciclos_productivo_biologico=1),
        GestionFase(
            id_gestion_fases=101, id_activo_biologico=10, id_ciclo_productiva=4,
            id_ciclos_productivo_biologico=2, nombre_ciclo='Cachama',
            nombre_fase_actual='Engorde', paso_actual=2, total_pasos=2,
            fecha_inicio=fecha_2, fecha_finalizacion=None, es_activa=True, id_usuario=3,
        ),
    ]
    repo = ActivoRepoFake(_activo(), gestiones)
    use_case = CambiarFaseUseCase(db=db, repo=repo, ciclo_port=CicloPortFake(_ciclo()))

    with pytest.raises(ConflictError) as exc:
        use_case.execute(
            10,
            CambiarFaseDTO(id_ciclo_productiva=4, fase_destino_id=1),
            _usuario(),
        )
    assert exc.value.code == 'TRANSICION_NO_ESTANDAR_SIN_CONFIRMAR'

    resultado = use_case.execute(
        10,
        CambiarFaseDTO(id_ciclo_productiva=4, fase_destino_id=1, confirmacion_no_estandar=True),
        _usuario(),
    )
    assert resultado.nombre_fase_actual == 'Alevinaje'
    assert resultado.es_transicion_no_estandar is True


def test_fecha_inicio_futura_rechazada_por_el_dto() -> None:
    futura = datetime.now(timezone.utc).replace(year=datetime.now(timezone.utc).year + 1)
    with pytest.raises(ValueError, match='no puede ser futura'):
        CambiarFaseDTO(id_ciclo_productiva=4, fecha_inicio=futura)


def test_fecha_inicio_pasada_es_aceptada_por_el_dto() -> None:
    pasada = datetime(2026, 1, 1, tzinfo=timezone.utc)
    dto = CambiarFaseDTO(id_ciclo_productiva=4, fecha_inicio=pasada)
    assert dto.fecha_inicio == pasada
