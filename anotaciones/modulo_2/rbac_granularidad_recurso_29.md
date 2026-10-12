# RBAC del Módulo 2 — permisos más amplios que los actores del RF (recurso 29)

Tarea Taiga "[Back-end] RBAC sistemático más amplio/estrecho de lo autorizado (Módulo 2)"
(2 pts). Origen: hallazgo transversal #5 de `estado_M02.md`.

**Estado: análisis listo — decisión pendiente del equipo de análisis.** La sección
"Decisión final" al final de este documento se completa cuando el equipo decida.

## Fecha y fuentes

2026-09-24. Tres fuentes cruzadas, todas verificadas ese día:

1. **Actores de cada RF:** campo `**Actores:**` de
   `anotaciones/Requerimientos/Especificacion-Requerimientos-Modulo2.md`.
2. **Permiso que exige cada endpoint:** introspección de las rutas de
   `activo_biologico_router.py` en `origin/dev`. Cada dependencia
   `require_permission_m02` expone `id_recurso`, `id_accion` y `rf_origen`.
3. **Permisos reales por rol:** `modulo1.permisos` en `sgpmp_dev`.

## Permisos vigentes en `sgpmp_dev`

| Rol | Usuarios | Recurso 29 `activos_biologicos` | Recurso 30 `asociacion_sensor_activo` | Recurso 31 `bitacora_auditoria_m02` |
|---|:---:|:---:|:---:|:---:|
| 1 Administrador | 5 | CRUDE | CRU | CR |
| 2 Productor | 17 | CRUDE | CRU | R |
| 3 Veterinario | 2 | CRUDE | R | R |
| 4 Ingeniero de Campo | 2 | CRUE | CRU | — |
| 5 Contador | — | — | — | R |
| 21/22 Integración M04/M06 | 1 c/u | R | — | — |

Todo el CRUD de los RF-33 a RF-48, más las lecturas de RF-50 y RF-51, cuelga del
**mismo recurso 29**. Solo el router de M02 usa ese recurso; ningún otro módulo lo
consulta.

## Matriz RF × rol (recurso 29)

Las marcas se leen así: ✅ = el RF lo lista y tiene acceso; ➕ = tiene acceso y el RF
**no** lo lista; — = ni lo lista ni tiene acceso.

| RF | Endpoint | Acción | Actores del RF | Admin | Prod | Vet | Ing |
|---|---|:---:|---|:---:|:---:|:---:|:---:|
| RF-33 | `POST /` · `GET /` | C · R | P, A, I | ✅ | ✅ | ➕ | ✅ |
| RF-34 | `GET /{id}/infraestructura` | R | P, A, I | ✅ | ✅ | ➕ | ✅ |
| RF-35 | `GET /{id}` · `PATCH /{id}` | R · U | P, V, I | ➕ | ✅ | ✅ | ✅ |
| RF-36 | `POST /{id}/eventos/ingreso` · `GET /{id}/ficha-lote` | C · R | P, V, I | ➕ | ✅ | ✅ | ✅ |
| RF-37 | `POST /{id}/fases` | E | P, V, A | ✅ | ✅ | ✅ | ➕ |
| RF-38 | `POST /{id}/cierre` | D | P, V, A | ✅ | ✅ | ✅ | — |
| RF-39 | `GET /{id}/eventos` | R | V, P, I, A | ✅ | ✅ | ✅ | ✅ |
| RF-40 | `POST /{id}/eventos/crecimiento` | C | P, V, I | ➕ | ✅ | ✅ | ✅ |
| RF-41 | `POST /{id}/eventos/sanitario` | C | V, P, I | ➕ | ✅ | ✅ | ✅ |
| RF-42 | `POST /{id}/eventos/reproductivo` | C | V, P | ➕ | ✅ | ✅ | ➕ |
| RF-43 | `POST /{id}/eventos/productivo` | C | P, V | ➕ | ✅ | ✅ | ➕ |
| RF-44 | `PATCH /{id}/estado` | E | P, A, V | ✅ | ✅ | ✅ | ➕ |
| RF-45 | `POST /{id}/eventos/baja` | C | P, A, V | ✅ | ✅ | ✅ | ➕ |
| RF-46 | `GET /{id}/historial` | R | P, A, V | ✅ | ✅ | ✅ | ➕ |
| RF-47 | `GET /{id}/ficha-integral` | R | P, A, V | ✅ | ✅ | ✅ | ➕ |
| RF-48 | `GET/POST /{id}/transferencias…` | E | P, A | ✅ | ✅ | ➕ | ➕ |

