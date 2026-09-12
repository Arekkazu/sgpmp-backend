# RESULTADO — TC-M02-G80

## 0. RESUMEN EJECUTIVO

| Dimensión | Resultado |
|---|---|
| VEREDICTO | **RECHAZADO** |
| Subtipo | — |
| COBERTURA ACTORES | COMPLETA |
| SUB-CASOS | 2/4 aprobados · **2/4 rechazados** |
| PETICIONES OFICIALES | 8/8 |
| AISLAMIENTO C1/C2/C3 | **CORRECTO** |
| PERSISTENCIA INDEBIDA | **SÍ** — en TC-M02-136, con ambos actores |
| Equipo responsable | **Desarrollo Backend** |

**Justificación:** con los cuatro escenarios correctamente aislados y ejecutados por los dos actores, C1 (E-07) y C3 (E-09) se comportan según la ficha, pero **la regla C2 no está implementada**: el sistema aceptó con `HTTP 201` transferir un bovino INDIVIDUAL a un `Estanque` y materializó el movimiento en base de datos; además, **E-06 responde `HTTP 400` en lugar del `422`** que exigen la ficha y el contrato OpenAPI.

| Sub-caso | Regla | Resultado |
|---|---|---|
| TC-M02-134 | E-06 destino = origen | ❌ **RECHAZADO** — regla correcta, pero HTTP 400 en vez de 422 |
| TC-M02-135 | E-07 C1 especie | ✅ **APROBADO** |
| TC-M02-136 | E-08 C2 tipo | ❌ **RECHAZADO** — transferencia aceptada y persistida |
| TC-M02-137 | E-09 C3 capacidad | ✅ **APROBADO** |

> ### ⚠ CAMBIO DE ESTADO PROVOCADO POR EL DEFECTO
>
> Al no existir la validación C2, las dos peticiones de TC-M02-136 **se ejecutaron realmente**. Los activos **280** (`QAJE-IND-OUTLIER`) y **285** (`QAJE-IND-1MED`) pasaron de la infraestructura **48** (`Corral QA JE Origen`) a la **52** (`Estanque QA JE Piscicola`), con los movimientos **25** y **26** e historiales **286** y **287**.
>
> QA **no revirtió** el cambio: hacerlo exigiría una escritura, prohibida por este paquete. Detalle exacto para su restauración en §12.

---

## 1. Identificación

- **Caso:** TC-M02-G80
- **Sub-casos:** TC-M02-134, TC-M02-135, TC-M02-136, TC-M02-137
- **RF:** RF-48 — Transferencia interna de activos biológicos
- **CU:** CU10C
- **Responsable:** Juan Esteban
- **Rama:** `qa/juan-esteban-m02`
- **HEAD:** `41369ea4ab3948eacb1ab9b2d0549310e285eeae` — *Agrega variables jwt y cookie a enviroments de back*
- **Estado del árbol:** sin modificaciones sobre archivos versionados; solo artefactos de QA sin seguimiento
- **Fecha/hora:** 2026-09-10, 09:55 UTC · duración de la ejecución 11,0 s
- **Ambiente:** TEST desplegado, HTTPS — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`
- **Herramienta:** Postman + Newman, reporteros `cli`, `json` y `htmlextra`
- **Evidencia BD:** PostgreSQL TEST `158.69.200.27:5448/sgpmp_test`, usuario `member_qa`, solo lectura

---

## 2. Gate

| Verificación | Resultado |
|---|---|
| Repositorio | ✅ `https://github.com/Arekkazu/sgpmp-backend.git` |
| Rama | ✅ `qa/juan-esteban-m02` (no se cambió de rama) |
| HEAD | ✅ `41369ea` |
| HTTPS backend | ✅ `GET /openapi.json` → **HTTP 200** |
| PostgreSQL solo lectura | ✅ `SELECT 1;` responde con `member_qa` |
| OpenAPI | ✅ revisado; ver §2.1 |

### 2.1 Contrato revisado

`POST /activos-biologicos/{id_activo}/transferencias`

- Body obligatorio: `infraestructura_origen_id` (int), `infraestructura_destino_id` (int), `fecha_transferencia` (date), `motivo_transferencia` (str).
- **Respuestas declaradas: `201, 401, 403, 404, 409, 422, 500`.** El contrato **no declara `400`**.
- `GET /activos-biologicos/{id_activo}/transferencias/disponibles` existe y devuelve por destino: `id_infraestructura`, `nombre`, `tipo`, `capacidad_maxima`, `id_especie`. No expone la ocupación actual.
- `fecha_transferencia` posterior a hoy se rechaza en el propio DTO (E-10), por lo que usar la fecha de hoy evita introducir esa condición.

Este dato es decisivo para TC-M02-134: el `400` observado **no está declarado en el contrato** y contradice el `422` de la ficha.

### 2.2 Orden real de validación (lectura de código, para garantizar el aislamiento)

```text
E-01 concurrencia            → TRANSFERENCIA_CONCURRENTE          (409)
E-02 activo existe           → ACTIVO_NO_ENCONTRADO               (404)
E-03 activo ACTIVO           → ACTIVO_NO_ACTIVO                   (409)
E-04 origen activo           → SIN_INFRAESTRUCTURA_ORIGEN         (400)
     origen coincide         → INFRAESTRUCTURA_ORIGEN_INCORRECTA  (400)
E-05 destino existe/activo   → INFRAESTRUCTURA_DESTINO_INVALIDA   (400)
E-06 destino ≠ origen        → DESTINO_IGUAL_ORIGEN               (400)  ← TC-M02-134
E-07 C1 especie              → INCOMPATIBILIDAD_ESPECIE           (422)  ← TC-M02-135
     ⚠ NO EXISTE NINGÚN CONTROL C2 / E-08                                ← TC-M02-136
E-09 C3 capacidad            → CAPACIDAD_EXCEDIDA                 (422)  ← TC-M02-137
```

