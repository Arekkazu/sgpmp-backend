# Guía de contribución y trazabilidad de cambios

Este documento complementa el `Manual de Operación del Área de Análisis`. Define
cómo se documenta, revisa y versiona cada cambio que llega a `main`, de forma que
la trazabilidad sea automática y no dependa de que alguien la escriba a mano.

> Estado POC: este documento y los workflows asociados se están validando en
> la rama `poc/docs-automation-setup` antes de adoptarse sobre `main`/`dev`.
> Mientras tanto, el flujo de trabajo real del equipo (`dev` como rama de
> integración, PRs de `feature/*` hacia `dev`) sigue sin cambios.

## 1. Flujo de dos etapas y quién aprueba cada una

El equipo trabaja con dos etapas de aprobación, no una sola:

```
feature/RF-XX ──PR──▶ dev ──(lote listo)──▶ main
       │                              │
  aprueban:                     aprueban:
  Líder de Desarrollo            Líder de Pruebas
  Líder de IoT                   Líder de Proyecto
                                       │
                              push a main ──▶ release.yml
                              (versión, tag, TRAZABILIDAD_CAMBIOS.md)
```

- **Etapa 1 — `feature/* → dev`**: integración continua. La aprueban el
  **Líder de Desarrollo** y el **Líder de IoT** (este último obligatorio si
  el cambio toca `src/telemetry/` u otro módulo con componente IoT/sensores).
  No dispara versión ni release — solo integra.
- **Etapa 2 — `dev → main`**: PR de "promoción". Un lote de cambios ya
  integrados en `dev` que el **Líder de Pruebas** certifica como correcto y
  el **Líder de Proyecto** aprueba para pasar a `main`. Solo al mergear este
  PR se dispara `release.yml` (versión, tag, `TRAZABILIDAD_CAMBIOS.md`).
- **Líder de Análisis**: revisa y comenta en cualquiera de las dos etapas
  (visibilidad sobre qué se integra y qué se promueve), pero **no es
  aprobador obligatorio** — su revisión no bloquea el merge.

Si el Líder de Pruebas encuentra un bug o algo pendiente en el PR `dev →
main`, usa **"Request changes"** en vez de aprobar. El PR queda bloqueado
hasta que se corrija, se vuelva a pedir revisión y se apruebe — no hay forma
de que ese lote llegue a `main` mientras siga en estado "changes requested".

> **Limitación técnica a tener en cuenta:** `CODEOWNERS` es un solo archivo
> por repo, basado en ruta de archivo — GitHub no distingue hacia qué rama
> va el PR. Por eso `CODEOWNERS` lista la unión de los cuatro leads como
> aprobadores válidos (garantiza que solo alguien de ese grupo pueda
> satisfacer el check), pero **quién específicamente debe aprobar según el
> destino (Desarrollo/IoT para `dev`, Pruebas/Proyecto para `main`) es
> convención de equipo**: quien abre el PR debe pedir la revisión
> ("Request review") a las personas correctas según hacia dónde va.

## 2. Ramas

- `main`: siempre desplegable. Protegida — nadie hace push directo.
- `dev`: rama de integración continua entre features (uso real actual del equipo).
- `feature/rf-XX[-YY]-descripcion-corta`: una rama por requerimiento o sub-tarea
  (convención ya en uso, ej. `feature/rf05-rf06-unified-rbac-account-profile`).
- `fix/BUG-XXX-descripcion-corta`: corrección de un defecto registrado.
- `hotfix/...`: corrección urgente directo sobre una versión ya desplegada.

Regla: el nombre de la rama debe permitir identificar, sin abrir el PR, a qué
módulo (`identity_access`, `biological_assets`, `telemetry`, `prediction`,
`supplies`, `configuration`) y a qué requerimiento (RF/RNF) o bug pertenece.

## 3. Commits — Conventional Commits + referencia obligatoria

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
por el workflow `pr-checks.yml` (ver sección 5).