RF-49 (recurso 30), RF-50 y RF-51 (identidades técnicas) y RF-52 (recurso 31) quedan
fuera de esta matriz: tienen recurso propio o actores de sistema, y ninguno aparece en
el hallazgo #5.

### Lo que la matriz corrige del hallazgo #5

- **Ningún rol queda por debajo de lo que el RF autoriza.** El único caso "más
  estrecho" (Veterinario sin `PATCH /{id}` en RF-35) ya se corrigió en el PR #426
  (`e84c0ac2`). Hoy el problema es solo de exceso de acceso.
- **El exceso es más amplio de lo que dice el hallazgo.** No son solo RF-37, 44 y 45
  con el Ingeniero de Campo:
  - **Ingeniero de Campo de más en 8 RF:** 37, 42, 43, 44, 45, 46, 47 y 48.
  - **Administrador de más en 6 RF:** 35, 36, 40, 41, 42 y 43. Ninguno de esos RF lo
    lista como actor.
  - **Veterinario de más en 3 RF:** 33, 34 y 48.
- **El ejemplo del hallazgo es inexacto.** Dice que en RF-43 "los 4 roles aplican",
  pero RF-43 solo lista Productor y Veterinario.
- **La especificación es ambigua en dos RF:** los campos `Fuente` y `Actores` no
  coinciden.
  - RF-34: `Fuente` = Productor/Administrador; `Actores` = +Ingeniero de campo.
  - RF-40: `Fuente` = Productor/Veterinario/Administrador; `Actores` =
    Productor/Veterinario/Ingeniero de campo.
  - Este análisis usa `Actores`.

## Qué se puede corregir solo ajustando permisos (sin tocar código)

Un permiso es el par `(recurso 29, acción)`. Si varios RF comparten ese par, el rol
solo puede quedar autorizado en todos o en ninguno. Por eso, para cada acción, se
puede autorizar como máximo a los roles que **todos** los RF de esa acción listan (la
intersección de actores):

| Acción | RF que la comparten | Intersección de actores | ¿Se puede ajustar sin granularizar? |
|:---:|---|---|---|
| **E** | 37, 44, 48 | P, A (y V en 37/44) | **Sí, para el Ingeniero de Campo.** Ninguno de los 3 RF lo lista. Quitarle `E` corrige RF-37 y RF-44 por completo y RF-48 parcialmente (el Veterinario sigue de más en RF-48). |
| **C** | 33, 36, 40, 41, 42, 43, 45 | solo P | **No.** Cada rol aparece como actor en al menos uno. Quitar `C` a cualquiera rompe un RF donde sí es actor. |
| **R** | 33, 34, 35, 36, 39, 46, 47 (+50, 51) | P | **No.** RF-39 lista a los 4 roles. Quitarle `R` al Ingeniero rompe RF-33 a RF-36 y RF-39. |
| **U** | 35 | P, V, I | **No para el Administrador.** Los triggers `trg_proteger_permisos_admin_update/_delete` hacen inmutables los permisos `admin_*`: no se pueden desactivar ni borrar (verificado en `sgpmp_dev`). |
| **D** | 38 | P, V, A | Ya coincide. |

**Los excesos del Administrador no se pueden corregir quitando permisos.** Sus permisos
`admin_*` son permanentes por diseño de M01. La única vía sería granularizar (opción B)
y no concederle el recurso nuevo. Antes hay que decidir si el Administrador debe
quedar excluido de verdad o si el RF lo omitió porque se da por hecho que tiene acceso
total.