Entre E-07 y E-09 **no hay ninguna comprobación de compatibilidad entre el tipo de infraestructura y el tipo de activo**. Se buscó en todas las capas antes de concluir:

- caso de uso `registrar_transferencia_use_case.py`: no existe;
- filtro de `listar_infraestructuras_disponibles`: solo excluye la infraestructura de origen;
- disparadores de `modulo2.activos_biologicos` e `historial_infraestructura_activo`: ninguno valida tipo;
- catálogos: no existe **ninguna** tabla de compatibilidad (`information_schema` no devuelve nada con `%compatib%`), y `modulo9.tipos_area` es un catálogo de nombres (`id_tipo_area`, `nombre`, `es_activo`, fechas) sin relación con el tipo de activo.

La lectura de código explica el resultado; la evidencia que sustenta el veredicto es la ejecución de §7.

---

## 3. Revisión previa — SOLO LECTURA

Todos los recursos pertenecen a la **finca 57** (`Finca QA Juan Esteban`, del Productor), de modo que los cuatro escenarios comparten finca y el Productor tiene acceso legítimo. El Administrador (usuario 1, rol 1) tiene alcance global.

**Escrituras SETUP: 0.** La etapa se limitó a `SELECT`, `GET /openapi.json`, `GET /activos-biologicos/{id}`, `GET .../transferencias/disponibles` y los dos `POST /sesiones/` de autenticación.

### 3.1 Infraestructuras de la finca 57

```sql
SELECT i.id_infraestructura, i.nombre, i.tipo, i.es_activo, i.capacidad_maxima, i.id_especie,
       COALESCE(SUM(CASE WHEN ab.tipo='INDIVIDUAL' THEN 1 ELSE COALESCE(dp.cantidad_actual,0) END),0) AS ocupacion
FROM modulo9.infraestructuras i
LEFT JOIN modulo2.activos_biologicos ab ON ab.id_infraestructura = i.id_infraestructura AND ab.id_estado NOT IN (5,6)
LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales dp ON dp.id_activo_biologico = ab.id_activo_biologico
WHERE i.id_finca = 57 GROUP BY 1,2,3,4,5,6 ORDER BY 1;
```

*(La fórmula de ocupación reproduce exactamente la del backend en `infraestructura_m09_adapter.calcular_ocupacion`: los INDIVIDUAL cuentan 1, los POBLACIONAL suman `cantidad_actual`, y se excluyen los estados CERRADO y BAJA.)*

| id | nombre | tipo | activa | capacidad | especie habilitada | ocupación |
|---:|---|---|---|---:|---:|---:|
| 47 | Corral QA JE Capacidad | Corral | ✅ | **50** | 40 (bovino) | **48** |
| 48 | Corral QA JE Origen | Corral | ✅ | 1000 | *NULL* | 223 |
| 49 | Corral QA JE Baja Logica | Corral | ❌ | 50 | *NULL* | 1 |
| 50 | Corral QA JE Inactivo | Corral | ❌ | 50 | *NULL* | 0 |
| 51 | Corral QA JE Destino OK | Corral | ✅ | 200 | 40 (bovino) | 2 |
| 52 | Estanque QA JE Piscicola | **Estanque** | ✅ | 100 | *NULL* | 0 |
| 53 | Galpon QA JE Aves | Galpón | ✅ | 100 | **41 (ave)** | 0 |

### 3.2 Activos utilizados

Todos son de la especie **40 (Bovino Qa Je)** y estaban en estado **ACTIVO**.

| Activo | Identificador | Tipo | Cantidad | Origen inicial | Usado en |
|---:|---|---|---:|---:|---|
| 294 | QAJE-TRF-REGLAS | INDIVIDUAL | — | 51 | TC-M02-134 y TC-M02-135, ambos actores |
| 280 | QAJE-IND-OUTLIER | INDIVIDUAL | — | 48 | TC-M02-136, Productor |
| 285 | QAJE-IND-1MED | INDIVIDUAL | — | 48 | TC-M02-136, Administrador |
| 296 | *(lote sin identificador)* | POBLACIONAL | **10** | 48 | TC-M02-137, ambos actores |

TC-M02-134, 135 y 137 son rechazos que no alteran nada, por lo que ambos actores comparten activo. **TC-M02-136 usa un activo distinto por actor**: era la única forma de garantizar que, si el producto no aplicaba C2 y la transferencia se materializaba, el segundo actor siguiera encontrando su escenario en pie. Esa previsión resultó necesaria.

### 3.3 Inventario mínimo

