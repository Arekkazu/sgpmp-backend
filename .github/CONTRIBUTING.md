# Guía de contribución y trazabilidad de cambios

Este documento complementa el `Manual de Operación del Área de Análisis`. Define
cómo se documenta, revisa y versiona cada cambio que llega a `main`, de forma que
la trazabilidad sea automática y no dependa de que alguien la escriba a mano.

> Estado POC: este documento y los workflows asociados se están validando en
> la rama `poc/docs-automation-setup` antes de adoptarse sobre `main`/`dev`.
> Mientras tanto, el flujo de trabajo real del equipo (`dev` como rama de
> integración, PRs de `feature/*` hacia `dev`) sigue sin cambios.

## 1. Ramas

- `main`: siempre desplegable. Protegida — nadie hace push directo.
- `dev`: rama de integración continua entre features (uso real actual del equipo).
- `feature/rf-XX[-YY]-descripcion-corta`: una rama por requerimiento o sub-tarea
  (convención ya en uso, ej. `feature/rf05-rf06-unified-rbac-account-profile`).
- `fix/BUG-XXX-descripcion-corta`: corrección de un defecto registrado.
- `hotfix/...`: corrección urgente directo sobre una versión ya desplegada.

Regla: el nombre de la rama debe permitir identificar, sin abrir el PR, a qué
módulo (`identity_access`, `biological_assets`, `telemetry`, `prediction`,
`supplies`, `configuration`) y a qué requerimiento (RF/RNF) o bug pertenece.

## 2. Commits — Conventional Commits + referencia obligatoria

Formato:

```
<tipo>(<módulo>): <descripción corta> (RF-XXX)

[cuerpo opcional]

Refs: RF-XXX
RFC: RFC-XXX      # solo si el cambio viene de una solicitud de cambio aprobada
```

Tipos permitidos: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `style`.

Ejemplo real, sobre el proyecto:

```
feat(prediction): implementa RF-68 modelo de riesgo de contagio (RFC-014)

Calcula P_contagio = Wfs*Fs + Wfa*Fa + Wfd*Fd con pesos configurables
desde configuration.

Refs: RF-68
RFC: RFC-014
```

Todo commit que no incluya un ID de RF o BUG válido es rechazado automáticamente
por el workflow `pr-checks.yml` (ver sección 4).

> Al mergear `dev` u otra rama dentro de tu `feature/*` (para actualizarla),
> dejá el mensaje de merge que genera Git por defecto (`Merge branch '...'`).
> El lint de commits los ignora automáticamente solo si conservan ese formato
> — si le escribís un mensaje propio (ej. `merge: actualizo con dev`), el
> commit sí se linta como si fuera uno normal y el check falla por no tener
> un tipo válido ni referencia a RF.

## 3. Pull Request hacia `main`

Todo cambio a `main` pasa por PR usando la plantilla de
`.github/PULL_REQUEST_TEMPLATE.md`. El título del PR debe seguir el mismo
formato que los commits: `tipo(módulo): descripción (RF-XXX)`.

Un PR no puede fusionarse hasta que:

1. Pasen todos los checks automáticos (`pr-checks.yml`).
2. Tenga al menos una aprobación (dos si toca un módulo de criticidad Alta:
   `identity_access`, `biological_assets` o `prediction` — ver `CODEOWNERS`).
3. La rama esté actualizada contra `main` (sin conflictos).

## 4. Qué automatiza el pipeline

| Momento | Automatización | Dónde |
|---|---|---|
| Al abrir/actualizar el PR | Lint de commits, validación de que el título/commits referencian un RF o BUG válido, y `pytest` | `.github/workflows/pr-checks.yml` |
| Al mergear a `main` | Cálculo de versión SemVer según el tipo de commit, generación de `CHANGELOG.md`, creación del tag y del Release en GitHub | `.github/workflows/release.yml` |
| Al crear el Release | Append automático de una fila a `docs/trazabilidad/TRAZABILIDAD_CAMBIOS.md` con versión, PRs incluidos y RF/RFC referenciados | `scripts/append_trazabilidad.js`, invocado desde `release.yml` |

Ese archivo `docs/trazabilidad/TRAZABILIDAD_CAMBIOS.md` es lo que se entrega al director: una
tabla generada por el pipeline, no mantenida a mano, que cruza versión →
requerimientos → PRs → fecha.

## 5. Configuración de `main` que debe activarse en GitHub (una sola vez)

En **Settings → Branches → Branch protection rules** para `main`:

- Require a pull request before merging (mínimo 1 aprobación).
- Require review from Code Owners.
- Require status checks to pass before merging → seleccionar los jobs de
  `pr-checks.yml` (`lint-commits`, `test`, `verify-traceability`).
- Require branches to be up to date before merging.
- Require linear history (evita merges "sucios").
- Do not allow bypassing the above settings (incluye administradores).
- No permitir force-push ni borrado de la rama.

Esto no se puede configurar solo con un workflow — es ajuste de repositorio, y
solo lo hace quien tenga permisos de administrador.

## 6. Relación con la RTM y el RFC

- Un PR **no** reemplaza al RFC. El RFC autoriza el cambio; el PR es la
  ejecución técnica. Un PR que implemente un cambio de alcance sin un RFC
  aprobado se rechaza en revisión, aunque pase los checks automáticos.
- Cuando el PR se fusiona, Análisis actualiza el estado del RF en la RTM a
  "En pruebas" o "Aprobado/Cumplido" según corresponda — este paso sigue
  siendo manual porque depende de criterio funcional, no solo de que el
  código exista.