> Al mergear `dev` u otra rama dentro de tu `feature/*` (para actualizarla),
> dejá el mensaje de merge que genera Git por defecto (`Merge branch '...'`).
> El lint de commits los ignora automáticamente solo si conservan ese formato
> — si le escribís un mensaje propio (ej. `merge: actualizo con dev`), el
> commit sí se linta como si fuera uno normal y el check falla por no tener
> un tipo válido ni referencia a RF.

## 4. Pull Request — hacia `dev` o hacia `main`

Todo cambio pasa por PR usando la plantilla de
`.github/PULL_REQUEST_TEMPLATE.md`. El título del PR debe seguir el mismo
formato que los commits: `tipo(módulo): descripción (RF-XXX)`.

Un PR no puede fusionarse hasta que:

1. Pasen todos los checks automáticos (`pr-checks.yml`), sea cual sea el destino.
2. Tenga las aprobaciones que corresponden a su etapa (ver sección 1):
   Desarrollo + IoT si va hacia `dev`; Pruebas + Proyecto si va hacia `main`.
3. La rama esté actualizada contra su destino (sin conflictos).

## 5. Qué automatiza el pipeline

| Momento | Automatización | Dónde |
|---|---|---|
| Al abrir/actualizar un PR (hacia `dev` o `main`) | Lint de commits, validación de que el título/commits referencian un RF o BUG válido, y `pytest` | `.github/workflows/pr-checks.yml` |
| Al mergear a `main` | Cálculo de versión SemVer según el tipo de commit, generación de `CHANGELOG.md`, creación del tag y del Release en GitHub | `.github/workflows/release.yml` |
| Al crear el Release | Append automático de una fila a `docs/trazabilidad/TRAZABILIDAD_CAMBIOS.md` con versión, PRs incluidos y RF/RFC referenciados | `scripts/append_trazabilidad.js`, invocado desde `release.yml` |

`release.yml` **solo** corre con push a `main` — nunca con merges a `dev` —
para que la versión/tag/trazabilidad se generen únicamente cuando algo pasó
el filtro de Pruebas y Proyecto, no en cada integración diaria.

Ese archivo `docs/trazabilidad/TRAZABILIDAD_CAMBIOS.md` es lo que se entrega al director: una
tabla generada por el pipeline, no mantenida a mano, que cruza versión →
requerimientos → PRs → fecha.

## 6. Configuración que debe activarse en GitHub (una sola vez, admin del repo)

**Aún no está activada — pendiente antes de que este flujo rija de verdad.**

En **Settings → Branches → Branch protection rules**, una regla para `dev` y
otra para `main` (cada una por separado, mismos requisitos):

- Require a pull request before merging.
- Require review from Code Owners.
- Require approvals (número mínimo según la etapa).
- Dismiss stale pull request approvals when new commits are pushed — clave
  para que una aprobación de Pruebas no quede "vigente" tras un fix nuevo.
- Require status checks to pass before merging → seleccionar los jobs de
  `pr-checks.yml` (`lint-commits`, `test`, `verify-traceability`).
- Require branches to be up to date before merging.
- Require linear history (evita merges "sucios").
- Do not allow bypassing the above settings (incluye administradores).
- No permitir force-push ni borrado de la rama.

Esto no se puede configurar solo con un workflow — es ajuste de repositorio, y
solo lo hace quien tenga permisos de administrador.

## 7. Relación con la RTM y el RFC

- Un PR **no** reemplaza al RFC. El RFC autoriza el cambio; el PR es la
  ejecución técnica. Un PR que implemente un cambio de alcance sin un RFC
  aprobado se rechaza en revisión, aunque pase los checks automáticos.
- Cuando el PR `dev → main` se fusiona, Análisis actualiza el estado del RF
  en la RTM a "En pruebas" o "Aprobado/Cumplido" según corresponda — este
  paso sigue siendo manual porque depende de criterio funcional, no solo de
  que el código exista.