| # | Pregunta | Resultado |
|---|---|---|
| D1 | ¿Qué activos ACTIVO existen? | 19 en la finca 57 (15 INDIVIDUAL y 4 POBLACIONAL), todos de especie 40. |
| D2 | ¿Qué activos son INDIVIDUAL? | 279, 280, 282, 285, 287, 289, 290, 291, 292, 293, 294, 295, 297, 298, 299. |
| D3 | ¿Qué activos son LOTE? | 281 (100), 283 (48), **296 (10)**, 300 (100). |
| D4 | ¿Cantidad actual de cada LOTE candidato? | **296 → 10**, exactamente el valor que exige la ficha. |
| D5 | ¿Infraestructura origen de cada activo? | 294 → 51 · 280 → 48 · 285 → 48 · 296 → 48. |
| D6 | ¿Infraestructuras destino activas en la misma finca? | 47, 48, 51, 52 y 53 (49 y 50 están inactivas y quedan descartadas). |
| D7 | ¿Especies habilitadas por infraestructura? | 47 → 40 · 51 → 40 · 53 → **41** · 48 y 52 → *NULL* (sin restricción). |
| D8 | ¿Tipo de cada infraestructura? | 47, 48, 49, 50, 51 → Corral · 52 → **Estanque** · 53 → Galpón. |
| D9 | ¿Capacidad máxima de cada destino? | 47 → **50** · 48 → 1000 · 51 → 200 · 52 → 100 · 53 → 100. |
| D10 | ¿Ocupación actual real de cada destino? | 47 → **48** · 48 → 223 · 51 → 2 · 52 → 0 · 53 → 0. |
| D11 | ¿Qué devuelve `GET /transferencias/disponibles`? | 38 destinos para cada activo. Ver §4. |
| D12 | ¿El Productor tiene acceso legítimo? | Sí: los cuatro activos y las cinco infraestructuras están en la finca 57, cuyo `id_usuario` es 35. |
| D13 | ¿El Administrador tiene permisos de transferencia? | Sí: `modulo1.permisos` confirma `(rol 1, recurso 29, acción 5)` activo, igual que para el rol 2. Ambos logins devolvieron 200. |

### 3.4 Aislamiento verificado de cada sub-caso

| Sub-caso | destino ≠ origen | destino ACTIVO | misma finca | C1 | C2 | C3 | Regla que debe fallar |
|---|---|---|---|---|---|---|---|
| **TC-M02-134** | ✗ *(esa es la condición)* | ✅ 51 activa | ✅ | no relevante | no relevante | no relevante | **E-06** |
| **TC-M02-135** | ✅ 53 ≠ 51 | ✅ | ✅ | **FALLA** (41 ≠ 40) | *ver nota* | **CUMPLE** (0+1 ≤ 100) | **E-07** |
| **TC-M02-136** | ✅ 52 ≠ 48 | ✅ | ✅ | **CUMPLE** (52 sin especie restringida) | **FALLA** (Estanque para bovino INDIVIDUAL) | **CUMPLE** (0+1 ≤ 100) | **E-08** |
| **TC-M02-137** | ✅ 47 ≠ 48 | ✅ | ✅ | **CUMPLE** (40 = 40) | **CUMPLE** (Corral) | **FALLA** (48+10 = 58 > 50) | **E-09** |

**Sobre C2 en TC-M02-135 (hipótesis A5).** El destino 53 es un `Galpón`, tipo que conceptualmente tampoco corresponde a un bovino. Es un matiz que debe declararse, y no invalida el sub-caso por dos razones verificadas:

1. **No existe ninguna regla C2 en el sistema** (§2.2): no hay código, disparador ni catálogo que relacione tipo de infraestructura con tipo de activo, de modo que ese destino no puede infringir una segunda regla *evaluable*. Entre las reglas que el sistema sí evalúa, la petición solo incumple C1.
2. **No existe alternativa mejor.** La consulta sobre todo el sistema devuelve exactamente **una** infraestructura activa habilitada para una especie distinta de la bovina:

```sql
SELECT i.id_infraestructura, i.id_finca, i.nombre, i.tipo, i.capacidad_maxima, i.id_especie
FROM modulo9.infraestructuras i
WHERE i.es_activo AND i.id_especie IS NOT NULL AND i.id_especie <> 40;
--  53 | 57 | Galpon QA JE Aves | Galpón | 100 | 41   → única fila
```

No hay ningún `Corral` habilitado para otra especie en ninguna finca. El escenario ejecutado es el único posible, y el resultado obtenido (`INCOMPATIBILIDAD_ESPECIE`) confirma que la regla que actuó fue C1.

---

## 4. GET transferencias/disponibles

| Activo | Total devueltos | ¿Excluye su origen? | ¿Aparece 53 (falla C1)? | ¿Aparece 52 (falla C2)? | ¿Aparece 47 (falla C3)? | Destinos de otras fincas |
|---:|---:|---|---|---|---|---:|
| 294 (INDIVIDUAL, origen 51) | 38 | ✅ sí, 51 ausente | **SÍ** | **SÍ** | SÍ *(no aplica: es INDIVIDUAL, 48+1 ≤ 50)* | 34 |
| 296 (LOTE 10, origen 48) | 38 | ✅ sí, 48 ausente | **SÍ** | **SÍ** | **SÍ** | 34 |

**Coherencia del filtrado:** el listado solo aplica el criterio de E-06 —excluye la infraestructura de origen—. **No filtra C1, no filtra C3 y no restringe por finca**: de los 38 destinos ofrecidos, 34 pertenecen a fincas ajenas al activo. Un usuario que se guíe por este listado recibe como "disponibles" destinos que el `POST` rechazará.

Conforme a §16, esto no invalida los sub-casos —lo que se evalúa es el rechazo del `POST`—, pero constituye un **hallazgo adicional**, registrado como OBS-G80-03.

---

