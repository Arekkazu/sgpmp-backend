# Convención de commits — SGPMP Backend

Este documento aplica a **todo commit que llegue a `dev`** (directo o vía PR).
No es una preferencia de estilo: `dev` corre un pipeline de versionamiento
automatizado (`semantic-release`) que **lee el historial de commits para
decidir qué versión publicar, qué entra al `CHANGELOG.md` y qué se registra
en `docs/trazabilidad/TRAZABILIDAD_CAMBIOS.md`**. Un commit que no sigue este
formato es invisible para esas tres cosas — no rompe el build, pero
desaparece de la trazabilidad silenciosamente.

**Herramientas de IA (Claude Code y otras) que trabajen en este repo deben
seguir esta convención al generar mensajes de commit** — ver el aviso en
`CLAUDE.md`.

---

## Formato

```
tipo(scope): descripción corta en minúscula, sin punto final

cuerpo opcional — explica el porqué, no el qué (el diff ya dice el qué)

BREAKING CHANGE: solo si aplica, ver sección de abajo
```

- **`tipo`**: obligatorio, uno de la tabla de abajo.
- **`(scope)`**: opcional pero recomendado — normalmente el módulo o el RF/RFC principal (`identity-access`, `rf23-mod9`, `biological_assets`, `docker`, `ci`...). Ya es el patrón que el equipo viene usando, mantenerlo.
- **Sin prefijo de tipo = commit invisible para el pipeline.** Mensajes como `"Fix RF:11"`, `"Stubs cambiados"`, `"Cors fixing"` no cuentan para nada, aunque el trabajo sí sea real.

## Tipos y qué provocan en la versión

| Tipo | Uso | Efecto en versión |
|---|---|---|
| `feat` | Funcionalidad nueva | **minor** (`1.2.0` → `1.3.0`) |
| `fix` | Corrección de bug | **patch** (`1.2.0` → `1.2.1`) |
| `perf` | Mejora de rendimiento | **patch** |
| `refactor` | Reestructuración sin cambiar comportamiento externo | **patch** |
| `docs` | Solo documentación | Sin versión (pero sí queda en el historial) |
| `chore` | Tareas de mantenimiento (deps, config, limpieza) | Sin versión |
| `test` | Solo pruebas | Sin versión |
| `build` | Build system, Docker, dependencias de empaquetado | Sin versión |
| `ci` | Workflows de CI/CD | Sin versión |
| `style` | Formato, espacios, sin cambio de lógica | Sin versión |

**Excepción de scope:** un commit con scope `biological_assets` o `prediction`
siempre bumpea **minor**, sin importar el tipo — son los dos módulos que el
equipo marcó como críticos para versionar más visible. Confirmar con
Análisis antes de agregar otro scope a esta lista (vive en `.releaserc.json`).

## Breaking changes

No basta con mencionarlo en el texto libre — hay que marcarlo en uno de estos
dos formatos, si no, el pipeline no lo detecta como `major`:

```
feat(auth)!: cambiar el algoritmo de firma de JWT
```

o con el footer explícito:

```
feat(auth): cambiar el algoritmo de firma de JWT

BREAKING CHANGE: los tokens firmados con el algoritmo anterior dejan de ser válidos.
```

## Referenciar RF / RNF / RFC / BUG

Cuando el commit implementa o corrige un requerimiento, solicitud de cambio o
defecto reportado, inclúyelo en el `scope` o en el subject — la extracción es
tolerante a mayúsculas y guion (`RF-23`, `rf23`, `RF 23` se detectan igual):

```
feat(rf23-mod9): rangos de configuracion por tipo de dispositivo IoT
fix(rf11): retirar listado legacy sin autenticacion
docs: cerrar RFC-002, sincronizar reenvio de activacion dev->test
```

Esto es lo que alimenta `TRAZABILIDAD_CAMBIOS.md` — sin la referencia, el
cambio queda en el `CHANGELOG.md` pero sin trazar a un RF/RFC/BUG concreto.

## Reglas adicionales, no negociables

- **No crear tags de Git manualmente.** El pipeline es la única fuente de
  tags desde que está activo. Un tag manual desincroniza el cálculo de
  "última versión" y puede saltarse o repetir versiones.
- **No hacer squash-merge de PRs a `dev`.** El pipeline analiza cada commit
  individual de la rama, no solo el título del PR — un squash colapsa todo
  en un solo mensaje y se pierde la granularidad (y probablemente las
  referencias a RF individuales de cada commit). Merge commit normal, como
  ya se viene haciendo.
- **No repetir la numeración manual `V 0.1.X`** en títulos de merge una vez
  el pipeline esté activo — la numeración real la pone el tag automático;
  las dos conviviendo generan confusión sobre cuál es la versión real.

## Ejemplos completos (basados en trabajo real de este repo)

```
feat(identity-access): CU07-CU08 - RBAC, roles/permisos y notificaciones push FCM (RF-14)

fix(rf03): permitir eliminar roles no protegidos sin usuarios

chore(docker): agregar pg_cron a Postgres de dev (preventivo, mismo patron que test)

docs(rf01): cerrar el checklist de seguimiento

fix(sesiones): #1827 lock en refresco de tokens para evitar carrera de sesion 401
```
