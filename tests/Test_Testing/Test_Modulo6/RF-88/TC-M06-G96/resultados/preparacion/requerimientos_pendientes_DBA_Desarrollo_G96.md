# TC-M06-G96 — Requerimientos pendientes (DBA / Desarrollo)

**Grupo:** TC-M06-G96 · RF-88 · subcasos TC-M06-05 / 06 / 07  
**Estado del grupo:** **PREPARADO_CON_RIESGOS** (sin autorización de ejecución funcional)  
**Ambiente:** TEST `https://api.inmero.co/api-sgpmp-test`  
**Fecha de solicitud:** 2026-11-13  
**Solicitante:** QA (Laura López)  
**Restricción vigente:** QA **no** ejecutará POST/PUT/PATCH/DELETE ni cierres hasta autorización expresa tras resolver estos puntos.

---

## 0. Contexto y por qué se solicita

La preparación de solo lectura confirmó el seed del responsable (#967):

| Dato | Valor verificado |
|---|---|
| Titular | NIT `901999213` · `[SEED-QA-M06-DEP] Agropecuaria Depreciacion S.A.S.` |
| Finca / infra | 478 / 1253 |
| Periodo | **411** ABIERTO (2026-11-01 … 2026-11-30) |
| Activo | **2126** `QA-M06-DEP-COSTO-10M` ACTIVO |
| Valoración | **66** · costo 10.000.000 · dep 0 · det 0 · libros 10.000.000 · vida útil **100** meses |
| Reconocimiento | **886** CONFIRMADO · `VALORACION_POR_COSTO` |
| Eventos sanitarios | **0** |
| Alerta `VALOR_LIBROS_AJUSTADO_A_CERO` | baseline **0** en activo 2126 |

Con un solo activo y sin mecanismo de “depreciación = monto”, los tres subcasos **no pueden ejecutarse de forma aislada** sin contaminar el baseline ni afectar el periodo compartido.

### Matriz objetivo (no negociable para el criterio de aceptación)

| Subcaso | Costo | Depreciación acum. | Deterioro acum. | Esperado |
|---|---:|---:|---:|---|
| **TC-M06-05** | 10.000.000 | 2.000.000 | 1.000.000 | Libros **7.000.000** |
| **TC-M06-06** | 10.000.000 | 10.000.000 | 0 | Libros **0** |
| **TC-M06-07** | 10.000.000 | 7.000.000 | 5.000.000 | Libros **0** + alerta persistente `VALOR_LIBROS_AJUSTADO_A_CERO` (cálculo −2.000.000) |

---

## 1. Necesidad de tres escenarios aislados

### Problema

Los montos de 05 / 06 / 07 son **absolutos** (no incrementales). Tras un POST de deterioro o un cierre que acumule depreciación sobre el activo **2126**:

- el baseline 10M / 0 / 0 desaparece;
- el siguiente subcaso ya no es reproducible;
- el periodo **411** cerrado impacta **todos** los activos del NIT seed.

### Solicitud (preferida)

**Tres activos independientes** (o tres valoraciones activas gemelas), cada uno con su propio reconocimiento CONFIRMADO y baseline limpio, etiquetados de forma inequívoca, por ejemplo:

| Escenario | Etiqueta sugerida | Estado inicial exigido |
|---|---|---|
| A → TC-M06-05 | `QA-M06-G96-05-LIBROS-7M` | costo 10M · dep **0** · det **0** · libros 10M |
| B → TC-M06-06 | `QA-M06-G96-06-LIBROS-0-SOLO-DEP` | costo 10M · dep **0** · det **0** · libros 10M |
| C → TC-M06-07 | `QA-M06-G96-07-LIBROS-0-ALERTA` | costo 10M · dep **0** · det **0** · libros 10M |

### Alternativa aceptable (si no hay tres activos)

Un único activo **más** un procedimiento de **restauración total** entre subcasos (ver §7), documentado y ejecutable por DBA **sin** que QA altere matrices ni vidas útiles.

### Qué NO debe hacerse

- Encadenar 05 → 06 → 07 sobre el activo 2126 sin reset.
- Cerrar el periodo 411 del seed actual como atajo para “probar depreciación” en los tres subcasos.
- Reutilizar activos ya tocados por otras corridas M06 sin declarar IDs frescos.

---

## 2. Solicitud a DBA — datos exclusivos por escenario

### Responsabilidad DBA

Preparar (o clonar) en **TEST** la infraestructura de datos de cada escenario, **sin** depender de que QA ejecute cierres ni cambie configuración contable.

### Entregables mínimos por escenario (A / B / C)

Para **cada** subcaso, DBA debe entregar por escrito (issue / comentario / tabla):

| Campo | Descripción |
|---|---|
| `id_titular` / NIT | Preferible NIT exclusivo por escenario; si se comparte NIT, justificar aislamiento |
| `id_finca` | Finca asignada al usuario Contador de prueba |
| `id_infraestructura` | Infraestructura del activo |
| `id_activo_biologico` | Activo exclusivo del subcaso |
| `nombre` / código QA | Etiqueta identificable en listados |
| `id_valoracion_por_costo` | Valoración activa |
| `id_reconocimiento` | Estado **CONFIRMADO** · `VALORACION_POR_COSTO` |
| `id_periodo` | Periodo **ABIERTO** usable sin cerrar periodos de otros casos |
| Baseline numérico | costo / dep / det / libros (ideal: 10M / 0 / 0 / 10M) |
| `id_evento_sanitario` | Obligatorio en escenarios A (05) y C (07); opcional en B (06) |
| Usuario Contador | Correo / `id_usuario` con asignación a la finca del escenario |
| Matriz / cuentas | Confirmación de que el escenario puede registrar deterioro (y, si aplica, cierre) sin faltantes de configuración |

### Opciones de seed de depreciación (elige DBA + Desarrollo de común acuerdo)

**Opción DBA-1 (recomendada para aislamiento):** pre-cargar en la valoración activa los montos de depreciación **antes** de que QA escriba:

| Escenario | dep pre-cargada | det inicial | libros iniciales tras seed |
|---|---:|---:|---:|
| A (05) | **2.000.000** | 0 | **8.000.000** |
| B (06) | **10.000.000** | 0 | **0** |
| C (07) | **7.000.000** | 0 | **3.000.000** |

Con esta opción QA solo ejecuta (tras autorización) el POST de deterioro en 05 y 07; el 06 queda en verificación de lectura del baseline de libros 0.

**Opción DBA-2:** dejar dep=0 y entregar activos + periodos **exclusivos** para que Desarrollo indique el procedimiento de cierre/vida útil (ver §3). En este caso DBA debe garantizar que el cierre de ese periodo **no** afecte otros casos QA.

### Restricciones explícitas hacia el seed actual

Mientras no haya clones:

- **No** autorizar a QA a cerrar el periodo **411**.
- **No** modificar el activo **2126**, valoración **66** ni reconocimiento **886** como “campo de prueba compartido” para los tres subcasos.
- Si el seed 2126 se reutiliza para **un solo** subcaso, DBA debe declarar cuál y el procedimiento de restauración post-prueba.

### Criterio de aceptación del entregable DBA

QA podrá, solo con GET, verificar por cada escenario:

1. `GET /finanzas/activos/{id}` → montos baseline acordados.  
2. `GET /finanzas/activos/{id}/eventos-sanitarios` → ≥1 evento usable (05 y 07).  
3. `GET /finanzas/periodos?...` → periodo ABIERTO del escenario.  
4. Contador asignado a la finca del escenario (sin pedir secretos en el ticket).

---

## 3. Solicitud a Desarrollo — procedimiento soportado de depreciación exacta

### Responsabilidad Desarrollo

Documentar el **único procedimiento soportado en API** (o seed autorizado) para obtener exactamente:

- depreciación acumulada **2.000.000** (TC-M06-05),
- **10.000.000** (TC-M06-06),
- **7.000.000** (TC-M06-07).

### Hallazgo QA (no negociable en el diseño actual)

- **No existe** `POST` que reciba un monto de depreciación acumulada.
- La depreciación se calcula en el **cierre** (`POST /finanzas/periodos/{id}/cierre`) a partir de `vida_util_meses`, fechas y meses transcurridos.
- En el seed actual, vida útil = **100** meses → depreciación mensual teórica **100.000**; un solo mes **no** produce 2M / 7M / 10M.

### Preguntas que Desarrollo debe responder por escrito

1. ¿Se aprueba **seed DBA** de `depreciacion_acumulada` / `valor_contable_por_costo` (Opción DBA-1)?  
2. Si no: ¿cuál es la combinación soportada de `vida_util_meses` + número de cierres + fechas para cada monto, **sin** que QA modifique matrices globales de especie compartida?  
3. ¿Existe (o se habilitará) un endpoint / herramienta de QA para fijar depreciación de prueba?  
4. Si el camino es cierre: ¿qué periodo(s) exclusivos deben usarse y qué asientos/auditoría se esperan (`DEPRECIACION_REGISTRADA`)?  
5. En TC-M06-06, al llegar libros a 0 solo por depreciación, ¿debe generarse o no `VALOR_LIBROS_AJUSTADO_A_CERO`? (el commit #968 indica que el cierre también puede registrarla “cuando el ajuste ocurre”).

### Entregable Desarrollo (depreciación)

Tabla firmada:

| Subcaso | Método (seed / cierre / otro) | Parámetros exactos | Endpoint(s) | Efectos colaterales | Quién ejecuta el paso |
|---|---|---|---|---|---|
| 05 | … | … | … | … | DBA / Dev / QA |
| 06 | … | … | … | … | … |
| 07 | … | … | … | … | … |

Hasta recibir esta tabla, QA **no** ejecutará cierres ni cambios de vida útil.

---

## 4. Solicitud a Desarrollo — eventos sanitarios para deterioros

### Responsabilidad Desarrollo (+ apoyo DBA en datos)

`POST /finanzas/activos/{id}/deterioros` exige `id_evento_sanitario` del **mismo** activo (`impacto_economico_cop` > 0, `justificacion` ≥ 30).

Estado actual activo 2126: **0** eventos (`GET .../eventos-sanitarios` → 200, vacío).

### Solicitud

1. Identificar el **flujo API soportado** (M02 / RF-41 u otro) para crear un evento sanitario usable por M06, con roles y payload mínimo.  
2. Alternativa: DBA inserta eventos de prueba (como en la prueba de integración de #968) y entrega los `id_evento_sanitario`.  
3. Entregar **al menos un evento por activo** de los escenarios 05 y 07 (idealmente eventos distintos, no reutilizados entre deterioros si el dominio lo impide).

### Montos de deterioro que QA aplicará (solo tras autorización)

| Subcaso | `impacto_economico_cop` | Dep previa esperada | Resultado libros |
|---|---:|---:|---:|
| TC-M06-05 | 1.000.000 | 2.000.000 | 7.000.000 |
| TC-M06-07 | 5.000.000 | 7.000.000 | 0 (+ alerta) |

### Entregable

| Escenario | `id_activo` | `id_evento_sanitario` | Cómo se creó | ¿Consumible una sola vez? |
|---|---|---|---|---|
| 05 | … | … | API / seed | sí/no |
| 07 | … | … | API / seed | sí/no |

---

## 5. Confirmación de despliegue del fix #968 (`8829599f`)

### Evidencia ya recopilada por QA (solo lectura)

| Chequeo | Resultado |
|---|---|
| Commit | `8829599f` — *fix(rf88-mod6): alerta persistente cuando el valor en libros negativo se ajusta a cero (#968)* |
| Presente en `origin/test` | **Sí** (`git merge-base --is-ancestor`) |
| Presente en `origin/dev` | **Sí** |
| Presente en rama local `laura` (HEAD) | **No** (árbol local de QA incompleto respecto al fix) |
| Tag cercano | aparece bajo linaje `v1.4.0-rc.52+` |
| Enum en TEST | `GET /finanzas/auditoria?tipo_evento=VALOR_LIBROS_AJUSTADO_A_CERO` → **200** (tipo inválido → 400) |
| Alta de la alerta | **No verificada** (sin POST de deterioro/cierre) |

### Solicitud a Desarrollo / DevOps

Confirmar por escrito, con evidencia de despliegue:

1. Versión / imagen / commit **exacto** corriendo en `api.inmero.co/api-sgpmp-test`.  
2. Que incluye `8829599f` (o un sucesor que conserve el comportamiento).  
3. Que la migración `c6e8a0b2d453_rf88_alerta_valor_libros_cero` está aplicada en la BD de TEST.  
4. Que el flujo de escritura registra:
   - evento de auditoría `VALOR_LIBROS_AJUSTADO_A_CERO` (WARNING),
   - en deterioro: posible `valor_libros_calculado` en la respuesta,
   - aviso a Contador (`ALERTA_FINANCIERA_NIC41` según el diseño del commit).

**Criterio QA:** el cierre del issue #968 **no** se toma como prueba de que la alerta funciona en TEST hasta que exista confirmación de deploy **y** una corrida autorizada que demuestre el alta.

---

## 6. Consulta y verificación de la alerta persistente

### Fuente de verdad (TC-M06-07)

```
GET /finanzas/auditoria
  ?tipo_evento=VALOR_LIBROS_AJUSTADO_A_CERO
  &id_activo_biologico={id_activo_escenario_07}
  &formato=TECNICO|LEGIBLE
  &orden=DESC
```

Permiso: `auditoria_financiera` R (Contador lo tiene en la sesión de preparación).

### Qué debe permitir verificar

| Campo / aspecto | Esperado en TC-M06-07 |
|---|---|
| `total_registros` | ≥ 1 **después** del deterioro (baseline 0) |
| Tipo | `VALOR_LIBROS_AJUSTADO_A_CERO` |
| Severidad | WARNING (según #968) |
| Payload / descripción | valor **calculado** negativo (p. ej. −2.000.000) y valor **aplicado** 0 |
| Contexto | costo, depreciación y deterioro del momento del ajuste |
| Distinción | distinto de `DETERIORO_REGISTRADO` (este último no cumple el criterio de alerta del caso) |

### Complemento (no sustituye auditoría)

- Respuesta del `POST .../deterioros`: aviso / `valor_libros_calculado` si el deploy lo expone.  
- Bandeja: `GET /notificaciones` · código esperado `ALERTA_FINANCIERA_NIC41`.

### Solicitud a Desarrollo

Confirmar el contrato exacto del payload en `formato=TECNICO` (nombres de campos) para que QA no dependa de inferencias del commit local.

---

## 7. Procedimiento de restauración / aislamiento anti-contaminación

### Objetivo

Impedir que la ejecución de un subcaso deje el ambiente inutilizable para el siguiente o para otros grupos M06.

### Solicitud conjunta DBA + Desarrollo

Definir **uno** de estos modos y documentarlo:

| Modo | Descripción | Preferencia |
|---|---|---|
| **Aislamiento por triple seed** | Tres activos/periodos exclusivos; sin reset entre subcasos | **Preferido** |
| **Reset DBA entre subcasos** | Tras cada corrida, DBA restaura valoración (dep/det/libros), limpia deterioros/asientos de prueba y deja periodo ABIERTO | Aceptable |
| **Titular desechable** | NIT/finca/periodo creados solo para G96 y descartables | Aceptable |

### Contenido mínimo del procedimiento

1. Checklist pre-prueba (GET baseline).  
2. Operaciones autorizadas a QA (lista blanca de POST).  
3. Operaciones **prohibidas** (cierre de periodos compartidos, cambio de vida útil de especie compartida, matriz global).  
4. Checklist post-prueba / restore (quién, qué tablas/IDs, tiempo de respuesta).  
5. Señal de “escenario contaminado” (p. ej. det ≠ 0 o alerta ya presente antes de 07).

### Regla QA hasta entonces

G96 permanece en **PREPARADO_CON_RIESGOS**. No se ejecutará ningún POST de deterioro ni cierre.

---

## 8. Matriz de responsabilidades y datos a entregar

| # | Bloqueo | Responsable | Entregable concreto | Desbloquea |
|---|---|---|---|---|
| R1 | Un solo activo para tres montos absolutos | **DBA** | Tres IDs de activo (o reset documentado) + finca/periodo/reconocimiento | 05, 06, 07 |
| R2 | Depreciaciones exactas 2M / 10M / 7M | **Desarrollo** (+ DBA si seed) | Tabla método/parámetros o seed numérico | 05, 06, 07 |
| R3 | Sin eventos sanitarios | **Desarrollo** (flujo) + **DBA** (datos) | `id_evento_sanitario` por activo 05 y 07 | 05, 07 |
| R4 | Confirmación deploy #968 | **Desarrollo / DevOps** | Commit/imagen + migración en TEST | 07 (alerta) |
| R5 | Contrato de consulta de alerta | **Desarrollo** | Campos TECNICO/LEGIBLE + ejemplo | 07 |
| R6 | Anti-reutilización / restore | **DBA** + **Desarrollo** | Procedimiento escrito | todo el grupo |

### Datos que QA devolverá al recibir el seed (verificación GET, sin escritura)

- Tabla de IDs observados vs declarados.  
- Baseline numérico.  
- Conteo de eventos sanitarios.  
- Conteo baseline de `VALOR_LIBROS_AJUSTADO_A_CERO`.  
- Dictamen: mantener `PREPARADO_CON_RIESGOS` **o** pasar a `LISTO_PARA_EJECUCION` solo si QA autoriza expresamente.

---

## 9. Operaciones POST previstas (futuras — no ejecutadas)

| POST | Condición previa | Efecto esperado | Subcaso |
|---|---|---|---|
| (posible) alta evento sanitario vía API M02 | flujo confirmado por Dev | habilita `id_evento_sanitario` | 05, 07 |
| (posible) cierre de periodo **exclusivo** | procedimiento Dev + periodo no compartido | acumula depreciación | según tabla Dev |
| `POST /finanzas/activos/{id}/deterioros` impacto 1.000.000 | dep=2M · evento OK | libros 7.000.000 | 05 |
| `POST /finanzas/activos/{id}/deterioros` impacto 5.000.000 | dep=7M · evento OK | libros 0 + `VALOR_LIBROS_AJUSTADO_A_CERO` | 07 |

Ninguna de estas operaciones se ejecutó en esta fase ni queda autorizada por este documento.

---

## 10. Dictamen

| Ítem | Estado |
|---|---|
| Preparación de lectura G96 | Completa |
| Datos seed #967 (2126 / 66 / 886 / 411) | Verificados |
| Ejecución funcional 05/06/07 | **Bloqueada** por R1–R6 |
| Dictamen de grupo | **PREPARADO_CON_RIESGOS** |
| Próximo paso QA | Revisar respuestas DBA/Dev → solo entonces **autorización expresa** de ejecución |

**Referencias internas:**  
`informe_preparacion_G96.md` · `plan_escenarios_G96.md` · `inspeccion_preparacion_G96.json`