## 5. Resultados TC-M02-134 — destino igual al origen

| Actor | Activo | Origen | Destino enviado | HTTP | Error | ¿Hubo cambios? | Resultado |
|---|---:|---:|---:|---:|---|---|---|
| Productor | 294 | 51 | 51 | **400** ⚠ | `DESTINO_IGUAL_ORIGEN` | NO | **RECHAZADO** |
| Administrador | 294 | 51 | 51 | **400** ⚠ | `DESTINO_IGUAL_ORIGEN` | NO | **RECHAZADO** |

Mensaje devuelto en ambos casos:

```text
La infraestructura destino debe ser diferente a la infraestructura origen del activo.
field: infraestructura_destino_id
```

Verificaciones de la sección 15:

1. origen confirmado (51, leído del propio activo antes de enviar); ✅
2. destino enviado = origen; ✅
3. resto del payload válido (fecha de hoy, motivo presente); ✅
4. **HTTP = 422 → ✗ se obtuvo `400`**;
5. el error corresponde a E-06 (`DESTINO_IGUAL_ORIGEN`); ✅
6. el mensaje corresponde a «destino diferente al origen»; ✅
7. no hay transferencia; ✅
8. no cambian asociaciones; ✅
9. no cambian contadores. ✅

**La regla de negocio funciona correctamente. Lo que incumple es el código HTTP:** la ficha exige `422 UNPROCESSABLE ENTITY` y el contrato OpenAPI **no declara `400`** entre las respuestas de este endpoint. Registrado como DEF-G80-02.

**Resultado TC-M02-134: RECHAZADO** (categoría `HTTP_COM`, §19.6).

---

## 6. Resultados TC-M02-135 — incompatibilidad C1 por especie

| Actor | Activo | Destino | C1 | C2 | C3 | HTTP | Error | Cambios | Resultado |
|---|---:|---:|---|---|---|---:|---|---|---|
| Productor | 294 (bovino) | 53 (Galpón, aves) | **FALLA** | — | OK | **422** | `INCOMPATIBILIDAD_ESPECIE` | NO | **APROBADO** |
| Administrador | 294 (bovino) | 53 (Galpón, aves) | **FALLA** | — | OK | **422** | `INCOMPATIBILIDAD_ESPECIE` | NO | **APROBADO** |

```text
La infraestructura Galpon QA JE Aves no está habilitada para la especie del activo.
Seleccione una infraestructura compatible con la especie.
field: infraestructura_destino_id
```

Las doce verificaciones de la sección 15 se cumplen: activo bovino confirmado, destino habilitado solo para la especie 41, destino distinto del origen, destino activo, misma finca, C1 falla, C3 se cumple (ocupación 0 + 1 ≤ 100), `HTTP 422`, error E-07, el mensaje identifica la incompatibilidad de especie y no menciona capacidad ni ninguna otra regla, y no hubo ningún cambio.

**Resultado TC-M02-135: APROBADO.**

---

## 7. Resultados TC-M02-136 — incompatibilidad C2 por tipo

| Actor | Activo | Destino Estanque | C1 | C2 | C3 | HTTP | Error | Cambios | Resultado |
|---|---:|---:|---|---|---|---:|---|---|---|
| Productor | 280 (bovino INDIVIDUAL) | 52 | CUMPLE | **FALLA** | CUMPLE | **201** ❌ | *ninguno: transferencia creada* | **SÍ** | **RECHAZADO** |
| Administrador | 285 (bovino INDIVIDUAL) | 52 | CUMPLE | **FALLA** | CUMPLE | **201** ❌ | *ninguno: transferencia creada* | **SÍ** | **RECHAZADO** |

Respuesta obtenida (Productor):

```json
{
  "id_movimiento": 25,
  "id_activo_biologico": 280,
  "infraestructura_origen": "Corral QA JE Origen",
  "infraestructura_destino": "Estanque QA JE Piscicola",
  "fecha_transferencia": "2026-09-10T00:00:00Z"
}
```

y la equivalente para el Administrador con `id_movimiento: 26` y `id_activo_biologico: 285`.

**El sistema no rechazó la transferencia: la ejecutó.** Un bovino INDIVIDUAL quedó ubicado en una infraestructura de tipo `Estanque`. El aislamiento estaba garantizado: la infraestructura 52 no tiene especie restringida (`id_especie` NULL), por lo que C1 no podía dispararse, y su capacidad era 100 con ocupación 0, por lo que C3 tampoco. La única regla incumplida era C2.

**Resultado TC-M02-136: RECHAZADO.** Registrado como DEF-G80-01.

---

## 8. Resultados TC-M02-137 — capacidad excedida C3

| Actor | LOTE | Cantidad | Capacidad | Ocupación | Proyección | HTTP | Error | Cambios | Resultado |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| Productor | 296 | **10** | **50** | **48** | **58** | **422** | `CAPACIDAD_EXCEDIDA` | NO | **APROBADO** |
| Administrador | 296 | **10** | **50** | **48** | **58** | **422** | `CAPACIDAD_EXCEDIDA` | NO | **APROBADO** |

```text
La infraestructura Corral QA JE Capacidad no tiene capacidad disponible.
Capacidad máxima: 50, ocupación actual: 48.
field: infraestructura_destino_id
```

