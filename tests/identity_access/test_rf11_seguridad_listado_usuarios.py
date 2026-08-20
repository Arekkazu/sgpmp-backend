"""Regresiones estructurales del listado administrativo RF-11."""
from __future__ import annotations

import ast
from pathlib import Path


RUTA_ROUTER = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "identity_access"
    / "infrastructure"
    / "routers"
    / "usuarios_routers.py"
)


def _rutas_get() -> dict[str, ast.Call]:
    arbol = ast.parse(RUTA_ROUTER.read_text(encoding="utf-8"))
    rutas = {}

    for nodo in ast.walk(arbol):
        if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        for decorador in nodo.decorator_list:
            if not isinstance(decorador, ast.Call):
                continue

            funcion = decorador.func

            if not (
                isinstance(funcion, ast.Attribute)
                and isinstance(funcion.value, ast.Name)
                and funcion.value.id == "router"
                and funcion.attr == "get"
                and decorador.args
                and isinstance(decorador.args[0], ast.Constant)
            ):
                continue

            rutas[decorador.args[0].value] = decorador

    return rutas


def test_no_existe_listado_legacy_sin_autenticacion() -> None:
    """GET /usuarios/ no debe existir como endpoint de listado."""
    assert "/" not in _rutas_get()


def test_listado_administrativo_conserva_rbac() -> None:
    """GET /usuarios/admin debe conservar el permiso de lectura de usuarios."""
    decorador = _rutas_get()["/admin"]

    dependencias = next(
        palabra.value
        for palabra in decorador.keywords
        if palabra.arg == "dependencies"
    )

    assert "require_permission(1, 2)" in ast.unparse(dependencias)