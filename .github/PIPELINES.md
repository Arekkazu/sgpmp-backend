# Pipelines del repositorio

> Estado POC: validado en la rama `poc/docs-automation-setup`. `deploy.yml`
> queda fuera de esta primera fase porque el repo aún no tiene Dockerfile ni
> infraestructura de despliegue definida — se agregará como fase siguiente.

Dos workflows, cada uno con un disparador distinto:

```
feature/* ──PR──▶ [1] pr-checks.yml ──merge──▶ main ──push──▶ [2] release.yml
                    (valida)                                    (versiona)
```

## 1. `pr-checks.yml` — Validación de Pull Request

| | |
|---|---|
| Dispara con | Abrir, editar o actualizar un PR contra `main` |
| Qué hace | (a) Lint de commits con Conventional Commits · (b) verifica que el título del PR referencia un RF/RNF válido · (c) corre `pytest` |
| Bloquea el merge si | Cualquier job falla — se configura como *required status check* en branch protection |
| Quién lo mira | Desarrollo (mientras corrige su PR) y el revisor (antes de aprobar) |
| Resultado visible | ✅/❌ en la pestaña "Checks" del PR, directo en GitHub |

## 2. `release.yml` — Versionamiento y trazabilidad

| | |
|---|---|
| Dispara con | Push directo a `main` (justo después de que un PR se fusiona) |
| Qué hace | (a) `semantic-release` analiza los commits desde la última versión · (b) calcula el siguiente número SemVer · (c) genera/actualiza `CHANGELOG.md` · (d) crea el tag `vX.Y.Z` y el Release en GitHub · (e) corre `scripts/append_trazabilidad.js`, que agrega la fila correspondiente a `docs/trazabilidad/TRAZABILIDAD_CAMBIOS.md` |
| Bloquea algo | No — es informativo/generativo, no vuelve a validar el código |
| Resultado visible | Nuevo commit `chore(release): vX.Y.Z` en `main`, tag nuevo, Release en GitHub con las notas |

## Pendiente (fase siguiente, no cubierta por esta POC)

- `deploy.yml`: build de imagen + despliegue a Staging/Producción. Requiere
  primero definir Dockerfile y ambiente de destino (ver sección 16 del manual
  de Análisis).

## Estructura de archivos

```
.commitlintrc.json          # config, raíz por convención de la herramienta
.releaserc.json             # config, raíz por convención de la herramienta
.github/
├── CODEOWNERS
├── PULL_REQUEST_TEMPLATE.md
├── CONTRIBUTING.md
├── PIPELINES.md            # este archivo
└── workflows/
    ├── pr-checks.yml
    └── release.yml
docs/
└── trazabilidad/
    └── TRAZABILIDAD_CAMBIOS.md
scripts/
└── append_trazabilidad.js
```

## Orden de instalación en un repositorio nuevo

1. Copiar `.github/` (completo), `scripts/`, `.releaserc.json` y
   `.commitlintrc.json` a la raíz del repo destino. Crear
   `docs/trazabilidad/` (puede empezar vacío; `append_trazabilidad.js` crea
   el archivo con encabezado en el primer release si no existe).
2. Activar branch protection en `main` (sección 5 de `.github/CONTRIBUTING.md`).
3. Reemplazar los placeholders marcados con `TODO` en `pr-checks.yml`.
4. Reemplazar los `@usuario` de `CODEOWNERS` por los handles reales.
5. Hacer un primer PR de prueba para confirmar que los workflows encadenan
   correctamente.