Las catorce verificaciones de la sección 15 se cumplen. La respuesta informa por sí misma la **capacidad máxima 50** y la **ocupación actual 48**, exactamente los valores de la ficha, y el cálculo `48 + 10 = 58 > 50` se afirma en la prueba. La ocupación reportada por el sistema coincide con la calculada por `SELECT` en la revisión previa, lo que confirma que el cálculo de ocupación es correcto.

**Resultado TC-M02-137: APROBADO.**

---

## 9. Verificación de ausencia de persistencia

| Actor | Sub-caso | Ubicación cambió | Historial cambió | Ocupación origen cambió | Ocupación destino cambió | Nueva asociación |
|---|---|---|---|---|---|---|
| Productor | 134 | NO | NO | NO | NO | NO |
| Productor | 135 | NO | NO | NO | NO | NO |
| Productor | **136** | **SÍ** (48 → 52) | **SÍ** (historial 286) | **SÍ** (48: 223 → 222) | **SÍ** (52: 0 → 1) | **SÍ** |
| Productor | 137 | NO | NO | NO | NO | NO |
| Administrador | 134 | NO | NO | NO | NO | NO |
| Administrador | 135 | NO | NO | NO | NO | NO |
| Administrador | **136** | **SÍ** (48 → 52) | **SÍ** (historial 287) | **SÍ** (48: 222 → 221) | **SÍ** (52: 1 → 2) | **SÍ** |
| Administrador | 137 | NO | NO | NO | NO | NO |

Los seis rechazos (134, 135 y 137 con ambos actores) cumplen `Δ ubicación = 0`, `Δ historial = 0`, `Δ ocupación origen = 0` y `Δ ocupación destino = 0`. Los dos cambios corresponden a las peticiones que **el sistema aceptó indebidamente**: no son persistencia parcial de un rechazo, sino la ejecución completa de una transferencia que debía haberse rechazado.

```sql
-- Ubicación e historial de los cuatro activos, después de la ejecución
SELECT ab.id_activo_biologico, ab.identificador, ab.id_infraestructura AS infra_actual,
       (SELECT count(*) FROM modulo2.historial_infraestructura_activo h
         WHERE h.id_activo_biologico = ab.id_activo_biologico) AS n_historial
FROM modulo2.activos_biologicos ab WHERE ab.id_activo_biologico IN (280, 285, 294, 296);
```

| activo | identificador | infra inicial | infra actual | historial antes → después |
|---:|---|---:|---:|---|
| 280 | QAJE-IND-OUTLIER | 48 | **52** ⚠ | 1 → **2** |
| 285 | QAJE-IND-1MED | 48 | **52** ⚠ | 1 → **2** |
| 294 | QAJE-TRF-REGLAS | 51 | 51 ✅ | 2 → 2 |
| 296 | *(lote)* | 48 | 48 ✅ | 1 → 1 |

```sql
-- Filas de historial creadas durante la ejecución
SELECT id_historial, id_activo_biologico, id_infraestructura, fecha_inicio, fecha_fin, id_usuario_registro
FROM modulo2.historial_infraestructura_activo WHERE id_historial > 285;
--  286 | 280 | 52 | 2026-09-10 09:55:36.722155+00 | NULL | 35   (Productor)
--  287 | 285 | 52 | 2026-09-10 09:55:38.810146+00 | NULL |  1   (Administrador)

SELECT count(*), max(id_historial) FROM modulo2.historial_infraestructura_activo;  -- 251 | 287  (antes 249 | 285)
```

| Ocupación | Antes | Después | Δ |
|---|---:|---:|---:|
| 47 (destino C3) | 48 | 48 | **0** |
| 48 (origen de 280, 285 y 296) | 223 | **221** | **−2** ⚠ |
| 51 (origen de 294) | 2 | 2 | **0** |
| 52 (destino C2) | 0 | **2** | **+2** ⚠ |
| 53 (destino C1) | 0 | 0 | **0** |

---

## 10. Diagnóstico

**¿Fue necesario? SÍ**, para los dos sub-casos rechazados.

### 10.1 TC-M02-136 — la transferencia incompatible por tipo fue aceptada

- **Actores:** Productor y Administrador. **Activos:** 280 y 285. **Origen:** 48. **Destino:** 52 (`Estanque`).
- **C1:** CUMPLE · **C2:** FALLA · **C3:** CUMPLE.
- **Esperado:** `HTTP 422`, error E-08 por tipo de infraestructura incompatible, sin cambios.
- **Obtenido:** `HTTP 201` con `id_movimiento` 25 y 26; los activos quedaron ubicados en el Estanque.
- **Reproducción:** 2/2 (los dos actores, con activos distintos y resultado idéntico). **No se repitió una tercera vez** de forma deliberada: cada repetición movería otro activo, y la evidencia ya es concluyente.

**Hipótesis descartadas:**

