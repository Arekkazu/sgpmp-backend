"""Pruebas de regresión para las categorías de auditoría de RF-10."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.identity_access.application.use_cases.auditoria.consultar_auditoria_use_case import (
    ConsultarAuditoriaUseCase,
)
from src.identity_access.domain.value_objects.evento_categoria import (
    EventoCategoria,
    categoria_para_tipo_evento,
    tipos_evento_para_categoria,
)
from src.identity_access.infrastructure.repositories.evento_repository import (
    SqlAlchemyEventoRepository,
)
from src.shared.errors import InfrastructureError


TIPOS_POR_CATEGORIA = {
    EventoCategoria.AUTENTICACION: (*range(1, 9), *range(20, 25)),
    EventoCategoria.MODIFICACION: tuple(range(9, 16)),
    EventoCategoria.CONSULTA: tuple(range(16, 20)),
}


class DbFake:
    """Doble mínimo para comprobar lo entregado por el repositorio al ORM."""

    def __init__(self) -> None:
        self.eventos = []
        self.flushes = 0

    def add(self, evento) -> None:
        self.eventos.append(evento)

    def flush(self) -> None:
        self.flushes += 1


class EventoRepoConsultaFake:
    """Captura los filtros enviados por el caso de uso."""

    def __init__(self) -> None:
        self.filtro_conteo = None
        self.filtro_listado = None
        self.eventos_registrados = []

    def contar_eventos(self, **filtros) -> int:
        self.filtro_conteo = filtros
        return 0

    def listar_eventos(self, **filtros) -> list:
        self.filtro_listado = filtros
        return []

    def registrar(self, **evento) -> None:
        self.eventos_registrados.append(evento)


class UnidadTrabajoFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


@pytest.mark.parametrize(
    ("categoria", "tipos_evento"),
    TIPOS_POR_CATEGORIA.items(),
)
def test_catalogo_clasifica_todos_los_tipos_del_modulo(
    categoria: EventoCategoria,
    tipos_evento: tuple[int, ...],
) -> None:
    assert tipos_evento_para_categoria(categoria) == tipos_evento
    assert all(
        categoria_para_tipo_evento(tipo_evento) == categoria
        for tipo_evento in tipos_evento
    )


def test_catalogo_cubre_todos_los_tipos_actuales_sin_duplicados() -> None:
    tipos = [
        tipo
        for tipos_categoria in TIPOS_POR_CATEGORIA.values()
        for tipo in tipos_categoria
    ]

    assert sorted(tipos) == list(range(1, 25))
    assert len(tipos) == len(set(tipos))


def test_tipo_sin_categoria_no_usa_un_valor_por_defecto() -> None:
    with pytest.raises(ValueError, match="no tiene una categoría configurada"):
        categoria_para_tipo_evento(999)


@pytest.mark.parametrize(
    ("tipo_evento", "categoria_esperada"),
    [
        (3, EventoCategoria.AUTENTICACION),
        (12, EventoCategoria.MODIFICACION),
        (17, EventoCategoria.CONSULTA),
        (20, EventoCategoria.AUTENTICACION),
        (24, EventoCategoria.AUTENTICACION),
    ],
)
def test_repositorio_guarda_la_categoria_real(
    tipo_evento: int,
    categoria_esperada: EventoCategoria,
) -> None:
    db = DbFake()
    repo = SqlAlchemyEventoRepository(db)

    repo.registrar(
        tipo_evento=tipo_evento,
        exitoso=True,
        id_usuario=42,
        detalle={"prueba": True},
    )

    assert db.eventos[0].categoria == categoria_esperada.value
    assert db.flushes == 1


def test_repositorio_rechaza_tipo_no_catalogado() -> None:
    db = DbFake()
    repo = SqlAlchemyEventoRepository(db)

    with pytest.raises(InfrastructureError) as error:
        repo.registrar(
            tipo_evento=999,
            exitoso=True,
            id_usuario=42,
            detalle={},
        )

    assert error.value.code == "CATEGORIA_EVENTO_NO_DEFINIDA"
    assert db.eventos == []
    assert db.flushes == 0


def test_lectura_corrige_categoria_historica_sin_modificar_la_fila() -> None:
    fila_historica = SimpleNamespace(
        id_evento=7,
        tipo_evento=12,
        fecha_evento=datetime.now(timezone.utc),
        modulo="MODULO1",
        resultado="EXITOSO",
        detalle={"accion": "EDITAR_ROL"},
        id_usuario=42,
        categoria="AUTENTICACION",
        estado="PROCESADO",
        id_sesion=None,
    )

    evento = SqlAlchemyEventoRepository._a_entidad(fila_historica)

    assert evento.categoria == EventoCategoria.MODIFICACION.value
    assert fila_historica.categoria == "AUTENTICACION"


def test_caso_de_uso_propaga_el_filtro_de_categoria() -> None:
    repo = EventoRepoConsultaFake()
    db = UnidadTrabajoFake()
    use_case = ConsultarAuditoriaUseCase(eventos_repo=repo, db=db)

    use_case.execute(
        usuario_actual=SimpleNamespace(id_usuario=42, id_rol=1),
        id_usuario=None,
        tipo_evento=None,
        categoria=EventoCategoria.CONSULTA,
        fecha_desde=None,
        fecha_hasta=None,
        pagina=1,
        tamano=20,
    )

    assert repo.filtro_conteo["categoria"] == EventoCategoria.CONSULTA
    assert repo.filtro_listado["categoria"] == EventoCategoria.CONSULTA
    assert repo.eventos_registrados[0]["detalle"]["filtros"]["categoria"] == "CONSULTA"
    assert db.commits == 1