**Nota sobre el commit `15c4611e` (RF-37).** Ese commit no quitó el `E` al Ingeniero
porque "le quitaría acceso a RF-44 y RF-48 también". La matriz muestra que eso no es
un problema: **ninguno de los tres RF lista al Ingeniero de Campo**, así que quitárselo
es consistente con los tres.

## Opciones para el equipo de análisis

### A — Ajustar solo lo que el modelo actual permite

- Qué cambia: se desactiva el permiso `ing_ejecutar_cambio_fase` (rol 4, recurso 29,
  acción E).
- Esfuerzo: DML de 1 fila vía migración Alembic, con aprobación del DBA. No toca
  código. El permiso no es `admin_*`, así que se puede revertir.
- Corrige: RF-37 y RF-44 del todo; RF-48 parcialmente.
- Efecto para el Ingeniero de Campo (2 usuarios en dev): deja de poder cambiar fase,
  cambiar estado y transferir.
- Lo demás queda documentado como deuda aceptada.

### B — Granularizar el recurso 29

- Qué cambia: se crean recursos por operación y cada endpoint pasa a exigir el suyo,
  ubicado por nombre con `tiene_permiso_sobre`, igual que `datos_clinicos_activo` y los
  `datos_analiticos_*`. Recursos candidatos, según los RF con actores distintos:
  - `activos_fases` (RF-37)
  - `activos_estado` (RF-44)
  - `activos_bajas` (RF-45)
  - `activos_transferencias` (RF-48)
  - `activos_eventos_reproductivos` (RF-42)
  - `activos_eventos_productivos` (RF-43)
  - `activos_ingresos` (RF-36)
- Esfuerzo: migración con recursos y permisos sembrados según los actores de cada RF
  (con aprobación del DBA), cambios en el router, en los tests de RBAC y en los accesos
  directos de RF-47.
- Corrige: el Ingeniero de Campo y el Veterinario en todos los casos. El Administrador
  solo si se decide no concederle esos recursos nuevos.
- Riesgo: el frontend podría estar leyendo permisos del recurso 29 para mostrar u
  ocultar botones. Habría que coordinarlo.
- Estimación: bastante más que los 2 pts de esta tarea.

### C — Aceptar el modelo actual y documentarlo

El recurso 29 se declara "gestión de activos" de forma intencional y los actores de
cada RF se leen como mínimos, no como exclusivos. No hay cambios.

## Recomendación

**A ahora, y B solo para los casos que análisis confirme como restricción real.**

- **A** es la única corrección que no tiene costo, que el RF respalda en los tres casos
  y que no requiere código.
- **B** implica cambiar el contrato con el frontend. Solo vale la pena donde excluir a
  un rol sea un requisito de negocio de verdad. Los candidatos más claros son RF-45
  (registrar baja, que tiene efecto financiero NIC-41) y RF-48 (transferencias).

## Preguntas para el equipo de análisis

1. **¿Qué valen los actores del RF?** ¿Son la lista **exclusiva** de quién puede operar,
   o el **mínimo** que debe poder hacerlo? Todo lo demás depende de esto.
2. **¿Se excluye al Administrador en RF-35, 36 y 40 a 43, o su omisión es implícita**
   (acceso total por ser administrador)?
3. **¿Se aprueba quitarle al Ingeniero de Campo la acción E** (cambiar fase, cambiar
   estado, transferir), es decir, la opción A?
4. **¿Qué casos justifican granularizar** (opción B)?
5. **RF-34 y RF-40: ¿qué campo manda, `Fuente` o `Actores`?** No coinciden.

## Decisión final

_Pendiente._ Registrar aquí la decisión del equipo de análisis (fecha, opción elegida y
alcance). Si se elige A o B, el DDL/DML irá en una migración Alembic con aprobación del
DBA y en un PR aparte.