| # | Hipótesis | Descarte |
|---|---|---|
| A1 | Activo no ACTIVO | `GET` previo: `nombre_estado = ACTIVO` en ambos, afirmado en SETUP. |
| A2 | Origen incorrecto | El origen se leyó del propio activo inmediatamente antes de enviar y se afirmó en la petición; no apareció `INFRAESTRUCTURA_ORIGEN_INCORRECTA`. |
| A3 | Destino inactivo | Infra 52 `es_activo = true`; no apareció `INFRAESTRUCTURA_DESTINO_INVALIDA`. |
| A4 | Destino de otra finca | 48 y 52 están ambas en la finca 57. |
| A7 | **También incumple C1** | **Descartada:** la infraestructura 52 tiene `id_especie` NULL. El control C1 solo actúa `if infra_destino.id_especie is not None and != activo.id_especie`, de modo que con NULL no puede dispararse. Afirmado además sobre la respuesta del GET de disponibles. |
| A8 | **También incumple C3** | **Descartada:** capacidad 100 con ocupación 0 al iniciar; 0+1 = 1 ≤ 100. |
| A12 | Fecha futura | Fecha de hoy; el DTO habría respondido antes en caso contrario. |
| A13 | Concurrencia activa | No apareció `TRANSFERENCIA_CONCURRENTE`. |
| A14 | Actor/token incorrecto | `sub` del JWT afirmado contra 35 y 1. |
| A15 | Variable Postman incorrecta | El cuerpo realmente enviado consta en el reporte JSON con `infraestructura_destino_id: 52`. |
| A16 | Assertion con expectativa errónea | La ficha define E-08 explícitamente; el resultado no fue «otro error», fue **éxito**. |
| A17 | Artefacto Newman | No aplica: un `201` con `id_movimiento` y filas nuevas en BD no puede ser artefacto del cliente. |

- **Atribución: DEFECTO DEL PRODUCTO.**
- **Causa raíz: confirmada por QA.** La regla C2 no está implementada en ninguna capa del sistema (§2.2): no existe en el caso de uso, ni en el filtro de destinos disponibles, ni en disparadores de base de datos, ni como catálogo de compatibilidad.

### 10.2 TC-M02-134 — E-06 responde 400 en lugar de 422

- **Actores:** ambos. **Activo:** 294. **Origen y destino:** 51.
- **Esperado:** `HTTP 422` con E-06.
- **Obtenido:** `HTTP 400` con `error_code: DESTINO_IGUAL_ORIGEN` y el mensaje correcto; sin persistencia.
- **Reproducción:** **3/3** — Productor, Administrador y una repetición diagnóstica con `curl` sobre HTTPS, que devolvió el mismo `400` sin crear historial (`max(id_historial)` siguió en 287 y el activo 294 siguió en la infraestructura 51).

**Hipótesis descartadas:** A16 es la única candidata a error propio y queda descartada porque **las dos fuentes coinciden en contra del 400**: la ficha exige `422` y el contrato OpenAPI declara `201, 401, 403, 404, 409, 422, 500` sin incluir `400`. A17 queda descartada por la reproducción con `curl`.

- **Atribución: DEFECTO DEL PRODUCTO**, limitado al código HTTP.
- **Causa raíz: confirmada por QA.** E-06 se señaliza con `ValidationError`, que la jerarquía de errores del proyecto asigna a `HTTP 400`, mientras que C1 y C3 usan `BusinessRuleError`, asignado a `HTTP 422`. La ficha y el contrato esperan `422` para las cuatro reglas de compatibilidad. Nota para Desarrollo: por el mismo motivo, E-04, `INFRAESTRUCTURA_ORIGEN_INCORRECTA` y E-05 también responderían `400`; no se probaron por estar fuera del alcance de G80.

El diagnóstico **explica** los dos fallos; no rescató ninguna ejecución. Ninguna aserción se relajó ni se reejecutó el caso.

---

## 11. VEREDICTO FINAL

# ❌ RECHAZADO

**Justificación:** el gate se completó, el SETUP no realizó ninguna escritura, los cuatro escenarios quedaron correctamente aislados sobre datos reales de la finca 57 y se ejecutaron las 8 peticiones oficiales con los dos actores. C1 (E-07) y C3 (E-09) se comportan conforme a la ficha, incluida la información de capacidad máxima 50 y ocupación actual 48. Sin embargo, **dos de los cuatro sub-casos incumplen**: la regla C2 no existe y el sistema materializó dos transferencias que debía rechazar, y E-06 responde con un código HTTP que contradice la ficha y el contrato.

### DEF-G80-01 — TC-M02-136: transferencia a infraestructura de tipo incompatible aceptada

```text
TC-M02-G80 / TC-M02-136 — RECHAZADO

Actores: Productor (usuario 35) y Administrador (usuario 1)
Activos: 280 QAJE-IND-OUTLIER (Productor) y 285 QAJE-IND-1MED (Administrador)
         ambos bovinos (especie 40), INDIVIDUAL, en estado ACTIVO
Infraestructura origen: 48 Corral QA JE Origen
Infraestructura destino: 52 Estanque QA JE Piscicola

Precondiciones confirmadas:
- destino diferente al origen;
- destino ACTIVO;
- misma finca (57);
- C1 = CUMPLE — la infraestructura 52 no restringe especie (id_especie NULL);
- C3 = CUMPLE — capacidad 100, ocupación 0;
- C2 = NO CUMPLE — un bovino INDIVIDUAL no corresponde a una infraestructura de tipo Estanque.

Esperado:
HTTP 422 con el error E-08 por tipo de infraestructura incompatible,
sin modificar ubicación, historial, asociaciones ni contadores.

Obtenido:
HTTP 201. El sistema creó los movimientos 25 y 26 y ejecutó ambas transferencias.

Persistencia:
SELECT confirma que los activos 280 y 285 quedaron en la infraestructura 52,
con las filas de historial 286 y 287 abiertas (fecha_fin NULL).
La ocupación de la 48 bajó de 223 a 221 y la de la 52 subió de 0 a 2.

Reproducibilidad: 2/2 (dos actores, dos activos distintos, resultado idéntico).
Atribución: DEFECTO DEL PRODUCTO.
Causa raíz: confirmada por QA — la regla C2 no está implementada en ninguna capa:
  ni en registrar_transferencia_use_case.py, ni en el filtro de destinos disponibles,
  ni en disparadores de BD, ni existe catálogo de compatibilidad tipo-infraestructura/tipo-activo.
Categoría: VAL_ENTRADA / FLUJO.
Equipo responsable: Desarrollo Backend.
Severidad: Severo.
Tiempo máximo: 1 día hábil.
Fecha límite: 2026-09-11.
Impacto: cualquier usuario con permiso de transferencia puede ubicar un activo en una
  infraestructura funcionalmente inadecuada para su tipo. El sistema registra la ubicación
  como válida, de modo que el error se propaga a ocupación, trazabilidad e indicadores,
  y no existe control automático que lo impida ni lo señale.
```

