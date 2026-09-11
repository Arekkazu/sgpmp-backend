#!/usr/bin/env python3
"""
Reconstruye retroactivamente TRAZABILIDAD_CAMBIOS.md a partir del historial
real de `dev`, aplicando EXACTAMENTE las mismas reglas de bump que
.releaserc.json (poc/docs-automation-setup) y la misma extracción de
IDs que scripts/append_trazabilidad.js -- para que este documento manual
sea metodológicamente idéntico a lo que el pipeline real habría generado.

Agrupación: por día calendario (no hay forma de saber en qué momentos
exactos se habría disparado CI en el pasado -- se documenta como supuesto
explícito en el propio archivo de salida).
"""
import os
import re
import subprocess
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sh(cmd):
    return subprocess.check_output(cmd, cwd=REPO, shell=True, text=True)


def extract_ids(subject):
    rf = []
    for m in re.finditer(r"\b(rf|rnf)[\s-]?(\d+)((?:\s*/\s*\d+)*)\b", subject, re.I):
        prefix = m.group(1).upper()
        rf.append(f"{prefix}-{m.group(2)}")
        for n in re.findall(r"\d+", m.group(3) or ""):
            rf.append(f"{prefix}-{n}")
    rfc = [f"RFC-{m.group(1)}" for m in re.finditer(r"\brfc[\s-]?(\d+)\b", subject, re.I)]
    bug = [f"BUG-{m.group(1)}" for m in re.finditer(r"\bbug[\s-]?(\d+)\b", subject, re.I)]
    return rf, rfc, bug


def classify(subject):
    """Replica .releaserc.json commit-analyzer (conventionalcommits)."""
    m = re.match(r"^(\w+)(?:\(([^)]+)\))?(!)?:", subject)
    if not m:
        return None
    ctype, scope, breaking = m.group(1), m.group(2), m.group(3)
    if breaking or "BREAKING CHANGE" in subject:
        return "major"
    if scope in ("biological_assets", "prediction"):
        return "minor"
    if ctype == "feat":
        return "minor"
    if ctype in ("fix", "perf", "refactor"):
        return "patch"
    return None  # docs/chore/test/build/ci/style -> sin release


def main():
    log = sh('git log origin/dev --reverse --pretty=format:"%H|||%ad|||%s" --date=short')
    commits = []
    for line in log.splitlines():
        h, date, subject = line.split("|||", 2)
        commits.append((h[:7], date, subject))

    batches = defaultdict(list)
    for h, date, subject in commits:
        batches[date].append((h, subject))

    major = minor = patch = 0
    first = True
    rows = []
    for date in sorted(batches.keys()):
        batch = batches[date]
        levels = [classify(s) for _, s in batch]
        if not any(levels):
            continue  # nada liberable ese día, semantic-release no habría corrido
        level = "major" if "major" in levels else "minor" if "minor" in levels else "patch"

        if first:
            major, minor, patch = 1, 0, 0
            first = False
        elif level == "major":
            major, minor, patch = major + 1, 0, 0
        elif level == "minor":
            minor, patch = minor + 1, 0
        else:
            patch += 1

        version = f"{major}.{minor}.{patch}"
        rf_set, rfc_set, bug_set = set(), set(), set()
        commit_lines = []
        for h, subject in batch:
            rf, rfc, bug = extract_ids(subject)
            rf_set.update(rf)
            rfc_set.update(rfc)
            bug_set.update(bug)
            commit_lines.append(f"{h} {subject}")

        rows.append(
            f"| {version} | v{version} | {date} | {', '.join(sorted(rf_set)) or '—'} "
            f"| {', '.join(sorted(rfc_set)) or '—'} | {', '.join(sorted(bug_set)) or '—'} "
            f"| {'<br>'.join(commit_lines)} |"
        )

    header = """# Trazabilidad de cambios — reconstrucción manual (backend, rama `dev`)

> ⚠️ **Este documento es una reconstrucción retroactiva, no la salida real
> del pipeline automatizado.** Se generó aplicando manualmente las mismas
> reglas que ya están configuradas en `poc/docs-automation-setup`
> (`.releaserc.json` + `scripts/append_trazabilidad.js`) sobre el
> historial real de `dev`, para tener una bitácora de versionamiento
> disponible **ya**, mientras se termina de promover el pipeline real a
> `main` (ver plan de automatización acordado).
>
> **Supuestos explícitos de esta reconstrucción** (documentados para que
> quede claro qué es real y qué es una aproximación):
> - Se agrupó por **día calendario** — no hay forma de saber retroactivamente
>   en qué momentos exactos se habría disparado CI; el pipeline real agrupa
>   por cada push a la rama de release, que puede no coincidir con esto.
> - Se numeró empezando en `1.0.0` (default de `semantic-release` en su
>   primer release) — el equipo puede decidir otro punto de partida real.
> - Las reglas de bump (`feat`→minor, `fix`/`perf`/`refactor`→patch,
>   `docs`/`chore`/`test`→sin release, `breaking`→major, scopes
>   `biological_assets`/`prediction`→minor) son copia exacta de
>   `.releaserc.json`.
> - La extracción de RF/RNF/RFC/BUG es copia exacta de
>   `scripts/append_trazabilidad.js` (tolerante a mayúsculas/guion).
>
> **Cuando el pipeline real corra sobre `main`, este archivo se reemplaza**
> por el generado automáticamente — este es un puente, no el destino final.
>
> **Hallazgo adicional:** en el historial real de `dev` ya existe una
> numeración manual informal (`V 0.1.0` ... `V 0.1.16`, texto plano dentro
> de algunos títulos de merge commit, no tags de Git) que arranca el
> `2026-08-20` y llega hasta `V 0.1.16` el `2026-08-31` — evidencia de que
> el equipo ya tenía la intención de versionar, aunque sin automatizar ni
> seguir semver estricto (incrementa por cada merge, no por tipo de
> cambio). **Recomendación:** cuando se active el pipeline real, continuar
> esa numeración desde `0.1.17` en vez de reiniciar en `1.0.0` — mantiene
> continuidad con lo que el equipo ya venía usando a mano.

| Versión | Tag | Fecha | RF/RNF | RFC | Bugs | Commits incluidos |
|---|---|---|---|---|---|---|
"""
    print(header + "\n".join(rows))
    print(f"\n\n<!-- TOTAL: {len(rows)} versiones reconstruidas de {len(commits)} commits -->")


if __name__ == "__main__":
    main()
