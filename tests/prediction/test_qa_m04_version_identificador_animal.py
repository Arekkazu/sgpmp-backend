# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-03 | Arekkazu | QA-M04 RF-69: la versión trae el identificador del animal además del id |
"""QA-M04 RF-69: Modelos IA mostraba «Animal #49»; la versión ahora trae su identificador."""
from __future__ import annotations

from src.prediction.infrastructure.routers.version_modelo_router import _respuestas

_BASE = {"id_version_modelo": 1, "nombre_version": "v", "estado_version": "SOMBRA",
         "esta_produccion": False, "fuente_datos": "SINTETICA"}


class _Version:
    def __init__(self, id_activo):
        self._datos = {**_BASE, "id_activo_biologico": id_activo}

    def __getattr__(self, nombre):
        return self._datos.get(nombre)


class _Db:
    def __init__(self):
        self.consultas = 0

    def execute(self, sql, params):
        self.consultas += 1
        filas = [(i, f"BOV-{i:03d}") for i in params["ids"] if i != 7]
        return type("R", (), {"all": lambda self: filas})()


def test_cada_version_individual_trae_el_identificador_en_una_sola_consulta():
    db = _Db()
    r = _respuestas(db, [_Version(49), _Version(None), _Version(49), _Version(7)])
    assert [x.identificador_activo for x in r] == ["BOV-049", None, "BOV-049", None]
    assert db.consultas == 1


def test_sin_versiones_individuales_no_consulta():
    db = _Db()
    _respuestas(db, [_Version(None)])
    assert db.consultas == 0