### DEF-G80-02 — TC-M02-134: E-06 responde HTTP 400 en lugar de 422

```text
TC-M02-G80 / TC-M02-134 — RECHAZADO

Actores: Productor y Administrador
Activo: 294 QAJE-TRF-REGLAS, bovino INDIVIDUAL, ACTIVO
Origen y destino enviados: 51 Corral QA JE Destino OK

Precondiciones confirmadas: activo ACTIVO, origen vigente 51, infraestructura 51 activa,
fecha no futura, motivo presente.

Esperado: HTTP 422 UNPROCESSABLE ENTITY con el error E-06.
Obtenido: HTTP 400 BAD REQUEST con error_code DESTINO_IGUAL_ORIGEN y el mensaje correcto.

La regla de negocio se aplica bien: la petición se rechaza, el mensaje es el previsto,
el campo señalado es infraestructura_destino_id y no hubo ninguna persistencia.
Lo que incumple es el código HTTP.

Persistencia: SELECT confirma Δ = 0 en ubicación, historial y ocupaciones.
Reproducibilidad: 3/3 (Productor, Administrador y repetición con curl sobre HTTPS).
Atribución: DEFECTO DEL PRODUCTO, limitado al código HTTP.
Causa raíz: confirmada por QA — E-06 se señaliza con ValidationError (HTTP 400),
  mientras que C1 y C3 usan BusinessRuleError (HTTP 422). El contrato OpenAPI de este
  endpoint declara 201, 401, 403, 404, 409, 422 y 500, y no incluye 400.
Categoría: HTTP_COM.
Equipo responsable: Desarrollo Backend.
Severidad: Medio.
Tiempo máximo: 2 días hábiles.
Fecha límite: 2026-09-14.
Impacto: un cliente construido a partir del contrato no contempla un 400 en este endpoint
  y trataría el rechazo como un error inesperado en vez de como una validación de negocio.
  Afecta por igual a E-04, INFRAESTRUCTURA_ORIGEN_INCORRECTA y E-05, que comparten el mismo
  mecanismo, aunque quedan fuera del alcance de G80.
```

---

## 12. Datos para Registro de Errores

### DEF-G80-01 — La regla C2 de compatibilidad por tipo de infraestructura no está implementada

- **ID sugerido:** DEF-G80-01
- **Descripción:** `POST /activos-biologicos/{id}/transferencias` acepta con `HTTP 201` la transferencia de un activo bovino INDIVIDUAL a una infraestructura de tipo `Estanque`, y la materializa. RF-48 / E-08 exige rechazarla con `HTTP 422`.
- **RF:** RF-48 · **Caso/sub-caso:** TC-M02-G80 / TC-M02-136 · **Actor:** Productor y Administrador (ambos)
- **Categoría:** `VAL_ENTRADA` / `FLUJO` · **Equipo responsable:** **Desarrollo Backend**
- **Severidad:** **Severo** · **Tiempo máximo:** 1 día hábil · **Fecha detección:** 2026-09-10 · **Fecha límite:** **2026-09-11** · **Estado:** Abierto
- **Evidencia:** [reporte_tc_m02_g80.json](reporte_tc_m02_g80.json) y [reporte_tc_m02_g80.html](reporte_tc_m02_g80.html), peticiones «TC-M02-136» de ambos actores (`id_movimiento` 25 y 26); consultas `SELECT` de §9.
- **Causa raíz:** confirmada por QA — no existe la validación en ninguna capa (§2.2).
- **Nota de implementación:** el sistema no dispone hoy de ningún catálogo que relacione tipo de infraestructura con tipo o especie de activo. Implementar E-08 exige antes definir ese modelo de compatibilidad, decisión que corresponde a Desarrollo y Análisis, no a QA.

### DEF-G80-02 — E-06 devuelve HTTP 400, no declarado en el contrato

- **ID sugerido:** DEF-G80-02
- **Descripción:** al enviar `infraestructura_destino_id` igual al origen, el endpoint rechaza correctamente con `error_code: DESTINO_IGUAL_ORIGEN` pero responde `HTTP 400`. La ficha exige `422` y el contrato OpenAPI no declara `400` para este endpoint.
- **RF:** RF-48 · **Caso/sub-caso:** TC-M02-G80 / TC-M02-134 · **Actor:** Productor y Administrador (ambos)
- **Categoría:** `HTTP_COM` · **Equipo responsable:** **Desarrollo Backend**
- **Severidad:** **Medio** · **Tiempo máximo:** 2 días hábiles · **Fecha detección:** 2026-09-10 · **Fecha límite:** **2026-09-14** · **Estado:** Abierto
- **Evidencia:** peticiones «TC-M02-134» de ambos actores en el reporte Newman, y reproducción con `curl` (§10.2).
- **Causa raíz:** confirmada por QA — `ValidationError` → 400 frente a `BusinessRuleError` → 422.

