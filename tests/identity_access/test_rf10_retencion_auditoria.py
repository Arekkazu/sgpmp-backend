"""Pruebas unitarias de la política de retención de auditoría RF-10."""
from datetime import datetime, timezone

import pytest

from src.identity_access.application.use_cases.auditoria import (
    archivar_auditoria_use_case as modulo_caso,
)
from src.identity_access.application.use_cases.auditoria.archivar_auditoria_use_case import (
    ArchivarAuditoriaUseCase,
    restar_meses,
)


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class EventoRepoArchivoFake:
    def __init__(self, lotes: list[int | Exception], bloqueo: bool = True) -> None:
        self.lotes = iter(lotes)
        self.bloqueo = bloqueo
        self.llamadas = []

    def adquirir_bloqueo_archivado(self) -> bool:
        return self.bloqueo

    def archivar_eventos_anteriores(self, fecha_corte, limite) -> int:
        self.llamadas.append((fecha_corte, limite))
        resultado = next(self.lotes)
        if isinstance(resultado, Exception):
            raise resultado
        return resultado


def test_restar_doce_meses_usa_calendario_y_conserva_zona_horaria() -> None:
    referencia = datetime(2024, 2, 29, 8, 30, tzinfo=timezone.utc)

    corte = restar_meses(referencia, 12)

    assert corte == datetime(2023, 2, 28, 8, 30, tzinfo=timezone.utc)


def test_archivado_procesa_lotes_y_confirma_una_sola_transaccion(monkeypatch) -> None:
    monkeypatch.setattr(modulo_caso, "TAMANO_LOTE_ARCHIVADO", 2)
    monkeypatch.setattr(modulo_caso, "MAXIMO_LOTES_POR_EJECUCION", 3)
    repo = EventoRepoArchivoFake([2, 1])
    db = DbFake()
    referencia = datetime(2026, 8, 27, 4, 0, tzinfo=timezone.utc)

    resultado = ArchivarAuditoriaUseCase(repo, db).execute(referencia)

    assert resultado.fecha_corte == datetime(2025, 8, 27, 4, 0, tzinfo=timezone.utc)
    assert resultado.eventos_archivados == 3
    assert resultado.lotes_procesados == 2
    assert resultado.bloqueo_adquirido is True
    assert resultado.limite_alcanzado is False
    assert [limite for _, limite in repo.llamadas] == [2, 2]
    assert db.commits == 1
    assert db.rollbacks == 0


def test_archivado_no_compite_si_otra_replica_tiene_el_bloqueo() -> None:
    repo = EventoRepoArchivoFake([], bloqueo=False)
    db = DbFake()

    resultado = ArchivarAuditoriaUseCase(repo, db).execute()

    assert resultado.bloqueo_adquirido is False
    assert resultado.eventos_archivados == 0
    assert repo.llamadas == []
    assert db.commits == 0
    assert db.rollbacks == 1


def test_archivado_reporta_si_alcanza_el_maximo_de_lotes(monkeypatch) -> None:
    monkeypatch.setattr(modulo_caso, "TAMANO_LOTE_ARCHIVADO", 2)
    monkeypatch.setattr(modulo_caso, "MAXIMO_LOTES_POR_EJECUCION", 2)
    repo = EventoRepoArchivoFake([2, 2])
    db = DbFake()

    resultado = ArchivarAuditoriaUseCase(repo, db).execute()

    assert resultado.eventos_archivados == 4
    assert resultado.lotes_procesados == 2
    assert resultado.limite_alcanzado is True
    assert db.commits == 1


def test_archivado_revierte_la_transaccion_si_falla_un_lote() -> None:
    repo = EventoRepoArchivoFake([RuntimeError("sin espacio")])
    db = DbFake()

    with pytest.raises(RuntimeError, match="sin espacio"):
        ArchivarAuditoriaUseCase(repo, db).execute()

    assert db.commits == 0
    assert db.rollbacks == 1
