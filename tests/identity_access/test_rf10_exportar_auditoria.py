"""Pruebas unitarias de la exportación del historial de auditoría RF-10."""
from datetime import datetime, timezone

import pytest

from src.identity_access.application.use_cases.auditoria.exportar_auditoria_use_case import (
    LIMITE_EXPORTACION,
    TIPO_EXPORTACION_AUDITORIA,
    ExportarAuditoriaUseCase,
)
from src.identity_access.domain.entities.evento import Evento
from src.shared.errors import InfrastructureError, ValidationError


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class EventoRepoFake:
    def __init__(
        self,
        eventos: list[Evento],
        total: int | None = None,
        clasificacion: dict[int, str] | None = None,
    ) -> None:
        self.eventos = eventos
        self.total = total if total is not None else len(eventos)
        self.clasificacion = clasificacion or {e.id_evento: "INTEGRO" for e in eventos}
        self.registrados: list[dict] = []
        self.filtros_clasificar: dict | None = None
        self.filtros_iterar: dict | None = None

    def contar_eventos(self, **filtros) -> int:
        return self.total

    def clasificar_conjunto(self, **filtros) -> dict[int, str]:
        self.filtros_clasificar = filtros
        return self.clasificacion

    def iterar_eventos(self, **filtros):
        self.filtros_iterar = filtros
        yield from self.eventos

    def registrar(self, **evento) -> None:
        self.registrados.append(evento)


class UsuarioRepoFake:
    def __init__(self, existe: bool = True) -> None:
        self.existe = existe

    def obtener_por_id(self, id_usuario: int):
        return object() if self.existe else None


class UsuarioActualFake:
    id_usuario = 7
    id_rol = 1


def evento(id_evento: int, **overrides) -> Evento:
    base = dict(
        id_evento=id_evento,
        tipo_evento=1,
        fecha_evento=datetime(2026, 1, 1, tzinfo=timezone.utc),
        modulo="IDENTITY_ACCESS",
        resultado="EXITOSO",
        detalle={},
        id_usuario=7,
        categoria="AUTENTICACION",
        estado="ACTIVO",
        nombre_usuario="Ana Torres",
        direccion_ip="10.0.0.7",
        descripcion="Registro de usuario",
    )
    base.update(overrides)
    return Evento(**base)


def _caso(repo: EventoRepoFake, db: DbFake, usuarios=None) -> ExportarAuditoriaUseCase:
    return ExportarAuditoriaUseCase(
        eventos_repo=repo, db=db, usuarios_repo=usuarios or UsuarioRepoFake()
    )


def _exportar(caso: ExportarAuditoriaUseCase, **kwargs):
    parametros = dict(
        usuario_actual=UsuarioActualFake(),
        id_usuario=None,
        tipo_evento=None,
        fecha_desde=None,
        fecha_hasta=None,
    )
    parametros.update(kwargs)
    return caso.execute(**parametros)


def test_recorre_el_conjunto_completo_conservando_los_filtros() -> None:
    repo = EventoRepoFake([evento(1), evento(2)])
    caso = _caso(repo, DbFake())
    desde = datetime(2025, 1, 1, tzinfo=timezone.utc)

    lineas, total, exportados = _exportar(caso, id_usuario=7, tipo_evento=1, fecha_desde=desde)
    list(lineas)

    assert (total, exportados) == (2, 2)
    assert repo.filtros_iterar["limite"] == LIMITE_EXPORTACION
    assert repo.filtros_iterar["id_usuario"] == 7
    assert repo.filtros_iterar["tipo_evento"] == 1
    assert repo.filtros_iterar["fecha_desde"] == desde


def test_registra_un_unico_evento_de_exportacion() -> None:
    repo = EventoRepoFake([evento(i) for i in range(1, 21)])
    db = DbFake()

    lineas, _, _ = _exportar(_caso(repo, db))
    list(lineas)

    assert len(repo.registrados) == 1
    assert db.commits == 1
    registrado = repo.registrados[0]
    assert registrado["tipo_evento"] == TIPO_EXPORTACION_AUDITORIA
    assert registrado["detalle"]["total_exportado"] == 20
    assert registrado["detalle"]["truncado"] is False