### OBS-G80-03 — `GET /transferencias/disponibles` ofrece destinos que el POST rechaza

- **ID sugerido:** OBS-G80-03
- **Descripción:** el listado de destinos disponibles solo excluye la infraestructura de origen. Devuelve 38 destinos, entre ellos el Galpón habilitado solo para aves (incumple C1), el Estanque (incumple C2) y el Corral sin capacidad para el lote (incumple C3), además de **34 infraestructuras de fincas ajenas al activo**.
- **RF:** RF-48 · **Caso/sub-caso:** TC-M02-G80, hallazgo complementario previsto en §16 · **Actor:** Productor
- **Categoría:** Funcional / coherencia entre filtrado y validación · **Equipo responsable:** **Desarrollo Backend**
- **Severidad:** **Medio** — no bloquea, pero induce al usuario a intentar transferencias que serán rechazadas · **Tiempo máximo:** 2 días hábiles · **Fecha detección:** 2026-09-10 · **Fecha límite:** **2026-09-14** · **Estado:** Abierto
- **Evidencia:** §4 de este informe y las dos peticiones «GET transferencias/disponibles» del reporte Newman.
- **Causa raíz:** confirmada por QA — `listar_infraestructuras_disponibles` invoca `listar_activas(excluir_id=...)` sin aplicar C1, C3 ni alcance por finca.

### Cambio de estado pendiente de restauración

No es un defecto, sino la consecuencia de DEF-G80-01. Se detalla para que el equipo pueda revertirlo:

| Activo | Identificador | Estaba en | Quedó en | Movimiento | Historial |
|---:|---|---:|---:|---:|---:|
| 280 | QAJE-IND-OUTLIER | 48 `Corral QA JE Origen` | 52 `Estanque QA JE Piscicola` | 25 | 286 |
| 285 | QAJE-IND-1MED | 48 `Corral QA JE Origen` | 52 `Estanque QA JE Piscicola` | 26 | 287 |

QA no revirtió el cambio porque hacerlo exigiría una escritura, prohibida por este paquete. **Equipo responsable de la restauración: DBA / Implementación**, coordinado con Desarrollo Backend.

---

## 13. Declaración de cumplimiento

- ✅ No se modificó código fuente. Los archivos de `src/` solo se leyeron para conocer el orden de validación y buscar la regla C2.
- ✅ No hubo `git commit` ni `git push`. Tampoco `merge`, `rebase`, `reset` ni cambio de rama. El árbol no tiene modificaciones sobre archivos versionados.
- ✅ No se ejecutó SQL de escritura. Todas las sentencias fueron `SELECT` con el usuario `member_qa`.
- ✅ **SETUP realizó 0 escrituras.**
- ✅ No se modificaron capacidades, ocupaciones ni compatibilidades. Los valores 50 y 48 de TC-M02-137 son los que ya existían en TEST.
- ✅ No se alteró la cantidad del lote: el activo 296 tenía y conserva 10 individuos.
- ✅ Se probaron los dos actores obligatorios; ninguno recibió 403.
- ✅ Cada sub-caso aisló una única regla, con el aislamiento verificado por `SELECT` y por aserción (§3.4).
- ⚠ **No todos los rechazos quedaron sin persistencia:** las dos peticiones de TC-M02-136 **no fueron rechazadas**, sino aceptadas, y por eso modificaron datos. Los seis rechazos reales dejaron `Δ = 0`. El cambio queda documentado en §9 y §12.
- ✅ No se ejecutaron escenarios fuera de G80: no se provocó concurrencia, ni activo inexistente, ni activo no ACTIVO, ni destino inactivo, ni fecha futura, ni transferencia parcial de lote.
- ✅ No se inventaron resultados: todo procede del reporte de Newman, de la reproducción con `curl` o de una consulta `SELECT` reproducible.
- ✅ No se ejecutaron migraciones ni se desplegaron o reiniciaron servicios.

---

## 14. Artefactos

```text
tests/Test_Testing/Test_Modulo2/RF-48/TC-M02-G80/
├── construir_coleccion.cjs        generador determinista de la colección
├── test_tc_m02_g80.json           colección Postman (00-SETUP-LECTURA, 01-CASO-PRINCIPAL, 02-DIAGNOSTICO)
└── Resultados/
    ├── reporte_tc_m02_g80.html    reporte Newman (htmlextra)
    ├── reporte_tc_m02_g80.json    reporte Newman (json), con cuerpos de petición y respuesta
    └── TC-M02-G80_resultado.md    este informe
```

Un solo HTML, un solo JSON, un solo informe. No se generó ningún `.log` por actor ni por consulta. La carpeta `02-DIAGNOSTICO` quedó vacía: el diagnóstico se resolvió con la lectura del contrato, del reporte JSON, del código fuente, una reproducción con `curl` y consultas `SELECT`.

**Ejecución:** 27 peticiones · 27 scripts de prueba · **151 aserciones, 6 fallidas** · 11,0 s · **8 peticiones oficiales**. Las 6 aserciones fallidas son la evidencia de los dos defectos: 2 por el HTTP 400 de E-06, 2 por el HTTP 201 de C2 y 2 por el cambio de ubicación que provocó.
