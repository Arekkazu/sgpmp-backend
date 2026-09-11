"""Regresión de auditoría obligatoria para registro y activación."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

CREAR_PATH = (
    ROOT
    / "src/identity_access/application/use_cases/registro/crear_usuario_use_case.py"
)

ACTIVAR_PATH = (
    ROOT
    / "src/identity_access/application/use_cases/registro/activar_cuenta_use_case.py"
)

ROUTER_PATH = (
    ROOT
    / "src/identity_access/infrastructure/routers/usuarios_routers.py"
)


def _metodo_execute(ruta: Path) -> ast.FunctionDef:
    modulo = ast.parse(ruta.read_text(encoding="utf-8"))
    clase = next(n for n in modulo.body if isinstance(n, ast.ClassDef))

    return next(
        n
        for n in clase.body
        if isinstance(n, ast.FunctionDef) and n.name == "execute"
    )


def _llamadas_en_orden(ruta: Path) -> list[str]:
    execute = _metodo_execute(ruta)

    return [
        ast.unparse(n.func)
        for n in ast.walk(execute)
        if isinstance(n, ast.Call)
    ]


def _funcion_router(nombre: str) -> ast.FunctionDef:
    modulo = ast.parse(ROUTER_PATH.read_text(encoding="utf-8"))

    return next(
        nodo
        for nodo in modulo.body
        if isinstance(nodo, ast.FunctionDef) and nodo.name == nombre
    )


def test_registro_audita_en_la_misma_transaccion() -> None:
    fuente = CREAR_PATH.read_text(encoding="utf-8")
    llamadas = _llamadas_en_orden(CREAR_PATH)

    assert "TIPO_REGISTRO_USUARIO = 1" in fuente
    assert "self.eventos_repo.registrar" in llamadas

    assert fuente.index("self.cuentas_repo.crear") < fuente.index(
        "self.eventos_repo.registrar"
    )

    assert fuente.index("self.eventos_repo.registrar") < fuente.index(
        "self.db.commit"
    )


def test_activacion_audita_en_la_misma_transaccion() -> None:
    fuente = ACTIVAR_PATH.read_text(encoding="utf-8")
    llamadas = _llamadas_en_orden(ACTIVAR_PATH)

    assert "TIPO_ACTIVACION_CUENTA = 2" in fuente
    assert "self.eventos_repo.registrar" in llamadas

    assert fuente.index("self.cuentas_repo.guardar") < fuente.index(
        "self.eventos_repo.registrar"
    )

    assert fuente.index("self.eventos_repo.registrar") < fuente.index(
        "self.db.commit"
    )


def test_router_inyecta_eventos_y_contexto_del_request() -> None:
    fuente = ROUTER_PATH.read_text(encoding="utf-8")

    for nombre_funcion in ("crear_usuario", "activar_cuenta"):
        funcion = _funcion_router(nombre_funcion)
        bloque = ast.get_source_segment(fuente, funcion)

        assert bloque is not None
        assert "_contexto_auditoria(request)" in bloque
        assert "eventos_repo=SqlAlchemyEventoRepository(db)" in bloque


def test_auditoria_no_incluye_secretos() -> None:
    for ruta in (CREAR_PATH, ACTIVAR_PATH):
        fuente = ruta.read_text(encoding="utf-8")

        inicio = fuente.index("self.eventos_repo.registrar")
        fin = fuente.index("self.db.commit", inicio)
        detalle_evento = fuente[inicio:fin]

        assert '"token"' not in detalle_evento
        assert '"contrasena"' not in detalle_evento
        assert '"numero_identificacion"' not in detalle_evento