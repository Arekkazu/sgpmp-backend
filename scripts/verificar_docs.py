# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: script de cobertura de docstrings (pdoc) |
"""Verifica la cobertura de docstrings de ``src/`` con el criterio de pdoc.

Un archivo está completo cuando tiene docstring de módulo y docstring en cada
clase, función y método **público** (nombres que no empiezan por ``_``). Los
``__init__.py`` vacíos se ignoran porque pdoc no aporta nada en ellos.

Uso::

    .venv/bin/python scripts/verificar_docs.py
    .venv/bin/python scripts/verificar_docs.py --modulo telemetry --detalle
    .venv/bin/python scripts/verificar_docs.py --fail-under 100

El código de salida es 1 si la cobertura global queda por debajo de
``--fail-under``; sirve como verificación objetiva antes de regenerar pdoc.
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SRC = RAIZ / "src"


@dataclass
class Archivo:
    """Resultado de cobertura de un archivo Python."""

    ruta: Path
    modulo: str
    tiene_doc_modulo: bool = False
    clases: int = 0
    clases_documentadas: int = 0
    funciones: int = 0
    funciones_documentadas: int = 0
    huecos: list[str] = field(default_factory=list)

    @property
    def publicos(self) -> int:
        """Total de miembros públicos (clases + funciones/métodos)."""
        return self.clases + self.funciones

    @property
    def documentados(self) -> int:
        """Total de miembros públicos con docstring."""
        return self.clases_documentadas + self.funciones_documentadas

    @property
    def completa(self) -> bool:
        """Indica si el archivo no tiene ningún hueco de documentación."""
        return self.tiene_doc_modulo and self.publicos == self.documentados

    @property
    def cobertura(self) -> float:
        """Porcentaje de miembros públicos documentados (0-100)."""
        if self.publicos == 0:
            return 100.0 if self.tiene_doc_modulo else 0.0
        return 100.0 * self.documentados / self.publicos


def _es_init_vacio(ruta: Path, arbol: ast.Module) -> bool:
    """Indica si es un ``__init__.py`` sin código ni docstring."""
    if ruta.name != "__init__.py":
        return False
    if ast.get_docstring(arbol):
        return False
    return not any(
        not isinstance(nodo, ast.Expr) or not isinstance(nodo.value, ast.Constant)
        for nodo in arbol.body
    )


def _miembros_publicos(arbol: ast.Module):
    """Genera (nodo, ambito) de clases y funciones públicas de primer nivel.

    También recorre los métodos públicos de cada clase. El ámbito se usa para
    mostrar el nombre completo del miembro en el reporte.
    """
    for nodo in arbol.body:
        if isinstance(nodo, ast.ClassDef) and not nodo.name.startswith("_"):
            yield nodo, nodo.name
            for sub in nodo.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and not sub.name.startswith("_"):
                    yield sub, f"{nodo.name}.{sub.name}"
        elif isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)) and not nodo.name.startswith("_"):
            yield nodo, nodo.name


def analizar_archivo(ruta: Path) -> Archivo | None:
    """Analiza un archivo y devuelve su cobertura, o ``None`` si se ignora."""
    try:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        print(f"ERROR al leer {ruta}: {exc}", file=sys.stderr)
        return None

    if _es_init_vacio(ruta, arbol):
        return None

    resultado = Archivo(ruta=ruta, modulo=ruta.relative_to(SRC).parts[0])
    resultado.tiene_doc_modulo = bool(ast.get_docstring(arbol))
    if not resultado.tiene_doc_modulo:
        resultado.huecos.append(f"{ruta}:1:modulo")

    for nodo, ambito in _miembros_publicos(arbol):
        es_clase = isinstance(nodo, ast.ClassDef)
        if es_clase:
            resultado.clases += 1
        else:
            resultado.funciones += 1
        if ast.get_docstring(nodo):
            if es_clase:
                resultado.clases_documentadas += 1
            else:
                resultado.funciones_documentadas += 1
        else:
            resultado.huecos.append(f"{ruta}:{nodo.lineno}:{ambito}")

    return resultado


def analizar(modulo: str | None) -> list[Archivo]:
    """Analiza todos los archivos de ``src`` (opcionalmente uno solo)."""
    resultados: list[Archivo] = []
    for ruta in sorted(SRC.rglob("*.py")):
        if "__pycache__" in ruta.parts:
            continue
        if modulo and ruta.relative_to(SRC).parts[0] != modulo:
            continue
        resultado = analizar_archivo(ruta)
        if resultado is not None:
            resultados.append(resultado)
    return resultados


def imprimir_resumen(resultados: list[Archivo]) -> float:
    """Imprime la tabla por módulo y devuelve la cobertura global."""
    por_modulo: dict[str, list[Archivo]] = {}
    for r in resultados:
        por_modulo.setdefault(r.modulo, []).append(r)

    print(f"{'modulo':24}{'archivos':>9}{'completos':>10}{'huecos':>8}{'miembros':>9}{'doc':>7}{'cob%':>7}")
    total_miembros = total_doc = total_huecos = 0
    for nombre in sorted(por_modulo):
        archivos = por_modulo[nombre]
        miembros = sum(a.publicos for a in archivos)
        doc = sum(a.documentados for a in archivos)
        huecos = sum(len(a.huecos) for a in archivos)
        completos = sum(1 for a in archivos if a.completa)
        cob = 100.0 * doc / miembros if miembros else 100.0
        total_miembros += miembros
        total_doc += doc
        total_huecos += huecos
        print(f"{nombre:24}{len(archivos):>9}{completos:>10}{huecos:>8}{miembros:>9}{doc:>7}{cob:>7.1f}")

    global_cob = 100.0 * total_doc / total_miembros if total_miembros else 100.0
    print("-" * 74)
    print(f"{'TOTAL':24}{len(resultados):>9}{sum(1 for a in resultados if a.completa):>10}{total_huecos:>8}{total_miembros:>9}{total_doc:>7}{global_cob:>7.1f}")
    return global_cob


def imprimir_detalle(resultados: list[Archivo]) -> None:
    """Imprime cada hueco con su ubicación ``archivo:línea:miembro``."""
    for r in resultados:
        if r.huecos:
            print(f"\n## {r.ruta} ({r.cobertura:.0f}%)")
            for hueco in r.huecos:
                print(f"  {hueco}")


def main() -> int:
    """Punto de entrada del verificador de cobertura."""
    parser = argparse.ArgumentParser(description="Cobertura de docstrings de src/ (pdoc).")
    parser.add_argument("--modulo", help="analiza solo un módulo (ej. telemetry)")
    parser.add_argument("--detalle", action="store_true", help="lista cada hueco archivo:línea:miembro")
    parser.add_argument("--fail-under", type=float, default=None, help="falla si la cobertura global es menor a N%%")
    args = parser.parse_args()

    resultados = analizar(args.modulo)
    if not resultados:
        print(f"No se encontraron archivos para el módulo {args.modulo!r}.", file=sys.stderr)
        return 2

    cobertura = imprimir_resumen(resultados)
    if args.detalle:
        imprimir_detalle(resultados)

    if args.fail_under is not None and cobertura < args.fail_under:
        print(f"\nFALLO: cobertura {cobertura:.1f}% < {args.fail_under:.1f}%", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