def test_trunca_en_el_limite_y_lo_reporta() -> None:
    repo = EventoRepoFake([evento(1)], total=LIMITE_EXPORTACION + 500)

    _, total, exportados = _exportar(_caso(repo, DbFake()))

    assert total == LIMITE_EXPORTACION + 500
    assert exportados == LIMITE_EXPORTACION
    assert repo.registrados[0]["detalle"]["truncado"] is True


def test_un_registro_manipulado_aborta_antes_de_emitir_y_sin_auditar() -> None:
    repo = EventoRepoFake([evento(1), evento(2)], clasificacion={1: "INTEGRO", 2: "MANIPULADO"})
    db = DbFake()

    with pytest.raises(InfrastructureError) as excinfo:
        _exportar(_caso(repo, db))

    assert excinfo.value.code == "INTEGRIDAD_AUDITORIA_VIOLADA"

    # El evento de exportación no debe quedar: la descarga nunca ocurrió.
    assert repo.registrados == []
    assert db.commits == 0


def test_un_registro_legado_no_aborta_la_exportacion() -> None:
    repo = EventoRepoFake([evento(1)], clasificacion={1: "LEGADO"})

    lineas, _, _ = _exportar(_caso(repo, DbFake()))
    filas = list(lineas)

    assert filas[1].rstrip("\r\n").endswith("LEGADO")


def test_rango_de_fechas_invertido_es_filtro_inconsistente() -> None:
    repo = EventoRepoFake([])

    with pytest.raises(ValidationError) as excinfo:
        _exportar(
            _caso(repo, DbFake()),
            fecha_desde=datetime(2026, 6, 1, tzinfo=timezone.utc),
            fecha_hasta=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    assert excinfo.value.code == "FILTROS_INCONSISTENTES"


def test_usuario_filtrado_inexistente_es_filtro_inconsistente() -> None:
    repo = EventoRepoFake([])

    with pytest.raises(ValidationError) as excinfo:
        _exportar(_caso(repo, DbFake(), UsuarioRepoFake(existe=False)), id_usuario=999)

    assert excinfo.value.code == "FILTROS_INCONSISTENTES"


def test_el_csv_lleva_bom_crlf_y_escapa_comas_comillas_y_saltos() -> None:
    repo = EventoRepoFake([
        evento(1, nombre_usuario="Ramírez, Leandro", descripcion='Intento "fallido"\nrevisado')
    ])

    lineas, _, _ = _exportar(_caso(repo, DbFake()))
    filas = list(lineas)

    assert filas[0].startswith("﻿ID,Usuario,Tipo evento")
    assert filas[0].endswith("\r\n")
    assert '"Ramírez, Leandro"' in filas[1]
    assert '"Intento ""fallido""\nrevisado"' in filas[1]


def test_la_etiqueta_del_tipo_sale_del_catalogo_del_servidor() -> None:
    repo = EventoRepoFake([evento(1, tipo_evento=26)])

    lineas, _, _ = _exportar(_caso(repo, DbFake()))
    filas = list(lineas)

    assert "EXPORTACION_AUDITORIA" in filas[1]


def test_si_falla_auditar_la_exportacion_el_archivo_igual_se_entrega() -> None:
    repo = EventoRepoFake([evento(1)])
    db = DbFake()
    repo.registrar = lambda **_: (_ for _ in ()).throw(RuntimeError("db caída"))

    lineas, _, exportados = _exportar(_caso(repo, db))

    assert exportados == 1
    assert list(lineas)[1].startswith("1,")
    assert db.rollbacks == 1


def test_el_archivo_no_crece_por_eventos_nuevos_durante_la_exportacion() -> None:
    """El evento de la propia exportación no debe colarse en su propio CSV.

    Se registra entre el conteo y la emisión, así que sin el corte el archivo
    traía una fila más de las que anuncia `X-Registros-Exportados`.
    """
    eventos = [evento(1), evento(2)]
    repo = EventoRepoFake(eventos)
    # El repo devuelve una fila extra, como si hubiera entrado un evento nuevo
    # después del conteo.
    repo.iterar_eventos = lambda **_: iter([*eventos, evento(3)])

    lineas, _, exportados = _exportar(_caso(repo, DbFake()))
    filas = list(lineas)

    assert exportados == 2
    assert len(filas) - 1 == exportados
