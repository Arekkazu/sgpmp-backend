"""INC-M02-37-G33 (#462), RF-37: `es_transicion_no_estandar` debe quedar persistido.

El POST /activos-biologicos/{id}/fases devolvía `true` porque eco-aba el valor en
memoria, pero `crear_gestion_fase` no lo escribía y `obtener_gestiones_fases` no
lo leía: el historial siempre lo mostraba `false`. Estas pruebas fijan que el
valor viaja al INSERT, que el eco sale de la fila persistida y que la lectura del
historial lo mapea.
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.biological_assets.domain.entities.activo_biologico import GestionFase
from src.biological_assets.infrastructure.repositories.activo_biologico_repository import (
    SqlAlchemyActivoBiologicoRepository,
)

AHORA = datetime.now(timezone.utc)


class _Fila:
    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)


class _Resultado:
    def __init__(self, filas: list[_Fila]) -> None:
        self._filas = filas

    def fetchone(self):
        return self._filas[0] if self._filas else None

    def fetchall(self):
        return self._filas


class DbFake:
    """Registra cada `execute` y devuelve resultados canned en orden."""

    def __init__(self, resultados: list[list[_Fila]]) -> None:
        self._cola = [_Resultado(f) for f in resultados]
        self.llamadas: list[tuple[str, dict]] = []

    def execute(self, stmt, params=None):
        self.llamadas.append((str(stmt), params or {}))
        return self._cola.pop(0)


def _gestion(es_no_estandar: bool) -> GestionFase:
    return GestionFase(
        id_gestion_fases=0,
        id_activo_biologico=7,
        id_ciclo_productiva=3,
        id_ciclos_productivo_biologico=31,
        nombre_ciclo="Ciclo completo trucha 2025-A",
        fecha_inicio=AHORA,
        es_activa=True,
        id_usuario=9,
        es_transicion_no_estandar=es_no_estandar,
    )


def _fila_insertada(es_no_estandar: bool) -> _Fila:
    return _Fila(
        id_gestion_fases=55, fecha_inicio=AHORA, fecha_finalizacion=None, es_activa=True,
        id_usuario=9, motivo_cambio=None, es_transicion_no_estandar=es_no_estandar,
    )


def test_crear_gestion_fase_envia_el_flag_al_insert() -> None:
    db = DbFake([[_fila_insertada(True)]])

    SqlAlchemyActivoBiologicoRepository(db).crear_gestion_fase(_gestion(True))

    sql, params = db.llamadas[0]
    assert "es_transicion_no_estandar" in sql.split("VALUES")[0]
    assert params["es_no_estandar"] is True


def test_crear_gestion_fase_estandar_persiste_false() -> None:
    db = DbFake([[_fila_insertada(False)]])

    resultado = SqlAlchemyActivoBiologicoRepository(db).crear_gestion_fase(_gestion(False))

    assert db.llamadas[0][1]["es_no_estandar"] is False
    assert resultado.es_transicion_no_estandar is False


def test_crear_gestion_fase_el_eco_sale_de_la_fila_persistida_no_de_la_memoria() -> None:
    """Si la BD devolviera `false` (columna sin migrar o no escrita), el POST no
    debe afirmar `true`: era exactamente la contradicción POST vs GET del issue."""
    db = DbFake([[_fila_insertada(False)]])

    resultado = SqlAlchemyActivoBiologicoRepository(db).crear_gestion_fase(_gestion(True))

    assert resultado.es_transicion_no_estandar is False


def test_obtener_gestiones_fases_mapea_el_flag_del_historial() -> None:
    fila = _Fila(
        id_gestion_fases=55, id_activo_biologico=7, id_ciclo_productiva=3,
        id_ciclos_productivo_biologico=33, nombre_ciclo="Ciclo completo trucha 2025-A",
        fecha_inicio=AHORA, fecha_finalizacion=None, es_activa=True, id_usuario=9,
        motivo_cambio=None, es_transicion_no_estandar=True, total_pasos=3,
    )
    fases_del_ciclo = [
        _Fila(id_ciclos_productivo_biologico=31, nombre_fase="Alevinaje"),
        _Fila(id_ciclos_productivo_biologico=32, nombre_fase="Juvenil"),
        _Fila(id_ciclos_productivo_biologico=33, nombre_fase="Engorde"),
    ]
    db = DbFake([[fila], fases_del_ciclo])

    historial = SqlAlchemyActivoBiologicoRepository(db).obtener_gestiones_fases(7)

    assert "gf.es_transicion_no_estandar" in db.llamadas[0][0]
    assert historial[0].es_transicion_no_estandar is True
    assert historial[0].paso_actual == 3
