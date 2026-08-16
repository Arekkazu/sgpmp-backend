# Pipelines del repositorio

> Estado POC: validado en la rama `poc/docs-automation-setup`. `deploy.yml`
> queda fuera de esta primera fase porque el repo aún no tiene Dockerfile ni
> infraestructura de despliegue definida — se agregará como fase siguiente.

Dos workflows, cada uno con un disparador distinto, sobre un flujo de **dos
etapas de aprobación** (ver `.github/CONTRIBUTING.md` sección 1):

```
feature/* ──PR──▶ [1] pr-checks.yml ──▶ dev ──PR──▶ [1] pr-checks.yml ──▶ main ──push──▶ [2] release.yml
              (valida)     aprueban:                (valida)   aprueban:                    (versiona)
                       Desarrollo + IoT                    Pruebas + Proyecto
```

`pr-checks.yml` es el **mismo workflow** en ambas etapas (mismos tres jobs);
lo que cambia entre una y otra es quién aprueba el PR, no qué se valida
automáticamente.

## 1. `pr-checks.yml` — Validación de Pull Request

| | |
|---|---|
| Dispara con | Abrir, editar o actualizar un PR contra `dev` **o** contra `main` |
| Qué hace | (a) Lint de commits con Conventional Commits · (b) verifica que el título del PR referencia un RF/RNF válido · (c) corre `pytest` |
| Bloquea el merge si | Cualquier job falla — se configura como *required status check* en branch protection (en ambas ramas) |
| Quién lo mira | Desarrollo (mientras corrige su PR) y quien deba aprobar esa etapa (Desarrollo/IoT en `dev`, Pruebas/Proyecto en `main`) |
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
- Branch protection en `dev` y `main` (sección 6 de `.github/CONTRIBUTING.md`)
  — sin esto, nada de lo anterior es obligatorio todavía, es solo lo que
  correría automáticamente si el PR se abre.
- Reemplazar los `@usuario` de `CODEOWNERS` por los handles reales de
  Líder de Desarrollo, Líder de IoT, Líder de Pruebas y Líder de Proyecto.

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
